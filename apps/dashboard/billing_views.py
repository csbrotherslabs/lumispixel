from decimal import Decimal

from django.contrib import messages
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.billing.ai_usage import get_usage_balance
from apps.billing.models import Plan, PlanAllowance, PlanPrice
from apps.billing.services import PlanUnavailableError, ensure_subscription, select_plan
from apps.galleries.models import Gallery

from .views import _dashboard_context, photographer_workspace_required


GIB = 1024 ** 3


def _format_bytes(value):
    value = int(value or 0)
    if value >= 1024 ** 4:
        return f"{value / 1024 ** 4:.1f} TB"
    if value >= GIB:
        number = value / GIB
        return f"{number:.0f} GB" if number.is_integer() else f"{number:.1f} GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB"
    return "0 GB" if value == 0 else f"{value / 1024:.1f} KB"


def _allowance_display(allowance):
    if allowance.limit_type == PlanAllowance.LimitType.UNLIMITED:
        return "Unlimited"
    if allowance.limit_type == PlanAllowance.LimitType.CUSTOM:
        return "Custom"
    if allowance.key == "storage_bytes":
        return _format_bytes(allowance.value)
    return f"{allowance.value:,} {allowance.unit}" if allowance.value is not None else "—"


def _price_copy(plan):
    prices = {price.billing_interval: price for price in plan.prices.all() if price.is_active}
    monthly = prices.get(PlanPrice.BillingInterval.MONTHLY)
    annual = prices.get(PlanPrice.BillingInterval.ANNUAL)
    custom = prices.get(PlanPrice.BillingInterval.CUSTOM)

    if custom or (monthly is None and annual is None):
        return {"monthly": "Custom", "annual": "Custom"}

    monthly_copy = "$0" if monthly and monthly.amount_cents == 0 else (
        f"${monthly.amount_cents // 100:,}/month" if monthly and monthly.amount_cents is not None else "—"
    )
    if annual and annual.amount_cents is not None:
        monthly_equivalent = annual.amount_cents / 12 / 100
        annual_copy = f"${monthly_equivalent:.0f}/month · ${annual.amount_cents / 100:,.0f}/year"
    else:
        annual_copy = monthly_copy
    return {"monthly": monthly_copy, "annual": annual_copy}


def _plan_cards(current_plan):
    cards = []
    plans = (
        Plan.objects.filter(is_active=True, is_public=True)
        .prefetch_related("prices", "allowances")
        .order_by("sort_order", "pk")
    )
    for plan in plans:
        allowances = {item.key: item for item in plan.allowances.all()}
        cards.append({
            "code": plan.code,
            "name": plan.name,
            "description": plan.description,
            "is_current": plan.pk == current_plan.pk,
            "selectable": plan.customer_selectable,
            "price": _price_copy(plan),
            "allowances": [
                ("Storage", _allowance_display(allowances.get("storage_bytes"))) if allowances.get("storage_bytes") else ("Storage", "—"),
                ("Active galleries", _allowance_display(allowances.get("active_galleries"))) if allowances.get("active_galleries") else ("Active galleries", "—"),
                ("CRM contacts", _allowance_display(allowances.get("crm_contacts"))) if allowances.get("crm_contacts") else ("CRM contacts", "—"),
                ("Team members", _allowance_display(allowances.get("team_members"))) if allowances.get("team_members") else ("Team members", "—"),
                ("Monthly AI actions", _allowance_display(allowances.get("ai_monthly_actions"))) if allowances.get("ai_monthly_actions") else ("Monthly AI actions", "—"),
            ],
        })
    return cards


def _storage_summary(profile, plan):
    used = Gallery.objects.for_photographer(profile).aggregate(
        total=Coalesce(Sum("storage_used"), Value(0), output_field=DecimalField())
    )["total"]
    used = int(used or 0)
    allowance = plan.allowances.filter(key="storage_bytes").first()
    if allowance is None:
        return {"used": _format_bytes(used), "limit": "Not configured", "percent": None, "remaining": None}
    if allowance.limit_type == PlanAllowance.LimitType.UNLIMITED:
        return {"used": _format_bytes(used), "limit": "Unlimited", "percent": None, "remaining": "Unlimited"}
    if allowance.limit_type == PlanAllowance.LimitType.CUSTOM or allowance.value is None:
        return {"used": _format_bytes(used), "limit": "Custom", "percent": None, "remaining": "Custom"}
    percent = round((Decimal(used) / Decimal(allowance.value)) * 100) if allowance.value else 0
    return {
        "used": _format_bytes(used),
        "limit": _format_bytes(allowance.value),
        "percent": min(percent, 100),
        "percent_raw": percent,
        "remaining": _format_bytes(max(allowance.value - used, 0)),
    }


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def billing_account(request):
    profile = request.studio
    subscription = ensure_subscription(profile)

    if request.method == "POST":
        plan_code = request.POST.get("plan", "").strip().lower()
        if not plan_code:
            messages.error(request, "Choose a plan before continuing.")
            return redirect("photographer_workspace:billing")
        try:
            updated = select_plan(profile, plan_code, enforce_customer_selectable=True)
        except Plan.DoesNotExist:
            messages.error(request, "That plan is not available.")
        except PlanUnavailableError as exc:
            messages.info(request, str(exc))
        else:
            if updated.plan_id == subscription.plan_id:
                messages.success(request, f"Your {updated.plan.name} plan is already active.")
            else:
                messages.success(request, f"Your workspace is now on the {updated.plan.name} plan.")
        return redirect("photographer_workspace:billing")

    plan = subscription.plan
    ai_balance = get_usage_balance(profile)
    entitlements = list(plan.entitlements.filter(enabled=True).order_by("label").values_list("label", flat=True))
    context = _dashboard_context(request, "billing", "Billing & Plan")
    context.update({
        "subscription": subscription,
        "current_plan": plan,
        "plan_cards": _plan_cards(plan),
        "storage_summary": _storage_summary(profile, plan),
        "ai_summary": {
            "included_allowance": ai_balance.included_allowance,
            "used": ai_balance.included_consumed,
            "reserved": ai_balance.included_reserved,
            "remaining": ai_balance.included_remaining,
            "purchased": ai_balance.purchased_balance,
            "purchased_available": ai_balance.purchased_available,
            "limit_type": ai_balance.allowance_limit_type,
            "period_start": ai_balance.period_starts_at,
            "period_end": ai_balance.period_ends_at,
        },
        "entitlements": entitlements,
        "pricing_url": reverse("core:pricing"),
        "launch_notice": "Paid upgrades and payment methods will be enabled after LumisPixel AI launch readiness and Stripe integration are complete.",
    })
    return render(request, "photographer_workspace/billing/account.html", context)
