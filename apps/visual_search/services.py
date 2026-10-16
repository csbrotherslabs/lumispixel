"""Durable scheduling shared by web and future mobile upload entry points."""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.galleries.models import GalleryPhoto
from .models import FaceIndexJob, GalleryFaceSearchPolicy

logger = logging.getLogger(__name__)


def schedule_face_indexing(photo_id):
    """Record an idempotent job only when biometric processing was authorized.

    Call inside the same transaction as photo creation when possible. No broker
    communication occurs until the outermost transaction has committed.
    """
    if not getattr(settings, "VISUAL_SEARCH_FACE_INDEXING_ENABLED", False):
        return None
    photo = GalleryPhoto.objects.select_related("gallery").filter(pk=photo_id).first()
    if not photo or photo.status != GalleryPhoto.Status.COMPLETED or not photo.file:
        return None
    if photo.gallery.deleted_at or photo.gallery.archived_at:
        return None
    if not GalleryFaceSearchPolicy.objects.filter(
        gallery_id=photo.gallery_id, processing_authorized=True
    ).exists():
        return None
    job, created = FaceIndexJob.objects.get_or_create(
        photo=photo,
        source_version=1,
        model_version=getattr(settings, "VISUAL_SEARCH_FACE_MODEL_VERSION", "arcface-buffalo-l-v1"),
        defaults={"source_key": photo.file.name},
    )
    if created or job.status == FaceIndexJob.Status.PENDING:
        transaction.on_commit(lambda job_id=job.pk: dispatch_face_index_job(job_id))
    return job


def dispatch_face_index_job(job_id):
    """Broker failures never invalidate a completed photo upload; jobs remain pending."""
    from .tasks import process_face_index_job

    try:
        process_face_index_job.delay(job_id)
    except Exception:
        logger.exception("Face indexing dispatch failed; pending job %s is recoverable", job_id)
