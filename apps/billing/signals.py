from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import PhotographerProfile

from .services import ensure_subscription


@receiver(post_save, sender=PhotographerProfile)
def provision_free_subscription(sender, instance, created, **kwargs):
    if created:
        ensure_subscription(instance)
