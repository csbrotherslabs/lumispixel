from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.dashboard.invitation_delivery import rotate_invitation_after_delivery
from apps.dashboard.models import StudioMembership


class InvitationDeliveryRegressionTests(SimpleTestCase):
    def setUp(self):
        self.membership = StudioMembership(
            invitation_token_digest="existing-digest",
            invitation_sent_at=timezone.now(),
            invitation_expires_at=timezone.now() + timezone.timedelta(days=2),
            status=StudioMembership.Status.INVITED,
        )

    @patch("apps.dashboard.invitation_delivery.apply_token")
    @patch("apps.dashboard.invitation_delivery.send_invitation", side_effect=RuntimeError("mail unavailable"))
    def test_failed_delivery_keeps_existing_credential_authoritative(self, _send, apply_mock):
        before = (
            self.membership.invitation_token_digest,
            self.membership.invitation_sent_at,
            self.membership.invitation_expires_at,
        )
        with self.assertRaises(RuntimeError):
            rotate_invitation_after_delivery(Mock(), self.membership)
        apply_mock.assert_not_called()
        self.assertEqual(before, (
            self.membership.invitation_token_digest,
            self.membership.invitation_sent_at,
            self.membership.invitation_expires_at,
        ))

    @patch("apps.dashboard.invitation_delivery.apply_token")
    @patch("apps.dashboard.invitation_delivery.send_invitation")
    def test_success_applies_token_only_after_delivery(self, send_mock, apply_mock):
        request = Mock()
        raw_token = rotate_invitation_after_delivery(request, self.membership)
        send_mock.assert_called_once_with(request, self.membership, raw_token)
        apply_mock.assert_called_once()
