"""Queue derivative generation when photo upload becomes complete."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import GalleryPhoto


@receiver(post_save, sender=GalleryPhoto)
def queue_gallery_derivatives(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    if instance.status != GalleryPhoto.Status.COMPLETED or not instance.file:
        return
    update_fields = kwargs.get("update_fields")
    if not kwargs.get("created") and update_fields is not None and "status" not in update_fields and "file" not in update_fields:
        return
    from .tasks import generate_gallery_photo_derivatives
    photo_id = instance.pk
    # A broker outage must not turn an already committed upload into a failed
    # HTTP response. Missing derivatives can be recovered by the backfill command.
    transaction.on_commit(
        lambda: generate_gallery_photo_derivatives.delay(photo_id), robust=True
    )
