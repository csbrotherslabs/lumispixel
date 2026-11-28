from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.dashboard.team_invitations import find_valid_invitation, issue_token


class InvitationExpiredReplayTests(TestCase):
    def test_expired_token_cannot_be_reused_and_lookup_is_read_only(self):
        owner = User.objects.create_user(email="expired-owner@example.com", password="pass12345", primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        studio = PhotographerProfile.objects.create(user=owner, slug="expired-owner", onboarding_completed=True)
        membership = StudioMembership.objects.create(studio=studio, invitation_email="expired@example.com", role=StudioMembership.Role.PHOTOGRAPHER, invited_by=owner)
        token = issue_token(membership)
        StudioMembership.objects.filter(pk=membership.pk).update(invitation_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(find_valid_invitation(token))
        membership.refresh_from_db()
        self.assertEqual(membership.status, StudioMembership.Status.INVITED)
        self.assertNotEqual(membership.invitation_token_digest, token)
        self.assertLessEqual(membership.invitation_expires_at, timezone.now())
        self.assertIsNone(find_valid_invitation(token))
