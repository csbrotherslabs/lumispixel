"""First-party gallery event recording and bounded reporting helpers."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import GalleryAnalyticsEvent, GalleryOrder


def track_gallery_event(*, gallery, event_type, visitor_identifier="", session_identifier="",
                        user=None, photo=None, album=None, device_category="unknown", source="", metadata=None,
                        occurred_at=None):
    """Record only allow-listed analytics fields; callers should never pass raw PII in metadata."""
    if event_type not in GalleryAnalyticsEvent.EventType.values:
        raise ValueError("Unsupported gallery analytics event type.")
    event = GalleryAnalyticsEvent(
        photographer=gallery.photographer, gallery=gallery,
        visitor_identifier=visitor_identifier[:64], session_identifier=session_identifier[:64],
        authenticated_user=user if getattr(user, "is_authenticated", False) else None,
        event_type=event_type, related_photo=photo, related_album=album,
        device_category=device_category if device_category in GalleryAnalyticsEvent.Device.values else GalleryAnalyticsEvent.Device.UNKNOWN,
        source=source[:24], metadata=metadata or {}, occurred_at=occurred_at or timezone.now(),
    )
    event.full_clean()
    event.save()
    return event


def gallery_analytics_report(*, gallery, start=None, end=None, album_id=None, device="", visitor_type="all"):
    """Build a report using a bounded date window and owner-scoped querysets."""
    today = timezone.localdate()
    end = min(end or today, today)
    start = max(start or end - timedelta(days=29), end - timedelta(days=365))
    end_exclusive = end + timedelta(days=1)
    events = GalleryAnalyticsEvent.objects.for_photographer(gallery.photographer).filter(
        gallery=gallery, occurred_at__date__gte=start, occurred_at__date__lt=end_exclusive
    )
    if album_id:
        events = events.filter(related_album_id=album_id)
    if device in GalleryAnalyticsEvent.Device.values:
        events = events.filter(device_category=device)
    if visitor_type == "client":
        events = events.filter(authenticated_user__isnull=False)
    elif visitor_type == "guest":
        events = events.filter(authenticated_user__isnull=True)

    event_counts = dict(events.values_list("event_type").annotate(total=Count("id")))
    unique_visitors = events.exclude(visitor_identifier="").values("visitor_identifier").distinct().count()
    sessions = events.exclude(session_identifier="").values("session_identifier").distinct().count()
    revenue = events.filter(event_type=GalleryAnalyticsEvent.EventType.PURCHASE).aggregate(total=Sum("metadata__revenue"))["total"] or Decimal("0")
    daily_rows = {row["day"]: row for row in events.annotate(day=TruncDate("occurred_at")).values("day").annotate(
        views=Count("id", filter=Q(event_type=GalleryAnalyticsEvent.EventType.VIEW)),
        visitors=Count("visitor_identifier", distinct=True),
        downloads=Count("id", filter=Q(event_type__in=[GalleryAnalyticsEvent.EventType.DOWNLOAD, GalleryAnalyticsEvent.EventType.GALLERY_DOWNLOAD])),
        favorites=Count("id", filter=Q(event_type=GalleryAnalyticsEvent.EventType.FAVORITE)),
    ).order_by("day")}
    days, cursor = [], start
    while cursor <= end:
        row = daily_rows.get(cursor, {})
        days.append({"date": cursor.isoformat(), "label": cursor.strftime("%b %d"), "views": row.get("views", 0), "visitors": row.get("visitors", 0), "downloads": row.get("downloads", 0), "favorites": row.get("favorites", 0)})
        cursor += timedelta(days=1)

    popular = list(events.filter(related_photo__isnull=False).values("related_photo_id", "related_photo__original_name", "related_album__name").annotate(
        views=Count("id", filter=Q(event_type=GalleryAnalyticsEvent.EventType.PHOTO_VIEW)),
        favorites=Count("id", filter=Q(event_type=GalleryAnalyticsEvent.EventType.FAVORITE)),
        downloads=Count("id", filter=Q(event_type=GalleryAnalyticsEvent.EventType.DOWNLOAD)),
        purchases=Count("id", filter=Q(event_type=GalleryAnalyticsEvent.EventType.PURCHASE)),
    ).order_by("-views", "-favorites")[:10])
    recent = list(events.filter(event_type__in=["favorite", "comment", "share", "download", "purchase"]).select_related("related_photo", "authenticated_user")[:8])
    device_counts = dict(events.values_list("device_category").annotate(total=Count("id")))
    source_counts = dict(events.exclude(source="").values_list("source").annotate(total=Count("id")))
    client_count = events.filter(authenticated_user__isnull=False).values("visitor_identifier").distinct().count()
    returning = events.exclude(visitor_identifier="").values("visitor_identifier").annotate(visits=Count("session_identifier", distinct=True)).filter(visits__gt=1).count()
    total_downloads = event_counts.get("download", 0) + event_counts.get("gallery_download", 0)
    paid_orders = GalleryOrder.objects.filter(gallery=gallery, payment_status__in=[GalleryOrder.Status.PAID, GalleryOrder.Status.COMPLETED], created_at__date__range=(start, end))
    order_revenue = paid_orders.aggregate(total=Sum("total"))["total"] or revenue
    order_count = paid_orders.count()
    return {"start": start, "end": end, "events": events, "days": days, "popular": popular, "recent": recent,
            "counts": {"views": event_counts.get("view", 0), "visitors": unique_visitors, "downloads": total_downloads,
                       "favorites": event_counts.get("favorite", 0), "shares": event_counts.get("share", 0), "revenue": order_revenue},
            "visitor": {"new": max(unique_visitors-returning, 0), "returning": returning, "client": client_count,
                        "guest": max(unique_visitors-client_count, 0), "sessions": sessions},
            "download": {"individual": event_counts.get("download", 0), "gallery": event_counts.get("gallery_download", 0)},
            "store": {"revenue": order_revenue, "orders": order_count, "average": order_revenue/order_count if order_count else Decimal("0"),
                      "conversion": (order_count/unique_visitors*100) if unique_visitors else 0},
            "devices": device_counts, "sources": source_counts, "has_data": events.exists()}
