"""Resend workflow for studio invitations.

This module deliberately owns the resend sequencing so a replacement token is
never persisted before the corresponding email has been delivered.
"""

from .invitation_delivery import rotate_invitation_after_delivery


def resend_studio_invitation(request, membership):
    return rotate_invitation_after_delivery(request, membership)
