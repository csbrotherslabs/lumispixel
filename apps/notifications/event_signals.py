"""Connect persisted application events to the existing notification inbox."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.models import Subscription
from apps.clients.models import ClientSession, ClientInvoice, Contract, InvoicePayment, Lead
from apps.dashboard.models import StudioInvitationEvent
from apps.galleries.models import GalleryAnalyticsEvent, GalleryActivity, GalleryMultipartUpload, GalleryPhoto
from apps.internal_ops.models import SupportTicket, SupportTicketComment
from .events import emit, owner_event
from .models import Notification

TRACKED = (ClientSession, ClientInvoice, Contract, InvoicePayment, Subscription, SupportTicket, User, GalleryPhoto, GalleryMultipartUpload)


def remember(sender, instance, raw=False, **kwargs):
    if raw:
        return
    instance._notification_saved_fields = kwargs.get("update_fields")
    fields = [name for name in ("status", "starts_at", "duration_minutes", "location", "password", "aborted_at")
              if any(f.name == name for f in sender._meta.fields)]
    instance._notification_previous = sender.objects.filter(pk=instance.pk).values(*fields).first() if instance.pk else None


for model in TRACKED:
    pre_save.connect(remember, sender=model, dispatch_uid=f"notifications.remember.{model._meta.label}")


def changed(instance, field):
    saved = getattr(instance, "_notification_saved_fields", None)
    if saved is not None and field not in saved:
        return False
    previous = getattr(instance, "_notification_previous", None)
    return previous is not None and previous.get(field) != getattr(instance, field)


def transition_key(instance, event):
    # The saved timestamp distinguishes legitimate repeated transitions.
    stamp = getattr(instance, "updated_at", None)
    return f"{instance._meta.label}:{instance.pk}:{event}:{stamp or getattr(instance, 'status', '')}"


@receiver(post_save, sender=Lead, dispatch_uid="notifications.lead")
def lead_saved(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        owner_event(instance, f"lead:{instance.pk}", "New lead", f"A new lead from {instance.first_name} is ready for follow-up.", "leads", Notification.Category.MESSAGE)


@receiver(post_save, sender=ClientSession, dispatch_uid="notifications.booking")
def booking_saved(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if created:
        event = "created"
    elif changed(instance, "status"):
        event = instance.status
    elif any(changed(instance, field) for field in ("starts_at", "duration_minutes", "location")):
        event = "rescheduled"
    else:
        return
    labels = {"created": "New booking", "confirmed": "Booking confirmed", "cancelled": "Booking cancelled", "completed": "Session completed", "tentative": "Booking awaiting confirmation", "rescheduled": "Booking rescheduled"}
    owner_event(instance, transition_key(instance, event), labels.get(event, "Booking updated"),
                f"{instance.session_type}: {instance.starts_at:%Y-%m-%d %H:%M %Z}.", "bookings", client=True)


@receiver(post_save, sender=Contract, dispatch_uid="notifications.contract")
def contract_saved(sender, instance, created, raw=False, **kwargs):
    if raw or (not created and not changed(instance, "status")) or instance.status not in {"sent", "signed", "voided"}:
        return
    owner_event(instance, transition_key(instance, instance.status), f"Contract {instance.get_status_display().lower()}",
                instance.title, "contracts", client=True)


@receiver(post_save, sender=ClientInvoice, dispatch_uid="notifications.invoice")
def invoice_saved(sender, instance, created, raw=False, **kwargs):
    if raw or (not created and not changed(instance, "status")) or instance.status not in {"sent", "void"}:
        return
    owner_event(instance, transition_key(instance, instance.status), f"Invoice {instance.get_status_display().lower()}",
                f"Invoice {instance.invoice_number or instance.pk}.", "invoices", Notification.Category.PAYMENT, client=True)


@receiver(post_save, sender=InvoicePayment, dispatch_uid="notifications.payment")
def payment_saved(sender, instance, created, raw=False, **kwargs):
    if raw or (not created and not changed(instance, "status")) or instance.status not in {"completed", "failed", "canceled"}:
        return
    if instance.invoice.photographer_id != instance.photographer_id:
        return
    owner_event(instance.invoice, transition_key(instance, instance.status), f"Payment {instance.get_status_display().lower()}",
                f"{instance.amount} {instance.invoice.currency} for invoice {instance.invoice.invoice_number or instance.invoice_id}.",
                "invoices", Notification.Category.PAYMENT, client=True)


@receiver(post_save, sender=GalleryAnalyticsEvent, dispatch_uid="notifications.gallery.client")
def gallery_client_event(sender, instance, created, raw=False, **kwargs):
    labels = {"favorite": "Photo favorited", "comment": "New photo comment", "download": "Photo downloaded", "gallery_download": "Gallery downloaded", "purchase": "Gallery purchase"}
    if raw or not created or instance.event_type not in labels or instance.photographer_id != instance.gallery.photographer_id:
        return
    if instance.authenticated_user_id == instance.photographer.user_id:
        return
    emit(recipient=instance.photographer.user, event_key=f"gallery-client:{instance.pk}", title=labels[instance.event_type],
         message=f"New client activity in {instance.gallery.name}.",
         category=Notification.Category.DOWNLOAD if "download" in instance.event_type else Notification.Category.GALLERY,
         action_url=reverse("photographer_workspace:galleries"))


@receiver(post_save, sender=GalleryActivity, dispatch_uid="notifications.gallery.upload")
def gallery_activity(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.event_type not in {"photos_uploaded", "ai_completed"} or instance.photographer_id != instance.gallery.photographer_id:
        return
    emit(recipient=instance.photographer.user, event_key=f"gallery-activity:{instance.pk}", title=instance.get_event_type_display(),
         message=instance.gallery.name, category=Notification.Category.GALLERY, action_url=reverse("photographer_workspace:galleries"))


@receiver(post_save, sender=StudioInvitationEvent, dispatch_uid="notifications.team")
def team_event(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    member = instance.membership
    if instance.action in {"sent", "resent"}:
        user = member.user or User.objects.filter(email__iexact=member.invitation_email).first()
        emit(recipient=user, event_key=f"team:{instance.pk}", title="Studio team invitation", message="You have been invited to join a photography studio.", action_url=reverse("notifications:index"))
    else:
        emit(recipient=member.studio.user, event_key=f"team:{instance.pk}", title=f"Team invitation {instance.get_action_display().lower()}", message="A studio invitation has been updated.", action_url=reverse("photographer_workspace:team_members"))


@receiver(post_save, sender=SupportTicketComment, dispatch_uid="notifications.support.reply")
def support_reply(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.is_internal or instance.author_user_id == instance.ticket.requester_id:
        return
    emit(recipient=instance.ticket.requester, event_key=f"support-reply:{instance.pk}", title="Support replied to your ticket", message=instance.ticket.subject,
         category=Notification.Category.MESSAGE, action_url=reverse("support_ticket_detail", args=[instance.ticket.reference]))


@receiver(post_save, sender=SupportTicket, dispatch_uid="notifications.support.status")
def support_status(sender, instance, created, raw=False, **kwargs):
    if raw or created or not changed(instance, "status"):
        return
    emit(recipient=instance.requester, event_key=transition_key(instance, instance.status), title=f"Support ticket {instance.get_status_display().lower()}", message=instance.subject,
         category=Notification.Category.MESSAGE, action_url=reverse("support_ticket_detail", args=[instance.reference]))


@receiver(post_save, sender=User, dispatch_uid="notifications.password")
def password_changed(sender, instance, created, raw=False, **kwargs):
    if not raw and not created and changed(instance, "password"):
        emit(recipient=instance, event_key=f"password:{instance.pk}:{instance.password}", title="Your password changed", message="Your account password was changed. Contact support if this was unexpected.", category=Notification.Category.SECURITY, action_url=reverse("support_help_center"))


@receiver(post_save, sender=Subscription, dispatch_uid="notifications.subscription")
def subscription_changed(sender, instance, created, raw=False, **kwargs):
    if not raw and not created and changed(instance, "status"):
        emit(recipient=instance.photographer.user, event_key=transition_key(instance, instance.status), title="Subscription status changed", message=f"Your subscription is {instance.get_status_display().lower()}.", category=Notification.Category.PAYMENT, action_url=reverse("photographer_workspace:billing"))


@receiver(post_save, sender=GalleryPhoto, dispatch_uid="notifications.photo.failure")
def photo_failed(sender, instance, created, raw=False, **kwargs):
    if raw or instance.status != "failed" or (not created and not changed(instance, "status")) or instance.photographer_id != instance.gallery.photographer_id:
        return
    emit(recipient=instance.photographer.user, event_key=f"photo-failed:{instance.pk}", title="Photo processing failed", message=f"A photo in {instance.gallery.name} needs attention.", category=Notification.Category.GALLERY, action_url=reverse("photographer_workspace:galleries"))


@receiver(post_save, sender=GalleryMultipartUpload, dispatch_uid="notifications.upload.stopped")
def upload_stopped(sender, instance, created, raw=False, **kwargs):
    if raw or not instance.aborted_at or (not created and not changed(instance, "aborted_at")) or instance.photographer_id != instance.gallery.photographer_id:
        return
    emit(recipient=instance.photographer.user, event_key=f"upload-stopped:{instance.pk}", title="Upload stopped", message=f"An upload in {instance.gallery.name} was cancelled or interrupted.", category=Notification.Category.GALLERY, action_url=reverse("photographer_workspace:galleries"))
