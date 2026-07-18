from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.dashboard.views import WORKSPACE_MODULES


def make_user(email, role=User.PrimaryRole.PHOTOGRAPHER):
    return User.objects.create_user(email=email, password="pass12345", primary_role=role, last_active_workspace=User.Workspace.PHOTOGRAPHER if role == User.PrimaryRole.PHOTOGRAPHER else User.Workspace.CLIENT, email_verified=True, account_status=User.AccountStatus.ACTIVE)


class PhotographerWorkspaceTests(TestCase):
    def make_photographer(self, completed=True, **profile_kwargs):
        user = make_user(profile_kwargs.pop("email", "photo@example.com"))
        profile = PhotographerProfile.objects.create(user=user, slug=profile_kwargs.pop("slug", "photo"), onboarding_completed=completed, **profile_kwargs)
        return user, profile

    def test_anonymous_client_and_incomplete_access_rules(self):
        url = reverse("photographer_workspace:dashboard")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)
        client_user = make_user("client@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(url), reverse("clients:dashboard"), fetch_redirect_response=False)
        self.client.logout()
        incomplete, _ = self.make_photographer(False, email="incomplete@example.com", slug="incomplete")
        self.client.force_login(incomplete)
        self.assertRedirects(self.client.get(url), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:galleries")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)

    def test_completed_photographer_dashboard_and_post_login_destination(self):
        user, _ = self.make_photographer(True, business_name="Lumis Studio", display_name="Alex Lens", website_theme=PhotographerProfile.WebsiteTheme.MODERN_STUDIO)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back, Lumis Studio")
        self.assertContains(response, "Modern Studio")
        self.assertContains(response, "Total Galleries")
        self.assertContains(response, "0")
        self.assertContains(response, f'href="{reverse("core:index")}" aria-label="LumisPixel home"')

    def test_missing_images_and_invalid_theme_fallback_do_not_error(self):
        user, profile = self.make_photographer(True, email="fallback@example.com", slug="fallback", display_name="Fallback Photo")
        PhotographerProfile.objects.filter(pk=profile.pk).update(website_theme="legacy")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fallback Photo")
        self.assertContains(response, "Elegant")

    def test_navigation_urls_and_placeholders_resolve(self):
        user, _ = self.make_photographer(True, email="nav@example.com", slug="nav")
        self.client.force_login(user)
        for module in WORKSPACE_MODULES:
            url = reverse(f"photographer_workspace:{module['url_name']}")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, module["title"])
            if module["key"] != "dashboard":
                self.assertContains(response, "Back to Dashboard")

    def test_active_navigation_item_is_correct(self):
        user, _ = self.make_photographer(True, email="active@example.com", slug="active")
        self.client.force_login(user)
        response = self.client.get(reverse("photographer_workspace:analytics"))
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Analytics")

    def test_client_cannot_access_module_url(self):
        client_user = make_user("client-module@example.com", User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=client_user, onboarding_completed=True)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(reverse("photographer_workspace:orders")), reverse("clients:dashboard"), fetch_redirect_response=False)

    def test_system_checks_pass(self):
        call_command("check")
