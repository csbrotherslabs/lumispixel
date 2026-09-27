import csv
import json

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import internal_employee_required
from .governance import actor_for_request, cancel_approval, can_review_approval, create_approval, decide_approval, mark_approval_executed, parse_proposed_changes, record_audit
from .models import ApprovalRequest, Department, EmployeeProfile, InternalAuditEvent


def _superuser_flag(request):
    return request.user.is_superuser


@internal_employee_required
def audit_trail(request):
    events = InternalAuditEvent.objects.select_related("actor__user")
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "all")
    actor_id = request.GET.get("actor", "")
    action = request.GET.get("action", "").strip()

    if q:
        events = events.filter(Q(summary__icontains=q) | Q(target_id__icontains=q) | Q(reason__icontains=q) | Q(actor__user__email__icontains=q))
    if category != "all":
        events = events.filter(category=category)
    if actor_id:
        events = events.filter(actor_id=actor_id)
    if action:
        events = events.filter(action__icontains=action)

    context = {
        "employee": actor_for_request(request),
        "is_internal_superuser": _superuser_flag(request),
        "active_nav": "audit",
        "events": events[:250],
        "query": q,
        "selected_category": category,
        "selected_actor": actor_id,
        "action_query": action,
        "category_choices": InternalAuditEvent.Category.choices,
        "employees": EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE).select_related("user").order_by("user__first_name", "user__last_name"),
        "event_count": InternalAuditEvent.objects.count(),
        "security_count": InternalAuditEvent.objects.filter(category=InternalAuditEvent.Category.SECURITY).count(),
        "approval_count": InternalAuditEvent.objects.filter(action__startswith="approval.request.").count(),
    }
    return render(request, "internal_ops/governance/audit_list.html", context)


@internal_employee_required
def audit_event_detail(request, event_id):
    event = get_object_or_404(InternalAuditEvent.objects.select_related("actor__user"), pk=event_id)
    return render(request, "internal_ops/governance/audit_detail.html", {
        "employee": actor_for_request(request),
        "is_internal_superuser": _superuser_flag(request),
        "active_nav": "audit",
        "event": event,
        "metadata_pretty": json.dumps(event.metadata, indent=2, sort_keys=True),
    })


@internal_employee_required
def audit_export_csv(request):
    events = InternalAuditEvent.objects.select_related("actor__user")[:5000]
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="lumispixel-audit-export.csv"'
    writer = csv.writer(response)
    writer.writerow(["timestamp", "category", "action", "actor_email", "target_type", "target_id", "summary", "reason"])
    for event in events:
        writer.writerow([
            event.created_at.isoformat(), event.category, event.action,
            event.actor.user.email if event.actor else "system/superuser",
            event.target_type, event.target_id, event.summary, event.reason,
        ])
    record_audit(
        actor=actor_for_request(request),
        category=InternalAuditEvent.Category.SECURITY,
        action="audit.export.csv",
        target_type="internal_audit_event",
        summary="Exported internal audit trail to CSV",
        reason="Operational audit export",
        metadata={"row_limit": 5000, "user_id": str(request.user.pk), "superuser": request.user.is_superuser},
    )
    return response


@internal_employee_required
def approval_list(request):
    approvals = ApprovalRequest.objects.select_related("requester__user", "requester_user", "approver_department", "reviewed_by__user", "reviewed_by_user")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    risk = request.GET.get("risk", "all")
    mine = request.GET.get("mine") == "1"
    if q:
        approvals = approvals.filter(Q(reference__icontains=q) | Q(title__icontains=q) | Q(target_id__icontains=q) | Q(requester_user__email__icontains=q))
    if status != "all":
        approvals = approvals.filter(status=status)
    if risk != "all":
        approvals = approvals.filter(risk_level=risk)
    if mine:
        approvals = approvals.filter(requester_user=request.user)

    return render(request, "internal_ops/governance/approval_list.html", {
        "employee": actor_for_request(request),
        "is_internal_superuser": _superuser_flag(request),
        "active_nav": "approvals",
        "approvals": approvals[:200],
        "query": q,
        "selected_status": status,
        "selected_risk": risk,
        "mine": mine,
        "status_choices": ApprovalRequest.Status.choices,
        "risk_choices": ApprovalRequest.Risk.choices,
        "pending_count": ApprovalRequest.objects.filter(status=ApprovalRequest.Status.PENDING).count(),
        "high_risk_count": ApprovalRequest.objects.filter(status=ApprovalRequest.Status.PENDING, risk_level__in=[ApprovalRequest.Risk.HIGH, ApprovalRequest.Risk.CRITICAL]).count(),
        "my_pending_count": ApprovalRequest.objects.filter(status=ApprovalRequest.Status.PENDING, requester_user=request.user).count(),
    })


