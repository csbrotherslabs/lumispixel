"""Queue derivative generation when photo upload becomes complete."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import GalleryPhoto


@receiver(post_save, sender=GalleryPhoto)
def queue_gallery_derivatives(sender, instance, **kwargs):
    if instance.status != GalleryPhoto.Status.COMPLETED or not instance.file:
        return
    from .tasks import generate_gallery_photo_derivatives
    photo_id = instance.pk
    transaction.on_commit(lambda: generate_gallery_photo_derivatives.delay(photo_id))
