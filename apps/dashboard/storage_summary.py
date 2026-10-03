"""Plan-aware dashboard storage summary; uses upload accounting."""
from django.db.models import Sum
from django.urls import reverse

from apps.billing.services import PlanConfigurationError, ensure_subscription, get_allowance
from apps.galleries.models import Gallery


def storage_label(value):
    if value >= 1024 ** 4:
        return f"{value / 1024 ** 4:g} TB"
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.1f}".rstrip("0").rstrip(".") + " GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f}".rstrip("0").rstrip(".") + " MB"
    return f"{value:,} bytes"


def build_storage_summary(access):
    if access.membership is not None:
        return None
    studio = access.studio
    try:
        subscription = ensure_subscription(studio)
        allowance = get_allowance(studio, "storage_bytes")
        if not allowance.is_custom and not allowance.is_unlimited and (
            allowance.value is None or allowance.value < 0
        ):
            raise PlanConfigurationError("Invalid storage allowance.")
    except PlanConfigurationError:
        return {"unavailable": True}
    used = int(Gallery.objects.filter(photographer=studio).aggregate(total=Sum("storage_used"))["total"] or 0)
    summary = {"plan": subscription.plan.name, "used": storage_label(used),
               "url": reverse("photographer_workspace:galleries")}
    if allowance.is_custom or allowance.is_unlimited:
        summary["limit_description"] = "Custom storage allowance" if allowance.is_custom else "Unlimited storage"
    else:
        limit = allowance.value
        summary.update({"limit": storage_label(limit),
                        "remaining": storage_label(max(limit - used, 0)),
                        "percent": min(100, round(used / limit * 100, 2)) if limit else 100,
                        "full": used >= limit})
    return summary
