from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.dashboard.team_invitations import find_valid_invitation


class InvitationLockingTests(SimpleTestCase):
    @patch("apps.dashboard.team_invitations.StudioMembership.objects")
    def test_acceptance_lookup_can_lock_membership_row(self, objects):
        locked = Mock()
        objects.select_related.return_value.select_for_update.return_value = locked
        locked.filter.return_value.first.return_value = None

        find_valid_invitation("token", lock=True)

        objects.select_related.return_value.select_for_update.assert_called_once_with()
        locked.filter.assert_called_once()
