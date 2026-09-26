from unittest import TestCase
from serve import listen_address


class StartupTests(TestCase):
    def test_hosted_default_is_container_port(self):
        self.assertEqual(listen_address(True, {}), ("0.0.0.0", 8080))

    def test_desktop_default_stays_local(self):
        self.assertEqual(listen_address(False, {}), ("127.0.0.1", 8501))

    def test_injected_port_always_wins(self):
        for port in (8080, 8501, 9090):
            self.assertEqual(listen_address(True, {"PORT": str(port)}), ("0.0.0.0", port))

    def test_bad_port_has_actionable_error(self):
        for port in ("", "abc", "0", "-1", "65536"):
            with self.subTest(port=port), self.assertRaisesRegex(ValueError, "PORT must be"):
                listen_address(True, {"PORT": port})
