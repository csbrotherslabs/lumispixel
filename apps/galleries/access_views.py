from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

from . import views


def _gallery_unavailable(request):
    """Return a neutral 404 without disclosing why gallery access failed."""
    return render(request, "galleries/gallery_access_unavailable.html", status=404)


@never_cache
@require_GET
def stable_gallery_access(request, public_id):
    try:
        return views.stable_gallery_access(request, public_id)
    except views.PrivateGalleryLoginRequired as error:
        return views._private_gallery_login(request, error.gallery)
    except Http404:
        return _gallery_unavailable(request)


@never_cache
@require_GET
def client_gallery_access(request, token):
    try:
        return views.client_gallery_access(request, token)
    except views.PrivateGalleryLoginRequired as error:
        return views._private_gallery_login(request, error.gallery)
    except Http404:
        return _gallery_unavailable(request)


@never_cache
@require_GET
def public_semantic_results(request, public_id):
    try:
        return views.stable_gallery_access(request, public_id, search_results=True)
    except views.PrivateGalleryLoginRequired as error:
        return views._private_gallery_login(request, error.gallery)
    except Http404:
        return _gallery_unavailable(request)


@never_cache
@require_GET
def invited_semantic_results(request, token):
    try:
        return views.client_gallery_access(request, token, search_results=True)
    except views.PrivateGalleryLoginRequired as error:
        return views._private_gallery_login(request, error.gallery)
    except Http404:
        return _gallery_unavailable(request)
