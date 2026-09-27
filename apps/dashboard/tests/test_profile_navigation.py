from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User


class PhotographerProfileNavigationTests(TestCase):
    def test_profile_uses_shared_site_navigation_and_sidebar(self):
        user = User.objects.create_user(
            email="photographer@example.com",
            password="TestPass123!",
            first_name="Amara",
            last_name="Reed",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        PhotographerProfile.objects.create(user=user, business_name="North & Pine", onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'class="header color-fixed')
        self.assertContains(response, 'class="aside_info_wrapper')
        self.assertNotContains(response, 'class="lpw-sidebar"')
