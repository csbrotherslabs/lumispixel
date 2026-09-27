from django.test import SimpleTestCase

from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token


class InvitationTokenHashingTests(SimpleTestCase):
    def test_raw_token_is_not_persisted(self):
        membership = StudioMembership()
        membership.save = lambda *args, **kwargs: None

        raw_token = issue_token(membership)

        self.assertTrue(raw_token)
        self.assertNotEqual(membership.invitation_token_digest, raw_token)
        self.assertEqual(len(membership.invitation_token_digest), 64)
        self.assertNotIn(raw_token, membership.invitation_token_digest)
