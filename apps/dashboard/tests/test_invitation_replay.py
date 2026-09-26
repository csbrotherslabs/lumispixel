from unittest.mock import patch

from django.test import SimpleTestCase

from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import find_valid_invitation


class InvitationReplayTests(SimpleTestCase):
    @patch("apps.dashboard.team_invitations.StudioMembership.objects")
    def test_lookup_requires_invited_status(self, objects):
        objects.select_related.return_value.filter.return_value.first.return_value = None

        find_valid_invitation("already-used-token")

        kwargs = objects.select_related.return_value.filter.call_args.kwargs
        self.assertEqual(kwargs["status"], StudioMembership.Status.INVITED)
        self.assertIn("invitation_token_digest", kwargs)
