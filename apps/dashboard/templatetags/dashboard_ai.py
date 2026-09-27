from django import template

from apps.dashboard.ai_wallet import build_ai_wallet

register = template.Library()


@register.simple_tag
def ai_wallet_for(photographer):
    if photographer is None:
        return None
    return build_ai_wallet(photographer)
