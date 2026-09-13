import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.services import build_public_url

from .governance import record_audit
from .models import EmployeeProfile, InternalAuditEvent

logger = logging.getLogger(__name__)
User = get_user_model()


class EmployeeManagementError(ValueError):
    pass


class EmployeeInvitationError(RuntimeError):
    pass


def is_employee_manager(user, employee=None):
    """Superusers, executives, and Human Resources manage employee records."""
    if user.is_superuser:
        return True
    employee = employee or getattr(user, "employee_profile", None)
    if not employee or employee.status != EmployeeProfile.Status.ACTIVE:
        return False
    if employee.role_id and employee.role.is_executive:
        return True
    if employee.department_id and employee.department.code in {"executive", "human-resources"}:
        return True
    return False


def can_assign_executive_role(user, employee=None):
    """HR may manage staff, but Executive privilege requires superuser/Executive authority."""
    if user.is_superuser:
        return True
    employee = employee or getattr(user, "employee_profile", None)
    return bool(
        employee
        and employee.status == EmployeeProfile.Status.ACTIVE
        and (
            (employee.role_id and employee.role.is_executive)
            or (employee.department_id and employee.department.code == "executive")
        )
    )


def _employee_snapshot(employee):
    return {
        "employee_id": employee.employee_id,
        "email": employee.user.email,
        "first_name": employee.user.first_name,
        "last_name": employee.user.last_name,
        "title": employee.title,
        "department": employee.department.code if employee.department_id else None,
        "role": employee.role.code if employee.role_id else None,
        "manager": employee.manager.employee_id if employee.manager_id else None,
        "status": employee.status,
        "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
    }


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
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                primary_role=User.PrimaryRole.CLIENT,
                last_active_workspace=User.Workspace.OPERATIONS,
                account_status=User.AccountStatus.ACTIVE,
                email_verified=True,
                email_verified_at=timezone.now(),
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
        else:
            if hasattr(user, "employee_profile"):
                raise EmployeeManagementError("This LumisPixel account is already linked to an employee.")
            changed = []
            if first_name and not user.first_name:
                user.first_name = first_name
                changed.append("first_name")
            if last_name and not user.last_name:
                user.last_name = last_name
                changed.append("last_name")
            if changed:
                changed.append("updated_at")
                user.save(update_fields=changed)

        employee = EmployeeProfile.objects.create(
            user=user,
            employee_id=employee_id,
            title=title,
            department=department,
            role=role,
            manager=manager,
            status=EmployeeProfile.Status.ACTIVE,
            hire_date=hire_date,
        )
        record_audit(
            actor=actor_employee,
            category=InternalAuditEvent.Category.EMPLOYEE,
            action="employee.created",
            target_type="employee_profile",
            target_id=employee.employee_id,
            summary=f"Added employee {user.display_name}",
            reason="Employee provisioning",
            metadata={
                "actor_user_id": str(actor_user.pk),
                "superuser": actor_user.is_superuser,
                "created_user_account": created_user,
                "employee": _employee_snapshot(employee),
            },
        )
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
        locked = EmployeeProfile.objects.select_for_update().select_related("user", "department", "role", "manager").get(pk=employee.pk)
        before = _employee_snapshot(locked)
        user = locked.user
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name", "updated_at"])
        locked.title = title
        locked.department = department
        locked.role = role
        locked.manager = manager
        locked.status = status
        locked.hire_date = hire_date
        locked.save(update_fields=["title", "department", "role", "manager", "status", "hire_date", "updated_at"])
        after = _employee_snapshot(locked)
        record_audit(
            actor=actor_employee,
            category=InternalAuditEvent.Category.EMPLOYEE,
            action="employee.updated",
            target_type="employee_profile",
            target_id=locked.employee_id,
            summary=f"Updated employee {user.display_name}",
            reason=reason,
            metadata={
                "actor_user_id": str(actor_user.pk),
                "superuser": actor_user.is_superuser,
                "before": before,
                "after": after,
            },
        )
        return locked


def send_employee_invitation(request, employee, *, created_user=False):
    """Email a secure set-password link for new accounts, or a sign-in notice for existing accounts."""
    user = employee.user
    if created_user:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        path = reverse("accounts:password-reset-confirm", kwargs={"uidb64": uidb64, "token": token})
        action_url = build_public_url(request, path)
        action_label = "Set your password"
        guidance = "Use the secure link below to choose a password, then sign in to LumisPixel Internal."
    else:
        action_url = build_public_url(request, reverse("accounts:login"))
        action_label = "Sign in to LumisPixel"
        guidance = "Your existing LumisPixel account now has employee access. Sign in with your current credentials."

    subject = "You've been added to LumisPixel Internal"
    body = (
        f"Hi {user.first_name or 'there'},\n\n"
        f"You've been added to LumisPixel Internal as {employee.title or 'a LumisPixel employee'}.\n"
        f"{guidance}\n\n{action_label}: {action_url}\n\n"
        "If you were not expecting this invitation, contact a LumisPixel administrator."
    )
    html = (
        f"<p>Hi {user.first_name or 'there'},</p>"
        f"<p>You've been added to <strong>LumisPixel Internal</strong> as {employee.title or 'a LumisPixel employee'}.</p>"
        f"<p>{guidance}</p>"
        f"<p><a href=\"{action_url}\">{action_label}</a></p>"
        "<p>If you were not expecting this invitation, contact a LumisPixel administrator.</p>"
    )
    try:
        with mail.get_connection(fail_silently=False) as connection:
            message = mail.EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                connection=connection,
            )
            message.attach_alternative(html, "text/html")
            sent = message.send(fail_silently=False)
    except (OSError, SMTPException) as exc:
        logger.exception("Employee invitation delivery failed for %s", user.email)
        raise EmployeeInvitationError("The employee was added, but the invitation email could not be sent.") from exc
    if sent != 1:
        raise EmployeeInvitationError("The employee was added, but the invitation email was not accepted by the email backend.")
    return True
