from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.invitation_actions import revoke_pending_invitation
from apps.dashboard.models import StudioMembership


class InvitationRevocationTests(SimpleTestCase):
    @patch("apps.dashboard.invitation_actions.get_object_or_404")
    @patch("apps.dashboard.invitation_actions.record")
    def test_revocation_requires_pending_status_and_clears_token(self, _record, get_mock):
        membership = Mock()
        get_mock.return_value = membership
        studio = Mock()

        revoke_pending_invitation(Mock(), studio, 9)

        lookup = get_mock.call_args.kwargs
        self.assertIs(lookup["studio"], studio)
        self.assertEqual(lookup["status"], StudioMembership.Status.INVITED)
        self.assertEqual(membership.status, StudioMembership.Status.INACTIVE)
        self.assertEqual(membership.invitation_token_digest, "")
