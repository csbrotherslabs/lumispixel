from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import find_valid_invitation


class InvitationExpiryTests(SimpleTestCase):
    @patch("apps.dashboard.team_invitations.StudioMembership.objects")
    def test_expired_invitation_is_invalidated(self, objects):
        membership = Mock(
            invitation_expires_at=timezone.now() - timezone.timedelta(seconds=1),
            status=StudioMembership.Status.INVITED,
            invitation_token_digest="digest",
        )
        objects.select_related.return_value.filter.return_value.first.return_value = membership

        result = find_valid_invitation("expired-token")

        self.assertIsNone(result)
        self.assertEqual(membership.status, StudioMembership.Status.EXPIRED)
        self.assertEqual(membership.invitation_token_digest, "")
        membership.save.assert_called_once()
