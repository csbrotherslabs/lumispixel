"""Delivery-safe helpers for rotating studio invitation credentials."""

from .team_invitations import apply_token, prepare_token, send_invitation


def rotate_invitation_after_delivery(request, membership):
    """Email a replacement invite before invalidating the current credential.

    The membership's persisted digest and validity timestamps are unchanged if
    email delivery raises. Once delivery succeeds, the newly delivered token is
    made authoritative in one explicit persistence step.
    """
    raw_token, token_digest, sent_at, expires_at = prepare_token()
    send_invitation(request, membership, raw_token)
    apply_token(membership, token_digest, sent_at, expires_at)
    return raw_token
