from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import issue_token


class InvitationInvalidDecisionTests(TestCase):
    def test_invalid_acceptance_decision_does_not_consume_token(self):
        owner = User.objects.create_user(email="decision-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="decision-owner", onboarding_completed=True)
        invitee = User.objects.create_user(email="decision-invitee@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        membership = StudioMembership.objects.create(studio=studio, invitation_email=invitee.email, role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        token = issue_token(membership)
        self.client.force_login(invitee)
        response = self.client.post(reverse("photographer_workspace:invitation_accept", args=[token]), {"decision": "unexpected"})
        self.assertEqual(response.status_code, 400)
        membership.refresh_from_db()
        self.assertEqual(membership.status, StudioMembership.Status.INVITED)
        self.assertTrue(membership.invitation_token_digest)
