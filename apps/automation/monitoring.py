from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import AutomationJob


def snapshot():
    counts = {row["status"]: row["count"] for row in
              AutomationJob.objects.values("status").annotate(count=Count("pk"))}
    result = {status: counts.get(status, 0) for status in AutomationJob.Status.values}
    result["total"] = sum(result.values())
    result["overdue"] = AutomationJob.objects.filter(
        status__in=[AutomationJob.Status.PENDING, AutomationJob.Status.RETRY],
        available_at__lt=timezone.now() - timedelta(minutes=15),
    ).count()
    return result
