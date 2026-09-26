"""Read selected files from a personal OneDrive using delegated Microsoft sign-in."""
from pathlib import PurePosixPath
import time
from urllib.parse import quote, urlparse

import msal
import requests

from context_me.documents import MAX_FILE_BYTES, convert_docx, load_document

SCOPES = ["Files.Read"]
GRAPH = "https://graph.microsoft.com/v1.0"


class OneDrive:
    """Tokens are kept in the administrator's private, server-side session."""

    def __init__(self, client_id, serialized_cache=None):
        if not client_id.strip():
            raise ValueError("Set ONEDRIVE_CLIENT_ID in your hosting secrets first. See ONEDRIVE.md.")
        self.cache = msal.SerializableTokenCache()
        if serialized_cache:
            self.cache.deserialize(serialized_cache)
        self.app = msal.PublicClientApplication(
            client_id.strip(), authority="https://login.microsoftonline.com/consumers",
            timeout=30, token_cache=self.cache,
        )

    def serialize_cache(self):
        return self.cache.serialize()

    def begin_sign_in(self):
        flow = self.app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise ValueError("Microsoft could not start sign-in. Check the app registration and enable public client flows.")
        return flow

    def finish_sign_in(self, flow):
        if time.time() >= flow.get("expires_at", 0):
            raise ValueError("The sign-in code expired. Start a new OneDrive connection.")
        # One polling attempt per click rather than blocking the app until expiry.
        result = self.app.acquire_token_by_device_flow(flow, exit_condition=lambda _: True)
        if "access_token" in result:
            return True
        if result.get("error") in ("authorization_pending", "slow_down"):
            return False
        raise ValueError("Microsoft sign-in was not completed. Start a new connection and try again.")

    def token(self):
        accounts = self.app.get_accounts()
        result = self.app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
        if not result or "access_token" not in result:
            raise ValueError("Reconnect OneDrive: your Microsoft session is missing or expired.")
        return result["access_token"]

    def read_document(self, path):
        path = path.strip().strip("/")
        if not path or any(part in (".", "..") for part in path.split("/")) or "\\" in path:
            raise ValueError("Enter a OneDrive file path such as ContextMe/profile.json, using forward slashes.")
        if PurePosixPath(path).suffix.lower() not in (".docx", ".json"):
            raise ValueError("Choose a .docx or converter-produced .json file.")
        headers = {"Authorization": "Bearer " + self.token()}
        url = GRAPH + "/me/drive/root:/" + quote(path, safe="/")
        with requests.get(url, headers=headers, timeout=30, allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError("Could not read that OneDrive file. Check the path, account, and read permission.")
            metadata = response.json()
        if "file" not in metadata or metadata.get("size", 0) > MAX_FILE_BYTES:
            raise ValueError("Select a file no larger than 20 MB.")
        with requests.get(url + ":/content", headers=headers, timeout=30, allow_redirects=False) as response:
            if response.status_code != 302:
                raise ValueError("OneDrive did not provide a download link. Reconnect and try again.")
            download_url = response.headers.get("Location", "")
        parsed = urlparse(download_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("OneDrive returned an invalid download link.")
        # Graph's download URL is preauthenticated; never send the Graph token to it.
        with requests.get(download_url, stream=True, timeout=60) as response:
            if response.status_code != 200:
                raise ValueError("OneDrive download failed. Try loading the file again.")
            parts, length = [], 0
            for part in response.iter_content(chunk_size=65536):
                length += len(part)
                if length > MAX_FILE_BYTES:
                    raise ValueError("The downloaded file exceeds 20 MB.")
                parts.append(part)
        raw = b"".join(parts)
        filename = metadata.get("name", PurePosixPath(path).name)
        if PurePosixPath(filename).suffix.lower() == ".docx":
            return convert_docx(raw, filename)
        return load_document(raw)
