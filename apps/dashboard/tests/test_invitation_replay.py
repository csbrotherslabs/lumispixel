from django.test import TestCase

from apps.accounts.models import User, PhotographerProfile
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token, find_valid_invitation


class InvitationReplayTests(TestCase):
    def test_lookup_requires_invited_status(self):
        owner = User.objects.create_user(email="owner@example.com", password="password123", email_verified=True)
        studio = PhotographerProfile.objects.create(user=owner)
        membership = StudioMembership.objects.create(
            studio=studio, invitation_email="invitee@example.com",
            role=StudioMembership.Role.PHOTOGRAPHER, status=StudioMembership.Status.INVITED,
        )
        token = issue_token(membership)
        self.assertEqual(find_valid_invitation(token).pk, membership.pk)
        self.assertIsNone(find_valid_invitation("incorrect-token"))
        for status in (StudioMembership.Status.ACTIVE, StudioMembership.Status.INACTIVE):
            membership.status = status
            membership.save(update_fields=["status"])
            self.assertIsNone(find_valid_invitation(token))
