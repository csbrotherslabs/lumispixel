from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, PhotographerWebsiteProfile, User
from apps.photographers.themes import THEME_DEFINITIONS


class PhotographerSettingsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="TestPass123!",
            first_name="Amara",
            last_name="Reed",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user,
            business_name="North & Pine",
            onboarding_completed=True,
            website_theme=PhotographerProfile.WebsiteTheme.BASIC,
        )
        self.website = PhotographerWebsiteProfile.objects.create(
            photographer_profile=self.profile,
            theme_content={"hero_heading": "Keep this content"},
        )
        self.client.force_login(self.user)

    def test_settings_renders_all_website_designs_and_preview_links(self):
        response = self.client.get(reverse("photographer_workspace:settings"))

        self.assertEqual(response.status_code, 200)
        for definition in THEME_DEFINITIONS.values():
            self.assertContains(response, definition["name"])
            self.assertContains(
                response,
                reverse("photographers:theme-preview", args=[definition["slug"]]),
            )
        self.assertContains(response, "Preview another design without changing your current website")
        self.assertContains(response, "Current website")

    def test_preview_does_not_change_saved_website_theme(self):
        preview_url = reverse("photographers:theme-preview", args=[THEME_DEFINITIONS["elegant"]["slug"]])
        response = self.client.get(preview_url)

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.BASIC)

    def test_switch_changes_theme_and_applies_new_default_sections_without_losing_content(self):
        response = self.client.post(
            reverse("photographer_workspace:switch_website_theme"),
            {"website_theme": PhotographerProfile.WebsiteTheme.ELEGANT},
        )

        self.assertRedirects(response, reverse("photographer_workspace:settings"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.website.refresh_from_db()
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.ELEGANT)
        self.assertEqual(self.website.theme_content["hero_heading"], "Keep this content")
        enabled_sections = list(
            self.website.sections.filter(is_enabled=True)
            .order_by("display_order")
            .values_list("section_type", flat=True)
        )
        self.assertEqual(enabled_sections, THEME_DEFINITIONS["elegant"]["sections"])

    def test_invalid_switch_does_not_change_theme(self):
        response = self.client.post(
            reverse("photographer_workspace:switch_website_theme"),
            {"website_theme": "not-a-theme"},
        )

        self.assertRedirects(response, reverse("photographer_workspace:settings"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.BASIC)

    def test_switch_endpoint_rejects_get(self):
        response = self.client.get(reverse("photographer_workspace:switch_website_theme"))
        self.assertEqual(response.status_code, 405)
