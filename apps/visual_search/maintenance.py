"""Reconcile stored vectors and recover interrupted indexing jobs."""
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.galleries.models import GalleryPhoto
from .models import FaceIndexJob


def reconcile():
    from .vector_store import vector_connection, delete_photo_embeddings
    from .services import dispatch_face_index_job
    with vector_connection() as conn:
        rows = conn.execute("SELECT DISTINCT photo_id, gallery_id FROM visual_search.app_face_embeddings").fetchall()
    removed = 0
    for photo_id, gallery_id in rows:
        if not GalleryPhoto.objects.filter(
            pk=photo_id, gallery_id=gallery_id,
            status=GalleryPhoto.Status.COMPLETED,
            gallery__deleted_at__isnull=True,
            gallery__archived_at__isnull=True,
            gallery__face_search_policy__processing_authorized=True,
        ).exists():
            delete_photo_embeddings(photo_id)
            removed += 1
    stale_before = timezone.now() - timedelta(seconds=int(settings.CELERY_TASK_TIME_LIMIT) + 300)
    recovered = 0
    with transaction.atomic():
        jobs = list(FaceIndexJob.objects.select_for_update().filter(
            status=FaceIndexJob.Status.PROCESSING, started_at__lt=stale_before
        )[:100])
        for job in jobs:
            job.status = FaceIndexJob.Status.PENDING if job.attempts < 4 else FaceIndexJob.Status.FAILED
            job.last_error = "Worker interrupted or timed out"
            job.save(update_fields=["status", "last_error", "updated_at"])
            recovered += 1
    if settings.VISUAL_SEARCH_FACE_INDEXING_ENABLED:
        ids = list(FaceIndexJob.objects.filter(status=FaceIndexJob.Status.PENDING).order_by(
            "created_at").values_list("pk", flat=True)[:100])
        for job_id in ids:
            dispatch_face_index_job(job_id)
    return {"removed_photo_vectors": removed, "recovered_jobs": recovered}
