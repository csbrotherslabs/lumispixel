from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase
from django.utils import timezone

from apps.dashboard.invitation_actions import resend_pending_invitation


class InvitationResendCooldownTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.resend_studio_invitation")
    def test_immediate_resend_is_rejected(self, resend_mock, get_mock):
        get_mock.return_value = Mock(invitation_sent_at=timezone.now())

        with self.assertRaises(PermissionDenied):
            resend_pending_invitation(Mock(), Mock(), 3)

        resend_mock.assert_not_called()
