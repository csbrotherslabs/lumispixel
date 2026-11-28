"""Retire older gallery links only after verified recipient use of the latest replacement."""
import hashlib
from django.db import transaction
from django.utils import timezone
from apps.notifications.models import EmailSupersession, EmailDelivery
from .models import AccessToken, GalleryInvitation


@transaction.atomic
def activate_replacement(*, token, user):
    if not user.is_authenticated or not getattr(user, "email_verified", False):
        return False
    invitation = GalleryInvitation.objects.select_for_update().filter(pk=token.invitation_id,
        status__in=[GalleryInvitation.Status.PENDING, GalleryInvitation.Status.ACTIVE]).first()
    if not invitation or user.email.casefold() != invitation.email.casefold():
        return False
    scope = hashlib.sha256(f"gallery.invite:{invitation.pk}".encode()).hexdigest()
    pointer = EmailSupersession.objects.select_for_update().filter(scope=scope).first()
    if not pointer or not pointer.current_id:
        return False
    # The event key survives sensitive payload cleanup.
    delivery = EmailDelivery.objects.filter(pk=pointer.current_id,
        event_key=f"gallery.invite:{invitation.pk}:{token.pk}", status__in=["sent","sending","uncertain"]).first()
    if not delivery:
        return False
    now = timezone.now()
    current = AccessToken.objects.select_for_update().filter(pk=token.pk, invitation=invitation, revoked_at__isnull=True).first()
    if not current or (current.expires_at and current.expires_at <= now):
        return False
    AccessToken.objects.filter(invitation=invitation, pk__lt=current.pk, revoked_at__isnull=True).update(revoked_at=now)
    return True
