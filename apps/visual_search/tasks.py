"""Worker entry point. Inference is intentionally disabled until separately implemented."""

from celery import shared_task
from django.db import transaction

from apps.galleries.models import GalleryPhoto
from .models import FaceIndexJob, GalleryFaceSearchPolicy


@shared_task
def process_face_index_job(job_id):
    # This first milestone creates durable jobs only. Do not claim completion
    # or fetch/process biometric data until a reviewed inference worker exists.
    with transaction.atomic():
        job = FaceIndexJob.objects.select_for_update().select_related("photo__gallery").filter(pk=job_id).first()
        if not job or job.status != FaceIndexJob.Status.PENDING:
            return "not_pending"
        photo = job.photo
        if (
            photo.status != GalleryPhoto.Status.COMPLETED
            or photo.gallery.deleted_at
            or photo.gallery.archived_at
            or photo.file.name != job.source_key
            or not GalleryFaceSearchPolicy.objects.filter(
                gallery_id=photo.gallery_id, processing_authorized=True
            ).exists()
        ):
            job.status = FaceIndexJob.Status.CANCELLED
            job.save(update_fields=["status", "updated_at"])
            return "cancelled"
    return "awaiting_inference_worker"
