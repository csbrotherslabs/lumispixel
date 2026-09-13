from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import internal_employee_required
from .employee_forms import EmployeeCreateForm, EmployeeUpdateForm
from .employee_services import (
    EmployeeInvitationError,
    EmployeeManagementError,
    create_employee,
    is_employee_manager,
    send_employee_invitation,
    update_employee,
)
from .governance import actor_for_request, record_audit
from .models import Department, EmployeeProfile, InternalAuditEvent


def _base_context(request, active_nav="employees"):
    employee = actor_for_request(request)
    return {
        "employee": employee,
        "is_internal_superuser": request.user.is_superuser,
        "active_nav": active_nav,
        "can_manage_employees": is_employee_manager(request.user, employee),
    }


@internal_employee_required
def employee_list(request):
    employees = EmployeeProfile.objects.select_related("user", "department", "role", "manager__user")
    q = request.GET.get("q", "").strip()
    department = request.GET.get("department", "all")
    status = request.GET.get("status", "all")
    if q:
        employees = employees.filter(Q(employee_id__icontains=q) | Q(user__email__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(title__icontains=q))
    if department != "all":
        employees = employees.filter(department__code=department)
    if status != "all":
        employees = employees.filter(status=status)
    context = _base_context(request)
    context.update({
        "employees": employees[:250], "query": q, "selected_department": department, "selected_status": status,
        "departments": Department.objects.filter(is_active=True).annotate(employee_count=Count("employees")).order_by("name"),
        "status_choices": EmployeeProfile.Status.choices,
        "total_count": EmployeeProfile.objects.count(),
        "active_count": EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE).count(),
        "invited_count": EmployeeProfile.objects.filter(status=EmployeeProfile.Status.INVITED).count(),
        "suspended_count": EmployeeProfile.objects.filter(status=EmployeeProfile.Status.SUSPENDED).count(),
    })
    return render(request, "internal_ops/employees/list.html", context)


@internal_employee_required
def employee_detail(request, employee_id):
    target = get_object_or_404(EmployeeProfile.objects.select_related("user", "department", "role", "manager__user"), employee_id=employee_id)
    context = _base_context(request)
    audit_events = []
    if context["can_manage_employees"]:
        audit_events = InternalAuditEvent.objects.filter(category=InternalAuditEvent.Category.EMPLOYEE, target_type="employee_profile", target_id=target.employee_id).select_related("actor__user")[:30]
    context.update({
        "target_employee": target,
        "direct_reports": target.direct_reports.select_related("user", "department", "role").order_by("user__last_name", "user__first_name")[:50],
        "audit_events": audit_events,
    })
    return render(request, "internal_ops/employees/detail.html", context)


@internal_employee_required
@require_http_methods(["GET", "POST"])
def employee_create(request):
    employee = actor_for_request(request)
    if not is_employee_manager(request.user, employee):
        return HttpResponseForbidden("You do not have permission to add LumisPixel employees.")
    form = EmployeeCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            target, created_user = create_employee(actor_user=request.user, actor_employee=employee, **form.cleaned_data)
        except (EmployeeManagementError, PermissionError) as exc:
            messages.error(request, str(exc))
        else:
            try:
                send_employee_invitation(request, target, created_user=created_user)
            except EmployeeInvitationError as exc:
                messages.warning(request, str(exc))
            else:
                messages.success(request, f"{target.user.display_name} was added and notified.")
            return redirect("internal_ops:employee_detail", employee_id=target.employee_id)
    context = _base_context(request)
    context["form"] = form
    return render(request, "internal_ops/employees/form.html", context)


@internal_employee_required
@require_http_methods(["GET", "POST"])
def employee_edit(request, employee_id):
    actor = actor_for_request(request)
    if not is_employee_manager(request.user, actor):
        return HttpResponseForbidden("You do not have permission to manage LumisPixel employees.")
    target = get_object_or_404(EmployeeProfile.objects.select_related("user", "department", "role", "manager__user"), employee_id=employee_id)
    initial = {
        "first_name": target.user.first_name, "last_name": target.user.last_name, "title": target.title,
        "department": target.department_id, "role": target.role_id, "manager": target.manager_id,
        "status": target.status, "hire_date": target.hire_date,
    }
    form = EmployeeUpdateForm(request.POST or None, employee=target, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            target = update_employee(employee=target, actor_user=request.user, actor_employee=actor, **form.cleaned_data)
        except (EmployeeManagementError, PermissionError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Employee record updated and added to the audit trail.")
            return redirect("internal_ops:employee_detail", employee_id=target.employee_id)
    context = _base_context(request)
    context.update({"form": form, "target_employee": target, "editing": True})
    return render(request, "internal_ops/employees/form.html", context)


@internal_employee_required
@require_http_methods(["POST"])
def employee_resend_invitation(request, employee_id):
    actor = actor_for_request(request)
    if not is_employee_manager(request.user, actor):
        return HttpResponseForbidden("You do not have permission to manage LumisPixel employees.")
    target = get_object_or_404(EmployeeProfile.objects.select_related("user"), employee_id=employee_id)
    try:
        send_employee_invitation(request, target, created_user=not target.user.has_usable_password())
    except EmployeeInvitationError as exc:
        messages.warning(request, str(exc))
    else:
        record_audit(
            actor=actor,
            category=InternalAuditEvent.Category.EMPLOYEE,
            action="employee.invitation.sent",
            target_type="employee_profile",
            target_id=target.employee_id,
            summary=f"Sent employee access email to {target.user.display_name}",
            reason="Employee access invitation resent",
            metadata={"actor_user_id": str(request.user.pk), "superuser": request.user.is_superuser},
        )
        messages.success(request, "Employee access email sent.")
    return redirect("internal_ops:employee_detail", employee_id=target.employee_id)
