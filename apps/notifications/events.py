"""Recipient-scoped, transaction-safe inbox events with durable deduplication."""
import hashlib

from django.db import transaction

from .models import Notification, NotificationEventReceipt


def emit(*, recipient, event_key, title, message, category=Notification.Category.SYSTEM, action_url=""):
    if not recipient or not recipient.is_active:
        return None
    key = hashlib.sha256(event_key.encode()).hexdigest()
    with transaction.atomic():
        receipt, created = NotificationEventReceipt.objects.get_or_create(recipient=recipient, event_key=key)
        if not created:
            return receipt.notification
        notification = Notification.objects.create(
            recipient=recipient, title=title[:160], message=message[:1000],
            category=category, action_url=action_url, action_label="View details" if action_url else "",
        )
        receipt.notification = notification
        receipt.save(update_fields=["notification"])
        return notification


def owner_event(obj, event_key, title, message, module, category=Notification.Category.SYSTEM, client=False):
    from django.urls import reverse
    owner = obj.photographer
    emit(recipient=owner.user, event_key=event_key, title=title, message=message,
         category=category, action_url=reverse(f"photographer_workspace:{module}"))
    if client and obj.client_id and obj.client.photographer_id == obj.photographer_id and obj.client.user_id:
        emit(recipient=obj.client.user, event_key=event_key, title=title, message=message,
             category=category, action_url=reverse("clients:dashboard"))
