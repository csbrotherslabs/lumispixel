from django.test import SimpleTestCase

from apps.dashboard.team_invitations import prepare_token


class InvitationTokenUniquenessTests(SimpleTestCase):
    def test_prepared_invitation_tokens_are_unique(self):
        first, first_digest, *_ = prepare_token()
        second, second_digest, *_ = prepare_token()
        self.assertNotEqual(first, second)
        self.assertNotEqual(first_digest, second_digest)
