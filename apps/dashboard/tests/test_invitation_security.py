from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.dashboard.invitation_security import require_invited_email


class InvitationEmailBindingTests(SimpleTestCase):
    def test_matching_email_is_case_insensitive(self):
        user = SimpleNamespace(email="Invitee@Example.com")
        membership = SimpleNamespace(invitation_email="invitee@example.com")
        self.assertTrue(require_invited_email(user, membership))

    def test_wrong_authenticated_account_is_rejected(self):
        user = SimpleNamespace(email="attacker@example.com")
        membership = SimpleNamespace(invitation_email="invitee@example.com")
        with self.assertRaises(PermissionDenied):
            require_invited_email(user, membership)

    def test_blank_email_cannot_claim_invitation(self):
        user = SimpleNamespace(email="")
        membership = SimpleNamespace(invitation_email="invitee@example.com")
        with self.assertRaises(PermissionDenied):
            require_invited_email(user, membership)
