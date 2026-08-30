import calendar
from copy import deepcopy
from datetime import date, timedelta

from django.utils import timezone

from apps.clients.models import ClientSession
from apps.dashboard.models import ScheduleConstraint

from .themes import DEMO_CONTENT


def parse_equipment(raw_value):
    items = []
    for line in str(raw_value or "").splitlines():
        parts = [part.strip() for part in line.split("|", 2)]
        if not parts or not parts[0]:
            continue
        items.append({
            "name": parts[0][:80],
            "description": (parts[1] if len(parts) > 1 else "Professional equipment prepared for dependable coverage.")[:220],
            "icon": (parts[2] if len(parts) > 2 and parts[2].startswith("bi-") else "bi-camera")[:60],
        })
    return items[:12]


def public_availability(profile, month_count=2, today=None):
    """Return privacy-safe date states; never return booking or constraint metadata."""
    today = today or timezone.localdate()
    month_count = max(1, min(int(month_count or 2), 6))
    start = today.replace(day=1)
    final_month_index = start.month - 1 + month_count
    end_year = start.year + final_month_index // 12
    end_month = final_month_index % 12 + 1
    end = date(end_year, end_month, 1)

    booked_dates = set()
    limited_dates = set()
    sessions = ClientSession.objects.filter(
        photographer=profile,
        starts_at__date__gte=start,
        starts_at__date__lt=end,
    ).exclude(status=ClientSession.Status.CANCELLED).values_list("starts_at", "status")
    for starts_at, status in sessions:
        local_day = timezone.localtime(starts_at).date()
        if status in (ClientSession.Status.CONFIRMED, ClientSession.Status.COMPLETED):
            booked_dates.add(local_day)
        else:
            limited_dates.add(local_day)

    constraints = ScheduleConstraint.objects.filter(
        studio=profile,
        blocks_booking=True,
        starts_at__lt=timezone.make_aware(timezone.datetime.combine(end, timezone.datetime.min.time())),
        ends_at__gte=timezone.make_aware(timezone.datetime.combine(start, timezone.datetime.min.time())),
    ).values_list("starts_at", "ends_at")
    for starts_at, ends_at in constraints:
        cursor = max(timezone.localtime(starts_at).date(), start)
        last = min(timezone.localtime(ends_at - timedelta(microseconds=1)).date(), end - timedelta(days=1))
        while cursor <= last:
            booked_dates.add(cursor)
            cursor += timedelta(days=1)

    months = []
    year, month = start.year, start.month
    for _ in range(month_count):
        weeks = []
        for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month):
            days = []
            for day in week:
                status = "outside" if day.month != month or day < today else "booked" if day in booked_dates else "limited" if day in limited_dates else "available"
                days.append({"date": day, "day": day.day, "status": status, "in_month": day.month == month})
            weeks.append(days)
        months.append({"label": date(year, month, 1).strftime("%B %Y"), "weeks": weeks})
        month = month % 12 + 1
        if month == 1:
            year += 1
    return months


def preview_content(profile, website, overrides=None):
    content = dict(website.theme_content or {})
    content.update({key: value for key, value in (overrides or {}).items() if value not in (None, "")})
    demo = deepcopy(DEMO_CONTENT)
    equipment = parse_equipment(content.get("equipment_inventory"))
    if equipment:
        demo["equipment"] = equipment
    demo["availability"] = public_availability(profile, content.get("availability_window_months", 2))
    demo["availability_call_to_action"] = content.get("availability_call_to_action") or "Request this date"
    return demo
