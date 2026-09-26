from django.test import SimpleTestCase
from django.utils import timezone

from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import prepare_token


class InvitationTokenRotationTests(SimpleTestCase):
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
        self.assertEqual(len(digest), 64)
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
