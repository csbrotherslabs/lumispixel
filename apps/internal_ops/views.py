from django.shortcuts import render

from .decorators import internal_employee_required
from .models import Department, EmployeeProfile, InternalAuditEvent


@internal_employee_required
def dashboard(request):
    profile = request.employee_profile
    profile.record_access()

    InternalAuditEvent.objects.create(
        actor=profile,
        category=InternalAuditEvent.Category.ACCESS,
        action="internal.dashboard.view",
        target_type="internal_workspace",
        summary="Opened LumisPixel Internal",
    )

    context = {
        "employee": profile,
        "employee_count": EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE).count(),
        "department_count": Department.objects.filter(is_active=True).count(),
        "recent_activity": InternalAuditEvent.objects.select_related("actor__user")[:8],
        "modules": [
            {"name": "Customers", "icon": "bi-people", "description": "Account support and customer operations."},
            {"name": "Tickets", "icon": "bi-ticket-perforated", "description": "Assigned work, queues, escalations, and SLAs."},
            {"name": "Employees", "icon": "bi-person-badge", "description": "Organization, roles, access, and employee records."},
            {"name": "AI Operations", "icon": "bi-stars", "description": "AI usage, processing health, costs, and exceptions."},
            {"name": "Billing & Usage", "icon": "bi-credit-card", "description": "Plans, allowances, storage, and account economics."},
            {"name": "Reports", "icon": "bi-graph-up-arrow", "description": "Executive, financial, operational, and support intelligence."},
            {"name": "Audit", "icon": "bi-shield-check", "description": "Sensitive actions, access history, and compliance records."},
            {"name": "System", "icon": "bi-activity", "description": "Platform health, incidents, queues, and internal alerts."},
        ],
    }
    return render(request, "internal_ops/dashboard.html", context)
