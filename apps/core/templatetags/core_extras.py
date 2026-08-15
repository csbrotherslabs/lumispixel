from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def split(value, separator=','):
    return str(value).split(separator)


@register.filter
def usd(value):
    """Render monetary values with the store's en-US presentation."""
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


@register.filter
def contract_rich_text(value):
    """Render the contract editor's small, explicit formatting allowlist safely."""
    rendered = escape(value or "")
    for tag in ("strong", "em", "u", "ul", "ol", "li"):
        rendered = rendered.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        rendered = rendered.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    blocks = []
    for block in rendered.split("\n\n"):
        block = block.replace("\n", "<br>")
        if block.startswith(("<ul>", "<ol>")):
            blocks.append(block)
        else:
            blocks.append(f"<p>{block}</p>")
    return mark_safe("\n".join(blocks))
