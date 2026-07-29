from django import template

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
