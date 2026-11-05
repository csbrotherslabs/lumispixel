"""Non-biometric, photographer-issued private gallery access requests.

An invitation is an opaque bearer capability distributed out of band.
It is never generated from, linked to, or returned by face matching.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PrivateGalleryInvitation(models.Model):
    gallery = models.ForeignKey("galleries.Gallery", on_delete=models.CASCADE, related_name="private_access_invitations")
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, *, gallery, user, hours=48):
        token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            gallery=gallery, created_by=user, token_hash=token_digest(token),
            expires_at=timezone.now() + timedelta(hours=hours),
        )
        return invitation, token


class PrivateGalleryAccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    invitation = models.ForeignKey(PrivateGalleryInvitation, on_delete=models.CASCADE, related_name="requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="private_gallery_access_requests")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invitation", "requester"], name="private_access_one_request_per_invite"),
        ]
