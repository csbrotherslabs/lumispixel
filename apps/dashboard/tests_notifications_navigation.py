from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User


class PhotographerWorkspaceNotificationsNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
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
            user=self.user,
            business_name="North & Pine",
            onboarding_completed=True,
        )
        self.client.force_login(self.user)

    def test_workspace_topbar_links_to_real_notifications_inbox(self):
        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        notifications_url = reverse("notifications:index")
        placeholder_url = reverse("photographer_workspace:notifications")
        self.assertContains(response, f'href="{notifications_url}"', count=2)
        self.assertNotContains(response, f'href="{placeholder_url}"')

    def test_workspace_search_is_labeled_as_navigation_search(self):
        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'placeholder="Search navigation..."')
        self.assertContains(response, 'aria-label="Search workspace navigation"')
        self.assertNotContains(response, 'placeholder="Search workspace..."')
