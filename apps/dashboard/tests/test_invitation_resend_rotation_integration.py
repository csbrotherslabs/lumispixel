from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_resend import resend_studio_invitation


class InvitationResendRotationIntegrationTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_resend.rotate_invitation_after_delivery", return_value="new-token")
    def test_resend_uses_delivery_safe_rotation(self, rotate_mock):
        request = Mock()
        membership = Mock()
        self.assertEqual(resend_studio_invitation(request, membership), "new-token")
        rotate_mock.assert_called_once_with(request, membership)
