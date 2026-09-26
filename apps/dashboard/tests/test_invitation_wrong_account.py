from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token


class InvitationWrongAccountTests(TestCase):
    def test_authenticated_user_with_different_email_cannot_accept(self):
        owner = User.objects.create_user(email="wrong-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="wrong-owner", onboarding_completed=True)
        membership = StudioMembership.objects.create(studio=studio, invitation_email="intended@example.com", role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        token = issue_token(membership)
        outsider = User.objects.create_user(email="outsider@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        self.client.force_login(outsider)

        response = self.client.post(reverse("photographer_workspace:invitation_accept", args=[token]), {"decision": "accept"})

        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.status, StudioMembership.Status.INVITED)
        self.assertIsNone(membership.user_id)
        self.assertTrue(membership.invitation_token_digest)
