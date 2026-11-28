import logging
from datetime import timedelta
import hashlib
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from apps.notifications.email_delivery import public_url, queue_transactional_email
from apps.accounts.recovery import password_reset_state
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.html import escape
from django.utils.http import urlsafe_base64_encode



from .governance import record_audit
from .models import EmployeeProfile, InternalAuditEvent

logger = logging.getLogger(__name__)
User = get_user_model()


class EmployeeManagementError(ValueError):
    pass


class EmployeeInvitationError(RuntimeError):
    pass


def is_employee_manager(user, employee=None):
    if user.is_superuser:
        return True
    employee = employee or getattr(user, "employee_profile", None)
    if not employee or employee.status != EmployeeProfile.Status.ACTIVE:
        return False
    if employee.role_id and employee.role.is_executive:
        return True
    return bool(employee.department_id and employee.department.code in {"executive", "human-resources"})


def can_assign_executive_role(user, employee=None):
    if user.is_superuser:
        return True
    employee = employee or getattr(user, "employee_profile", None)
    return bool(employee and employee.status == EmployeeProfile.Status.ACTIVE and ((employee.role_id and employee.role.is_executive) or (employee.department_id and employee.department.code == "executive")))


def _employee_snapshot(employee):
    return {"employee_id": employee.employee_id, "email": employee.user.email, "first_name": employee.user.first_name, "last_name": employee.user.last_name, "title": employee.title, "department": employee.department.code if employee.department_id else None, "role": employee.role.code if employee.role_id else None, "manager": employee.manager.employee_id if employee.manager_id else None, "status": employee.status, "hire_date": employee.hire_date.isoformat() if employee.hire_date else None}


def create_employee(*, actor_user, actor_employee, email, first_name, last_name, employee_id, title="", department=None, role=None, manager=None, hire_date=None):
    email = User.objects.normalize_email(email)
    if not email:
        raise EmployeeManagementError("Email is required.")
    if role and role.is_executive and not can_assign_executive_role(actor_user, actor_employee):
        raise PermissionError("Only a superuser or Executive may assign an Executive role.")
    with transaction.atomic():
        user = User.objects.select_for_update().filter(email__iexact=email).first()
        created_user = user is None
        if user is None:
            user = User(email=email, first_name=first_name, last_name=last_name, primary_role=User.PrimaryRole.CLIENT, last_active_workspace=User.Workspace.OPERATIONS, account_status=User.AccountStatus.ACTIVE, email_verified=True, email_verified_at=timezone.now(), is_active=True)
            user.set_unusable_password()
            user.save()
        else:
            if hasattr(user, "employee_profile"):
                raise EmployeeManagementError("This LumisPixel account is already linked to an employee.")
            changed = []
            if first_name and not user.first_name:
                user.first_name = first_name; changed.append("first_name")
            if last_name and not user.last_name:
                user.last_name = last_name; changed.append("last_name")
            if changed:
                changed.append("updated_at"); user.save(update_fields=changed)
        employee = EmployeeProfile.objects.create(user=user, employee_id=employee_id, title=title, department=department, role=role, manager=manager, status=EmployeeProfile.Status.ACTIVE, hire_date=hire_date)
        record_audit(actor=actor_employee, category=InternalAuditEvent.Category.EMPLOYEE, action="employee.created", target_type="employee_profile", target_id=employee.employee_id, summary=f"Added employee {user.display_name}", reason="Employee provisioning", metadata={"actor_user_id": str(actor_user.pk), "superuser": actor_user.is_superuser, "created_user_account": created_user, "employee": _employee_snapshot(employee)})
        return employee, created_user


