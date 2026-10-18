"""Photographer-only, feature-gated server-rendered request inbox."""
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.visual_search.access_requests import PrivateGalleryAccessRequest
from .views import _dashboard_context, photographer_workspace_required


@photographer_workspace_required
@require_GET
def private_gallery_request_inbox_page(request):
    if not getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED", False):
        raise Http404()
    if request.studio.user_id != request.user.pk:
        raise Http404()
    status = request.GET.get("status", "pending")
    valid = {choice for choice, _ in PrivateGalleryAccessRequest.Status.choices}
    if status not in valid | {"all"}:
        status = "pending"
    records = PrivateGalleryAccessRequest.objects.filter(
        invitation__gallery__photographer__user=request.user,
    ).select_related("requester", "invitation__gallery").order_by("-created_at", "-pk")
    counts = {key: records.filter(status=key).count() for key in valid}
    if status != "all":
        records = records.filter(status=status)
    context = _dashboard_context(request, active_key="private_gallery_requests", title="Gallery access requests")
    context.update({
        "requests": list(records[:100]),
        "request_status": status,
        "status_counts": counts,
        "total_count": sum(counts.values()),
    })
    return render(request, "photographer_workspace/private_gallery_request_inbox.html", context)
