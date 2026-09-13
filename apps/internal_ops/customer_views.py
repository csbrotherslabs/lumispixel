from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render

from apps.billing.ai_usage import get_usage_balance
from apps.billing.models import Subscription
from apps.galleries.models import Gallery

from .decorators import internal_employee_required
from .models import InternalAuditEvent


User = get_user_model()
GIB = 1024 ** 3


def _format_bytes(value):
    value = int(value or 0)
    if value >= 1024 ** 4:
        return f"{value / 1024 ** 4:.1f} TB"
    if value >= GIB:
        amount = value / GIB
        return f"{amount:.0f} GB" if amount.is_integer() else f"{amount:.1f} GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB"
    return "0 GB" if value == 0 else f"{value / 1024:.1f} KB"


def _customer_queryset():
    return User.objects.filter(
        Q(client_profile__isnull=False) | Q(photographer_profile__isnull=False)
    ).distinct().order_by("-date_joined")


@internal_employee_required
def customer_list(request):
    query = request.GET.get("q", "").strip()
    account_type = request.GET.get("type", "all").strip().lower()
    status = request.GET.get("status", "all").strip().lower()

    customers = _customer_queryset()
    if query:
        customers = customers.filter(
            Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(photographer_profile__business_name__icontains=query)
            | Q(photographer_profile__display_name__icontains=query)
            | Q(client_profile__display_name__icontains=query)
        ).distinct()
    if account_type == "photographer":
        customers = customers.filter(photographer_profile__isnull=False)
    elif account_type == "client":
        customers = customers.filter(client_profile__isnull=False)
    if status != "all" and status in dict(User.AccountStatus.choices):
        customers = customers.filter(account_status=status)

    customer_rows = []
    for customer in customers[:100]:
        photographer = getattr(customer, "photographer_profile", None)
        subscription = None
        if photographer:
            subscription = Subscription.objects.select_related("plan").filter(photographer=photographer).first()
        customer_rows.append({
            "user": customer,
            "photographer": photographer,
            "client": getattr(customer, "client_profile", None),
            "subscription": subscription,
        })

    return render(request, "internal_ops/customers/list.html", {
        "customer_rows": customer_rows,
        "query": query,
        "account_type": account_type,
        "status_filter": status,
        "customer_count": _customer_queryset().count(),
        "photographer_count": _customer_queryset().filter(photographer_profile__isnull=False).count(),
        "client_count": _customer_queryset().filter(client_profile__isnull=False).count(),
    })


@internal_employee_required
def customer_detail(request, user_id):
    customer = get_object_or_404(_customer_queryset(), pk=user_id)
    photographer = getattr(customer, "photographer_profile", None)
    client = getattr(customer, "client_profile", None)
    subscription = None
    storage_used = 0
    gallery_count = 0
    ai_summary = None

    if photographer:
        subscription = Subscription.objects.select_related("plan").filter(photographer=photographer).first()
        gallery_qs = Gallery.objects.for_photographer(photographer)
        gallery_count = gallery_qs.count()
        storage_used = gallery_qs.aggregate(total=Sum("storage_used"))["total"] or 0
        if subscription:
            balance = get_usage_balance(photographer)
            ai_summary = {
                "used": balance.included_consumed,
                "reserved": balance.included_reserved,
                "remaining": balance.included_remaining,
                "allowance": balance.included_allowance,
                "purchased": balance.purchased_available,
                "limit_type": balance.allowance_limit_type,
                "period_end": balance.period_ends_at,
            }

    InternalAuditEvent.objects.create(
        actor=request.employee_profile,
        category=InternalAuditEvent.Category.CUSTOMER,
        action="internal.customer.view",
        target_type="accounts.User",
        target_id=str(customer.pk),
        summary=f"Viewed customer account {customer.email}",
        metadata={"customer_email": customer.email, "superuser": request.user.is_superuser},
    )

    account_types = []
    if photographer:
        account_types.append("Photographer")
    if client:
        account_types.append("Client")

    return render(request, "internal_ops/customers/detail.html", {
        "customer": customer,
        "photographer": photographer,
        "client_profile": client,
        "subscription": subscription,
        "account_types": account_types,
        "gallery_count": gallery_count,
        "storage_used": _format_bytes(storage_used),
        "ai_summary": ai_summary,
        "recent_customer_activity": InternalAuditEvent.objects.filter(
            target_type="accounts.User", target_id=str(customer.pk)
        ).select_related("actor__user")[:10],
    })
