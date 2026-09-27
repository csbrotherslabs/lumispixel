from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_delivery import rotate_invitation_after_delivery


class InvitationResendOldTokenTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_delivery.apply_token")
    @patch("apps.dashboard.invitation_delivery.send_invitation")
    def test_old_digest_is_not_replaced_until_new_link_is_delivered(self, send_mock, apply_mock):
        membership = Mock(invitation_token_digest="old-digest")
        observed = []
        send_mock.side_effect = lambda *_args: observed.append(membership.invitation_token_digest)
        rotate_invitation_after_delivery(Mock(), membership)
        self.assertEqual(observed, ["old-digest"])
        apply_mock.assert_called_once()
