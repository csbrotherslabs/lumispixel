from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioInvitationEvent, StudioMembership


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TeamInvitationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.com", password="password123",
                                              first_name="Studio", last_name="Owner", primary_role=User.PrimaryRole.PHOTOGRAPHER, onboarding_completed=True,
                                              account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.studio = PhotographerProfile.objects.create(user=self.owner, display_name="Northlight Studio", onboarding_completed=True)
        self.client.force_login(self.owner)
        self.invite_url = reverse("photographer_workspace:invite_member")
        self.payload = {"first_name": "Avery", "last_name": "Stone", "email": "  AVERY@Example.COM ",
                        "role": "photographer", "primary_location": "Downtown", "phone": "+1 555 123 4567",
                        "specialties": "Portraits", "message": "Welcome aboard"}

    def test_send_normalizes_email_limits_role_and_records_audit(self):
        response = self.client.post(self.invite_url, self.payload)
        self.assertRedirects(response, reverse("photographer_workspace:team_members"))
        invitation = StudioMembership.objects.get(studio=self.studio)
        self.assertEqual(invitation.invitation_email, "avery@example.com")
        self.assertEqual(invitation.role, StudioMembership.Role.PHOTOGRAPHER)
        self.assertTrue(invitation.invitation_token_digest)
        self.assertGreater(invitation.invitation_expires_at, invitation.invitation_sent_at)
        self.assertEqual(invitation.invitation_events.get().action, StudioInvitationEvent.Action.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Northlight Studio", mail.outbox[0].subject)
        self.assertFalse(StudioMembership.objects.filter(role="owner").exists())
        denied = self.client.post(self.invite_url, self.payload | {"email": "other@example.com", "role": "owner"})
        self.assertRedirects(denied, reverse("photographer_workspace:team_members"))
        self.assertEqual(StudioMembership.objects.count(), 1)

    def test_duplicate_pending_resend_revoke_and_studio_isolation(self):
        self.client.post(self.invite_url, self.payload)
        invitation = StudioMembership.objects.get()
        first_digest = invitation.invitation_token_digest
        self.client.post(self.invite_url, self.payload)
        self.assertEqual(StudioMembership.objects.count(), 1)
        self.client.post(reverse("photographer_workspace:invitation_action", args=[invitation.pk, "resend"]))
        invitation.refresh_from_db()
        self.assertNotEqual(invitation.invitation_token_digest, first_digest)
        self.assertTrue(invitation.invitation_events.filter(action="resent", actor=self.owner).exists())

        other = User.objects.create_user(email="other-owner@example.com", password="password123",
                                         primary_role=User.PrimaryRole.PHOTOGRAPHER, onboarding_completed=True, account_status=User.AccountStatus.ACTIVE, email_verified=True)
        PhotographerProfile.objects.create(user=other, display_name="Other Studio", onboarding_completed=True)
        self.client.force_login(other)
        response = self.client.post(reverse("photographer_workspace:invitation_action", args=[invitation.pk, "revoke"]))
        self.assertEqual(response.status_code, 404)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, StudioMembership.Status.INVITED)

        self.client.force_login(self.owner)
        self.client.post(reverse("photographer_workspace:invitation_action", args=[invitation.pk, "revoke"]))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, StudioMembership.Status.INACTIVE)
        self.assertEqual(invitation.invitation_token_digest, "")
        self.assertTrue(invitation.invitation_events.filter(action="revoked", actor=self.owner).exists())

    def test_accept_requires_matching_authenticated_email_and_token_is_single_use(self):
        self.client.post(self.invite_url, self.payload)
        invitation = StudioMembership.objects.get()
        token = mail.outbox[0].body.split("/team/invitations/accept/")[1].split("/")[0]
        accept_url = reverse("photographer_workspace:invitation_accept", args=[token])
        self.client.logout()
        self.assertContains(self.client.get(accept_url), "Sign in or create an account")
        unrelated = User.objects.create_user(email="unrelated@example.com", password="password123",
                                             account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.client.force_login(unrelated)
        self.assertContains(self.client.get(accept_url), "different email")
        self.assertEqual(self.client.post(accept_url, {"decision": "accept"}).status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, StudioMembership.Status.INVITED)
        invitee = User.objects.create_user(email="avery@example.com", password="password123",
                                           account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.client.force_login(invitee)
        self.assertContains(self.client.post(accept_url, {"decision": "accept"}), "Welcome to the studio")
        invitation.refresh_from_db()
        self.assertEqual(invitation.user, invitee)
        self.assertEqual(invitation.status, StudioMembership.Status.ACTIVE)
        self.assertEqual(invitation.invitation_token_digest, "")
        self.assertEqual(self.client.get(accept_url).status_code, 410)

    def test_active_member_is_not_invited_again_without_disclosing_external_accounts(self):
        member = User.objects.create_user(email="member@example.com", password="password123")
        StudioMembership.objects.create(studio=self.studio, user=member, invitation_email="member@example.com",
                                        status=StudioMembership.Status.ACTIVE)
        self.client.post(self.invite_url, self.payload | {"email": "MEMBER@example.com"})
        self.assertEqual(StudioMembership.objects.count(), 1)
        external = User.objects.create_user(email="external@example.com", password="password123")
        self.client.post(self.invite_url, self.payload | {"email": external.email})
        self.assertTrue(StudioMembership.objects.filter(invitation_email=external.email,
                                                        status=StudioMembership.Status.INVITED).exists())
