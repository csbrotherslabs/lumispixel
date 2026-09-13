import json

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import notify_user

from .models import ApprovalRequest, EmployeeProfile, InternalAuditEvent


def actor_for_request(request):
    return getattr(request, "employee_profile", None)


def record_audit(*, actor=None, category, action, target_type="", target_id="", summary, reason="", metadata=None):
    return InternalAuditEvent.objects.create(
        actor=actor,
        category=category,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        summary=summary,
        reason=reason,
        metadata=metadata or {},
    )


def _active_department_users(department):
    if not department:
        return []
    return [
        profile.user
        for profile in EmployeeProfile.objects.filter(
            status=EmployeeProfile.Status.ACTIVE,
            department=department,
            user__is_active=True,
        ).select_related("user")
    ]


def _executive_users():
    return [
        profile.user
        for profile in EmployeeProfile.objects.filter(
            status=EmployeeProfile.Status.ACTIVE,
            department__code="executive",
            user__is_active=True,
        ).select_related("user")
    ]


def _notify(users, *, title, message, approval):
    seen = set()
    for user in users:
        if not user or user.pk in seen:
            continue
        seen.add(user.pk)
        notify_user(
            recipient=user,
            category=Notification.Category.SYSTEM,
            title=title,
            message=message,
            action_url=f"/internal/approvals/{approval.reference}/",
            action_label="Open approval",
            metadata={"approval_reference": approval.reference, "risk_level": approval.risk_level},
        )


def can_review_approval(user, employee, approval):
    if approval.requester_user_id and approval.requester_user_id == user.pk:
        return False
    if approval.requester_id and employee and approval.requester_id == employee.pk:
        return False
    if user.is_superuser:
        return True
    if not employee or employee.status != EmployeeProfile.Status.ACTIVE:
        return False
    if employee.role and employee.role.is_executive:
        return True
    if employee.department and employee.department.code == "executive":
        return True
    return bool(approval.approver_department_id and employee.department_id == approval.approver_department_id)


@transaction.atomic
def create_approval(*, requester_user, requester_employee, kind, risk_level, title, reason, target_type="", target_id="", proposed_changes=None, approver_department=None):
    approval = ApprovalRequest.objects.create(
        requester=requester_employee,
        requester_user=requester_user,
        kind=kind,
        risk_level=risk_level,
        title=title,
        reason=reason,
        target_type=target_type,
        target_id=target_id,
        proposed_changes=proposed_changes or {},
        approver_department=approver_department,
    )
    record_audit(
        actor=requester_employee,
        category=InternalAuditEvent.Category.SECURITY,
        action="approval.request.create",
        target_type="approval_request",
        target_id=approval.reference,
        summary=f"Created approval request {approval.reference}",
        reason=reason,
        metadata={
            "kind": kind,
            "risk_level": risk_level,
            "target_type": target_type,
            "target_id": target_id,
            "proposed_changes": approval.proposed_changes,
            "requester_user_id": str(requester_user.pk),
        },
    )
    reviewers = _active_department_users(approver_department)
    if risk_level in {ApprovalRequest.Risk.HIGH, ApprovalRequest.Risk.CRITICAL} or not reviewers:
        reviewers += _executive_users()
    reviewers = [user for user in reviewers if user.pk != requester_user.pk]
    _notify(
        reviewers,
        title=f"Approval needed: {approval.reference}",
        message=f"{approval.get_risk_level_display()} risk — {approval.title}",
        approval=approval,
    )
    return approval


@transaction.atomic
def decide_approval(*, approval, reviewer_user, reviewer_employee, decision, note):
    approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ValueError("Only pending approvals can be reviewed.")
    if decision not in {ApprovalRequest.Status.APPROVED, ApprovalRequest.Status.REJECTED}:
        raise ValueError("Invalid approval decision.")
    if not note.strip():
        raise ValueError("A decision note is required.")
    if not can_review_approval(reviewer_user, reviewer_employee, approval):
        raise PermissionError("You are not allowed to review this approval.")

    approval.status = decision
    approval.reviewed_by = reviewer_employee
    approval.reviewed_by_user = reviewer_user
    approval.reviewed_at = timezone.now()
    approval.decision_note = note.strip()
    approval.save(update_fields=["status", "reviewed_by", "reviewed_by_user", "reviewed_at", "decision_note", "updated_at"])

    record_audit(
        actor=reviewer_employee,
        category=InternalAuditEvent.Category.SECURITY,
        action=f"approval.request.{decision}",
        target_type="approval_request",
        target_id=approval.reference,
        summary=f"{approval.get_status_display()} approval request {approval.reference}",
        reason=approval.decision_note,
        metadata={
            "reviewer_user_id": str(reviewer_user.pk),
            "requester_user_id": str(approval.requester_user_id or ""),
            "risk_level": approval.risk_level,
            "kind": approval.kind,
        },
    )
    if approval.requester_user:
        _notify(
            [approval.requester_user],
            title=f"Approval {approval.get_status_display().lower()}: {approval.reference}",
            message=approval.decision_note,
            approval=approval,
        )
    return approval


@transaction.atomic
def cancel_approval(*, approval, requester_user, requester_employee, reason):
    approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
    if approval.status != ApprovalRequest.Status.PENDING:
        raise ValueError("Only pending approvals can be cancelled.")
    if approval.requester_user_id != requester_user.pk and not requester_user.is_superuser:
        raise PermissionError("Only the requester or a superuser can cancel this approval.")
    approval.status = ApprovalRequest.Status.CANCELLED
    approval.decision_note = reason.strip()
    approval.reviewed_at = timezone.now()
    approval.save(update_fields=["status", "decision_note", "reviewed_at", "updated_at"])
    record_audit(
        actor=requester_employee,
        category=InternalAuditEvent.Category.SECURITY,
        action="approval.request.cancelled",
        target_type="approval_request",
        target_id=approval.reference,
        summary=f"Cancelled approval request {approval.reference}",
        reason=reason,
        metadata={"requester_user_id": str(requester_user.pk)},
    )
    return approval


@transaction.atomic
def mark_approval_executed(*, approval, executor_user, executor_employee, execution_note, execution_metadata=None):
    approval = ApprovalRequest.objects.select_for_update().get(pk=approval.pk)
    if approval.status != ApprovalRequest.Status.APPROVED:
        raise ValueError("Only approved requests can be marked executed.")
    if approval.requester_user_id == executor_user.pk:
        raise PermissionError("The requester cannot execute their own approved request.")
    approval.status = ApprovalRequest.Status.EXECUTED
    approval.executed_at = timezone.now()
    approval.save(update_fields=["status", "executed_at", "updated_at"])
    record_audit(
        actor=executor_employee,
        category=InternalAuditEvent.Category.SECURITY,
        action="approval.request.executed",
        target_type="approval_request",
        target_id=approval.reference,
        summary=f"Marked approval request {approval.reference} executed",
        reason=execution_note,
        metadata={"executor_user_id": str(executor_user.pk), "execution": execution_metadata or {}},
    )
    return approval


def parse_proposed_changes(raw):
    raw = (raw or "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Proposed changes must be a JSON object.")
    return value
