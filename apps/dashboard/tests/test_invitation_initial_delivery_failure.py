from smtplib import SMTPException
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioInvitationEvent, StudioMembership


class InvitationInitialDeliveryFailureTests(TestCase):
    def test_failed_initial_delivery_does_not_leave_live_credential_or_sent_event(self):
        owner = User.objects.create_user(email="initial-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        PhotographerProfile.objects.create(user=owner, slug="initial-owner", onboarding_completed=True)
        self.client.force_login(owner)
        payload = {"first_name": "Invite", "last_name": "Person", "email": "new-invitee@example.com", "role": StudioMembership.Role.PHOTOGRAPHER, "primary_location": "Studio", "phone": "", "specialties": "", "message": ""}

        with patch("apps.dashboard.team_invitations.EmailMultiAlternatives.send", side_effect=SMTPException("mail unavailable")):
            response = self.client.post(reverse("photographer_workspace:invite_member"), payload)

        self.assertEqual(response.status_code, 302)
        membership = StudioMembership.objects.get(invitation_email="new-invitee@example.com")
        self.assertEqual(membership.invitation_token_digest, "")
        self.assertIsNone(membership.invitation_sent_at)
        self.assertIsNone(membership.invitation_expires_at)
        self.assertFalse(membership.invitation_events.filter(action=StudioInvitationEvent.Action.SENT).exists())
