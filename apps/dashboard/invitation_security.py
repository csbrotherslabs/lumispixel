"""Security invariants shared by studio invitation endpoints."""

from django.core.exceptions import PermissionDenied


def require_invited_email(user, membership):
    """Reject authenticated acceptance from any account other than the invitee."""
    invited = (membership.invitation_email or "").strip().casefold()
    actual = (getattr(user, "email", "") or "").strip().casefold()
    if not invited or not actual or invited != actual:
        raise PermissionDenied("Sign in with the email address that received this invitation.")
    return True
