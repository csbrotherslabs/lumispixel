"""Display-ready AI wallet data for the photographer workspace."""
from datetime import timedelta

from apps.billing.ai_usage import get_usage_balance
from apps.billing.models import PlanAllowance
from apps.billing.services import PlanConfigurationError, ensure_subscription, get_allowance


def _percent(value, total):
    if not total:
        return 0
    return min(round(value / total * 100), 100)


def build_ai_wallet(photographer, *, moment=None):
    """Return a read-only wallet summary backed by the Phase 2 usage ledger."""
    subscription = ensure_subscription(photographer)
    base = {
        "plan_code": subscription.plan.code,
        "plan_name": subscription.plan.name,
        "configured": True,
        "is_custom": False,
        "is_unlimited": False,
        "included_allowance": None,
        "included_consumed": 0,
        "included_reserved": 0,
        "included_remaining": None,
        "purchased_balance": 0,
        "purchased_reserved": 0,
        "purchased_available": 0,
        "total_available": None,
        "used_percent": 0,
        "pending_percent": 0,
        "reset_date": None,
    }

    try:
        allowance = get_allowance(photographer, "ai_monthly_actions")
    except PlanConfigurationError:
        return {
            **base,
            "configured": False,
            "status_message": "AI usage allowance is not configured for this plan yet.",
        }

    if allowance.limit_type == PlanAllowance.LimitType.CUSTOM:
        return {
            **base,
            "is_custom": True,
            "status_message": "Your AI allowance is managed as a custom plan limit.",
        }

    balance = get_usage_balance(photographer, moment=moment)
    reset_date = (balance.period_ends_at + timedelta(microseconds=1)).date()

    if balance.allowance_limit_type == PlanAllowance.LimitType.UNLIMITED:
        return {
            **base,
            "is_unlimited": True,
            "included_consumed": balance.included_consumed,
            "included_reserved": balance.included_reserved,
            "purchased_balance": balance.purchased_balance,
            "purchased_reserved": balance.purchased_reserved,
            "purchased_available": balance.purchased_available,
            "total_available": None,
            "reset_date": reset_date,
        }

    allowance_total = balance.included_allowance or 0
    used_percent = _percent(balance.included_consumed, allowance_total)
    pending_percent = min(
        _percent(balance.included_reserved, allowance_total),
        max(100 - used_percent, 0),
    )
    included_remaining = balance.included_remaining or 0
    total_available = included_remaining + balance.purchased_available

    return {
        **base,
        "included_allowance": allowance_total,
        "included_consumed": balance.included_consumed,
        "included_reserved": balance.included_reserved,
        "included_remaining": included_remaining,
        "purchased_balance": balance.purchased_balance,
        "purchased_reserved": balance.purchased_reserved,
        "purchased_available": balance.purchased_available,
        "total_available": total_available,
        "used_percent": used_percent,
        "pending_percent": pending_percent,
        "reset_date": reset_date,
    }
