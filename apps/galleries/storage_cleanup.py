import logging

from django.conf import settings
from django.utils import timezone

from .models import GalleryStorageDeletion
from .multipart_uploads import delete_object as delete_b2_object

logger = logging.getLogger(__name__)


def enqueue_storage_deletions(items):
    """Persist object cleanup intent before database records lose file references."""
    rows = []
    seen = set()
    for item in items:
        key = (item["storage_backend"], item["object_key"])
        if not item["object_key"] or key in seen:
            continue
        seen.add(key)
        rows.append(GalleryStorageDeletion(
            storage_backend=item["storage_backend"],
            object_key=item["object_key"],
            photographer_id=item.get("photographer_id"),
            gallery_id=item.get("gallery_id"),
        ))
    if rows:
        GalleryStorageDeletion.objects.bulk_create(rows, ignore_conflicts=True)
    return rows


def process_storage_deletions(*, limit=200, max_attempts=None):
    max_attempts = max_attempts or settings.GALLERY_STORAGE_DELETION_MAX_ATTEMPTS
    pending = GalleryStorageDeletion.objects.filter(
        completed_at__isnull=True,
        attempts__lt=max_attempts,
    ).order_by("created_at")[:limit]
    completed = failed = 0
    for deletion in pending:
        try:
            if deletion.storage_backend == GalleryStorageDeletion.Backend.B2:
                delete_b2_object(key=deletion.object_key)
            else:
                from django.core.files.storage import default_storage
                default_storage.delete(deletion.object_key)
        except Exception as exc:
            failed += 1
            deletion.attempts += 1
            # Persist a safe diagnostic category, never provider exception text;
            # SDK errors can contain bucket names, endpoints, request IDs, or credentials.
            deletion.last_error = exc.__class__.__name__[:1000]
            deletion.last_attempt_at = timezone.now()
            deletion.save(update_fields=["attempts", "last_error", "last_attempt_at"])
            logger.exception("Storage deletion failed for %s", deletion.object_key)
            continue
        deletion.attempts += 1
        deletion.last_error = ""
        deletion.last_attempt_at = deletion.completed_at = timezone.now()
        deletion.save(update_fields=["attempts", "last_error", "last_attempt_at", "completed_at"])
        completed += 1
    exhausted = GalleryStorageDeletion.objects.filter(
        completed_at__isnull=True,
        attempts__gte=max_attempts,
    ).count()
    return {"completed": completed, "failed": failed, "exhausted": exhausted}
