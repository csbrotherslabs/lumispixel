from django.test import SimpleTestCase

from apps.dashboard.team_invitations import prepare_token


class InvitationTokenStorageTests(SimpleTestCase):
    def test_prepared_token_digest_does_not_store_raw_credential(self):
        raw_token, token_digest, _sent_at, _expires_at = prepare_token()
        self.assertNotEqual(raw_token, token_digest)
        self.assertEqual(len(token_digest), 64)
        self.assertGreaterEqual(len(raw_token), 32)
