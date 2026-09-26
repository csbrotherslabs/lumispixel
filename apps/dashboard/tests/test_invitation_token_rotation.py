from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import apply_token, prepare_token, send_invitation


class InvitationTokenRotationTests(TestCase):
    def test_prepare_token_does_not_mutate_existing_invitation(self):
        membership = StudioMembership(
            invitation_token_digest="existing-digest",
            invitation_sent_at=timezone.now(),
            invitation_expires_at=timezone.now() + timezone.timedelta(days=2),
            status=StudioMembership.Status.INVITED,
        )
        original = (
            membership.invitation_token_digest,
            membership.invitation_sent_at,
            membership.invitation_expires_at,
            membership.status,
        )

        raw_token, digest, sent_at, expires_at = prepare_token()

        self.assertTrue(raw_token)
        self.assertTrue(digest)
        self.assertGreater(expires_at, sent_at)
        self.assertEqual(
            original,
            (
                membership.invitation_token_digest,
                membership.invitation_sent_at,
                membership.invitation_expires_at,
                membership.status,
            ),
        )

    def test_apply_token_is_explicit_persistence_step(self):
        membership = StudioMembership.objects.create(
            studio_id=1,
            role=StudioMembership.Role.PHOTOGRAPHER,
            invitation_email="invitee@example.com",
            status=StudioMembership.Status.INVITED,
        )
        raw_token, digest, sent_at, expires_at = prepare_token()

        apply_token(membership, digest, sent_at, expires_at)
        membership.refresh_from_db()

        self.assertTrue(raw_token)
        self.assertEqual(membership.invitation_token_digest, digest)
        self.assertEqual(membership.invitation_sent_at, sent_at)
        self.assertEqual(membership.invitation_expires_at, expires_at)
        self.assertEqual(membership.status, StudioMembership.Status.INVITED)
