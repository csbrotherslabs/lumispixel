from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token


class InvitationReplayAfterAcceptTests(TestCase):
    def test_accepted_invitation_token_is_single_use(self):
        owner = User.objects.create_user(email="replay-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="replay-owner", onboarding_completed=True)
        invitee = User.objects.create_user(email="replay-invitee@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        membership = StudioMembership.objects.create(studio=studio, invitation_email=invitee.email, role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        token = issue_token(membership)
        self.client.force_login(invitee)

        accepted = self.client.post(reverse("photographer_workspace:invitation_accept", args=[token]), {"decision": "accept"})
        replay = self.client.get(reverse("photographer_workspace:invitation_accept", args=[token]))

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(replay.status_code, 410)
        membership.refresh_from_db()
        self.assertEqual(membership.status, StudioMembership.Status.ACTIVE)
        self.assertEqual(membership.invitation_token_digest, "")
