from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_actions import resend_pending_invitation


class InvitationAuditSuccessTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.resend_studio_invitation")
    @patch("apps.dashboard.invitation_actions.record")
    def test_successful_resend_records_event_after_delivery(self, record_mock, resend_mock, get_mock):
        membership = Mock(invitation_sent_at=None)
        get_mock.return_value = membership
        request = Mock()
        resend_pending_invitation(request, Mock(), 5)
        resend_mock.assert_called_once()
        record_mock.assert_called_once_with(membership, request.user, "resent")
