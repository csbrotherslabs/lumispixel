"""Security regression tests for studio invitation lifecycle."""

from smtplib import SMTPException
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioInvitationEvent, StudioMembership
from apps.dashboard.team_invitations import INVITATION_RESEND_COOLDOWN, issue_token


class StudioInvitationSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner-invite-security@example.com",
            password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.studio = PhotographerProfile.objects.create(
            user=self.owner,
            slug="invite-security-studio",
            onboarding_completed=True,
        )
        self.invitee = User.objects.create_user(
            email="invitee-security@example.com",
            password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.membership = StudioMembership.objects.create(
            studio=self.studio,
            invitation_email=self.invitee.email,
            role=StudioMembership.Role.PHOTOGRAPHER,
            invited_by=self.owner,
        )
        self.original_token = issue_token(self.membership)
        StudioMembership.objects.filter(pk=self.membership.pk).update(
            invitation_sent_at=timezone.now() - INVITATION_RESEND_COOLDOWN
        )
        self.membership.refresh_from_db()

    @patch("apps.dashboard.team_invitations.EmailMultiAlternatives.send", side_effect=SMTPException("mail unavailable"))
    def test_failed_resend_preserves_previous_secure_link(self, _send):
        old_digest = self.membership.invitation_token_digest
        old_expiry = self.membership.invitation_expires_at
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("photographer_workspace:invitation_action", args=[self.membership.pk, "resend"])
        )

        self.assertEqual(response.status_code, 302)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.invitation_token_digest, old_digest)
        self.assertEqual(self.membership.invitation_expires_at, old_expiry)
        self.assertFalse(
            self.membership.invitation_events.filter(action=StudioInvitationEvent.Action.RESENT).exists()
        )
        access = self.client.get(
            reverse("photographer_workspace:invitation_accept", args=[self.original_token])
        )
        self.assertEqual(access.status_code, 200)

    def test_wrong_email_account_cannot_accept_invitation(self):
        outsider = User.objects.create_user(
            email="wrong-account@example.com",
            password="pass12345",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_login(outsider)

        response = self.client.post(
            reverse("photographer_workspace:invitation_accept", args=[self.original_token]),
            {"decision": "accept"},
        )

        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, StudioMembership.Status.INVITED)
        self.assertIsNone(self.membership.user_id)
        self.assertTrue(self.membership.invitation_token_digest)

    def test_revoke_invalidates_invitation_link(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("photographer_workspace:invitation_action", args=[self.membership.pk, "revoke"])
        )
        self.assertEqual(response.status_code, 302)

        access = self.client.get(
            reverse("photographer_workspace:invitation_accept", args=[self.original_token])
        )
        self.assertEqual(access.status_code, 410)
