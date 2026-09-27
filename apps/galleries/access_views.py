from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import views


def _gallery_unavailable(request):
    """Return a neutral 404 without disclosing why gallery access failed."""
    return render(request, "galleries/gallery_access_unavailable.html", status=404)


@require_GET
def stable_gallery_access(request, public_id):
    try:
        return views.stable_gallery_access(request, public_id)
    except Http404:
        return _gallery_unavailable(request)


@require_GET
def client_gallery_access(request, token):
    try:
        return views.client_gallery_access(request, token)
    except Http404:
        return _gallery_unavailable(request)
