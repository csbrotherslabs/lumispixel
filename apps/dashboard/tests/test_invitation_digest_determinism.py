from django.test import SimpleTestCase

from apps.dashboard.team_invitations import _digest


class InvitationDigestDeterminismTests(SimpleTestCase):
    def test_same_raw_token_has_same_digest(self):
        self.assertEqual(_digest("sample-token"), _digest("sample-token"))
