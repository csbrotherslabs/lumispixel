from django.test import SimpleTestCase

from apps.dashboard import invitation_service


class InvitationServiceSurfaceTests(SimpleTestCase):
    def test_security_entry_points_are_exposed(self):
        self.assertTrue(callable(invitation_service.locked_invitation_for_acceptance))
        self.assertTrue(callable(invitation_service.resend_pending_invitation))
        self.assertTrue(callable(invitation_service.revoke_pending_invitation))
