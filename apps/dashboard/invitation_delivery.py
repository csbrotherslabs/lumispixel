"""Atomically persist a replacement credential and its durable email."""
from django.db import transaction
from django.utils import timezone
from .models import StudioMembership
from .team_invitations import apply_token, prepare_token, send_invitation, INVITATION_RESEND_COOLDOWN


@transaction.atomic
def rotate_invitation_after_delivery(request, membership):
    current = StudioMembership.objects.select_for_update().get(pk=membership.pk, studio_id=membership.studio_id)
    if current.status != StudioMembership.Status.INVITED:
        raise RuntimeError("Invitation is no longer pending")
    if current.invitation_sent_at and timezone.now() - current.invitation_sent_at < INVITATION_RESEND_COOLDOWN:
        raise RuntimeError("Please wait before resending")
    token, digest, sent_at, expires_at = prepare_token()
    apply_token(current, digest, sent_at, expires_at)
    send_invitation(request, current, token)
    return token
