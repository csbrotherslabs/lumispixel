from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token


class InvitationRevokeAccessTests(TestCase):
    def test_revoked_invitation_link_is_invalid(self):
        owner = User.objects.create_user(email="revoke-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="revoke-owner", onboarding_completed=True)
        membership = StudioMembership.objects.create(studio=studio, invitation_email="revoke-invitee@example.com", role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        token = issue_token(membership)
        self.client.force_login(owner)

        response = self.client.post(reverse("photographer_workspace:invitation_action", args=[membership.pk, "revoke"]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("photographer_workspace:invitation_accept", args=[token])).status_code, 410)