def update_employee(*, employee, actor_user, actor_employee, first_name, last_name, title, department, role, manager, status, hire_date, reason):
    if role and role.is_executive and not can_assign_executive_role(actor_user, actor_employee):
        raise PermissionError("Only a superuser or Executive may assign an Executive role.")
    if employee.user_id == actor_user.pk and status in {EmployeeProfile.Status.SUSPENDED, EmployeeProfile.Status.TERMINATED}:
        raise EmployeeManagementError("You cannot suspend or terminate your own employee access.")
    if employee.pk == getattr(manager, "pk", None):
        raise EmployeeManagementError("An employee cannot be their own manager.")
    if not reason.strip():
        raise EmployeeManagementError("A reason for the employee change is required.")
    with transaction.atomic():
        # Lock only the EmployeeProfile row. PostgreSQL rejects FOR UPDATE when
        # select_related() adds LEFT OUTER JOINs for nullable relations such as
        # department, role, or manager. Related objects can be loaded after the
        # row lock without attempting to lock the nullable side of those joins.
        locked = EmployeeProfile.objects.select_for_update().get(pk=employee.pk)
        locked = EmployeeProfile.objects.select_related("user", "department", "role", "manager").get(pk=locked.pk)
        before = _employee_snapshot(locked)
        user = locked.user; user.first_name = first_name; user.last_name = last_name; user.save(update_fields=["first_name", "last_name", "updated_at"])
        locked.title = title; locked.department = department; locked.role = role; locked.manager = manager; locked.status = status; locked.hire_date = hire_date
        locked.save(update_fields=["title", "department", "role", "manager", "status", "hire_date", "updated_at"])
        after = _employee_snapshot(locked)
        record_audit(actor=actor_employee, category=InternalAuditEvent.Category.EMPLOYEE, action="employee.updated", target_type="employee_profile", target_id=locked.employee_id, summary=f"Updated employee {user.display_name}", reason=reason, metadata={"actor_user_id": str(actor_user.pk), "superuser": actor_user.is_superuser, "before": before, "after": after})
        return locked


def send_employee_invitation(request, employee, *, created_user=False):
    """Persist the requested communication before attempting rendering/queueing."""
    from apps.notifications.intents import require_email
    with transaction.atomic():
        employee = EmployeeProfile.objects.select_for_update().select_related("user").get(pk=employee.pk)
        if not employee.can_access_internal or not employee.user.is_active:
            raise EmployeeInvitationError("Only active, eligible employees can receive access invitations.")
        event_key = f"employee.invite:{employee.pk}:{uuid4().hex}"
        recipient = employee.user.email
        require_email(event_key=event_key, recipients=[recipient], kind="employee.invite")
    try:
        return _queue_employee_invitation(request, employee, event_key=event_key, recipient=recipient)
    except Exception as exc:
        raise EmployeeInvitationError("Employee access was not changed, but the invitation could not be queued.") from exc


@transaction.atomic
def _queue_employee_invitation(request, employee, *, event_key, recipient):
    employee = EmployeeProfile.objects.select_for_update().select_related("user").get(pk=employee.pk)
    user = employee.user
    if not employee.can_access_internal or not user.is_active:
        raise EmployeeInvitationError("Only active, eligible employees can receive access invitations.")
    if user.email.casefold() != recipient.casefold():
        raise EmployeeInvitationError("Employee recipient changed; request a new invitation.")
    setup = not user.has_usable_password()
    deadline = timezone.now() + timedelta(hours=24)
    if setup:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk)); token = default_token_generator.make_token(user)
        action_url = public_url(reverse("accounts:password-reset-confirm", kwargs={"uidb64": uidb64, "token": token}))
        deadline = min(deadline, timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT - 1))
        action_label = "Set your password"; guidance = "Use the secure link below to choose a password, then sign in to LumisPixel Internal."
    else:
        action_url = public_url(reverse("accounts:login")); action_label = "Sign in to LumisPixel"; guidance = "Your existing LumisPixel account now has employee access. Sign in with your current credentials."
    subject = "You've been added to LumisPixel Internal"
    body = f"Hi {user.first_name or 'there'},\n\nYou've been added to LumisPixel Internal as {employee.title or 'a LumisPixel employee'}.\n{guidance}\n\n{action_label}: {action_url}\n\nIf you were not expecting this invitation, contact a LumisPixel administrator."
    safe_name = escape(user.first_name or "there"); safe_title = escape(employee.title or "a LumisPixel employee"); safe_url = escape(action_url); safe_guidance = escape(guidance); safe_label = escape(action_label)
    html = f"<p>Hi {safe_name},</p><p>You've been added to <strong>LumisPixel Internal</strong> as {safe_title}.</p><p>{safe_guidance}</p><p><a href=\"{safe_url}\">{safe_label}</a></p><p>If you were not expecting this invitation, contact a LumisPixel administrator.</p>"
    try:
        delivery = queue_transactional_email(
            event_key=event_key,
            subject=subject, plain_body=body, html_body=html, recipients=[user.email],
            sensitive=True, expires_at=deadline, lifecycle_kind="employee.invite",
            lifecycle_context={"employee_id": employee.pk, "user_id": str(user.pk),
                "setup": setup, "state": password_reset_state(user),
                "title": employee.title, "role_id": employee.role_id, "department_id": employee.department_id},
            supersession_scope=f"employee.invite:{employee.pk}",
        )
        if not delivery:
            raise ValueError("Missing recipient")
        return delivery
    except Exception as exc:
        logger.error("Employee invitation could not be queued")
        raise EmployeeInvitationError("Employee access was not changed, but the invitation could not be queued.") from exc
