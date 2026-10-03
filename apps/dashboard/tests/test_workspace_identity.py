from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.dashboard.identity import personal_photo_url
from apps.dashboard.views import _identity


class WorkspaceIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="identity@example.com", password="TestPass123!",
            first_name="Amara", account_status=User.AccountStatus.ACTIVE,
            email_verified=True, primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        self.studio = PhotographerProfile.objects.create(
            user=self.user, onboarding_completed=True,
            profile_photo="photographer_profiles/photos/old.jpg",
        )

    def test_updated_personal_photo_renders_on_dashboard_and_profile(self):
        personal = ClientProfile.objects.create(
            user=self.user, profile_photo="client-profiles/replacement.jpg",
        )
        self.client.force_login(self.user)
        for page in ("dashboard", "profile"):
            with self.subTest(page=page):
                response = self.client.get(reverse(f"photographer_workspace:{page}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, personal.profile_photo.url)
                self.assertNotContains(response, self.studio.profile_photo.url)

    def test_cleared_personal_photo_uses_initials(self):
        ClientProfile.objects.create(user=self.user)
        self.assertEqual(_identity(self.studio, self.user)["image_url"], "")

    def test_legacy_owner_photo_is_available_without_personal_profile(self):
        self.assertEqual(personal_photo_url(self.user), self.studio.profile_photo.url)

    def test_member_never_uses_workspace_owners_photo(self):
        member = User.objects.create_user(email="member@example.com", password="TestPass123!")
        self.assertEqual(_identity(self.studio, member)["image_url"], "")
