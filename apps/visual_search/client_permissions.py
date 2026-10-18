"""Authenticated client-controlled permissions for ephemeral public selfie search.

Collection is separately disabled until an approved notice/policy is deployed.
Withdrawal is always available, including when search is disabled.
"""
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import ClientSelfieSearchPermission, ClientBiometricDeletionRequest

PURPOSE = "public_gallery_selfie_search"


def active_client_permission(user):
    if not user.is_authenticated:
        return False
    version = getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION", "")
    return bool(version) and ClientSelfieSearchPermission.objects.filter(
        user=user, purpose=PURPOSE, policy_version=version,
        withdrawn_at__isnull=True,
    ).exists()


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def client_selfie_permission(request):
    if request.method == "GET":
        return JsonResponse({"purpose": PURPOSE, "authorized": active_client_permission(request.user)})
    if request.method == "DELETE":
        # Lock the user row to serialize grant/withdraw requests for this account.
        with transaction.atomic():
            type(request.user).objects.select_for_update().get(pk=request.user.pk)
            count = ClientSelfieSearchPermission.objects.filter(
                user=request.user, purpose=PURPOSE, withdrawn_at__isnull=True,
            ).update(withdrawn_at=timezone.now())
        # Selfie queries are processed in-memory and are not stored as a
        # per-client vector index. No client-vector deletion is claimed here.
        return JsonResponse({"authorized": False, "withdrawn": bool(count)})

    if not getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    version = getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION", "")
    if not version or not getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_NOTICE_URL", ""):
        return JsonResponse({"error": "unavailable"}, status=503)
    if ClientBiometricDeletionRequest.objects.filter(
        user=request.user, status__in=[
            ClientBiometricDeletionRequest.Status.PENDING,
            ClientBiometricDeletionRequest.Status.IN_REVIEW,
        ],
    ).exists():
        return JsonResponse({"error": "deletion_request_pending"}, status=409)
    if not getattr(request.user, "email_verified", False):
        return JsonResponse({"error": "account_not_verified"}, status=403)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        payload = {}
    if not isinstance(payload, dict) or payload.get("purpose") != PURPOSE or payload.get("policy_version") != version or payload.get("agree") is not True:
        return JsonResponse({"error": "explicit_authorization_required"}, status=400)
    with transaction.atomic():
        type(request.user).objects.select_for_update().get(pk=request.user.pk)
        if ClientBiometricDeletionRequest.objects.filter(
            user=request.user, status__in=[
                ClientBiometricDeletionRequest.Status.PENDING,
                ClientBiometricDeletionRequest.Status.IN_REVIEW,
            ],
        ).exists():
            return JsonResponse({"error": "deletion_request_pending"}, status=409)
        existing = ClientSelfieSearchPermission.objects.filter(
            user=request.user, purpose=PURPOSE, withdrawn_at__isnull=True,
        ).first()
        if existing and existing.policy_version != version:
            existing.withdrawn_at = timezone.now()
            existing.save(update_fields=["withdrawn_at"])
            existing = None
        if existing is None:
            ClientSelfieSearchPermission.objects.create(
                user=request.user, purpose=PURPOSE,
                policy_version=version, granted_at=timezone.now(),
            )
    return JsonResponse({"purpose": PURPOSE, "authorized": True, "policy_version": version})


@login_required
@ensure_csrf_cookie
@require_http_methods(["GET"])
def client_selfie_permission_page(request):
    """Self-service privacy controls; withdrawal remains accessible when disabled."""
    version = getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION", "")
    enrollment_enabled = bool(
        getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED", False)
        and version
        and getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_NOTICE_URL", "")
    )
    return render(request, "visual_search/client_selfie_permission.html", {
        "authorized": active_client_permission(request.user),
        "policy_version": version,
        "enrollment_enabled": enrollment_enabled,
        "notice_url": getattr(settings, "VISUAL_SEARCH_CLIENT_CONSENT_NOTICE_URL", ""),
    })


@login_required
@require_http_methods(["GET", "POST"])
def client_biometric_deletion(request):
    """User-scoped erasure request, not an unverified vector-delete operation."""
    if request.method == "GET":
        latest = ClientBiometricDeletionRequest.objects.filter(
            user=request.user,
        ).order_by("-requested_at").first()
        return JsonResponse({
            "status": latest.status if latest else "not_requested",
        })
    with transaction.atomic():
        type(request.user).objects.select_for_update().get(pk=request.user.pk)
        ClientSelfieSearchPermission.objects.filter(
            user=request.user, purpose=PURPOSE, withdrawn_at__isnull=True,
        ).update(withdrawn_at=timezone.now())
        pending = ClientBiometricDeletionRequest.objects.filter(
            user=request.user,
            status__in=[
                ClientBiometricDeletionRequest.Status.PENDING,
                ClientBiometricDeletionRequest.Status.IN_REVIEW,
            ],
        ).order_by("-requested_at").first()
        if pending is None:
            pending = ClientBiometricDeletionRequest.objects.create(user=request.user)
    return JsonResponse({"status": pending.status, "request_id": pending.pk}, status=202)
