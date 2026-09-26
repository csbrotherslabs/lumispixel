from smtplib import SMTPException
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioInvitationEvent, StudioMembership
from apps.dashboard.team_invitations import INVITATION_RESEND_COOLDOWN, issue_token


class InvitationResendDeliveryFailureTests(TestCase):
    def test_failed_resend_keeps_previous_link_and_does_not_record_resent(self):
        owner = User.objects.create_user(email="resend-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="resend-owner", onboarding_completed=True)
        membership = StudioMembership.objects.create(studio=studio, invitation_email="invitee@example.com", role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        original_token = issue_token(membership)
        StudioMembership.objects.filter(pk=membership.pk).update(invitation_sent_at=timezone.now() - INVITATION_RESEND_COOLDOWN)
        membership.refresh_from_db()
        old_digest = membership.invitation_token_digest
        old_expiry = membership.invitation_expires_at
        self.client.force_login(owner)

        with patch("apps.dashboard.team_invitations.EmailMultiAlternatives.send", side_effect=SMTPException("mail unavailable")):
            response = self.client.post(reverse("photographer_workspace:invitation_action", args=[membership.pk, "resend"]))

        self.assertEqual(response.status_code, 302)
        membership.refresh_from_db()
        self.assertEqual(membership.invitation_token_digest, old_digest)
        self.assertEqual(membership.invitation_expires_at, old_expiry)
        self.assertFalse(membership.invitation_events.filter(action=StudioInvitationEvent.Action.RESENT).exists())
        self.assertEqual(self.client.get(reverse("photographer_workspace:invitation_accept", args=[original_token])).status_code, 200)
