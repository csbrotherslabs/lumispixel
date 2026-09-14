from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.clients.models import ClientInvoice, ClientSession, Contract
from apps.galleries.models import Gallery

from .models import AutomationRule
from .services import dispatch_event


def _remember_previous_status(sender, instance):
    if not instance.pk:
        instance._workflow_previous_status = None
        return
    instance._workflow_previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(pre_save, sender=ClientSession)
def workflow_session_before_save(sender, instance, **kwargs):
    _remember_previous_status(sender, instance)


@receiver(pre_save, sender=Contract)
def workflow_contract_before_save(sender, instance, **kwargs):
    _remember_previous_status(sender, instance)


@receiver(pre_save, sender=ClientInvoice)
def workflow_invoice_before_save(sender, instance, **kwargs):
    _remember_previous_status(sender, instance)


@receiver(pre_save, sender=Gallery)
def workflow_gallery_before_save(sender, instance, **kwargs):
    _remember_previous_status(sender, instance)


def _changed_to(instance, status):
    return getattr(instance, "_workflow_previous_status", None) != status and instance.status == status


@receiver(post_save, sender=ClientSession)
def workflow_session_saved(sender, instance, created, **kwargs):
    if instance.event_kind != ClientSession.EventKind.BOOKING:
        return
    if _changed_to(instance, ClientSession.Status.CONFIRMED):
        dispatch_event(
            trigger=AutomationRule.Trigger.BOOKING_CONFIRMED,
            photographer=instance.photographer,
            target=instance,
            event_key=f"booking-confirmed:{instance.pk}",
        )
    if _changed_to(instance, ClientSession.Status.COMPLETED):
        dispatch_event(
            trigger=AutomationRule.Trigger.SHOOT_COMPLETED,
            photographer=instance.photographer,
            target=instance,
            event_key=f"shoot-completed:{instance.pk}",
        )


@receiver(post_save, sender=Contract)
def workflow_contract_saved(sender, instance, created, **kwargs):
    if _changed_to(instance, Contract.Status.SIGNED):
        dispatch_event(
            trigger=AutomationRule.Trigger.CONTRACT_SIGNED,
            photographer=instance.photographer,
            target=instance,
            event_key=f"contract-signed:{instance.pk}",
        )


@receiver(post_save, sender=ClientInvoice)
def workflow_invoice_saved(sender, instance, created, **kwargs):
    if _changed_to(instance, ClientInvoice.Status.PAID):
        dispatch_event(
            trigger=AutomationRule.Trigger.PAYMENT_RECEIVED,
            photographer=instance.photographer,
            target=instance,
            event_key=f"invoice-paid:{instance.pk}",
        )


@receiver(post_save, sender=Gallery)
def workflow_gallery_saved(sender, instance, created, **kwargs):
    if _changed_to(instance, Gallery.Status.PUBLISHED):
        dispatch_event(
            trigger=AutomationRule.Trigger.GALLERY_PUBLISHED,
            photographer=instance.photographer,
            target=instance,
            event_key=f"gallery-published:{instance.pk}",
        )
