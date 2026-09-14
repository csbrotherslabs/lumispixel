from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User


class PhotographerWorkspaceHelpNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="help-photographer@example.com",
            password="TestPass123!",
            first_name="Avery",
            last_name="Stone",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        PhotographerProfile.objects.create(
            user=self.user,
            business_name="Avery Stone Photography",
            slug="avery-stone-help-test",
            onboarding_completed=True,
        )

    def test_workspace_help_redirects_to_real_support_center(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("photographer_workspace:help"))

        self.assertRedirects(
            response,
            reverse("support_help_center"),
            fetch_redirect_response=False,
        )

    def test_workspace_help_flow_renders_support_ticket_intake(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("photographer_workspace:help"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How can we help?")
        self.assertContains(response, "Open a ticket")
        self.assertContains(response, "Submit support ticket")
        self.assertNotContains(response, "Coming Soon")

    def test_workspace_topbar_help_links_keep_stable_workspace_route(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("photographer_workspace:dashboard"))

        self.assertEqual(response.status_code, 200)
        help_url = reverse("photographer_workspace:help")
        self.assertContains(response, f'href="{help_url}"', count=2)

    def test_workspace_help_requires_photographer_workspace_access(self):
        response = self.client.get(reverse("photographer_workspace:help"))

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse("support_help_center"))
