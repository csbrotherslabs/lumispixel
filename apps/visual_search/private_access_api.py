"""Invitation-only requests. Generic responses prevent gallery enumeration."""
import json
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.galleries.models import Gallery
from .access_requests import (
    PrivateGalleryAccessRequest, PrivateGalleryInvitation, token_digest,
)


def _eligible(gallery):
    return (
        gallery.visibility != Gallery.Visibility.PUBLIC
        and gallery.status in (Gallery.Status.PUBLISHED, Gallery.Status.DELIVERED)
        and gallery.deleted_at is None and gallery.archived_at is None
        and gallery.published_at is not None
        and (gallery.expires_at is None or gallery.expires_at > timezone.now())
    )


def _payload(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


@login_required
@require_POST
def issue_private_invitation(request, gallery_id):
    """Only the gallery's photographer account can create an invitation."""
    if not getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    from .access_requests import PrivateGalleryInvitation
    gallery = Gallery.objects.select_related("photographer").filter(
        pk=gallery_id, photographer__user=request.user,
    ).first()
    if gallery is None:
        return JsonResponse({"error": "not_found"}, status=404)
    if not _eligible(gallery):
        return JsonResponse({"error": "not_available"}, status=400)
    invitation, token = PrivateGalleryInvitation.issue(gallery=gallery, user=request.user)
    # This is the only response containing the token. Never log it.
    return JsonResponse({"invitation_id": invitation.pk, "token": token, "expires_at": invitation.expires_at.isoformat()}, status=201)


@login_required
@require_POST
def submit_private_request(request):
    """Do not reveal whether a supplied invitation exists or is valid."""
    if not getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    data = _payload(request)
    token = data.get("invitation_token")
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        return JsonResponse({"message": "If the invitation is valid, your request will be delivered."}, status=202)
    invitation = PrivateGalleryInvitation.objects.select_related("gallery").filter(
        token_hash=token_digest(token), revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if invitation and _eligible(invitation.gallery) and invitation.created_by_id != request.user.pk:
        PrivateGalleryAccessRequest.objects.get_or_create(
            invitation=invitation, requester=request.user,
        )
    return JsonResponse({"message": "If the invitation is valid, your request will be delivered."}, status=202)


@login_required
@require_POST
def review_private_request(request, request_id):
    """Review is an administrative decision, NOT an access-control grant."""
    if not getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    data = _payload(request)
    decision = data.get("decision")
    if decision not in ("approved", "denied"):
        return JsonResponse({"error": "invalid_decision"}, status=400)
    with transaction.atomic():
        access_request = PrivateGalleryAccessRequest.objects.select_for_update().select_related(
            "invitation__gallery__photographer"
        ).filter(pk=request_id, invitation__gallery__photographer__user=request.user).first()
        if access_request is None:
            return JsonResponse({"error": "not_found"}, status=404)
        if not _eligible(access_request.invitation.gallery):
            return JsonResponse({"error": "not_available"}, status=400)
        if access_request.status != PrivateGalleryAccessRequest.Status.PENDING:
            return JsonResponse({"error": "already_reviewed"}, status=409)
        access_request.status = decision
        access_request.reviewed_at = timezone.now()
        access_request.save(update_fields=["status", "reviewed_at"])
    # Do not grant gallery permissions here; existing gallery invitation
    # and permission systems must separately authorize access.
    return JsonResponse({"status": decision, "access_granted": False})
