"""Invitation-only gallery requests with owner review and existing gallery access delivery."""
import hashlib
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.galleries.models import AccessToken, Gallery, GalleryInvitation
from apps.galleries.services import GalleryInvitationDeliveryError, send_gallery_invitation_email
from .access_requests import PrivateGalleryAccessRequest, PrivateGalleryInvitation, token_digest

logger = logging.getLogger(__name__)
GENERIC = {"message": "If the invitation is valid, your request will be delivered."}


def _enabled():
    return getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED", False)


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


def _throttle(request, action):
    """Fail closed without a configured shared atomic cache."""
    if not getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_SHARED_CACHE", False):
        raise RuntimeError("Shared rate-limit cache required")
    quota = int(getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_RATE_LIMIT", 10))
    window = int(getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_RATE_WINDOW", 3600))
    if not 1 <= quota <= 100 or window < 60:
        raise RuntimeError("Invalid rate limit")
    remote = request.META.get("REMOTE_ADDR", "")
    identity = hashlib.sha256(f"{request.user.pk}:{remote}:{action}".encode()).hexdigest()
    return not any(
        cache.add(f"private-access:{identity}:{slot}", 1, timeout=window)
        for slot in range(quota)
    )


def _check_throttle(request, action):
    try:
        if _throttle(request, action):
            response = JsonResponse({"error": "rate_limited"}, status=429)
            response["Retry-After"] = str(getattr(settings, "VISUAL_SEARCH_PRIVATE_ACCESS_RATE_WINDOW", 3600))
            return response
    except Exception:
        logger.exception("Private access limiter unavailable")
        return JsonResponse({"error": "unavailable"}, status=503)
    return None


@login_required
@require_POST
def issue_private_invitation(request, gallery_id):
    if not _enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    blocked = _check_throttle(request, "issue")
    if blocked is not None:
        return blocked
    gallery = Gallery.objects.filter(pk=gallery_id, photographer__user=request.user).first()
    if gallery is None:
        return JsonResponse({"error": "not_found"}, status=404)
    if not _eligible(gallery):
        return JsonResponse({"error": "not_available"}, status=400)
    invitation, token = PrivateGalleryInvitation.issue(gallery=gallery, user=request.user)
    return JsonResponse({"invitation_id": invitation.pk, "token": token, "expires_at": invitation.expires_at.isoformat()}, status=201)


@login_required
@require_POST
def revoke_private_invitation(request, invitation_id):
    if not _enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    blocked = _check_throttle(request, "revoke")
    if blocked is not None:
        return blocked
    invitation = PrivateGalleryInvitation.objects.filter(
        pk=invitation_id, gallery__photographer__user=request.user,
    ).first()
    if invitation is None:
        return JsonResponse({"error": "not_found"}, status=404)
    if invitation.revoked_at is None:
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at"])
    return JsonResponse({"revoked": True})


@login_required
@require_POST
def submit_private_request(request):
    if not _enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    blocked = _check_throttle(request, "submit")
    if blocked is not None:
        return blocked
    data = _payload(request)
    token = data.get("invitation_token")
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        return JsonResponse(GENERIC, status=202)
    invitation = PrivateGalleryInvitation.objects.select_related("gallery").filter(
        token_hash=token_digest(token), revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if (invitation and _eligible(invitation.gallery)
            and invitation.created_by_id != request.user.pk
            and request.user.email_verified and request.user.can_login):
        PrivateGalleryAccessRequest.objects.get_or_create(invitation=invitation, requester=request.user)
    return JsonResponse(GENERIC, status=202)


@login_required
@require_GET
def private_request_inbox(request):
    if not _enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    if not hasattr(request.user, "photographer_profile"):
        return JsonResponse({"results": []})
    records = PrivateGalleryAccessRequest.objects.filter(
        invitation__gallery__photographer__user=request.user,
    ).select_related("requester", "invitation").order_by("-created_at")[:100]
    return JsonResponse({"results": [
        {"id": item.pk, "gallery_id": item.invitation.gallery_id,
         "requester_email": item.requester.email, "status": item.status,
         "created_at": item.created_at.isoformat()}
        for item in records
    ]})


@login_required
@require_POST
def review_private_request(request, request_id):
    if not _enabled():
        return JsonResponse({"error": "unavailable"}, status=503)
    blocked = _check_throttle(request, "review")
    if blocked is not None:
        return blocked
    decision = _payload(request).get("decision")
    if decision not in ("approved", "denied"):
        return JsonResponse({"error": "invalid_decision"}, status=400)
    with transaction.atomic():
        item = PrivateGalleryAccessRequest.objects.select_for_update().select_related(
            "invitation__gallery__photographer", "requester",
        ).filter(pk=request_id, invitation__gallery__photographer__user=request.user).first()
        if item is None:
            return JsonResponse({"error": "not_found"}, status=404)
        gallery = item.invitation.gallery
        if (not _eligible(gallery) or item.invitation.revoked_at
                or item.invitation.expires_at <= timezone.now()):
            return JsonResponse({"error": "not_available"}, status=400)
        if item.status != PrivateGalleryAccessRequest.Status.PENDING:
            return JsonResponse({"error": "already_reviewed"}, status=409)
        if decision == "approved":
            if not item.requester.email_verified or not item.requester.can_login:
                return JsonResponse({"error": "requester_unverified"}, status=400)
            # Reuse the established gallery invitation and revocable AccessToken
            # mechanisms; do not invent a new access bypass.
            invitation, _ = GalleryInvitation.objects.get_or_create(
                gallery=gallery, email=item.requester.email,
                defaults={"client_name": item.requester.display_name()[:160]},
            )
            if invitation.status == GalleryInvitation.Status.DISABLED:
                return JsonResponse({"error": "invitation_disabled"}, status=409)
            token_record, raw_token = AccessToken.issue(invitation, expires_at=gallery.expires_at)
            try:
                send_gallery_invitation_email(request, invitation=invitation, raw_token=raw_token)
            except GalleryInvitationDeliveryError:
                # Transaction rollback removes the undelivered token and
                # leaves the request pending for a safe retry.
                transaction.set_rollback(True)
                return JsonResponse({"error": "delivery_failed"}, status=503)
            invitation.access_tokens.filter(revoked_at__isnull=True).exclude(
                pk=token_record.pk
            ).update(revoked_at=timezone.now())
        item.status = decision
        item.reviewed_at = timezone.now()
        item.save(update_fields=["status", "reviewed_at"])
    return JsonResponse({"status": decision, "access_granted": decision == "approved"})
