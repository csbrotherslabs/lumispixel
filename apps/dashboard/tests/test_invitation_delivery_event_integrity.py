from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_actions import resend_pending_invitation


class InvitationDeliveryEventIntegrityTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.resend_studio_invitation", side_effect=RuntimeError("mail unavailable"))
    @patch("apps.dashboard.invitation_actions.record")
    def test_resend_failure_does_not_record_success_event(self, record_mock, _resend, get_mock):
        membership = Mock(invitation_sent_at=None)
        get_mock.return_value = membership
        with self.assertRaises(RuntimeError):
            resend_pending_invitation(Mock(), Mock(), 42)
        record_mock.assert_not_called()
