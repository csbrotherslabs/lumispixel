"""Atomic security checks for accepting studio invitations."""

from django.db import transaction

from .invitation_security import require_invited_email
from .team_invitations import find_valid_invitation


@transaction.atomic
def locked_invitation_for_acceptance(token, user):
    """Resolve, lock, and bind an invitation to the authenticated account."""
    membership = find_valid_invitation(token, lock=True)
    if membership is None:
        return None
    require_invited_email(user, membership)
    return membership
