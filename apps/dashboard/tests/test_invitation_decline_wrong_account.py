from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token


class InvitationDeclineWrongAccountTests(TestCase):
    def test_wrong_account_cannot_decline_someone_elses_invitation(self):
        owner = User.objects.create_user(email="decline-wrong-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="decline-wrong-owner", onboarding_completed=True)
        membership = StudioMembership.objects.create(studio=studio, invitation_email="intended-decline@example.com", role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        token = issue_token(membership)
        outsider = User.objects.create_user(email="decline-outsider@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        self.client.force_login(outsider)
        self.client.post(reverse("photographer_workspace:invitation_accept", args=[token]), {"decision": "decline"})
        membership.refresh_from_db()
        self.assertEqual(membership.status, StudioMembership.Status.INVITED)
        self.assertTrue(membership.invitation_token_digest)
