"""Durable biometric purge requests for gallery and photo lifecycle changes."""
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from apps.galleries.models import Gallery, GalleryPhoto
from .models import GalleryFaceSearchPolicy, FaceIndexJob

def _queue_purge(kind, object_id):
    from .purges import enqueue_purge
    enqueue_purge(kind, object_id)


@receiver(post_delete, sender=GalleryPhoto)
def photo_deleted(sender, instance, **kwargs):
    _queue_purge("photo", instance.pk)


@receiver(post_delete, sender=Gallery)
def gallery_deleted(sender, instance, **kwargs):
    _queue_purge("gallery", instance.pk)


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
        _queue_purge("gallery", instance.gallery_id)


@receiver(post_save, sender=Gallery)
def gallery_inactive(sender, instance, **kwargs):
    if instance.deleted_at or instance.archived_at:
        _queue_purge("gallery", instance.pk)


@receiver(post_save, sender=GalleryPhoto)
def photo_inactive(sender, instance, **kwargs):
    if instance.status != GalleryPhoto.Status.COMPLETED:
        _queue_purge("photo", instance.pk)
