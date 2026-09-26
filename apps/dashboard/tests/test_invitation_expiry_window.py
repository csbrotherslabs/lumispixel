from django.test import SimpleTestCase

from apps.dashboard.team_invitations import INVITATION_LIFETIME, prepare_token


class InvitationExpiryWindowTests(SimpleTestCase):
    def test_prepared_invitation_uses_configured_lifetime(self):
        _raw, _digest, sent_at, expires_at = prepare_token()
        self.assertEqual(expires_at - sent_at, INVITATION_LIFETIME)
