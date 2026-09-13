from datetime import datetime

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .decorators import internal_employee_required
from .models import Department, EmployeeProfile, InternalAuditEvent, SupportTicket, SupportTicketComment


def _actor(request):
    return getattr(request, "employee_profile", None)


def _valid_choice(value, choices, fallback):
    allowed = {item[0] for item in choices}
    return value if value in allowed else fallback


@internal_employee_required
def ticket_list(request):
    tickets = SupportTicket.objects.select_related("requester", "assignee__user", "queue")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    priority = request.GET.get("priority", "all")
    mine = request.GET.get("mine") == "1"

    if q:
        tickets = tickets.filter(Q(reference__icontains=q) | Q(subject__icontains=q) | Q(requester__email__icontains=q) | Q(requester__first_name__icontains=q) | Q(requester__last_name__icontains=q))
    if status != "all":
        tickets = tickets.filter(status=status)
    if priority != "all":
        tickets = tickets.filter(priority=priority)
    if mine and _actor(request):
        tickets = tickets.filter(assignee=_actor(request))

    context = {
        "employee": _actor(request),
        "is_internal_superuser": request.user.is_superuser,
        "active_nav": "tickets",
        "tickets": tickets[:150],
        "query": q,
        "selected_status": status,
        "selected_priority": priority,
        "mine": mine,
        "status_choices": SupportTicket.Status.choices,
        "priority_choices": SupportTicket.Priority.choices,
        "open_count": SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).count(),
        "progress_count": SupportTicket.objects.filter(status=SupportTicket.Status.IN_PROGRESS).count(),
        "waiting_count": SupportTicket.objects.filter(status=SupportTicket.Status.WAITING_CUSTOMER).count(),
        "urgent_count": SupportTicket.objects.filter(priority=SupportTicket.Priority.URGENT).exclude(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED]).count(),
    }
    return render(request, "internal_ops/tickets/list.html", context)


@internal_employee_required
@require_http_methods(["GET", "POST"])
def ticket_detail(request, reference):
    ticket = get_object_or_404(SupportTicket.objects.select_related("requester", "assignee__user", "queue"), reference=reference)
    actor = _actor(request)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update":
            old = {"status": ticket.status, "priority": ticket.priority, "assignee_id": ticket.assignee_id, "queue_id": ticket.queue_id}
            ticket.status = _valid_choice(request.POST.get("status"), SupportTicket.Status.choices, ticket.status)
            ticket.priority = _valid_choice(request.POST.get("priority"), SupportTicket.Priority.choices, ticket.priority)
            assignee_id = request.POST.get("assignee") or None
            queue_id = request.POST.get("queue") or None
            ticket.assignee = EmployeeProfile.objects.filter(pk=assignee_id, status=EmployeeProfile.Status.ACTIVE).first() if assignee_id else None
            ticket.queue = Department.objects.filter(pk=queue_id, is_active=True).first() if queue_id else None
            due_at = request.POST.get("due_at", "").strip()
            ticket.due_at = datetime.fromisoformat(due_at) if due_at else None
            if ticket.due_at and timezone.is_naive(ticket.due_at):
                ticket.due_at = timezone.make_aware(ticket.due_at)
            if ticket.status == SupportTicket.Status.RESOLVED and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
            elif ticket.status not in {SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED}:
                ticket.resolved_at = None
            ticket.save()
            InternalAuditEvent.objects.create(actor=actor, category=InternalAuditEvent.Category.SUPPORT, action="internal.ticket.update", target_type="support_ticket", target_id=ticket.reference, summary=f"Updated ticket {ticket.reference}", metadata={"before": old, "status": ticket.status, "priority": ticket.priority, "assignee_id": ticket.assignee_id, "queue_id": ticket.queue_id, "superuser": request.user.is_superuser})
            messages.success(request, "Ticket updated.")
        elif action == "note":
            body = request.POST.get("body", "").strip()
            if body:
                SupportTicketComment.objects.create(ticket=ticket, author_employee=actor, author_user=request.user if actor is None else None, body=body, is_internal=True)
                InternalAuditEvent.objects.create(actor=actor, category=InternalAuditEvent.Category.SUPPORT, action="internal.ticket.note", target_type="support_ticket", target_id=ticket.reference, summary=f"Added internal note to {ticket.reference}", metadata={"superuser": request.user.is_superuser})
                messages.success(request, "Internal note added.")
        elif action == "reply":
            body = request.POST.get("body", "").strip()
            if body:
                SupportTicketComment.objects.create(ticket=ticket, author_employee=actor, author_user=request.user if actor is None else None, body=body, is_internal=False)
                if ticket.status not in {SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED}:
                    ticket.status = SupportTicket.Status.WAITING_CUSTOMER
                    ticket.save(update_fields=["status", "updated_at"])
                InternalAuditEvent.objects.create(actor=actor, category=InternalAuditEvent.Category.SUPPORT, action="internal.ticket.reply", target_type="support_ticket", target_id=ticket.reference, summary=f"Replied to customer on {ticket.reference}", metadata={"superuser": request.user.is_superuser})
                messages.success(request, "Reply sent to the customer thread.")
        return redirect("internal_ops:ticket_detail", reference=ticket.reference)

    InternalAuditEvent.objects.create(actor=actor, category=InternalAuditEvent.Category.SUPPORT, action="internal.ticket.view", target_type="support_ticket", target_id=ticket.reference, summary=f"Opened ticket {ticket.reference}", metadata={"superuser": request.user.is_superuser})
    return render(request, "internal_ops/tickets/detail.html", {
        "employee": actor,
        "is_internal_superuser": request.user.is_superuser,
        "active_nav": "tickets",
        "ticket": ticket,
        "employees": EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE).select_related("user", "department"),
        "departments": Department.objects.filter(is_active=True),
        "status_choices": SupportTicket.Status.choices,
        "priority_choices": SupportTicket.Priority.choices,
        "comments": ticket.comments.select_related("author_employee__user", "author_user"),
        "public_comments": ticket.comments.filter(is_internal=False).select_related("author_employee__user", "author_user"),
        "internal_comments": ticket.comments.filter(is_internal=True).select_related("author_employee__user", "author_user"),
    })
