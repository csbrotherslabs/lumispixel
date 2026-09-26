from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.dashboard.invitation_delivery import rotate_invitation_after_delivery
from apps.dashboard.models import StudioMembership


class InvitationDeliveryTests(SimpleTestCase):
    def setUp(self):
        self.membership = StudioMembership(
            invitation_token_digest="existing-digest",
            invitation_sent_at=timezone.now(),
            invitation_expires_at=timezone.now() + timezone.timedelta(days=2),
            status=StudioMembership.Status.INVITED,
        )

    @patch("apps.dashboard.invitation_delivery.apply_token")
    @patch("apps.dashboard.invitation_delivery.send_invitation", side_effect=RuntimeError("mail unavailable"))
    def test_delivery_failure_does_not_persist_replacement_token(self, send_mock, apply_mock):
        original = (
            self.membership.invitation_token_digest,
            self.membership.invitation_sent_at,
            self.membership.invitation_expires_at,
        )

        with self.assertRaises(RuntimeError):
            rotate_invitation_after_delivery(Mock(), self.membership)

        apply_mock.assert_not_called()
        self.assertEqual(
            original,
            (
                self.membership.invitation_token_digest,
                self.membership.invitation_sent_at,
                self.membership.invitation_expires_at,
            ),
        )

    @patch("apps.dashboard.invitation_delivery.apply_token")
    @patch("apps.dashboard.invitation_delivery.send_invitation")
    def test_success_persists_only_the_delivered_replacement(self, send_mock, apply_mock):
        raw_token = rotate_invitation_after_delivery(Mock(), self.membership)

        self.assertTrue(raw_token)
        send_mock.assert_called_once_with(send_mock.call_args.args[0], self.membership, raw_token)
        apply_mock.assert_called_once()
        self.assertEqual(apply_mock.call_args.args[0], self.membership)
