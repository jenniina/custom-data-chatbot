import json
import time
from unittest import TestCase
from unittest.mock import Mock, patch

from context_me.documents import dump_document
from context_me.onedrive import OneDrive
from tests.test_core import sample_document


def response(status, payload=None, headers=None, raw=b""):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = payload
    result.iter_content.return_value = [raw]
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


class OneDriveTests(TestCase):
    def setUp(self):
        patcher = patch("context_me.onedrive.msal.PublicClientApplication")
        self.msal = patcher.start()
        self.addCleanup(patcher.stop)
        self.app = self.msal.return_value
        self.app.get_accounts.return_value = [{"username": "test@example.invalid"}]
        self.app.acquire_token_silent.return_value = {"access_token": "private-token"}
        self.drive = OneDrive("client-id")

    @patch("context_me.onedrive.requests.get")
    def test_json_download_keeps_graph_token_off_download_request(self, get):
        document = sample_document()
        get.side_effect = [response(200, {"file": {}, "size": 100, "name": "profile.json"}),
                           response(302, headers={"Location": "https://test.files.1drv.com/download"}),
                           response(200, raw=dump_document(document).encode())]
        self.assertEqual(self.drive.read_document("Context Me/profile.json"), document)
        self.assertIn("Context%20Me/profile.json", get.call_args_list[0].args[0])
        self.assertEqual(get.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer private-token")
        self.assertNotIn("headers", get.call_args_list[2].kwargs)

    @patch("context_me.onedrive.requests.get")
    def test_docx_is_converted(self, get):
        from io import BytesIO
        from docx import Document
        document = Document()
        document.add_paragraph("I live in Helsinki.")
        raw = BytesIO()
        document.save(raw)
        get.side_effect = [response(200, {"file": {}, "size": len(raw.getvalue()), "name": "profile.docx"}),
                           response(302, headers={"Location": "https://test.files.1drv.com/download"}),
                           response(200, raw=raw.getvalue())]
        loaded = self.drive.read_document("profile.docx")
        self.assertIn("Helsinki", loaded["chunks"][0]["text"])

    @patch("context_me.onedrive.requests.get")
    def test_oversize_metadata_stops_download(self, get):
        get.return_value = response(200, {"file": {}, "size": 21 * 1024 * 1024})
        with self.assertRaisesRegex(ValueError, "20 MB"):
            self.drive.read_document("profile.json")
        self.assertEqual(get.call_count, 1)

    @patch("context_me.onedrive.requests.get")
    def test_unsafe_download_link_is_rejected(self, get):
        get.side_effect = [response(200, {"file": {}, "size": 100}), response(302, headers={"Location": "http://example.invalid/file"})]
        with self.assertRaisesRegex(ValueError, "invalid download"):
            self.drive.read_document("profile.json")
        self.assertEqual(get.call_count, 2)

    def test_expired_or_pending_login(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            self.drive.finish_sign_in({"expires_at": 0})
        self.app.acquire_token_by_device_flow.return_value = {"error": "authorization_pending"}
        self.assertFalse(self.drive.finish_sign_in({"expires_at": time.time() + 300}))

    def test_bad_path_and_missing_account(self):
        with self.assertRaises(ValueError):
            self.drive.read_document("../profile.json")
        self.app.get_accounts.return_value = []
        with self.assertRaisesRegex(ValueError, "Reconnect"):
            self.drive.read_document("profile.json")
