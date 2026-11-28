from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from django.http import Http404
from django.core.exceptions import PermissionDenied
from apps.accounts.models import User, PhotographerProfile
from apps.dashboard.models import StudioMembership
from apps.dashboard.invitation_actions import resend_pending_invitation, revoke_pending_invitation
from apps.dashboard.team_invitations import issue_token, find_valid_invitation
from apps.notifications.models import EmailDelivery

class InvitationRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.com", password="password123", email_verified=True)
        self.studio = PhotographerProfile.objects.create(user=self.owner)
        self.membership = StudioMembership.objects.create(studio=self.studio, invitation_email="invitee@example.com", role="photographer", status="invited")
        self.token = issue_token(self.membership)
        self.request = Mock(user=self.owner)
        self.membership.invitation_sent_at = timezone.now() - timedelta(minutes=2)
        self.membership.save(update_fields=["invitation_sent_at"])

    def resend(self):
        return resend_pending_invitation(self.request, self.studio, self.membership.pk)

    def revoke(self):
        return revoke_pending_invitation(self.request, self.studio, self.membership.pk)

    def test_resend_lookup_is_studio_scoped(self):
        other = PhotographerProfile.objects.create(user=User.objects.create_user(email="other@example.com"))
        with self.assertRaises(Http404):
            resend_pending_invitation(self.request, other, self.membership.pk)

    def test_revoke_clears_credential(self):
        self.revoke()
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.invitation_token_digest, "")
        self.assertIsNone(find_valid_invitation(self.token))
