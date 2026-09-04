from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.dashboard.models import StudioMembership


class PhotographerProfilePageTests(TestCase):
    def _user(self, email="owner@example.com"):
        return User.objects.create_user(
            email=email,
            password="TestPass123!",
            first_name="Amara",
            last_name="Reed",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )

    def test_owner_profile_renders_person_and_contexts(self):
        user = self._user()
        PhotographerProfile.objects.create(user=user, business_name="North & Pine", onboarding_completed=True)
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Profile")
        self.assertContains(response, "North &amp; Pine")
        self.assertContains(response, "Personal photo space")

    def test_profile_updates_user_identity_not_business_profile(self):
        user = self._user()
        studio = PhotographerProfile.objects.create(user=user, display_name="North & Pine Studio", onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.post(reverse("photographer_workspace:profile"), {
            "first_name": "Amara Updated",
            "last_name": "Reed",
        })

        self.assertRedirects(response, reverse("photographer_workspace:profile"))
        user.refresh_from_db()
        studio.refresh_from_db()
        self.assertEqual(user.first_name, "Amara Updated")
        self.assertEqual(studio.display_name, "North & Pine Studio")

    def test_team_member_can_manage_same_person_profile(self):
        owner = self._user("studio-owner@example.com")
        studio = PhotographerProfile.objects.create(user=owner, business_name="Collective Studio", onboarding_completed=True)
        member = self._user("member@example.com")
        member.primary_role = User.PrimaryRole.CLIENT
        member.save(update_fields=["primary_role", "updated_at"])
        StudioMembership.objects.create(studio=studio, user=member, role=StudioMembership.Role.PHOTOGRAPHER, status=StudioMembership.Status.ACTIVE)
        self.client.force_login(member)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Collective Studio")
        self.assertContains(response, "Photographer")

    def test_profile_requires_photographer_workspace_access(self):
        user = self._user("client-only@example.com")
        user.primary_role = User.PrimaryRole.CLIENT
        user.save(update_fields=["primary_role", "updated_at"])
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertRedirects(response, reverse("accounts:post-login-redirect"), fetch_redirect_response=False)
