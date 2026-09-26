from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch

from docx import Document

from context_me.documents import dump_document
from context_me.public_onedrive import read_public_document, validate_url
from tests.test_core import sample_document
from tests.test_onedrive import response


class PublicOneDriveTests(TestCase):
    def setUp(self):
        patcher = patch("context_me.public_onedrive.requests.Session")
        self.session_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.session = self.session_class.return_value.__enter__.return_value

    def test_short_url_downloads_and_converts_word(self):
        doc = Document()
        doc.add_paragraph("Sample personal profile.")
        raw = BytesIO()
        doc.save(raw)
        self.session.get.side_effect = [
            response(302, headers={"Location": "https://onedrive.live.com/download?authkey=example"}),
            response(200, raw=raw.getvalue()),
        ]
        converted = read_public_document("https://1drv.ms/w/example?e=keep&download=0", "My profile")
        self.assertEqual(converted["source"], "My profile.docx")
        self.assertIn("personal profile", converted["chunks"][0]["text"])
        first_url = self.session.get.call_args_list[0].args[0]
        self.assertIn("download=1", first_url)
        self.assertIn("e=keep", first_url)
        self.assertNotIn("download=0", first_url)

    def test_json_can_be_read(self):
        document = sample_document()
        self.session.get.return_value = response(200, raw=dump_document(document).encode())
        self.assertEqual(read_public_document("https://1drv.ms/u/example"), document)

    def test_untrusted_redirect_not_followed(self):
        self.session.get.return_value = response(302, headers={"Location": "http://127.0.0.1/private"})
        with self.assertRaises(ValueError):
            read_public_document("https://1drv.ms/w/example")
        self.assertEqual(self.session.get.call_count, 1)

    def test_html_not_imported(self):
        self.session.get.return_value = response(200, headers={"Content-Type": "text/html"}, raw=b"<html>login</html>")
        with self.assertRaisesRegex(ValueError, "web page"):
            read_public_document("https://1drv.ms/w/example")

    def test_download_size_limit(self):
        self.session.get.return_value = response(200, headers={"Content-Length": str(21 * 1024 * 1024)})
        with self.assertRaisesRegex(ValueError, "20 MB"):
            read_public_document("https://1drv.ms/w/example")

    def test_reject_other_hosts_and_credentials(self):
        for url in ["https://onedrive.live.com.evil.invalid/file", "https://127.0.0.1/file", "https://user:password@1drv.ms/w/example"]:
            with self.assertRaises(ValueError):
                validate_url(url)
