"""Stable integration and storage-accounting boundaries for galleries."""
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum


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
