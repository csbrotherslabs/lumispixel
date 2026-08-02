"""Authorization and query helpers for the operational team snapshot.

The current data model represents a studio by its owning PhotographerProfile.
It does not yet contain memberships, assignments, working hours, or leave.  These
helpers keep that limitation explicit and, importantly, make studio scope a
required input to every team query.
"""
from datetime import datetime, time, timedelta

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.clients.models import ClientSession


def authorized_studio(user):
    """Return the only studio the actor may inspect, or deny access."""
    from apps.dashboard.access import access_for
    return access_for(user, require="team").studio


def parse_team_filters(params):
    """Parse bounded, allow-listed overview filters from a query mapping."""
    try:
        selected_date = datetime.strptime(params.get("date", ""), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        selected_date = timezone.localdate()
    return {
        "date": selected_date,
        "location": (params.get("location", "") or "").strip()[:255],
        "q": (params.get("q", "") or "").strip()[:150],
        "role": params.get("role", "") if params.get("role", "") in {"", "owner"} else "",
        "availability": params.get("availability", "") if params.get("availability", "") in {"", "not_configured"} else "",
    }


def studio_sessions(profile, selected_date, selected_location=""):
    """Fetch one studio's day and 14-day window in three bounded queries.

    ``for_photographer`` is deliberately applied before every other constraint;
    callers cannot supply a studio/member identifier in the URL.
    """
    day_start = timezone.make_aware(datetime.combine(selected_date, time.min), timezone.get_current_timezone())
    day_end = day_start + timedelta(days=1)
    base = ClientSession.objects.for_photographer(profile).select_related("client")
    locations = list(base.exclude(location="").order_by("location").values_list("location", flat=True).distinct())
    # Unknown locations produce an honest empty result rather than widening scope.
    location_is_valid = not selected_location or selected_location in locations
    day = base.filter(starts_at__gte=day_start, starts_at__lt=day_end).exclude(status=ClientSession.Status.CANCELLED)
    upcoming = base.filter(starts_at__gte=day_end, starts_at__lt=day_end + timedelta(days=14)).exclude(status=ClientSession.Status.CANCELLED)
    if selected_location:
        day = day.filter(location=selected_location)
        upcoming = upcoming.filter(location=selected_location)
    return locations, list(day.order_by("starts_at")) if location_is_valid else [], list(upcoming.order_by("starts_at")) if location_is_valid else [], day_start, day_end


def sessions_overlap(first, second):
    """Return whether two persisted sessions overlap using their real durations."""
    if first.pk == second.pk:
        return False
    return (first.starts_at < second.starts_at + timedelta(minutes=second.duration_minutes)
            and second.starts_at < first.starts_at + timedelta(minutes=first.duration_minutes))
