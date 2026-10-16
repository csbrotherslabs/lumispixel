"""Consent-gated face indexing with stale-worker recovery and serialized writes."""
import logging
from uuid import uuid4
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.galleries.models import GalleryPhoto
from .models import FaceIndexJob, GalleryFaceSearchPolicy

logger = logging.getLogger(__name__)


def _eligible(job):
    photo = job.photo
    return (
        settings.VISUAL_SEARCH_FACE_INDEXING_ENABLED
        and photo.status == GalleryPhoto.Status.COMPLETED
        and photo.gallery.deleted_at is None
        and photo.gallery.archived_at is None
        and bool(photo.file)
        and photo.file.name == job.source_key
        and GalleryFaceSearchPolicy.objects.filter(
            gallery_id=photo.gallery_id, processing_authorized=True
        ).exists()
    )


@shared_task(bind=True, max_retries=3)
def process_face_index_job(self, job_id):
    with transaction.atomic():
        job = (FaceIndexJob.objects.select_for_update()
               .select_related("photo__gallery").filter(pk=job_id).first())
        if not job or job.status != FaceIndexJob.Status.PENDING:
            return "not_pending"
        if not _eligible(job):
            job.status = FaceIndexJob.Status.CANCELLED
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "finished_at", "updated_at"])
            return "cancelled"
        token = uuid4()
        job.claim_token = token
        job.status = FaceIndexJob.Status.PROCESSING
        job.attempts += 1
        job.started_at = timezone.now()
        job.save(update_fields=["status", "claim_token", "attempts", "started_at", "updated_at"])

    try:
        from .inference import extract_face_embeddings
        from .vector_store import replace_embeddings

        with job.photo.file.open("rb") as stream:
            vectors = extract_face_embeddings(stream)

        with transaction.atomic():
            current = (FaceIndexJob.objects.select_for_update()
                       .select_related("photo__gallery").get(pk=job_id))
            if current.status != FaceIndexJob.Status.PROCESSING or current.claim_token != token:
                return "superseded"
            # Lock policy to serialize authorization changes with the vector write.
            policy = (GalleryFaceSearchPolicy.objects.select_for_update()
                      .filter(gallery_id=current.photo.gallery_id).first())
            if not policy or not policy.processing_authorized or not _eligible(current):
                current.status = FaceIndexJob.Status.CANCELLED
                current.finished_at = timezone.now()
                current.save(update_fields=["status", "finished_at", "updated_at"])
                return "cancelled"
            replace_embeddings(
                photo_id=current.photo_id,
                gallery_id=current.photo.gallery_id,
                photographer_id=current.photo.photographer_id,
                source_version=current.source_version,
                model_version=current.model_version,
                vectors=vectors,
            )
            current.status = FaceIndexJob.Status.COMPLETED
            current.finished_at = timezone.now()
            current.last_error = ""
            current.save(update_fields=["status", "finished_at", "last_error", "updated_at"])
        return {"faces": len(vectors)}
    except Exception as exc:
        logger.exception("Face index job %s failed", job_id)
        with transaction.atomic():
            current = FaceIndexJob.objects.select_for_update().filter(pk=job_id).first()
            if current and current.status == FaceIndexJob.Status.PROCESSING and current.claim_token == token:
                current.status = (FaceIndexJob.Status.PENDING if self.request.retries < self.max_retries
                                  else FaceIndexJob.Status.FAILED)
                current.claim_token = None
                current.last_error = str(exc)[:1000]
                current.save(update_fields=["status", "claim_token", "last_error", "updated_at"])
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(60 * (2 ** self.request.retries), 300))
        return "failed"


@shared_task
def reconcile_face_index():
    """Recover interrupted jobs and remove vectors without valid consent or photos."""
    if not settings.VISUAL_SEARCH_DATABASE_URL:
        return "not_configured"
    from .maintenance import reconcile
    return reconcile()


@shared_task
def process_vector_purge(purge_id):
    from .purges import execute_purge
    return execute_purge(purge_id)


@shared_task
def reconcile_vector_purges():
    from .purges import recover_and_dispatch_purges
    return recover_and_dispatch_purges()
