"""Deletion-only discovery consent; disabled until legal and privacy approval."""
import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import ClientBiometricDeletionRequest, BiometricDeletionDiscoveryGrant


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def deletion_discovery_permission(request):
    deletion = ClientBiometricDeletionRequest.objects.filter(
        user=request.user, status__in=["pending", "in_review"],
    ).order_by("-requested_at").first()
    if deletion is None:
        return JsonResponse({"error": "deletion_request_required"}, status=404)
    if request.method == "GET":
        grant = BiometricDeletionDiscoveryGrant.objects.filter(request=deletion).first()
        return JsonResponse({"authorized": bool(grant and grant.active)})
    if request.method == "DELETE":
        BiometricDeletionDiscoveryGrant.objects.filter(
            request=deletion, withdrawn_at__isnull=True,
        ).update(withdrawn_at=timezone.now())
        return JsonResponse({"authorized": False})
    if not getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_LEGAL_APPROVED", False):
        return JsonResponse({"error": "legal_review_required"}, status=503)
    if not getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_ENABLED", False):
        return JsonResponse({"error": "unavailable"}, status=503)
    version = getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_POLICY_VERSION", "")
    notice = getattr(settings, "VISUAL_SEARCH_DELETION_DISCOVERY_NOTICE_URL", "")
    if not version or not notice:
        return JsonResponse({"error": "notice_not_configured"}, status=503)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_request"}, status=400)
    if not isinstance(data, dict) or data.get("agree") is not True or data.get("policy_version") != version:
        return JsonResponse({"error": "explicit_permission_required"}, status=400)
    with transaction.atomic():
        grant, _ = BiometricDeletionDiscoveryGrant.objects.update_or_create(
            request=deletion,
            defaults={
                "policy_version": version,
                "authorized_at": timezone.now(),
                "withdrawn_at": None,
            },
        )
    return JsonResponse({"authorized": True, "request_id": deletion.pk})
