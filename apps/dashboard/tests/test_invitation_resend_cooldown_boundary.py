from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.dashboard.invitation_actions import resend_pending_invitation
from apps.dashboard.team_invitations import INVITATION_RESEND_COOLDOWN


class InvitationResendCooldownBoundaryTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.resend_studio_invitation")
    @patch("apps.dashboard.invitation_actions.record")
    def test_resend_allowed_after_cooldown(self, _record, resend_mock, get_mock):
        get_mock.return_value = Mock(invitation_sent_at=timezone.now() - INVITATION_RESEND_COOLDOWN - timedelta(seconds=1))
        resend_pending_invitation(Mock(), Mock(), 3)
        resend_mock.assert_called_once()
