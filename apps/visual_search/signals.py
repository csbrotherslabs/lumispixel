"""Best-effort immediate purges, backed by periodic reconciliation."""
import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from apps.galleries.models import Gallery, GalleryPhoto
from .models import GalleryFaceSearchPolicy, FaceIndexJob

logger = logging.getLogger(__name__)


def _purge_photo(photo_id):
    from .vector_store import delete_photo_embeddings
    try:
        delete_photo_embeddings(photo_id)
    except Exception:
        logger.exception("Face purge failed for photo %s", photo_id)


def _purge_gallery(gallery_id):
    from .vector_store import delete_gallery_embeddings
    try:
        delete_gallery_embeddings(gallery_id)
    except Exception:
        logger.exception("Face purge failed for gallery %s", gallery_id)


@receiver(post_delete, sender=GalleryPhoto)
def photo_deleted(sender, instance, **kwargs):
    transaction.on_commit(lambda photo_id=instance.pk: _purge_photo(photo_id))


@receiver(post_delete, sender=Gallery)
def gallery_deleted(sender, instance, **kwargs):
    transaction.on_commit(lambda gallery_id=instance.pk: _purge_gallery(gallery_id))


@receiver(pre_save, sender=GalleryFaceSearchPolicy)
def discovery_requires_consent(sender, instance, **kwargs):
    if not instance.processing_authorized:
        instance.global_discovery_enabled = False


@receiver(post_save, sender=GalleryFaceSearchPolicy)
def processing_revoked(sender, instance, **kwargs):
    if not instance.processing_authorized:
        FaceIndexJob.objects.filter(
            photo__gallery_id=instance.gallery_id,
            status__in=[FaceIndexJob.Status.PENDING, FaceIndexJob.Status.PROCESSING],
        ).update(status=FaceIndexJob.Status.CANCELLED)
        transaction.on_commit(lambda gallery_id=instance.gallery_id: _purge_gallery(gallery_id))


@receiver(post_save, sender=Gallery)
def gallery_inactive(sender, instance, **kwargs):
    if instance.deleted_at or instance.archived_at:
        transaction.on_commit(lambda gallery_id=instance.pk: _purge_gallery(gallery_id))


@receiver(post_save, sender=GalleryPhoto)
def photo_inactive(sender, instance, **kwargs):
    if instance.status != GalleryPhoto.Status.COMPLETED:
        transaction.on_commit(lambda photo_id=instance.pk: _purge_photo(photo_id))
