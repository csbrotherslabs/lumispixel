from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from apps.accounts.models import User
from apps.galleries.models import GalleryInvitation

from .models import Notification
from .services import notify_user


@receiver(post_save, sender=GalleryInvitation, dispatch_uid="notifications.gallery_invitation_created")
def notify_existing_client_about_gallery(sender, instance, created, **kwargs):
    if not created:
        return
    client_user = User.objects.filter(
        email__iexact=instance.email,
        primary_role=User.PrimaryRole.CLIENT,
    ).first()
    if not client_user:
        return
    photographer_name = instance.gallery.photographer.display_name or "Your photographer"
    notify_user(
        recipient=client_user,
        category=Notification.Category.GALLERY,
        title=f"{instance.gallery.title} was shared with you",
        message=f"{photographer_name} invited you to view a gallery.",
        action_url=reverse("clients:dashboard"),
        action_label="Open client dashboard",
        metadata={"gallery_id": instance.gallery_id, "invitation_id": instance.pk},
    )
