"""Read-only, studio-scoped data assembly for the CRM command center."""
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientActivity, ClientSession, ClientTask, Lead
from apps.dashboard.access import scope_assigned


def build_crm_overview(access, *, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    month_start = today.replace(day=1)
    leads = Lead.objects.for_photographer(access.studio).filter(archived_at__isnull=True)
    clients = scope_assigned(Client.objects.all(), access)
    sessions = scope_assigned(ClientSession.objects.all(), access).filter(
        starts_at__gte=now
    ).exclude(status=ClientSession.Status.CANCELLED).select_related("client")

    open_leads = leads.exclude(status__in=(Lead.Status.BOOKED, Lead.Status.LOST))
    followups_due = open_leads.filter(next_follow_up__lte=today).count()
    total, booked = leads.count(), leads.filter(status=Lead.Status.BOOKED).count()
    metrics = [
        {"label": "Active Leads", "value": open_leads.count(), "icon": "bi-funnel", "context": "Excludes booked and lost leads"},
        {"label": "New Leads This Month", "value": leads.filter(created_at__date__gte=month_start).count(), "icon": "bi-person-plus", "context": "Created since the start of this month"},
        {"label": "Follow-ups Due", "value": followups_due, "icon": "bi-clock-history", "context": "Due today or overdue"},
        {"label": "Lead-to-Booking Conversion", "value": f"{booked / total * 100:.1f}%" if total else "—", "icon": "bi-graph-up-arrow", "context": "Booked leads divided by all recorded leads" if total else "Unavailable until a lead is recorded"},
        {"label": "Active Clients", "value": clients.filter(status=Client.Status.ACTIVE).count(), "icon": "bi-people", "context": "Active client records you can access"},
    ]
    counts = {row["status"]: row["count"] for row in leads.values("status").annotate(count=Count("pk"))}
    pipeline = [{"key": key, "label": "New Inquiry" if key == Lead.Status.NEW else label,
                 "count": counts.get(key, 0), "url": f'{reverse("photographer_workspace:leads")}?status={key}'}
                for key, label in Lead.Status.choices]

    priority = Case(
        When(next_follow_up__lt=today, then=Value(0)),
        When(next_follow_up=today, then=Value(1)),
        When(status=Lead.Status.NEW, then=Value(2)),
        default=Value(3), output_field=IntegerField(),
    )
    recent_leads = list(leads.select_related("converted_client").annotate(attention_order=priority)
                        .order_by("attention_order", F("next_follow_up").asc(nulls_last=True), "-created_at")[:8])

    tasks = ClientTask.objects.for_photographer(access.studio).exclude(
        status__in=(ClientTask.Status.COMPLETED, ClientTask.Status.CANCELLED)
    )
    if access.membership is not None and access.role == "photographer":
        tasks = tasks.filter(Q(lead__isnull=False) | Q(client__assigned_members=access.membership))
    task_order = Case(When(due_date__lt=today, then=Value(0)), When(due_date=today, then=Value(1)),
                      When(due_date__isnull=False, then=Value(2)), default=Value(3), output_field=IntegerField())
    tasks = tasks.select_related("client", "lead").annotate(due_order=task_order).order_by(
        "due_order", "due_date", "-created_at"
    ).distinct()[:6]

    activities = ClientActivity.objects.for_photographer(access.studio)
    if access.membership is not None and access.role == "photographer":
        activities = activities.filter(Q(lead__isnull=False) | Q(client__assigned_members=access.membership))
    activities = activities.select_related("client", "lead").distinct().order_by("-occurred_at")[:6]
    return {
        "crm_metrics": metrics, "pipeline": pipeline, "recent_leads": recent_leads,
        "upcoming_sessions": sessions.order_by("starts_at")[:5], "tasks": tasks,
        "recent_activity": activities, "today": today, "has_crm_data": bool(total or clients.exists()),
        "can_manage_crm": access.allows("clients"),
    }
