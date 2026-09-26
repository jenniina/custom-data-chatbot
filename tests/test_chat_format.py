from unittest import TestCase
from webapp.templatetags.chat_format import assistant_markdown


class MarkdownTests(TestCase):
    def test_profile_formatting_and_citations(self):
        html = assistant_markdown("A **visual designer** in Helsinki. [1]\n\nSee [portfolio](https://example.com/portfolio). [2]")
        self.assertIn("<strong>visual designer</strong>", html)
        self.assertIn('<a href="https://example.com/portfolio">portfolio</a>', html)
        self.assertEqual(html.count("<p>"), 2)
        self.assertIn("[1]", html)

    def test_html_and_unsafe_links_are_not_executable(self):
        html = assistant_markdown('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert%281%29)\n\n[bad](data:text/html,evil)\n\n[bad](file:///secret)')
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("href=", html)
        self.assertIn("&lt;script&gt;", html)

    def test_images_are_not_embedded(self):
        self.assertNotIn("<img", assistant_markdown("![tracking](https://example.com/image.png)"))

    def test_lists_code_and_heading_hierarchy(self):
        html = assistant_markdown("# Background\n\n- Design\n- Development\n\n`<script>`")
        self.assertIn("<h4>Background</h4>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<code>&lt;script&gt;</code>", html)
