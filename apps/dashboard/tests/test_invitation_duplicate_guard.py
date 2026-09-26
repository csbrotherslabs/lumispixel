from unittest.mock import Mock, patch

from django import forms
from django.test import SimpleTestCase

from apps.dashboard.team_invitations import InvitationForm


class InvitationDuplicateGuardTests(SimpleTestCase):
    @patch("apps.dashboard.team_invitations.StudioMembership.objects")
    def test_pending_duplicate_email_is_rejected(self, objects):
        active_query = Mock()
        active_query.filter.return_value.exists.return_value = False
        pending_query = Mock()
        pending_query.exists.return_value = True
        objects.filter.side_effect = [active_query, pending_query]

        form = InvitationForm(studio=Mock())
        form.cleaned_data = {"email": "Invitee@Example.com"}

        with self.assertRaises(forms.ValidationError):
            form.clean_email()
