"""Staff-only scope attestation after manual legal and operational verification."""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ClientBiometricDeletionRequest
from .deletion_service import try_complete_deletion


@staff_member_required
@require_POST
def attest_deletion_scope(request, deletion_id):
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_request"}, status=400)
    if not isinstance(payload, dict) or payload.get("scope_verified") is not True:
        return JsonResponse({"error": "explicit_attestation_required"}, status=400)
    note = payload.get("scope_note")
    if not isinstance(note, str) or not 20 <= len(note.strip()) <= 2000:
        return JsonResponse({"error": "scope_note_required"}, status=400)
    with transaction.atomic():
        item = ClientBiometricDeletionRequest.objects.select_for_update().filter(
            pk=deletion_id, status__in=["pending", "in_review"],
        ).first()
        if item is None:
            return JsonResponse({"error": "not_found"}, status=404)
        item.scope_verified_by = request.user
        item.scope_verified_at = timezone.now()
        item.resolution_note = note.strip()
        item.save(update_fields=[
            "scope_verified_by", "scope_verified_at", "resolution_note",
        ])
    completed = try_complete_deletion(deletion_id)
    return JsonResponse({
        "completed": completed,
        "status": "completed" if completed else "in_review",
        "message": "Scope attested; unresolved gallery reviews or erasures prevent closure." if not completed else "Verified scoped deletion complete.",
    })
