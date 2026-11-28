"""Stable integration, delivery, and storage-accounting boundaries for galleries."""
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.template.loader import render_to_string

from apps.accounts.services import build_public_url


@dataclass(frozen=True)
class IntegrationResult:
    accepted: bool
    reference: str = ""
    message: str = "Integration is not configured."


class PaymentGateway:
    def create_payment(self, order) -> IntegrationResult:
        return IntegrationResult(False)


class FulfillmentProvider:
    def submit_order(self, order) -> IntegrationResult:
        return IntegrationResult(False)


class GalleryInvitationDeliveryError(Exception):
    """Raised when a gallery invitation cannot be handed off to the email backend."""


@dataclass(frozen=True)
class StorageUsage:
    used_bytes: int
    limit_bytes: int

    @property
    def remaining_bytes(self):
        return max(0, self.limit_bytes - self.used_bytes)

    @property
    def percent_used(self):
        return 0 if not self.limit_bytes else min(100, round(self.used_bytes / self.limit_bytes * 100, 2))


def photographer_storage_usage(photographer):
    """Compute authoritative usage from persisted gallery photo byte sizes."""
    from .models import GalleryPhoto
    used = GalleryPhoto.objects.for_photographer(photographer).aggregate(total=Sum("file_size"))["total"] or 0
    return StorageUsage(int(used), settings.FREE_STORAGE_LIMIT_BYTES)


def validate_upload_quota(photographer, incoming_bytes):
    incoming_bytes = int(incoming_bytes or 0)
    if incoming_bytes <= 0:
        raise ValidationError("Upload size must be greater than zero.")
    if incoming_bytes > settings.MAX_GALLERY_UPLOAD_BYTES:
        raise ValidationError("This file exceeds the maximum permitted upload size.")
    usage = photographer_storage_usage(photographer)
    if incoming_bytes > usage.remaining_bytes:
        raise ValidationError("This upload would exceed the account's included storage limit.")
    return usage


def send_gallery_invitation_email(request, *, invitation, raw_token):
    """Send a branded client-gallery invitation using the configured Django email backend."""
    from django.urls import reverse

    gallery = invitation.gallery
    photographer = gallery.photographer
    gallery_path = reverse("galleries:client_gallery_access", args=[raw_token])
    gallery_url = build_public_url(request, gallery_path)
    studio_name = photographer.business_name or photographer.display_name or photographer.user.display_name
    context = {
        "invitation": invitation,
        "gallery": gallery,
        "gallery_url": gallery_url,
        "studio_name": studio_name,
        "brand_name": "LumisPixel",
        "site_url": build_public_url(request),
    }
    subject = f"Your {gallery.name} gallery is ready"
    text_body = render_to_string("galleries/email/client_gallery_invitation.txt", context)
    html_body = render_to_string("galleries/email/client_gallery_invitation.html", context)

    from datetime import timedelta
    from django.utils import timezone
    from django.core.exceptions import ImproperlyConfigured
    from apps.notifications.email_delivery import queue_transactional_email
    from .models import AccessToken

    token = AccessToken.objects.get(invitation=invitation, token_hash=AccessToken.digest(raw_token))
    deadline = timezone.now() + timedelta(hours=24)
    if token.expires_at:
        deadline = min(deadline, token.expires_at)
    try:
        delivery = queue_transactional_email(
            event_key=f"gallery.invite:{invitation.pk}:{token.pk}",
            subject=subject, plain_body=text_body, html_body=html_body,
            recipients=[invitation.email], sensitive=True, expires_at=deadline,
            lifecycle_kind="gallery.invite",
            lifecycle_context={"token_id": token.pk, "invitation_id": invitation.pk},
            supersession_scope=f"gallery.invite:{invitation.pk}",
        )
        if not delivery:
            raise ValueError("Missing recipient")
    except (ValueError, ValidationError, ImproperlyConfigured) as exc:
        raise GalleryInvitationDeliveryError("Gallery invitation could not be queued.") from exc
    return gallery_url
