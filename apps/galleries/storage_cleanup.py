import logging

from django.conf import settings
from django.utils import timezone

from .models import GalleryStorageDeletion
from .object_keys import validate_gallery_object_key, validate_relative_gallery_name
from .multipart_uploads import delete_object as delete_b2_object

logger = logging.getLogger(__name__)


def enqueue_storage_deletions(items):
    """Persist object cleanup intent before database records lose file references."""
    rows = []
    seen = set()
    for item in items:
        object_key = item["object_key"]
        if object_key and item["storage_backend"] == GalleryStorageDeletion.Backend.B2:
            if not object_key.startswith("private/"):
                object_key = f"private/{settings.GALLERY_STORAGE_ENVIRONMENT}/{validate_relative_gallery_name(object_key)}"
            validate_gallery_object_key(object_key)
        key = (item["storage_backend"], object_key)
        if not item["object_key"] or key in seen:
            continue
        seen.add(key)
        rows.append(GalleryStorageDeletion(
            storage_backend=item["storage_backend"],
            object_key=object_key,
            photographer_id=item.get("photographer_id"),
            gallery_id=item.get("gallery_id"),
        ))
    # Derivatives share the original's lifecycle. Queue their deletion with
    # the original; missing objects are harmless to the S3 delete operation.
    extra = []
    for row in rows:
        if row.storage_backend != GalleryStorageDeletion.Backend.B2:
            continue
        if "/originals/" not in row.object_key:
            continue
        stem = row.object_key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        prefix = row.object_key.rsplit("/originals/", 1)[0]
        for variant in ("thumbnail", "preview"):
            derivative_key = f"{prefix}/variants/{variant}/{stem}.webp"
            key = (row.storage_backend, derivative_key)
            if key not in seen:
                seen.add(key)
                extra.append(GalleryStorageDeletion(
                    storage_backend=row.storage_backend,
                    object_key=derivative_key,
                    photographer_id=row.photographer_id,
                    gallery_id=row.gallery_id,
                ))
    rows.extend(extra)
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
                validate_gallery_object_key(deletion.object_key)
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
