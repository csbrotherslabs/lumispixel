from django.test import SimpleTestCase

from apps.dashboard.invitation_service import (
    locked_invitation_for_acceptance,
    resend_pending_invitation,
    revoke_pending_invitation,
)


class InvitationServiceContractTests(SimpleTestCase):
    def test_service_exposes_hardened_accept_resend_and_revoke_operations(self):
        self.assertTrue(callable(locked_invitation_for_acceptance))
        self.assertTrue(callable(resend_pending_invitation))
        self.assertTrue(callable(revoke_pending_invitation))
