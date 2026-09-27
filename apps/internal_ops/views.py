from django.shortcuts import render
from django.utils import timezone

from .decorators import internal_employee_required
from .models import Department, EmployeeProfile, InternalAuditEvent


COMMAND_CENTER_MODULES = [
    {"name": "Customers", "icon": "bi-people", "description": "Account support, customer history, usage, and service operations.", "group": "Operations", "url_name": "internal_ops:customers"},
    {"name": "Tickets", "icon": "bi-ticket-perforated", "description": "Assigned work, queues, escalations, priorities, and SLAs.", "group": "Operations", "url_name": "internal_ops:tickets"},
    {"name": "Employees", "icon": "bi-person-badge", "description": "Organization, departments, roles, access, and employee records.", "group": "People", "url_name": "internal_ops:employees"},
    {"name": "AI Operations", "icon": "bi-stars", "description": "AI usage, processing health, costs, failures, and exceptions.", "group": "Intelligence", "url_name": "internal_ops:ai_operations"},
    {"name": "Billing & Usage", "icon": "bi-credit-card", "description": "Plans, allowances, storage, credits, and customer economics.", "group": "Intelligence", "url_name": "internal_ops:billing_operations"},
    {"name": "Reports", "icon": "bi-graph-up-arrow", "description": "Executive, financial, operational, support, and growth intelligence.", "group": "Intelligence"},
    {"name": "Audit", "icon": "bi-shield-check", "description": "Sensitive actions, access history, approvals, and compliance records.", "group": "Governance", "url_name": "internal_ops:audit"},
    {"name": "System", "icon": "bi-activity", "description": "Platform health, incidents, queues, integrations, and internal alerts.", "group": "Governance", "url_name": "internal_ops:system"},
]


@internal_employee_required
def dashboard(request):
    profile = request.employee_profile
    if profile is not None:
        profile.record_access()

    InternalAuditEvent.objects.create(
        actor=profile,
        category=InternalAuditEvent.Category.ACCESS,
        action="internal.dashboard.view",
        target_type="internal_workspace",
        summary="Opened LumisPixel Internal",
        metadata={
            "user_id": str(request.user.pk),
            "user_email": request.user.email,
            "superuser": request.user.is_superuser,
        },
    )

    active_employees = EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE)
    departments = Department.objects.filter(is_active=True).order_by("name")
    department_cards = [
        {
            "name": department.name,
            "code": department.code,
            "description": department.description,
            "employee_count": active_employees.filter(department=department).count(),
        }
        for department in departments
    ]

    today = timezone.localdate()
    context = {
        "employee": profile,
        "is_internal_superuser": request.user.is_superuser,
        "employee_count": active_employees.count(),
        "department_count": len(department_cards),
        "department_cards": department_cards,
        "recent_activity": InternalAuditEvent.objects.select_related("actor__user")[:8],
        "activity_today": InternalAuditEvent.objects.filter(created_at__date=today).count(),
        "modules": COMMAND_CENTER_MODULES,
    }
    return render(request, "internal_ops/dashboard.html", context)