@internal_employee_required
@require_http_methods(["GET", "POST"])
def approval_create(request):
    if request.method == "POST":
        kind = request.POST.get("kind", "")
        risk = request.POST.get("risk_level", "")
        title = request.POST.get("title", "").strip()
        reason = request.POST.get("reason", "").strip()
        target_type = request.POST.get("target_type", "").strip()
        target_id = request.POST.get("target_id", "").strip()
        department_id = request.POST.get("approver_department", "")
        department = Department.objects.filter(pk=department_id, is_active=True).first() if department_id else None
        try:
            proposed = parse_proposed_changes(request.POST.get("proposed_changes", ""))
        except (ValueError, json.JSONDecodeError) as exc:
            messages.error(request, f"Invalid proposed changes JSON: {exc}")
        else:
            valid_kinds = {value for value, _ in ApprovalRequest.Kind.choices}
            valid_risks = {value for value, _ in ApprovalRequest.Risk.choices}
            if kind not in valid_kinds or risk not in valid_risks or not title or not reason:
                messages.error(request, "Kind, risk, title, and business reason are required.")
            else:
                approval = create_approval(
                    requester_user=request.user,
                    requester_employee=actor_for_request(request),
                    kind=kind,
                    risk_level=risk,
                    title=title,
                    reason=reason,
                    target_type=target_type,
                    target_id=target_id,
                    proposed_changes=proposed,
                    approver_department=department,
                )
                messages.success(request, f"Approval request {approval.reference} created.")
                return redirect("internal_ops:approval_detail", reference=approval.reference)

    return render(request, "internal_ops/governance/approval_create.html", {
        "employee": actor_for_request(request),
        "is_internal_superuser": _superuser_flag(request),
        "active_nav": "approvals",
        "kind_choices": ApprovalRequest.Kind.choices,
        "risk_choices": ApprovalRequest.Risk.choices,
        "departments": Department.objects.filter(is_active=True).order_by("name"),
    })


@internal_employee_required
@require_http_methods(["GET", "POST"])
def approval_detail(request, reference):
    approval = get_object_or_404(
        ApprovalRequest.objects.select_related("requester__user", "requester_user", "approver_department", "reviewed_by__user", "reviewed_by_user"),
        reference=reference,
    )
    employee = actor_for_request(request)
    if request.method == "POST":
        action = request.POST.get("action")
        note = request.POST.get("note", "").strip()
        try:
            if action in {ApprovalRequest.Status.APPROVED, ApprovalRequest.Status.REJECTED}:
                decide_approval(approval=approval, reviewer_user=request.user, reviewer_employee=employee, decision=action, note=note)
            elif action == "cancel":
                if not note:
                    raise ValueError("A cancellation reason is required.")
                cancel_approval(approval=approval, requester_user=request.user, requester_employee=employee, reason=note)
            elif action == "executed":
                if not note:
                    raise ValueError("An execution note is required.")
                mark_approval_executed(approval=approval, executor_user=request.user, executor_employee=employee, execution_note=note)
            else:
                raise ValueError("Unknown approval action.")
        except (ValueError, PermissionError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Approval workflow updated.")
        return redirect("internal_ops:approval_detail", reference=approval.reference)

    related_audit = InternalAuditEvent.objects.filter(target_type="approval_request", target_id=approval.reference).select_related("actor__user")[:30]
    return render(request, "internal_ops/governance/approval_detail.html", {
        "employee": employee,
        "is_internal_superuser": _superuser_flag(request),
        "active_nav": "approvals",
        "approval": approval,
        "can_review": can_review_approval(request.user, employee, approval) and approval.status == ApprovalRequest.Status.PENDING,
        "can_cancel": approval.status == ApprovalRequest.Status.PENDING and (approval.requester_user_id == request.user.pk or request.user.is_superuser),
        "can_execute": approval.status == ApprovalRequest.Status.APPROVED and (request.user.is_superuser or approval.requester_user_id != request.user.pk),
        "proposed_changes_pretty": json.dumps(approval.proposed_changes, indent=2, sort_keys=True),
        "related_audit": related_audit,
    })
