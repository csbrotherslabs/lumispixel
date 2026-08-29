from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.accounts.services import create_photographer_workspace
from apps.dashboard.access import access_for
from apps.dashboard.models import StudioMembership


class MultiContextAccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="multi@example.com",
            password="TestPass123!",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.client_profile = ClientProfile.objects.create(
            user=self.user,
            display_name="Multi User",
            onboarding_completed=True,
        )

    def test_client_can_create_owned_workspace_without_losing_client_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:enable-photographer-workspace"))

        self.assertRedirects(
            response,
            reverse("photographers:setup-dashboard"),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertTrue(ClientProfile.objects.filter(pk=self.client_profile.pk).exists())
        self.assertTrue(PhotographerProfile.objects.filter(user=self.user).exists())
        self.assertEqual(self.user.last_active_workspace, User.Workspace.PHOTOGRAPHER)
        self.assertEqual(access_for(self.user).role, StudioMembership.Role.OWNER)

    def test_workspace_creation_is_idempotent(self):
        first, first_created = create_photographer_workspace(self.user)
        second, second_created = create_photographer_workspace(self.user)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PhotographerProfile.objects.filter(user=self.user).count(), 1)

    def test_user_can_be_client_owner_and_member_at_the_same_time(self):
        owned, _ = create_photographer_workspace(self.user)
        other_owner = User.objects.create_user(
            email="other-owner@example.com",
            password="TestPass123!",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        other_studio = PhotographerProfile.objects.create(
            user=other_owner,
            display_name="Other Studio",
            onboarding_completed=True,
        )
        membership = StudioMembership.objects.create(
            studio=other_studio,
            user=self.user,
            role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )

        self.assertTrue(self.user.has_client_profile)
        self.assertTrue(self.user.has_photographer_profile)
        self.assertTrue(self.user.can_use_photographer_workspace)
        self.assertEqual(access_for(self.user).studio, owned)
        self.assertEqual(access_for(self.user, studio=other_studio).membership, membership)

    def test_team_member_does_not_need_an_owned_photographer_profile(self):
        owner = User.objects.create_user(
            email="owner@example.com",
            password="TestPass123!",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        studio = PhotographerProfile.objects.create(user=owner, onboarding_completed=True)
        StudioMembership.objects.create(
            studio=studio,
            user=self.user,
            role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.user.last_active_workspace = User.Workspace.PHOTOGRAPHER
        self.user.save(update_fields=["last_active_workspace", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:post-login-redirect"))

        self.assertRedirects(
            response,
            reverse("photographer_workspace:dashboard"),
            fetch_redirect_response=False,
        )
        self.assertFalse(PhotographerProfile.objects.filter(user=self.user).exists())

    def test_workspace_creation_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("accounts:enable-photographer-workspace")).status_code,
            405,
        )

    def test_invitation_signup_creates_personal_identity_not_owned_workspace(self):
        owner = User.objects.create_user(
            email="invite-owner@example.com",
            password="TestPass123!",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        studio = PhotographerProfile.objects.create(user=owner, onboarding_completed=True)
        invitation = StudioMembership.objects.create(
            studio=studio,
            invitation_email="new-member@example.com",
            role=StudioMembership.Role.PHOTOGRAPHER,
            status=StudioMembership.Status.INVITED,
        )
        invitation_path = reverse(
            "photographer_workspace:invitation_accept",
            args=["invitation-token"],
        )

        response = self.client.post(
            f'{reverse("accounts:photographer-signup")}?next={invitation_path}',
            {
                "first_name": "New",
                "last_name": "Member",
                "email": invitation.invitation_email,
                "password": "NewMemberPass123!",
                "password_confirmation": "NewMemberPass123!",
                "accept_terms": "on",
                "accept_privacy": "on",
                "next": invitation_path,
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:verification-pending"),
            fetch_redirect_response=False,
        )
        user = User.objects.get(email=invitation.invitation_email)
        self.assertTrue(ClientProfile.objects.filter(user=user).exists())
        self.assertFalse(PhotographerProfile.objects.filter(user=user).exists())
