"""Read-only operational metrics; outbox records and provider events are distinct units."""
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.notifications.models import BrevoEmailEvent, EmailDelivery

PERIODS = (1, 7, 30, 90)
FAILURE_EVENTS = ("hard_bounce", "soft_bounce", "blocked", "invalid_email", "error")
FILTERS = ("all", "accepted", "delivered", "deferred", "provider_failure", "complaint", "pending", "sending", "retry", "uncertain", "dead", "cancelled", "expired")


def delivery_rows(days, now=None):
    now = now or timezone.now()
    events = BrevoEmailEvent.objects.filter(delivery_id=OuterRef("pk"))
    return EmailDelivery.objects.filter(created_at__gte=now-timedelta(days=days), created_at__lte=now).annotate(
        has_delivery=Exists(events.filter(event="delivered")),
        has_deferred=Exists(events.filter(event="deferred")),
        has_failure=Exists(events.filter(event__in=FAILURE_EVENTS)),
        has_complaint=Exists(events.filter(event="spam")),
    )


def filtered_rows(rows, status):
    predicates = {
        "accepted": Q(status="sent"),
        "delivered": Q(has_delivery=True),
        "deferred": Q(has_deferred=True),
        "provider_failure": Q(has_failure=True),
        "complaint": Q(has_complaint=True),
        "dead": Q(status__in=["dead", "failed"]),
    }
    if status in predicates:
        return rows.filter(predicates[status])
    if status in ("pending", "sending", "retry", "uncertain", "cancelled", "expired"):
        return rows.filter(status=status)
    return rows


def email_snapshot(days, now=None):
    now = now or timezone.now()
    rows = delivery_rows(days, now)
    counts = rows.aggregate(
        cancelled=Count("pk", filter=Q(status="cancelled")),
        expired=Count("pk", filter=Q(status="expired")),
        total=Count("pk"),
        accepted=Count("pk", filter=Q(status="sent")),
        delivered=Count("pk", filter=Q(has_delivery=True)),
        deferred=Count("pk", filter=Q(has_deferred=True)),
        provider_failure=Count("pk", filter=Q(has_failure=True)),
        complaint=Count("pk", filter=Q(has_complaint=True)),
        pending=Count("pk", filter=Q(status="pending")),
        sending=Count("pk", filter=Q(status="sending")),
        retry=Count("pk", filter=Q(status="retry")),
        uncertain=Count("pk", filter=Q(status="uncertain")),
        dead=Count("pk", filter=Q(status__in=["dead", "failed"])),
    )
    counts["delivery_evidence_rate"] = round(100*counts["delivered"]/counts["total"], 1) if counts["total"] else None
    events = BrevoEmailEvent.objects.filter(received_at__gte=now-timedelta(days=days), received_at__lte=now)
    event_counts = events.aggregate(total=Count("pk"), unmatched=Count("pk", filter=Q(delivery__isnull=True)))
    event_types = list(events.order_by("event").values("event").annotate(total=Count("pk")))
    backlog = EmailDelivery.objects.aggregate(
        uncertain=Count("pk", filter=Q(status="uncertain")),
        dead=Count("pk", filter=Q(status__in=["dead", "failed"])),
        overdue=Count("pk", filter=Q(status__in=["pending", "retry"], created_at__lt=now-timedelta(minutes=15)) &
                      (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lt=now-timedelta(minutes=15)))),
    )
    return counts, event_counts, event_types, backlog
