from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.clients.models import Client, Contract
from apps.dashboard.access import scope_assigned
from apps.dashboard.views import _dashboard_context, photographer_workspace_required


@photographer_workspace_required
@require_GET
def client_contracts(request, pk):
    """Expose a client's contracts as a first-class relationship in Client Detail."""
    if not request.studio_access.allows("clients"):
        raise PermissionDenied

    client = get_object_or_404(
        scope_assigned(Client.objects.all(), request.studio_access),
        pk=pk,
    )
    contracts = (
        Contract.objects.for_photographer(request.studio)
        .filter(client=client)
        .select_related("booking", "template")
        .order_by("-created_at", "-pk")
    )

    context = _dashboard_context(request, "clients", str(client))
    context.update(
        {
            "client_record": client,
            "contracts": contracts,
            "can_view_financials": request.studio_access.allows("financials"),
            "client_status_variant": {
                Client.Status.ACTIVE: "success",
                Client.Status.INACTIVE: "warning",
                Client.Status.ARCHIVED: "neutral",
            }[client.status],
            "edit_client_url": reverse("photographer_workspace:edit_client", args=[client.pk]),
            "client_email_url": f"mailto:{client.email}" if client.email else "",
            "client_phone_url": f"tel:{client.phone}" if client.phone else "",
            "hide_topbar_heading": True,
        }
    )
    return render(request, "photographer_workspace/client_contracts.html", context)
