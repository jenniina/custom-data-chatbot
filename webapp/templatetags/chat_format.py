"""Render untrusted assistant Markdown without enabling HTML or embedded images."""
from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

register = template.Library()
# CommonMark otherwise enables raw HTML by default. Do not enable HTML/plugins
# that emit untrusted markup. The parser also rejects unsafe link protocols.
renderer = MarkdownIt("commonmark", {"html": False}).disable("image")


@register.filter
def assistant_markdown(value):
    tokens = renderer.parse(str(value or ""))
    for token in tokens:
        if token.type in ("heading_open", "heading_close"):
            # Responses sit below the Conversation h2 and Chatbot h3.
            token.tag = "h4"
    return mark_safe(renderer.renderer.render(tokens, renderer.options, {}))
