"""Conservative bilingual extraction; labels are data, never executable guidance."""
import re

KEY = re.compile(r"^\[([A-Za-z_][A-Za-z0-9_.-]*)\]\s*")
LABEL = re.compile(r"(?:^|\n|\|)\s*(EN|FI):\s*", re.IGNORECASE)


def parse_text(text, allow_labels=True):
    match = KEY.match(text)
    key = match.group(1) if match else ""
    body = text[match.end():] if match else text
    labels = list(LABEL.finditer(body)) if allow_labels else []
    result = {"key": key, "en": "", "fi": "", "shared": ""}
    if (not labels or body[:labels[0].start()].strip()
            or len({m.group(1).lower() for m in labels}) != len(labels)):
        result["shared"] = body
        return result
    for i, label in enumerate(labels):
        end = labels[i + 1].start() if i + 1 < len(labels) else len(body)
        result[label.group(1).lower()] = body[label.end():end].strip()
    if not result["en"] and not result["fi"]:
        result["shared"] = body
    return result


def records_from_blocks(blocks, document_id):
    records = []
    for section, position, text, allow_labels in blocks:
        parsed = parse_text(text, allow_labels)
        record = dict(parsed, section=section, original_text=text,
                      first_block=position, last_block=position)
        previous = records[-1] if records else None
        # Pair only adjacent, complementary labels with matching keys/sections.
        # Missing/ambiguous counterparts stay separate rather than being guessed.
        if (previous and previous["section"] == section
                and previous["key"] == record["key"]
                and not previous["shared"] and not record["shared"]
                and bool(previous["en"]) != bool(previous["fi"])
                and bool(record["en"]) != bool(record["fi"])
                and bool(previous["en"]) != bool(record["en"])):
            previous["en"] = previous["en"] or record["en"]
            previous["fi"] = previous["fi"] or record["fi"]
            previous["original_text"] += "\n\n" + text
            previous["last_block"] = position
        else:
            records.append(record)
    for i, record in enumerate(records, 1):
        record["id"] = f"{document_id}-record-{i}"
        record["location"] = f"body blocks {record.pop('first_block')}–{record.pop('last_block')}"
    return records


def record_text(record):
    parts = []
    if record["key"]:
        parts.append("[" + record["key"] + "]")
    if record["shared"]:
        parts.append(record["shared"])
    for language in ("en", "fi"):
        if record[language]:
            parts.append(language.upper() + ": " + record[language])
    return "\n".join(parts)


def build_chunks(records, document_id, split_text):
    chunks, pending = [], []

    def flush():
        if not pending:
            return
        text = "\n\n".join(record_text(r) for r in pending)
        # Normal pairs stay whole, even when larger than the packing target.
        parts = [text] if len(text) <= 4000 else split_text(text)
        for part in parts:
            chunks.append({"id": f"{document_id}-{len(chunks) + 1}", "text": part,
                           "section": pending[0]["section"],
                           "location": "; ".join(dict.fromkeys(r["location"] for r in pending)),
                           "record_ids": [r["id"] for r in pending]})

    for record in records:
        if pending and (record["section"] != pending[0]["section"]
                        or sum(len(record_text(r)) + 2 for r in pending) + len(record_text(record)) > 1800):
            flush()
            pending = []
        pending.append(record)
    flush()
    return chunks
