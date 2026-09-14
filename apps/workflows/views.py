from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.dashboard.views import _identity, _workspace_nav, photographer_workspace_required

from .models import AutomationExecution, AutomationRule
from .services import ensure_default_rules


@photographer_workspace_required
@require_http_methods(["GET", "POST"])
def automation_dashboard(request):
    photographer = request.studio
    if photographer.user_id != request.user.id:
        raise PermissionDenied("Only the studio owner can manage automations.")
    ensure_default_rules(photographer)

    if request.method == "POST":
        rule_id = request.POST.get("rule_id")
        rule = AutomationRule.objects.filter(photographer=photographer, pk=rule_id).first()
        if not rule:
            messages.error(request, "That automation rule is not available in this workspace.")
            return redirect("photographer_workspace:workflows")
        rule.enabled = request.POST.get("enabled") == "on"
        rule.save(update_fields=["enabled", "updated_at"])
        messages.success(
            request,
            f"{rule.name} {'enabled' if rule.enabled else 'disabled'}.",
        )
        return redirect("photographer_workspace:workflows")

    rules = list(AutomationRule.objects.filter(photographer=photographer).order_by("pk"))
    executions = list(
        AutomationExecution.objects.filter(photographer=photographer)
        .select_related("rule")
        .order_by("-queued_at", "-pk")[:25]
    )
    enabled_count = sum(1 for rule in rules if rule.enabled)
    failure_count = sum(1 for execution in executions if execution.status == AutomationExecution.Status.FAILED)
    return render(
        request,
        "photographer_workspace/workflows/index.html",
        {
            "page_title": "Automation",
            "workspace_nav": _workspace_nav("workflows"),
            "identity": _identity(photographer, request.user),
            "automation_active": True,
            "rules": rules,
            "executions": executions,
            "enabled_count": enabled_count,
            "failure_count": failure_count,
        },
    )
