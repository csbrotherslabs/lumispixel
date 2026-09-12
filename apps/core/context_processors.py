from django.db import DatabaseError

from apps.billing.models import Plan, PlanAllowance, PlanPrice


AUDIENCE = {
    "free": "Build the foundation.",
    "pro": "Run the whole business.",
    "studio": "Scale with a team.",
    "enterprise": "Shape it around your operation.",
}

ALLOWANCE_ORDER = [
    "active_galleries",
    "storage_bytes",
    "crm_contacts",
    "team_members",
    "ai_monthly_actions",
]

LABELS = {
    "active_galleries": "active galleries",
    "crm_contacts": "CRM contacts",
    "team_members": "team members",
    "ai_monthly_actions": "AI image actions / month",
}


def _format_storage(value):
    gib = value / (1024 ** 3)
    if gib >= 1024 and gib % 1024 == 0:
        return f"{int(gib / 1024)} TB storage"
    return f"{int(gib)} GB storage"


def _format_allowance(allowance):
    if allowance.key == "storage_bytes":
        if allowance.limit_type == PlanAllowance.LimitType.UNLIMITED:
            return "Unlimited storage"
        if allowance.limit_type == PlanAllowance.LimitType.CUSTOM:
            return "Custom storage"
        return _format_storage(allowance.value or 0)

    label = LABELS.get(allowance.key, allowance.label)
    if allowance.limit_type == PlanAllowance.LimitType.UNLIMITED:
        return f"Unlimited {label}"
    if allowance.limit_type == PlanAllowance.LimitType.CUSTOM:
        return f"Custom {label}"
    return f"{allowance.value or 0:,} {label}"


def _monthly_text(price):
    if price is None or price.amount_cents is None:
        return "Custom"
    if price.amount_cents == 0:
        return "$0"
    return f"${price.amount_cents / 100:,.0f} / month"


def _annual_text(price):
    if price is None or price.amount_cents is None:
        return "Custom"
    if price.amount_cents == 0:
        return "$0"
    monthly_equivalent = price.amount_cents / 12 / 100
    return f"${monthly_equivalent:,.0f} / month · billed annually at ${price.amount_cents / 100:,.0f}"


def pricing_catalog():
    plans = (
        Plan.objects.filter(is_active=True, is_public=True)
        .prefetch_related("prices", "allowances")
        .order_by("sort_order", "pk")
    )
    catalog = []
    for plan in plans:
        prices = {item.billing_interval: item for item in plan.prices.all() if item.is_active}
        allowances = {item.key: item for item in plan.allowances.all()}
        catalog.append({
            "code": plan.code,
            "name": plan.name,
            "audience": AUDIENCE.get(plan.code, plan.description),
            "monthly": _monthly_text(prices.get(PlanPrice.BillingInterval.MONTHLY)),
            "annual": _annual_text(prices.get(PlanPrice.BillingInterval.ANNUAL)),
            "features": [_format_allowance(allowances[key]) for key in ALLOWANCE_ORDER if key in allowances],
            "available": plan.customer_selectable,
            "featured": plan.code == "pro",
            "badge": "Most Popular" if plan.code == "pro" else "",
        })
    return catalog


def marketing_pricing(request):
    try:
        catalog = pricing_catalog()
    except DatabaseError:
        catalog = []
    return {"marketing_pricing_plans": catalog}
