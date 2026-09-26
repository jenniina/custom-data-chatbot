"""Download anonymous OneDrive shares without Microsoft credentials."""
from email.message import Message
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

from context_me.documents import MAX_FILE_BYTES, convert_docx, load_document


def validate_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = (host in {"1drv.ms", "onedrive.live.com", "api.onedrive.com"}
               or host.endswith(".1drv.com") or host.endswith(".storage.live.com")
               or host.endswith(".sharepoint.com"))
    if (len(url) > 8192 or parsed.scheme != "https" or not allowed
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Use an HTTPS OneDrive sharing link, such as https://1drv.ms/…")
    return parsed


def read_public_document(url, source_name=""):
    parsed = validate_url(url.strip())
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key.lower() != "download"]
    query.append(("download", "1"))
    current = urlunparse(parsed._replace(query=urlencode(query), fragment=""))
    try:
        # Preserve Microsoft's share cookies while validating every redirect.
        with requests.Session() as session:
            for _ in range(8):
                validate_url(current)
                with session.get(current, stream=True, allow_redirects=False, timeout=(10, 30)) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise ValueError("OneDrive returned an incomplete redirect.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code != 200:
                        raise ValueError("The OneDrive file could not be downloaded. Use an Anyone-with-the-link file with downloads allowed.")
                    if "text/html" in response.headers.get("Content-Type", "").lower():
                        raise ValueError("OneDrive returned a web page instead of a file. Check that the link opens without sign-in and downloads are allowed; otherwise download and upload the file manually.")
                    length = response.headers.get("Content-Length", "")
                    if length.isdigit() and int(length) > MAX_FILE_BYTES:
                        raise ValueError("The OneDrive file exceeds 20 MB.")
                    parts, size = [], 0
                    for part in response.iter_content(chunk_size=65536):
                        size += len(part)
                        if size > MAX_FILE_BYTES:
                            raise ValueError("The OneDrive file exceeds 20 MB.")
                        parts.append(part)
                    raw = b"".join(parts)
                    disposition = Message()
                    disposition["Content-Disposition"] = response.headers.get("Content-Disposition", "")
                    filename = disposition.get_filename() or "OneDrive document.docx"
                    if raw.startswith(b"PK"):
                        name = PurePosixPath((source_name.strip() or filename).replace("\\", "/")).name
                        if not name.lower().endswith(".docx"):
                            name += ".docx"
                        return convert_docx(raw, name)
                    return load_document(raw)
        raise ValueError("OneDrive redirected too many times. Download and upload the file manually.")
    except requests.RequestException:
        # Never expose signed URLs, tokens, or document contents in error output.
        raise ValueError("Could not reach OneDrive. Check the link and connection, then try again.") from None
