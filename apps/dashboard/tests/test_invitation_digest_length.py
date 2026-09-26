from django.test import SimpleTestCase

from apps.dashboard.team_invitations import prepare_token


class InvitationDigestLengthTests(SimpleTestCase):
    def test_sha256_digest_has_expected_length(self):
        _raw, digest, *_ = prepare_token()
        self.assertEqual(len(digest), 64)
