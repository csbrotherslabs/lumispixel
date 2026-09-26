"""Canonical booking availability and conflict rules for the workspace."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Q
from django.utils import timezone

from apps.clients.models import ClientSession, MiniSession
from apps.dashboard.models import ScheduleConstraint, StudioMembership


def studio_timezone(studio):
    """Return the configured studio zone, falling back to Django's zone."""
    try:
        return ZoneInfo(studio.timezone) if studio.timezone else timezone.get_default_timezone()
    except ZoneInfoNotFoundError:
        return timezone.get_default_timezone()


def resource_query(member_ids):
    """Bookings with no assignment use the owner resource; members are independent."""
    member_ids = set(member_ids)
    return Q(assigned_members__in=member_ids) if member_ids else Q(assigned_members__isnull=True)


def _distinct_pks(queryset):
    """Materialize de-duplicated PKs before applying PostgreSQL row locks.

    PostgreSQL rejects SELECT DISTINCT ... FOR UPDATE. Relationship filters in
    scheduling can multiply rows, so discover the unique target rows first and
    then lock the base-table rows in a second query.
    """
    return list(queryset.values_list("pk", flat=True).distinct())


def conflicting_sessions(*, studio, starts_at, duration_minutes, member_ids=(), exclude_pk=None,
                         lock=False):
    """Return active same-resource bookings whose actual half-open intervals overlap."""
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    queryset = ClientSession.objects.for_photographer(studio).exclude(
        status=ClientSession.Status.CANCELLED
    ).filter(resource_query(member_ids), starts_at__lt=ends_at)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    if lock:
        queryset = ClientSession.objects.filter(pk__in=_distinct_pks(queryset)).select_for_update()
    else:
        queryset = queryset.distinct()
    return [row for row in queryset if row.starts_at + timedelta(minutes=row.duration_minutes) > starts_at]


def conflicting_constraints(*, studio, starts_at, duration_minutes, member_ids=(), lock=False):
    """Return blocking constraints on the same resource using half-open intervals."""
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    member_ids = set(member_ids)
    resource = Q(entire_team=True)
    if member_ids:
        resource |= Q(assigned_members__in=member_ids)
    else:
        resource |= Q(entire_team=False, assigned_members__isnull=True)
    queryset = ScheduleConstraint.objects.filter(
        studio=studio, blocks_booking=True, starts_at__lt=ends_at, ends_at__gt=starts_at,
    ).filter(resource)
    if lock:
        return ScheduleConstraint.objects.filter(pk__in=_distinct_pks(queryset)).select_for_update()
    return queryset.distinct()


def availability_for(*, studio, starts_at, duration_minutes, member_ids=(), exclude_pk=None,
                     lock=False, exclude_mini_pk=None):
    """Evaluate persisted working hours and active booking conflicts."""
    member_ids = set(member_ids)
    members = list(StudioMembership.objects.filter(
        studio=studio, pk__in=member_ids, status=StudioMembership.Status.ACTIVE
    ))
    if len(members) != len(member_ids):
        return {"available": False, "working_hours_ok": False, "conflicts": [], "constraint_conflicts": [],
                "error": "Select active photographers from this workspace."}

    zone = studio_timezone(studio)
    local_start = starts_at.astimezone(zone)
    local_end = (starts_at + timedelta(minutes=duration_minutes)).astimezone(zone)
    working_hours_ok = True
    for member in members:
        if member.working_days and local_start.strftime("%a") not in member.working_days:
            working_hours_ok = False
        if member.working_hours_start and local_start.time() < member.working_hours_start:
            working_hours_ok = False
        if member.working_hours_end and local_end.time() > member.working_hours_end:
            working_hours_ok = False
    conflicts = conflicting_sessions(
        studio=studio, starts_at=starts_at, duration_minutes=duration_minutes,
        member_ids=member_ids, exclude_pk=exclude_pk, lock=lock,
    )
    constraints = list(conflicting_constraints(
        studio=studio, starts_at=starts_at, duration_minutes=duration_minutes,
        member_ids=member_ids, lock=lock,
    ))
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    minis = MiniSession.objects.for_photographer(studio).exclude(status=MiniSession.Status.CANCELLED)
    if member_ids:
        minis = minis.filter(assigned_members__in=member_ids)
    else:
        minis = minis.filter(assigned_members__isnull=True)
    if exclude_mini_pk:
        minis = minis.exclude(pk=exclude_mini_pk)
    minis = minis.filter(starts_at__lt=ends_at)
    if lock:
        minis = MiniSession.objects.filter(pk__in=_distinct_pks(minis)).select_for_update()
    else:
        minis = minis.distinct()
    mini_conflicts = [row for row in minis if row.starts_at + timedelta(minutes=row.duration_minutes) > starts_at]
    return {"available": working_hours_ok and not conflicts and not constraints and not mini_conflicts,
            "working_hours_ok": working_hours_ok, "conflicts": conflicts,
            "constraint_conflicts": constraints, "mini_conflicts": mini_conflicts}


def parse_local_datetime(studio, date_value, time_value):
    """Interpret browser wall time in the persisted studio timezone."""
    value = datetime.fromisoformat(f"{date_value}T{time_value}")
    return timezone.make_aware(value, studio_timezone(studio))
