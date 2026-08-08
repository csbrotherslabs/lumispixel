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
MIN_COMPARISON_ASSIGNMENTS = 1
TREND_METRICS = tuple(METRIC for METRIC in (
    "shoots", "galleries", "completion_rate", "editing_turnaround",
    "gallery_delivery", "revenue", "satisfaction", "capacity",
))
PERFORMANCE_TREND_METRICS = ("shoots", "galleries", "gallery_delivery", "capacity", "satisfaction")


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


def calculate_period_metrics(studio, memberships, start, end, location="", include_financials=True):
    """Calculate one period from persisted bookings, payments, galleries and reviews."""
    start_at, end_at = _aware_bounds(start, end)
    member_ids = {member.pk for member in memberships}
    sessions = list(ClientSession.objects.for_photographer(studio).filter(
        starts_at__gte=start_at, starts_at__lt=end_at
    ).prefetch_related("assigned_members"))
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
        if session.status != ClientSession.Status.CANCELLED:
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
    # This branch is intentionally query-free for callers without financial access.
    payments = []
    if include_financials:
        payments = list(InvoicePayment.objects.for_photographer(studio).filter(
            status=InvoicePayment.Status.COMPLETED, paid_at__gte=start_at, paid_at__lt=end_at,
            invoice__booking_id__in=completed_ids,
        ).select_related("invoice__booking").prefetch_related("invoice__booking__assigned_members"))
    revenue = Decimal("0")
    revenue_by_service = defaultdict(lambda: Decimal("0"))
    revenue_by_location = defaultdict(lambda: Decimal("0"))
    for payment in payments:
        all_assigned = [member for member in payment.invoice.booking.assigned_members.all()
                        if member.status == StudioMembership.Status.ACTIVE]
        selected_count = sum(member.pk in member_ids for member in all_assigned)
        if all_assigned and selected_count:
            share = payment.amount * selected_count / len(all_assigned)
            revenue += share
            revenue_by_service[payment.invoice.booking.session_type or "Not specified"] += share
            revenue_by_location[payment.invoice.booking.location or "Not specified"] += share

    reviews = Review.objects.for_photographer(studio).filter(
        reviewed_at__gte=start_at, reviewed_at__lt=end_at)
    review_records = list(reviews.values("rating", "reviewed_at"))
    ratings = [review["rating"] for review in review_records]
    availability = _availability_minutes(memberships, start, end)
    eligible = [session for session in assigned_sessions if session.status != ClientSession.Status.CANCELLED]
    cancelled = [session for session in assigned_sessions if session.status == ClientSession.Status.CANCELLED]
    overdue = [session for session in eligible if session.starts_at < timezone.now()
               and session.status != ClientSession.Status.COMPLETED]
    completed_clients = [session.client_id for session in completed]
    repeat_assignments = sum(completed_clients.count(client_id) > 1 for client_id in completed_clients)
    status_distribution = [{"key": value, "label": label,
                            "value": sum(session.status == value for session in assigned_sessions)}
                           for value, label in ClientSession.Status.choices]
    return {
        "shoots": len(completed),
        "eligible_assignments": len(eligible),
        "completion_rate": (len(completed) * 100 / len(eligible)) if eligible else None,
        "galleries": len(galleries),
        "editing_turnaround": None,
        "gallery_delivery": (sum(delivery_durations) / len(delivery_durations)) if delivery_durations else None,
        "revenue": revenue if include_financials else None,
        "revenue_records": len(payments),
        "completed_booking_value": (sum((session.booking_value *
                                           len(session_members[session.pk]) /
                                           len([member for member in session.assigned_members.all()
                                                if member.status == StudioMembership.Status.ACTIVE])
                                           for session in completed
                                           if any(member.status == StudioMembership.Status.ACTIVE
                                                  for member in session.assigned_members.all())), Decimal("0"))
                                    if include_financials else None),
        "revenue_by_service": sorted(revenue_by_service.items(), key=lambda item: item[1], reverse=True),
        "revenue_by_location": sorted(revenue_by_location.items(), key=lambda item: item[1], reverse=True),
        "satisfaction": (sum(ratings) / len(ratings)) if len(ratings) >= MIN_SATISFACTION_RESPONSES else None,
        "review_count": len(ratings),
        "capacity": (scheduled_minutes * 100 / availability) if availability else None,
        "scheduled_minutes": scheduled_minutes,
        "availability_minutes": availability,
        "cancelled": len(cancelled), "overdue": len(overdue),
        "repeat_assignments": repeat_assignments, "status_distribution": status_distribution,
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


def _bucket_label(day, grouping):
    """Format chart labels without platform-specific ``strftime`` directives."""
    if grouping == "quarterly":
        return f"Q{(day.month - 1) // 3 + 1} {day.year}"
    if grouping in {"daily", "weekly"}:
        # ``%-d`` works on POSIX but raises ValueError on Windows.
        return f"{day.strftime('%b')} {day.day}"
    return day.strftime("%b %Y")


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
        label = _bucket_label(day, grouping)
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


def build_operational_insights(current, previous, memberships, start, end):
    """Return concise, deterministic observations backed by persisted records."""
    insights = []

    def add(key, text, detail):
        insights.append({"key": key, "text": text, "detail": detail})

    if (current["gallery_delivery"] is not None and previous
            and previous["gallery_delivery"] is not None and previous["gallery_delivery"] > 0):
        change = ((current["gallery_delivery"] - previous["gallery_delivery"])
                  / previous["gallery_delivery"] * 100)
        if abs(change) >= 5:
            direction = "improved" if change < 0 else "increased"
            add("gallery_delivery", f"Gallery turnaround {direction} {abs(change):.0f}% this period.",
                f'{current["gallery_delivery"]:.1f} days now; {previous["gallery_delivery"]:.1f} days previously.')

    completed = [session for session in current["sessions"]
                 if session.status == ClientSession.Status.COMPLETED]
    weekend_peak = sum(session.starts_at.weekday() in (4, 5) for session in completed)
    if len(completed) >= 4 and weekend_peak / len(completed) >= .5:
        share = round(weekend_peak * 100 / len(completed))
        add("demand_days", f"Friday and Saturday account for {share}% of completed shoots.",
            f"{weekend_peak} of {len(completed)} recorded completions.")

    if memberships and all(member.working_days and member.working_hours_start and member.working_hours_end
                           for member in memberships):
        high_capacity_days = 0
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            daily = _trend_points(current, memberships, day, day, "daily", "capacity")
            if daily and daily[0]["raw"] is not None and daily[0]["raw"] > 90:
                high_capacity_days += 1
        if high_capacity_days:
            add("capacity_days", f"Team capacity exceeded 90% on {high_capacity_days} day{'' if high_capacity_days == 1 else 's'}.",
                "Based on assigned booking time and configured working hours.")

    if current["overdue"]:
        verb = "is" if current["overdue"] == 1 else "are"
        add("overdue", f'{current["overdue"]} assignment{'' if current["overdue"] == 1 else 's'} {verb} overdue.',
            "Recorded assignments past their scheduled time and not completed.")
    return insights[:4]


def _member_rows(memberships, current, previous, start, end):
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
        # Always use every active assignee as the denominator.  Filtering the
        # report to one person must not turn their share of a shared booking
        # into the whole payment.
        active = [member for member in payment.invoice.booking.assigned_members.all()
                  if member.status == StudioMembership.Status.ACTIVE]
        if active:
            share = payment.amount / len(active)
            for member in active:
                if member.pk in rows:
                    rows[member.pk]["revenue"] += share
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
        # A trend is a percentage only when the prior period supplies a valid
        # denominator.  A zero/missing baseline is not presented as a change.
        trend = round((item["completed"] - prior) * 100 / prior) if previous and prior else None
        availability = _availability_minutes([member], start, end)
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


def team_performance_report(studio, params, *, can_view_financials=True):
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
    current = calculate_period_metrics(studio, memberships, start, end, location, can_view_financials)
    comparison = None
    comparison_label = "No comparison"
    if comparison_key in {"previous", "year"}:
        compare_start, compare_end = _comparison_dates(start, end, comparison_key)
        comparison = calculate_period_metrics(studio, memberships, compare_start, compare_end, location, can_view_financials)
        comparison_label = "Previous period" if comparison_key == "previous" else "Same period last year"
    elif comparison_key == "team":
        comparison = calculate_period_metrics(studio, all_memberships, start, end, location, can_view_financials)
        for key in ("shoots", "galleries", "revenue"):
            comparison[key] = (comparison[key] / len(all_memberships)
                               if all_memberships and comparison[key] is not None else None)
        comparison_label = "Team average"
    summary_metrics = build_summary_metrics(current, comparison, comparison_label, len(memberships))
    comparison_has_activity = bool(comparison and (
        comparison["eligible_assignments"] or comparison["galleries"] or
        comparison["review_count"] or comparison["revenue_records"]
    ))
    if comparison_key in {"previous", "year"} and not comparison_has_activity:
        summary_metrics = build_summary_metrics(current, None, comparison_label, len(memberships))

    rows = _member_rows(memberships, current,
                        comparison if comparison_key in {"previous", "year"} else None,
                        start, end)
    if not can_view_financials:
        for row in rows:
            row["revenue"] = None
    search = (params.get("q", "") or "").strip().lower()[:100]
    if search:
        rows = [row for row in rows if search in f'{row["name"]} {row["role"]} {row["location"]}'.lower()]
    sort = params.get("sort", "member")
    sort_fields = {"member": "name", "role": "role", "location": "location", "shoots": "completed",
                   "galleries": "galleries", "completion": "completion_rate", "turnaround": "turnaround",
                   "revenue": "revenue", "capacity": "capacity", "trend": "trend"}
    descending = params.get("direction", "asc") == "desc"
    sort_field = sort_fields.get(sort, "name")
    rows.sort(key=lambda row: (row.get(sort_field) is None,
                               row.get(sort_field) if row.get(sort_field) is not None else 0),
              reverse=descending)
    export_rows = list(rows)
    supported_comparison_metrics = ["shoots", "galleries", "turnaround", "capacity", "client", "trend", "completion"]
    if can_view_financials:
        supported_comparison_metrics.append("revenue")
    requested_metrics = params.getlist("columns") if hasattr(params, "getlist") else []
    comparison_metrics = [key for key in supported_comparison_metrics if key in requested_metrics]
    if not comparison_metrics:
        comparison_metrics = ["shoots", "galleries", "turnaround", "capacity", "client", "trend"]
    paginator = Paginator(rows, 10)
    page = paginator.get_page(params.get("page", 1))
    trend_metric = (params.get("metric", "shoots")
                    if params.get("metric", "shoots") in PERFORMANCE_TREND_METRICS else "shoots")
    if trend_metric == "revenue" and not can_view_financials:
        trend_metric = "shoots"
    grouping, groupings = _grouping(start, end, params.get("grouping", ""))
    trend = _trend_points(current, memberships, start, end, grouping, trend_metric)
    previous_trend = (_trend_points(comparison, memberships, compare_start, compare_end, grouping, trend_metric)
                      if comparison_key in {"previous", "year"} and comparison_has_activity else [])
    for index, point in enumerate(trend):
        previous_point = previous_trend[index] if index < len(previous_trend) else None
        point["previous_raw"] = previous_point["raw"] if previous_point else None
        point["previous"] = previous_point["value"] if previous_point and previous_point["raw"] is not None else None
        point["average_raw"] = (point["raw"] / len(memberships)
                                if point["raw"] is not None and memberships and trend_metric in {"shoots", "galleries", "revenue"}
                                else None)
        point["average"] = _display(trend_metric, point["average_raw"]) if point["average_raw"] is not None else None
    # Generated empty buckets are not a useful trend. Presentation only draws
    # the visualization when at least two periods contain supported activity.
    meaningful_trend_points = [point for point in trend if point["raw"] is not None and (
        trend_metric not in {"shoots", "galleries"} or point["raw"] > 0
    )]
    trend_has_enough_data = len(meaningful_trend_points) >= 2
    trend_max = max((point["raw"] or 0 for point in trend), default=0) or 1
    operational_insights = build_operational_insights(
        current, comparison if comparison_has_activity else None, memberships, start, end)
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
            "rows": page.object_list, "export_rows": export_rows, "page_obj": page,
            "sort": sort, "direction": "desc" if descending else "asc",
            "comparison_metrics": comparison_metrics,
            "comparison_metric_options": [
                ("shoots", "Shoots"), ("galleries", "Galleries"),
                ("turnaround", "Turnaround"), ("capacity", "Capacity"),
                ("client", "Client experience"), ("trend", "Trend"),
                ("completion", "Completion rate"),
            ] + ([("revenue", "Associated revenue")] if can_view_financials else []),
            "trend_metric": trend_metric, "trend_metrics": [(key, METRIC_DEFINITIONS[key][0])
                                                              for key in PERFORMANCE_TREND_METRICS],
            "grouping": grouping, "groupings": groupings, "trend": trend,
            "trend_has_enough_data": trend_has_enough_data, "trend_max": trend_max,
            "previous_trend": previous_trend,
            "comparison_has_activity": comparison_has_activity,
            "operational_insights": operational_insights,
            "solo_mode": len(all_memberships) == 1, "summary_metrics": summary_metrics,
            "can_view_financials": can_view_financials, "status_distribution": current["status_distribution"], "summary": {
                "members": len(memberships), "bookings": current["eligible_assignments"], "completed": current["shoots"],
                "completion_rate": round(current["completion_rate"]) if current["completion_rate"] is not None else None,
                "hours": round(current["scheduled_minutes"] / 60, 1), "revenue": current["revenue"],
                "galleries": current["galleries"], "turnaround": current["gallery_delivery"],
                "rating": current["satisfaction"], "reviews": current["review_count"],
                "completed_booking_value": current["completed_booking_value"],
                "cancelled": current["cancelled"], "overdue": current["overdue"],
                "repeat_assignments": current["repeat_assignments"],
                "completed_hours": round(sum(s.duration_minutes for s in current["sessions"] if s.status == ClientSession.Status.COMPLETED) / 60, 1)},
            "timeline": [{"label": day.strftime("%b %Y"), **values} for day, values in sorted(timeline.items())],
            "revenue_by_service": current["revenue_by_service"],
            "revenue_by_location": current["revenue_by_location"],
            "activity": activity[:10], "last_updated": timezone.now(),
            "has_assignments": bool(current["eligible_assignments"] or current["galleries"]),
            **{f"{section}_state": (params.get(f"{section}_state", "ready")
                                    if params.get(f"{section}_state") in {"loading", "error"} else "ready")
               for section in ("summary", "trend", "comparison", "insights")}}


