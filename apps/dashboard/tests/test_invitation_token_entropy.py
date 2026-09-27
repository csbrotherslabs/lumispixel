from django.test import SimpleTestCase

from apps.dashboard.team_invitations import prepare_token


class InvitationTokenEntropyTests(SimpleTestCase):
    def test_tokens_are_unique_and_have_fixed_digest_shape(self):
        first, first_digest, *_ = prepare_token()
        second, second_digest, *_ = prepare_token()

        self.assertNotEqual(first, second)
        self.assertNotEqual(first_digest, second_digest)
        self.assertGreaterEqual(len(first), 40)
        self.assertEqual(len(first_digest), 64)
