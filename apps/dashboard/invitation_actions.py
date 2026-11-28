"""Studio-scoped invitation actions with delivery-safe token handling."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .invitation_resend import resend_studio_invitation
from .models import StudioMembership
from .team_invitations import INVITATION_RESEND_COOLDOWN, record


@transaction.atomic
def resend_pending_invitation(request, studio, membership_id):
    membership = get_object_or_404(
        StudioMembership.objects.select_for_update(),
        pk=membership_id,
        studio=studio,
        status=StudioMembership.Status.INVITED,
    )
    if membership.invitation_sent_at and timezone.now() - membership.invitation_sent_at < INVITATION_RESEND_COOLDOWN:
        raise PermissionDenied("Please wait before resending this invitation.")
    resend_studio_invitation(request, membership)
    record(membership, request.user, "resent")
    return membership


@transaction.atomic
def revoke_pending_invitation(request, studio, membership_id):
    membership = get_object_or_404(
        StudioMembership.objects.select_for_update(),
        pk=membership_id,
        studio=studio,
        status=StudioMembership.Status.INVITED,
    )
    membership.status = StudioMembership.Status.INACTIVE
    membership.invitation_token_digest = ""
    membership.previous_invitation_digest = ""
    membership.previous_invitation_expires_at = None
    membership.invitation_expires_at = timezone.now()
    membership.save(update_fields=["status", "invitation_token_digest", "invitation_expires_at", "previous_invitation_digest", "previous_invitation_expires_at", "updated_at"])
    record(membership, request.user, "revoked")
    return membership
