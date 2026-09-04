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

    def test_owner_profile_renders_person_and_contexts_without_workspace_sidebar(self):
        user = self._user()
        PhotographerProfile.objects.create(user=user, business_name="North & Pine", onboarding_completed=True)
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amara Reed")
        self.assertContains(response, "North &amp; Pine")
        self.assertContains(response, "Personal photo space")
        self.assertContains(response, "Back to workspace")
        self.assertNotContains(response, 'class="lpw-sidebar"')

    def test_profile_is_display_only(self):
        user = self._user()
        PhotographerProfile.objects.create(user=user, display_name="North & Pine Studio", onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Save changes")
        self.assertNotContains(response, 'method="post"')
        self.assertContains(response, "Edit profile")

    def test_team_member_sees_person_profile_and_studio_context(self):
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

    def test_profile_rejects_post_edits(self):
        user = self._user()
        PhotographerProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.post(reverse("photographer_workspace:profile"), {"first_name": "Changed"})

        self.assertEqual(response.status_code, 405)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Amara")

    def test_profile_requires_photographer_workspace_access(self):
        user = self._user("client-only@example.com")
        user.primary_role = User.PrimaryRole.CLIENT
        user.save(update_fields=["primary_role", "updated_at"])
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertRedirects(response, reverse("accounts:post-login-redirect"), fetch_redirect_response=False)
