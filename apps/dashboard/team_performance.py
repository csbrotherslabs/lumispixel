"""Studio-scoped team performance reporting from existing operational records."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.clients.models import ClientActivity, ClientSession
from apps.dashboard.models import Review, StudioMembership, StudioMembershipEvent
from apps.galleries.models import Gallery, GalleryActivity


RANGES = {"30d": 30, "90d": 90, "year": 365}


def _bounds(params):
    today = timezone.localdate()
    key = params.get("range", "30d")
    if key == "custom":
        try:
            start = datetime.strptime(params.get("start", ""), "%Y-%m-%d").date()
            end = datetime.strptime(params.get("end", ""), "%Y-%m-%d").date()
            if start > end or (end - start).days > 730:
                raise ValueError
        except (TypeError, ValueError):
            key, end, start = "30d", today, today - timedelta(days=29)
    else:
        key = key if key in RANGES else "30d"
        end, start = today, today - timedelta(days=RANGES[key] - 1)
    tz = timezone.get_current_timezone()
    return key, start, end, timezone.make_aware(datetime.combine(start, time.min), tz), timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)


def team_performance_report(studio, params):
    """Return attributed member metrics without manufacturing assignment data."""
    range_key, start, end, start_at, end_at = _bounds(params)
    role = params.get("role", "") if params.get("role", "") in dict(StudioMembership.Role.choices) else ""
    location = (params.get("location", "") or "").strip()[:150]
    member_value = params.get("member", "")

    memberships = list(StudioMembership.objects.filter(studio=studio, status=StudioMembership.Status.ACTIVE)
                       .select_related("user").order_by("role", "user__first_name", "invitation_first_name"))
    if role:
        memberships = [m for m in memberships if m.role == role]
    if location:
        memberships = [m for m in memberships if location == m.primary_location or location in (m.additional_locations or [])]
    if member_value.isdigit():
        memberships = [m for m in memberships if m.pk == int(member_value)]
    member_ids = [m.pk for m in memberships]

    sessions = list(ClientSession.objects.for_photographer(studio).filter(
        starts_at__gte=start_at, starts_at__lt=end_at).exclude(status=ClientSession.Status.CANCELLED)
        .prefetch_related("assigned_members").select_related("client"))
    galleries = list(Gallery.objects.for_photographer(studio).filter(
        Q(published_at__gte=start_at, published_at__lt=end_at) | Q(created_at__gte=start_at, created_at__lt=end_at))
        .prefetch_related("assigned_members"))
    locations = list(ClientSession.objects.for_photographer(studio).exclude(location="")
                     .order_by("location").values_list("location", flat=True).distinct())
    if location:
        sessions = [s for s in sessions if s.location == location]

    stats = defaultdict(lambda: {"bookings": 0, "completed": 0, "hours": 0, "revenue": Decimal("0"),
                                 "galleries": 0, "turnaround": [], "activity": 0})
    timeline = defaultdict(lambda: {"bookings": 0, "completed": 0, "galleries": 0})
    for session in sessions:
        assigned = [m for m in session.assigned_members.all() if m.pk in member_ids]
        if not assigned:
            continue
        share = session.booking_value / len(assigned)
        bucket = session.starts_at.date().replace(day=1)
        for member in assigned:
            row = stats[member.pk]
            row["bookings"] += 1
            row["hours"] += session.duration_minutes / 60
            row["revenue"] += share
            if session.status == ClientSession.Status.COMPLETED:
                row["completed"] += 1
            timeline[bucket]["bookings"] += 1
            timeline[bucket]["completed"] += session.status == ClientSession.Status.COMPLETED
    for gallery in galleries:
        for member in [m for m in gallery.assigned_members.all() if m.pk in member_ids]:
            stats[member.pk]["galleries"] += gallery.status in {Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED}
            if gallery.event_date and gallery.published_at:
                stats[member.pk]["turnaround"].append(max(0, (gallery.published_at.date() - gallery.event_date).days))
            timeline[(gallery.published_at or gallery.created_at).date().replace(day=1)]["galleries"] += 1

    rows = []
    for member in memberships:
        data = stats[member.pk]
        name = member.user.full_name if member.user_id else f"{member.invitation_first_name} {member.invitation_last_name}".strip()
        turnaround = round(sum(data["turnaround"]) / len(data["turnaround"]), 1) if data["turnaround"] else None
        rows.append({"id": member.pk, "name": name or member.email, "initials": "".join(x[0] for x in (name or member.email).split()[:2]).upper(),
                     "role": member.get_role_display(), "location": member.primary_location or "Not set", **data,
                     "hours": round(data["hours"], 1), "revenue": data["revenue"], "turnaround": turnaround,
                     "completion_rate": round(data["completed"] * 100 / data["bookings"]) if data["bookings"] else None})
    total_bookings = sum(r["bookings"] for r in rows)
    total_completed = sum(r["completed"] for r in rows)
    average_turnaround = [r["turnaround"] for r in rows if r["turnaround"] is not None]
    reviews = Review.objects.filter(photographer=studio, reviewed_at__gte=start_at, reviewed_at__lt=end_at)
    review_count = reviews.count()
    rating = None
    if review_count:
        rating = round(sum(reviews.values_list("rating", flat=True)) / review_count, 1)

    activity = []
    for event in StudioMembershipEvent.objects.filter(membership__studio=studio, occurred_at__gte=start_at, occurred_at__lt=end_at).select_related("membership", "actor")[:8]:
        activity.append({"title": event.action.replace("_", " ").title(), "detail": event.membership.email, "at": event.occurred_at, "icon": "bi-person-gear"})
    for event in GalleryActivity.objects.for_photographer(studio).filter(created_at__gte=start_at, created_at__lt=end_at).select_related("gallery")[:8]:
        activity.append({"title": event.get_event_type_display(), "detail": event.gallery.name, "at": event.created_at, "icon": "bi-images"})
    activity.sort(key=lambda x: x["at"], reverse=True)

    return {"range_key": range_key, "start": start, "end": end, "compare": params.get("compare", "previous"),
            "selected_role": role, "selected_location": location, "selected_member": member_value,
            "roles": StudioMembership.Role.choices, "locations": locations, "members": memberships, "rows": rows,
            "summary": {"members": len(rows), "bookings": total_bookings, "completed": total_completed,
                        "completion_rate": round(total_completed * 100 / total_bookings) if total_bookings else None,
                        "hours": round(sum(r["hours"] for r in rows), 1), "revenue": sum((r["revenue"] for r in rows), Decimal("0")),
                        "galleries": sum(r["galleries"] for r in rows),
                        "turnaround": round(sum(average_turnaround) / len(average_turnaround), 1) if average_turnaround else None,
                        "rating": rating, "reviews": review_count},
            "timeline": [{"label": day.strftime("%b %Y"), **values} for day, values in sorted(timeline.items())],
            "activity": activity[:10], "last_updated": timezone.now(),
            "has_assignments": bool(total_bookings or sum(r["galleries"] for r in rows))}
