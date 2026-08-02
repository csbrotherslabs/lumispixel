"""Reusable, source-backed team performance calculations.

The functions in this module deliberately return presentation-neutral values so
HTML, exports, and future API endpoints share one definition of every metric.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from apps.clients.models import ClientSession, InvoicePayment
from apps.dashboard.models import Review, StudioMembership, StudioMembershipEvent
from apps.galleries.models import Gallery, GalleryActivity


RANGES = {"30d": 30, "90d": 90, "year": 365}
MIN_SATISFACTION_RESPONSES = 3
TREND_METRICS = tuple(METRIC for METRIC in (
    "shoots", "galleries", "completion_rate", "editing_turnaround",
    "gallery_delivery", "revenue", "satisfaction", "capacity",
))


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
    return key, start, end


def _aware_bounds(start, end):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(start, time.min), tz),
            timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz))


def _comparison_dates(start, end, comparison):
    days = (end - start).days + 1
    if comparison == "year":
        try:
            return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
        except ValueError:  # a range beginning or ending on leap day
            return start - timedelta(days=365), end - timedelta(days=365)
    return start - timedelta(days=days), start - timedelta(days=1)


def _availability_minutes(memberships, start, end):
    """Configured working time only; availability labels are not hour estimates."""
    total = 0
    for member in memberships:
        if not member.working_days or not member.working_hours_start or not member.working_hours_end:
            return None
        daily = (datetime.combine(start, member.working_hours_end) -
                 datetime.combine(start, member.working_hours_start)).total_seconds() / 60
        if daily <= 0:
            return None
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            # Working-day settings historically contain either ISO numbers or names.
            configured = {str(value).lower() for value in member.working_days}
            if str(day.isoweekday()) in configured or day.strftime("%A").lower() in configured:
                total += daily
    return total or None


def calculate_period_metrics(studio, memberships, start, end, location=""):
    """Calculate one period from persisted bookings, payments, galleries and reviews."""
    start_at, end_at = _aware_bounds(start, end)
    member_ids = {member.pk for member in memberships}
    sessions = list(ClientSession.objects.for_photographer(studio).filter(
        starts_at__gte=start_at, starts_at__lt=end_at
    ).exclude(status=ClientSession.Status.CANCELLED).prefetch_related("assigned_members"))
    if location:
        sessions = [session for session in sessions if session.location == location]

    assigned_sessions = []
    completed = []
    scheduled_minutes = 0
    session_members = {}
    for session in sessions:
        assigned = [member for member in session.assigned_members.all() if member.pk in member_ids]
        if not assigned:
            continue
        assigned_sessions.append(session)
        session_members[session.pk] = assigned
        scheduled_minutes += session.duration_minutes * len(assigned)
        if session.status == ClientSession.Status.COMPLETED:
            completed.append(session)

    galleries = list(Gallery.objects.for_photographer(studio).filter(
        published_at__gte=start_at, published_at__lt=end_at,
        status__in=(Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED),
    ).prefetch_related("assigned_members"))
    galleries = [gallery for gallery in galleries
                 if any(member.pk in member_ids for member in gallery.assigned_members.all())]

    # Publishing is the only persisted delivery timestamp. Editing completion is
    # not stored, so editing turnaround must remain unavailable rather than inferred.
    delivery_durations = []
    for gallery in galleries:
        if gallery.event_date and gallery.published_at:
            event_at = timezone.make_aware(datetime.combine(gallery.event_date, time.min),
                                           timezone.get_current_timezone())
            delivery_durations.append(max(0, (gallery.published_at - event_at).total_seconds() / 86400))

    completed_ids = [session.pk for session in completed]
    payments = list(InvoicePayment.objects.for_photographer(studio).filter(
        status=InvoicePayment.Status.COMPLETED, paid_at__gte=start_at, paid_at__lt=end_at,
        invoice__booking_id__in=completed_ids,
    ).select_related("invoice__booking").prefetch_related("invoice__booking__assigned_members"))
    revenue = Decimal("0")
    for payment in payments:
        all_assigned = [member for member in payment.invoice.booking.assigned_members.all()
                        if member.status == StudioMembership.Status.ACTIVE]
        selected_count = sum(member.pk in member_ids for member in all_assigned)
        if all_assigned and selected_count:
            revenue += payment.amount * selected_count / len(all_assigned)

    reviews = Review.objects.for_photographer(studio).filter(
        reviewed_at__gte=start_at, reviewed_at__lt=end_at)
    review_records = list(reviews.values("rating", "reviewed_at"))
    ratings = [review["rating"] for review in review_records]
    availability = _availability_minutes(memberships, start, end)
    return {
        "shoots": len(completed),
        "eligible_assignments": len(assigned_sessions),
        "completion_rate": (len(completed) * 100 / len(assigned_sessions)) if assigned_sessions else None,
        "galleries": len(galleries),
        "editing_turnaround": None,
        "gallery_delivery": (sum(delivery_durations) / len(delivery_durations)) if delivery_durations else None,
        "revenue": revenue,
        "revenue_records": len(payments),
        "satisfaction": (sum(ratings) / len(ratings)) if len(ratings) >= MIN_SATISFACTION_RESPONSES else None,
        "review_count": len(ratings),
        "capacity": (scheduled_minutes * 100 / availability) if availability else None,
        "scheduled_minutes": scheduled_minutes,
        "availability_minutes": availability,
        "sessions": assigned_sessions,
        "delivered_galleries": galleries,
        "payments": payments,
        "reviews": review_records,
    }


def _grouping(start, end, requested):
    days = (end - start).days + 1
    allowed = ("daily", "weekly") if days <= 45 else (("weekly", "monthly") if days <= 180 else ("monthly", "quarterly"))
    return requested if requested in allowed else allowed[0], allowed


def _bucket(day, grouping):
    if grouping == "daily":
        return day
    if grouping == "weekly":
        return day - timedelta(days=day.weekday())
    if grouping == "quarterly":
        return day.replace(month=((day.month - 1) // 3) * 3 + 1, day=1)
    return day.replace(day=1)


def _trend_points(data, memberships, start, end, grouping, metric):
    """Build chart buckets from prefetched records without issuing bucket-level queries."""
    buckets = {}
    cursor = _bucket(start, grouping)
    while cursor <= end:
        buckets[cursor] = {"shoots": 0, "eligible": 0, "galleries": 0, "delivery": [],
                           "revenue": Decimal("0"), "scheduled": 0, "ratings": []}
        cursor = (cursor + timedelta(days=1) if grouping == "daily" else
                  cursor + timedelta(days=7) if grouping == "weekly" else
                  (cursor.replace(month=cursor.month + 3) if cursor.month <= 9 else cursor.replace(year=cursor.year + 1, month=1)) if grouping == "quarterly" else
                  (cursor.replace(month=cursor.month + 1) if cursor.month < 12 else cursor.replace(year=cursor.year + 1, month=1)))
    for session in data["sessions"]:
        point = buckets.get(_bucket(session.starts_at.date(), grouping))
        if point:
            point["eligible"] += 1
            point["shoots"] += session.status == ClientSession.Status.COMPLETED
            point["scheduled"] += session.duration_minutes * len(session.assigned_members.all())
    for gallery in data["delivered_galleries"]:
        point = buckets.get(_bucket(gallery.published_at.date(), grouping))
        if point:
            point["galleries"] += 1
            if gallery.event_date:
                point["delivery"].append(max(0, (gallery.published_at.date() - gallery.event_date).days))
    for payment in data["payments"]:
        point = buckets.get(_bucket(payment.paid_at.date(), grouping))
        if point:
            active = [member for member in payment.invoice.booking.assigned_members.all()
                      if member.status == StudioMembership.Status.ACTIVE]
            selected = sum(member.pk in {item.pk for item in memberships} for member in active)
            if active and selected:
                point["revenue"] += payment.amount * selected / len(active)
    for review in data["reviews"]:
        point = buckets.get(_bucket(review["reviewed_at"].date(), grouping))
        if point:
            point["ratings"].append(review["rating"])
    points = []
    for day, values in buckets.items():
        bucket_end = min(end, (day + timedelta(days=6) if grouping == "weekly" else day))
        if grouping in {"monthly", "quarterly"}:
            next_day = (day.replace(month=day.month + (3 if grouping == "quarterly" else 1))
                        if day.month <= (9 if grouping == "quarterly" else 11)
                        else day.replace(year=day.year + 1, month=1))
            bucket_end = min(end, next_day - timedelta(days=1))
        availability = _availability_minutes(memberships, max(start, day), bucket_end)
        value = {"shoots": values["shoots"], "galleries": values["galleries"],
                 "completion_rate": values["shoots"] * 100 / values["eligible"] if values["eligible"] else None,
                 "editing_turnaround": None,
                 "gallery_delivery": sum(values["delivery"]) / len(values["delivery"]) if values["delivery"] else None,
                 "revenue": values["revenue"],
                 "satisfaction": sum(values["ratings"]) / len(values["ratings"]) if len(values["ratings"]) >= MIN_SATISFACTION_RESPONSES else None,
                 "capacity": values["scheduled"] * 100 / availability if availability else None}[metric]
        label = day.strftime("%b %-d" if grouping in {"daily", "weekly"} else ("Q%q %Y" if grouping == "quarterly" else "%b %Y"))
        if grouping == "quarterly":
            label = f"Q{(day.month - 1) // 3 + 1} {day.year}"
        points.append({"label": label, "raw": value, "value": _display(metric, value)})
    return points


METRIC_DEFINITIONS = {
    "shoots": ("Shoots completed", "Completed assigned shoots", "Bookings whose saved status is Completed and shoot date falls in the period.", "Cancelled, tentative, confirmed, and unassigned bookings."),
    "completion_rate": ("Assignment completion rate", "Completed eligible assignments ÷ eligible assigned work", "Non-cancelled bookings explicitly assigned to a selected active member.", "Cancelled and unassigned bookings."),
    "galleries": ("Galleries delivered", "Published or delivered assigned galleries", "Assigned galleries with an actual publication timestamp in the period.", "Draft, processing, archived, expired, and unassigned galleries."),
    "editing_turnaround": ("Average editing turnaround", "Actual edit completion − edit start", "Only workflows with both actual editing timestamps qualify.", "Estimated dates and gallery publication proxies. Editing timestamps are not currently recorded."),
    "gallery_delivery": ("Average gallery delivery time", "Publication timestamp − event date", "Assigned, published/delivered galleries with both persisted timestamps.", "Records missing an event date or publication timestamp."),
    "revenue": ("Revenue contribution", "Collected payments attributable to completed assigned bookings", "Completed payments linked to completed, assigned bookings in the period.", "Pending, failed, refunded, unlinked, or incomplete-booking payments. Contribution is shared work, not independently generated revenue."),
    "satisfaction": ("Average client satisfaction", "Mean valid studio review rating", f"Studio reviews in the period; shown only with at least {MIN_SATISFACTION_RESPONSES} responses.", "Periods below the reliability threshold. Reviews are never attributed to one person."),
    "capacity": ("Active team capacity utilization", "Assigned booking minutes ÷ configured working minutes", "Scheduled non-cancelled assigned workload and each selected member’s configured working days/hours.", "Members or periods without complete availability configuration."),
}


def _display(key, value):
    if value is None:
        return "Insufficient data" if key == "capacity" else "Not available"
    if key in {"completion_rate", "capacity"}:
        return f"{value:.1f}%"
    if key in {"editing_turnaround", "gallery_delivery"}:
        return f"{value:.1f} days"
    if key == "revenue":
        return f"${value:,.2f}"
    if key == "satisfaction":
        return f"{value:.1f}/5"
    return f"{value:,}"


def build_summary_metrics(current, comparison, comparison_label, member_count):
    metrics = []
    for key, definition in METRIC_DEFINITIONS.items():
        value, previous = current[key], comparison.get(key) if comparison else None
        change = None if value is None or previous is None else value - previous
        percent = None if change is None or previous in (0, Decimal("0")) else change / abs(previous) * 100
        direction = "unavailable" if change is None else ("up" if change > 0 else "down" if change < 0 else "steady")
        metrics.append({"key": key, "label": definition[0], "short_definition": definition[1],
                        "included": definition[2], "excluded": definition[3], "raw": value,
                        "value": _display(key, value), "comparison_label": comparison_label,
                        "previous": _display(key, previous) if previous is not None else "Comparison unavailable",
                        "change": (f"{percent:+.1f}%" if percent is not None else
                                   (f"{change:+.1f}" if change is not None else "No comparison")),
                        "direction": direction, "team_average": _display(key, value / member_count)
                        if member_count and value is not None and key in {"shoots", "galleries", "revenue"} else None})
    return metrics


def _member_rows(memberships, current, previous):
    """Fan prefetched report records into member rows in memory (constant query count)."""
    rows = {member.pk: {"member": member, "bookings": 0, "completed": 0, "minutes": 0,
                        "galleries": 0, "delivery": [], "revenue": Decimal("0")} for member in memberships}
    for session in current["sessions"]:
        for member in session.assigned_members.all():
            if member.pk in rows:
                rows[member.pk]["bookings"] += 1
                rows[member.pk]["completed"] += session.status == ClientSession.Status.COMPLETED
                rows[member.pk]["minutes"] += session.duration_minutes
    for gallery in current["delivered_galleries"]:
        for member in gallery.assigned_members.all():
            if member.pk in rows:
                rows[member.pk]["galleries"] += 1
                if gallery.event_date:
                    rows[member.pk]["delivery"].append(max(0, (gallery.published_at.date() - gallery.event_date).days))
    for payment in current["payments"]:
        assigned = [member for member in payment.invoice.booking.assigned_members.all() if member.pk in rows]
        for member in assigned:
            rows[member.pk]["revenue"] += payment.amount / len(assigned)
    previous_shoots = defaultdict(int)
    if previous:
        for session in previous["sessions"]:
            if session.status == ClientSession.Status.COMPLETED:
                for member in session.assigned_members.all():
                    previous_shoots[member.pk] += 1
    output = []
    for item in rows.values():
        member = item["member"]
        name = member.user.full_name if member.user_id else member.email
        prior = previous_shoots[member.pk]
        trend = item["completed"] - prior if previous else None
        availability = _availability_minutes([member], current["sessions"][0].starts_at.date(), current["sessions"][-1].starts_at.date()) if current["sessions"] else None
        output.append({"id": member.pk, "name": name, "initials": "".join(x[0] for x in name.split()[:2]).upper(),
                       "role": member.get_role_display(), "role_key": member.role,
                       "location": member.primary_location or "Not set", "status": member.get_status_display(),
                       "bookings": item["bookings"], "completed": item["completed"],
                       "completion_rate": round(item["completed"] * 100 / item["bookings"]) if item["bookings"] else None,
                       "hours": round(item["minutes"] / 60, 1), "galleries": item["galleries"],
                       "turnaround": round(sum(item["delivery"]) / len(item["delivery"]), 1) if item["delivery"] else None,
                       "revenue": item["revenue"], "satisfaction": None,
                       "capacity": round(item["minutes"] * 100 / availability) if availability else None,
                       "trend": trend})
    return output


def team_performance_report(studio, params):
    range_key, start, end = _bounds(params)
    role = params.get("role", "") if params.get("role", "") in dict(StudioMembership.Role.choices) else ""
    location = (params.get("location", "") or "").strip()[:150]
    member_value = params.get("member", "")
    status = params.get("status", "active")
    if status not in dict(StudioMembership.Status.choices):
        status = "active"
    specialty = params.get("specialty", "")
    query = (StudioMembership.objects.filter(studio=studio, status=status)
             .select_related("user").prefetch_related("specialties").order_by("role", "user__first_name"))
    all_memberships = list(query)
    memberships = list(all_memberships)
    if role:
        memberships = [member for member in memberships if member.role == role]
    if location:
        memberships = [member for member in memberships if location == member.primary_location or location in (member.additional_locations or [])]
    if member_value.isdigit():
        memberships = [member for member in memberships if member.pk == int(member_value)]
    if specialty:
        memberships = [member for member in memberships if any(str(item.pk) == specialty for item in member.specialties.all())]
    comparison_key = params.get("compare", "previous")
    if comparison_key not in {"previous", "year", "team", "none"}:
        comparison_key = "previous"
    current = calculate_period_metrics(studio, memberships, start, end, location)
    comparison = None
    comparison_label = "No comparison"
    if comparison_key in {"previous", "year"}:
        compare_start, compare_end = _comparison_dates(start, end, comparison_key)
        comparison = calculate_period_metrics(studio, memberships, compare_start, compare_end, location)
        comparison_label = "Previous period" if comparison_key == "previous" else "Same period last year"
    elif comparison_key == "team":
        comparison = calculate_period_metrics(studio, all_memberships, start, end, location)
        for key in ("shoots", "galleries", "revenue"):
            comparison[key] = comparison[key] / len(all_memberships) if all_memberships else None
        comparison_label = "Team average"
    summary_metrics = build_summary_metrics(current, comparison, comparison_label, len(memberships))

    rows = _member_rows(memberships, current, comparison if comparison_key in {"previous", "year"} else None)
    search = (params.get("q", "") or "").strip().lower()[:100]
    if search:
        rows = [row for row in rows if search in f'{row["name"]} {row["role"]} {row["location"]}'.lower()]
    sort = params.get("sort", "member")
    sort_fields = {"member": "name", "role": "role", "location": "location", "shoots": "completed",
                   "galleries": "galleries", "completion": "completion_rate", "turnaround": "turnaround",
                   "revenue": "revenue", "capacity": "capacity", "trend": "trend"}
    descending = params.get("direction", "asc") == "desc"
    rows.sort(key=lambda row: (row.get(sort_fields.get(sort, "name")) is None,
                               row.get(sort_fields.get(sort, "name")) or 0), reverse=descending)
    paginator = Paginator(rows, 10)
    page = paginator.get_page(params.get("page", 1))
    trend_metric = params.get("metric", "shoots") if params.get("metric", "shoots") in TREND_METRICS else "shoots"
    grouping, groupings = _grouping(start, end, params.get("grouping", ""))
    trend = _trend_points(current, memberships, start, end, grouping, trend_metric)
    previous_trend = _trend_points(comparison, memberships, compare_start, compare_end, grouping, trend_metric) if comparison_key in {"previous", "year"} else []
    for index, point in enumerate(trend):
        previous_point = previous_trend[index] if index < len(previous_trend) else None
        point["previous_raw"] = previous_point["raw"] if previous_point else None
        point["previous"] = previous_point["value"] if previous_point else "Unavailable"
        point["average_raw"] = (point["raw"] / len(memberships)
                                if point["raw"] is not None and memberships and trend_metric in {"shoots", "galleries", "revenue"}
                                else None)
        point["average"] = _display(trend_metric, point["average_raw"]) if point["average_raw"] is not None else None
    timeline = defaultdict(lambda: {"bookings": 0, "completed": 0, "galleries": 0})
    for session in current["sessions"]:
        bucket = session.starts_at.date().replace(day=1)
        timeline[bucket]["bookings"] += 1
        timeline[bucket]["completed"] += session.status == ClientSession.Status.COMPLETED
    for gallery in current["delivered_galleries"]:
        timeline[gallery.published_at.date().replace(day=1)]["galleries"] += 1
    activity = [{"title": event.action.replace("_", " ").title(), "detail": event.membership.email,
                 "at": event.occurred_at, "icon": "bi-person-gear"}
                for event in StudioMembershipEvent.objects.filter(membership__studio=studio).select_related("membership")[:8]]
    locations = list(ClientSession.objects.for_photographer(studio).exclude(location="").order_by("location").values_list("location", flat=True).distinct())
    return {"range_key": range_key, "start": start, "end": end, "compare": comparison_key,
            "selected_role": role, "selected_location": location, "selected_member": member_value,
            "selected_status": status, "selected_specialty": specialty, "statuses": StudioMembership.Status.choices,
            "specialties": sorted({(item.pk, item.name) for member in all_memberships for item in member.specialties.all()}, key=lambda item: item[1]),
            "roles": StudioMembership.Role.choices, "locations": locations, "members": memberships,
            "rows": page.object_list, "page_obj": page, "sort": sort, "direction": "desc" if descending else "asc",
            "trend_metric": trend_metric, "trend_metrics": [(key, METRIC_DEFINITIONS[key][0]) for key in TREND_METRICS],
            "grouping": grouping, "groupings": groupings, "trend": trend, "previous_trend": previous_trend,
            "solo_mode": len(all_memberships) == 1, "summary_metrics": summary_metrics, "summary": {
                "members": len(memberships), "bookings": current["eligible_assignments"], "completed": current["shoots"],
                "completion_rate": round(current["completion_rate"]) if current["completion_rate"] is not None else None,
                "hours": round(current["scheduled_minutes"] / 60, 1), "revenue": current["revenue"],
                "galleries": current["galleries"], "turnaround": current["gallery_delivery"],
                "rating": current["satisfaction"], "reviews": current["review_count"]},
            "timeline": [{"label": day.strftime("%b %Y"), **values} for day, values in sorted(timeline.items())],
            "activity": activity[:10], "last_updated": timezone.now(),
            "has_assignments": bool(current["eligible_assignments"] or current["galleries"]),
            "summary_state": params.get("summary_state", "ready") if params.get("summary_state") in {"loading", "empty", "error"} else "ready"}
