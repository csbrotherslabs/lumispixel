from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_resend import resend_studio_invitation


class InvitationResendTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_resend.rotate_invitation_after_delivery")
    def test_resend_uses_delivery_safe_rotation(self, rotate_mock):
        request = Mock()
        membership = Mock()
        rotate_mock.return_value = "replacement-token"

        result = resend_studio_invitation(request, membership)

        self.assertEqual(result, "replacement-token")
        rotate_mock.assert_called_once_with(request, membership)
