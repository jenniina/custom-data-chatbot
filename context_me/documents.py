"""Local DOCX extraction and a portable, versioned JSON document format."""

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from context_me.bilingual import records_from_blocks, build_chunks

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000


def chunks_for(text: str, size: int = 1800, overlap: int = 200) -> list[str]:
    """Bound chunks even for long unbroken text; retain context at boundaries."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be positive and overlap smaller than size.")
    result = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if part:
            result.append(part)
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return result


def convert_docx(raw: bytes, filename: str) -> dict:
    if Path(filename).suffix.lower() != ".docx":
        raise ValueError("Please select a .docx file. Save older .doc files as .docx in Word first.")
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("The document exceeds the 20 MB limit.")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("The expanded document exceeds the 100 MB limit.")
        doc = Document(BytesIO(raw))
    except (BadZipFile, KeyError) as exc:
        raise ValueError("This is not a readable Word .docx file.") from exc
    blocks = []
    heading = "Document"
    total = 0
    # Preserve paragraphs and tables in their original reading order.
    for position, block in enumerate(doc.iter_inner_content(), 1):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if block.style and block.style.name.startswith("Heading") and text:
                heading = text
        elif isinstance(block, Table):
            text = "\n".join(" | ".join(cell.text.strip() for cell in row.cells) for row in block.rows)
        else:
            continue
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            continue
        total += len(text)
        if total > MAX_TEXT_CHARS:
            raise ValueError("The document contains too much text; split it into smaller files.")
        blocks.append((heading, position, text, isinstance(block, Paragraph)))
    if not blocks:
        raise ValueError("No readable text found. Images and scanned pages need OCR before conversion.")
    document_id = sha256(raw).hexdigest()[:24]
    records = records_from_blocks(blocks, document_id)
    chunks = build_chunks(records, document_id, chunks_for)
    return {"schema_version": 2, "document_id": document_id,
            "source": Path(filename.replace("\\", "/")).name,
            "records": records, "chunks": chunks}


def dump_document(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2)


def load_document(raw: bytes | str) -> dict:
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("The JSON file exceeds the 20 MB limit.")
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("The file is not valid UTF-8 JSON.") from exc
    if not isinstance(document, dict) or document.get("schema_version") not in (1, 2):
        raise ValueError("Use a JSON document produced by the converter (schema version 1 or 2).")
    for key in ("document_id", "source"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise ValueError(f"Missing document field: {key}.")
    chunks = document.get("chunks")
    if not isinstance(chunks, list) or not chunks or len(chunks) > 10000:
        raise ValueError("The document must contain between 1 and 10,000 chunks.")
    seen = set()
    total = 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("Invalid text chunk.")
        for key in ("id", "text", "section", "location"):
            if not isinstance(chunk.get(key), str) or not chunk[key].strip():
                raise ValueError(f"Missing chunk field: {key}.")
        if chunk["id"] in seen or len(chunk["text"]) > 4000:
            raise ValueError("Chunk IDs must be unique and text no longer than 4,000 characters.")
        seen.add(chunk["id"])
        total += len(chunk["text"])
    if total > MAX_TEXT_CHARS * 2:
        raise ValueError("Too much text in this document.")
    result = {key: document[key] for key in ("schema_version", "document_id", "source", "chunks")}
    if document["schema_version"] == 2:
        records = document.get("records")
        if not isinstance(records, list) or not records or len(records) > 10000:
            raise ValueError("Version 2 requires between 1 and 10,000 source records.")
        ids, total = set(), 0
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Invalid bilingual record.")
            for key in ("id", "section", "location", "original_text", "key", "en", "fi", "shared"):
                if not isinstance(record.get(key), str):
                    raise ValueError(f"Invalid record field: {key}.")
            if any(not record[key].strip() for key in ("id", "section", "location", "original_text")):
                raise ValueError("Source record identity, location, and original text must be present.")
            if not any(record[key].strip() for key in ("en", "fi", "shared")) or record["id"] in ids:
                raise ValueError("Records must have unique IDs and nonempty content.")
            ids.add(record["id"])
            total += sum(len(record[key]) for key in ("en", "fi", "shared", "original_text"))
        if total > MAX_TEXT_CHARS * 3:
            raise ValueError("Too much text in bilingual records.")
        expected = build_chunks(records, document["document_id"], chunks_for)
        if document["chunks"] != expected:
            raise ValueError("Search passages do not match the bilingual records. Reconvert the Word document.")
        result["records"] = records
    return result
