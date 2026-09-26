from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.dashboard.invitation_acceptance import locked_invitation_for_acceptance


class InvitationAcceptanceGuardTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_acceptance.find_valid_invitation")
    def test_invalid_or_expired_token_returns_none(self, find_mock):
        find_mock.return_value = None
        self.assertIsNone(locked_invitation_for_acceptance("bad-token", SimpleNamespace(email="x@example.com")))
        find_mock.assert_called_once_with("bad-token", lock=True)

    @patch("apps.dashboard.invitation_acceptance.find_valid_invitation")
    def test_wrong_account_is_rejected_after_locked_lookup(self, find_mock):
        find_mock.return_value = SimpleNamespace(invitation_email="invitee@example.com")
        with self.assertRaises(PermissionDenied):
            locked_invitation_for_acceptance("token", SimpleNamespace(email="other@example.com"))
        find_mock.assert_called_once_with("token", lock=True)
