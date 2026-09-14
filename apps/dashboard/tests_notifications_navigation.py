from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User


class PhotographerWorkspaceNotificationsNavigationTests(TestCase):
    def test_workspace_topbar_links_to_real_notifications_inbox(self):
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
        PhotographerProfile.objects.create(
            user=user,
            business_name="North & Pine",
            onboarding_completed=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        notifications_url = reverse("notifications:index")
        placeholder_url = reverse("photographer_workspace:notifications")
        self.assertContains(response, f'href="{notifications_url}"', count=2)
        self.assertNotContains(response, f'href="{placeholder_url}"')