# Insight rules are deliberately ordered by operational urgency.  They use only
# persisted metrics, never a generated score or an employment recommendation.
INSIGHT_RULES = {
    "overdue_rising": "Current overdue assignments exceed the previous period.",
    "capacity_high": "Configured capacity is at least 85%.",
    "turnaround_high": "Member delivery time is over 20% slower than the team figure.",
    "on_time_declined": "Completion rate declined by at least 10 percentage points.",
    "shoots_up": "Completed shoots exceed the previous period.",
    "delivery_improved": "Gallery delivery is at least 10% faster than the previous period.",
    "satisfaction_up": "Supported satisfaction rose by at least 0.2 points.",
    "availability_missing": "Working-day or working-hour data is incomplete.",
}


def build_member_insights(current, previous, team, urls, comparison_label="Previous period"):
    """Return at most six deterministic, source-backed operational observations."""
    cards = []

    def add(key, title, explanation, metric, status, action, link_key):
        cards.append({"rule": key, "title": title, "explanation": explanation,
                      "metric": metric, "comparison": comparison_label, "status": status,
                      "action": action, "url": urls[link_key]})

    if current["overdue"] > previous["overdue"]:
        add("overdue_rising", "Overdue assignments increased",
            "The count of assigned work past its scheduled time is higher than in the comparison period.",
            f'{current["overdue"]} now · {previous["overdue"]} previously', "attention",
            "Review ownership and next steps for overdue work.", "bookings")
    if current["capacity"] is not None and current["capacity"] >= 85:
        add("capacity_high", "Member is approaching full capacity",
            "Scheduled assignment time is using most configured working time for this period.",
            f'{current["capacity"]:.1f}% configured capacity', "attention",
            "Review upcoming coverage before assigning more work.", "schedule")
    if (current["gallery_delivery"] is not None and team["gallery_delivery"] is not None
            and team["gallery_delivery"] > 0 and current["gallery_delivery"] > team["gallery_delivery"] * 1.2):
        add("turnaround_high", "Turnaround is above the team’s normal range",
            "Average gallery delivery time is more than 20% above the team result for the same period.",
            f'{current["gallery_delivery"]:.1f} days · team {team["gallery_delivery"]:.1f} days', "attention",
            "Review the assigned gallery workflow and any blockers.", "galleries")
    if (current["completion_rate"] is not None and previous["completion_rate"] is not None
            and current["completion_rate"] <= previous["completion_rate"] - 10):
        add("on_time_declined", "On-time delivery declined",
            "Assignment completion rate fell by at least 10 percentage points; no promised-delivery timestamp is available.",
            f'{current["completion_rate"]:.1f}% · previously {previous["completion_rate"]:.1f}%', "attention",
            "Review incomplete assignments and confirm realistic handoffs.", "bookings")
    if current["shoots"] > previous["shoots"] and previous["eligible_assignments"] >= MIN_COMPARISON_ASSIGNMENTS:
        add("shoots_up", "Completed shoots increased",
            "More explicitly assigned shoots reached Completed than in the previous period.",
            f'{current["shoots"]} completed · previously {previous["shoots"]}', "positive",
            "Check upcoming assignments and preserve the workflow supporting this change.", "bookings")
    if (current["gallery_delivery"] is not None and previous["gallery_delivery"] is not None
            and previous["gallery_delivery"] > 0 and current["gallery_delivery"] <= previous["gallery_delivery"] * .9):
        improvement = (previous["gallery_delivery"] - current["gallery_delivery"]) / previous["gallery_delivery"] * 100
        add("delivery_improved", "Gallery delivery time improved",
            "Average event-to-publication time is at least 10% shorter than in the previous period.",
            f'{current["gallery_delivery"]:.1f} days · {improvement:.0f}% faster', "positive",
            "Review delivered galleries to identify a repeatable workflow.", "galleries")
    if (current["satisfaction"] is not None and previous["satisfaction"] is not None
            and current["satisfaction"] >= previous["satisfaction"] + .2):
        add("satisfaction_up", "Client satisfaction improved",
            "The supported studio-level review average increased; reviews are not attributed to one member.",
            f'{current["satisfaction"]:.1f}/5 · previously {previous["satisfaction"]:.1f}/5', "positive",
            "Review client feedback for practices the team can repeat.", "activity")
    if current["capacity"] is None:
        add("availability_missing", "Capacity analysis needs availability data",
            "Working days or working hours are incomplete, so capacity cannot be calculated reliably.",
            "Capacity · insufficient data", "insufficient-data",
            "Complete the member’s availability before using capacity planning.", "profile")
    return cards[:6]
