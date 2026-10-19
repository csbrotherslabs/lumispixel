"""Semantic indexing is independently gated; jobs are idempotent and recoverable."""
import logging
from celery import shared_task
from django.conf import settings
from django.db import transaction
from apps.galleries.models import Gallery, GalleryPhoto
from .models import GallerySemanticSearchPolicy, SemanticIndexJob
from .semantic import semantic_enabled, embed_image, replace_photo, purge_gallery, purge_photo

logger = logging.getLogger(__name__)

def authorized(photo):
    return bool(
        semantic_enabled()
        and getattr(settings, "VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED", False)
        and photo.status == GalleryPhoto.Status.COMPLETED
        and photo.file
        and not photo.gallery.deleted_at
        and not photo.gallery.archived_at
        and GallerySemanticSearchPolicy.objects.filter(
            gallery_id=photo.gallery_id, processing_authorized=True
        ).exists()
    )

def schedule_semantic_photo(photo_id):
    if not semantic_enabled() or not getattr(settings, "VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED", False):
        return None
    photo = GalleryPhoto.objects.select_related("gallery").filter(pk=photo_id).first()
    if not photo or not authorized(photo):
        return None
    version = getattr(settings, "VISUAL_SEARCH_SEMANTIC_MODEL_VERSION", "clip-v1")
    job, _ = SemanticIndexJob.objects.get_or_create(
        photo=photo, model_version=version, source_key=photo.file.name,
    )
    if job.status != "completed":
        transaction.on_commit(lambda pk=job.pk: dispatch_semantic_job(pk))
    return job

def dispatch_semantic_job(job_id):
    try:
        index_semantic_photo.delay(job_id)
    except Exception:
        logger.exception("Semantic job %s remains recoverable", job_id)

@shared_task(bind=True, max_retries=5)
def index_semantic_photo(self, job_id):
    with transaction.atomic():
        job = SemanticIndexJob.objects.select_for_update().select_related("photo__gallery").filter(pk=job_id).first()
        if not job or job.status == "completed":
            return "already_completed"
        if not authorized(job.photo) or job.photo.file.name != job.source_key:
            job.status = "cancelled"
            job.save(update_fields=["status"])
            return "cancelled"
        job.status = "processing"
        job.save(update_fields=["status"])
    try:
        with job.photo.file.open("rb") as stream:
            vector = embed_image(stream)
        # Serialize authorization changes and vector writes with the policy row.
        with transaction.atomic():
            policy = GallerySemanticSearchPolicy.objects.select_for_update().get(gallery_id=job.photo.gallery_id)
            job.refresh_from_db()
            job.photo.refresh_from_db()
            if not policy.processing_authorized or not authorized(job.photo) or job.photo.file.name != job.source_key:
                job.status = "cancelled"
                job.save(update_fields=["status"])
                return "cancelled"
            replace_photo(photo=job.photo, vector=vector)
            job.status = "completed"
            job.save(update_fields=["status"])
        return "indexed"
    except Exception as exc:
        SemanticIndexJob.objects.filter(pk=job_id).update(status="pending")
        if self.request.retries >= self.max_retries:
            SemanticIndexJob.objects.filter(pk=job_id).update(status="failed")
            raise
        raise self.retry(exc=exc, countdown=min(60 * 2 ** self.request.retries, 3600))

@shared_task
def index_semantic_gallery(gallery_id):
    if not semantic_enabled() or not getattr(settings, "VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED", False):
        return "disabled"
    gallery = Gallery.objects.filter(pk=gallery_id, deleted_at__isnull=True, archived_at__isnull=True).first()
    if not gallery or not GallerySemanticSearchPolicy.objects.filter(gallery=gallery, processing_authorized=True).exists():
        return "unauthorized"
    count = 0
    for photo_id in GalleryPhoto.objects.filter(
        gallery=gallery, status=GalleryPhoto.Status.COMPLETED
    ).exclude(file="").values_list("pk", flat=True).iterator():
        if schedule_semantic_photo(photo_id):
            count += 1
    return count

@shared_task(bind=True, max_retries=5)
def purge_semantic_gallery(self, gallery_id):
    try:
        purge_gallery(gallery_id)
        SemanticIndexJob.objects.filter(photo__gallery_id=gallery_id).exclude(status="cancelled").update(status="cancelled")
        return "purged"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(60 * 2 ** self.request.retries, 3600))

@shared_task(bind=True, max_retries=5)
def purge_semantic_photo(self, photo_id):
    try:
        purge_photo(photo_id)
        SemanticIndexJob.objects.filter(photo_id=photo_id).exclude(status="cancelled").update(status="cancelled")
        return "purged"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(60 * 2 ** self.request.retries, 3600))
