from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import (
    AdministrativeRegion,
    ClientProfile,
    Country,
    PhotographerProfile,
    PhotographerSpecialty,
)
from apps.photographers.forms import PhotographerSpecialtiesForm
from apps.photographers.themes import SECTION_LIBRARY, THEME_DEFINITIONS

User = get_user_model()


def make_user(**kwargs):
    password = kwargs.pop("password", "TestPass123!")
    kwargs.setdefault("account_status", User.AccountStatus.ACTIVE)
    kwargs.setdefault("email_verified", True)
    return User.objects.create_user(password=password, **kwargs)


@override_settings(MEDIA_ROOT="/tmp/lumispixel-test-media")
class PhotographerOnboardingBehaviorTests(TestCase):
    def setUp(self):
        self.user = make_user(
            email="photo@example.com",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="photo")
        self.client_user = make_user(
            email="client@example.com",
            primary_role=User.PrimaryRole.CLIENT,
        )
        ClientProfile.objects.create(user=self.client_user)
        self.country = Country.objects.create(
            source_id=233,
            name="United States",
            iso2="US",
            iso3="USA",
        )
        self.region = AdministrativeRegion.objects.create(
            source_id=1456,
            country=self.country,
            name="California",
            code="US-CA",
            region_type="state",
        )

    def test_anonymous_user_redirects_to_login(self):
        response = self.client.get(reverse("photographers:setup-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_client_is_redirected_from_photographer_onboarding(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("photographers:setup-dashboard"))
        self.assertRedirects(
            response,
            reverse("clients:setup-dashboard"),
            fetch_redirect_response=False,
        )

    def test_photographer_can_access_all_onboarding_steps(self):
        self.client.force_login(self.user)
        for name in (
            "photographers:onboarding-welcome",
            "photographers:onboarding-profile",
            "photographers:onboarding-specialties",
            "photographers:onboarding-business",
            "photographers:onboarding-theme",
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_profile_step_exposes_location_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("photographers:onboarding-profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-location-country")
        self.assertContains(response, "data-location-region")

    def test_profile_step_persists_user_and_location_fields(self):
        self.client.force_login(self.user)
        image = SimpleUploadedFile(
            "avatar.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        logo = SimpleUploadedFile(
            "logo.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        response = self.client.post(
            reverse("photographers:onboarding-profile"),
            {
                "first_name": "Pat",
                "last_name": "Pixel",
                "display_name": "Pat Pixel",
                "business_name": "Lumis Studio",
                "phone_number": "+1 555 1212",
                "website": "https://example.com",
                "country_record": self.country.pk,
                "administrative_region": self.region.pk,
                "city": "Oakland",
                "timezone": "America/Los_Angeles",
                "profile_photo": image,
                "business_logo": logo,
            },
        )

        self.assertRedirects(
            response,
            reverse("photographers:onboarding-specialties"),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Pat")
        self.assertEqual(self.profile.display_name, "Pat Pixel")
        self.assertEqual(self.profile.country_record, self.country)
        self.assertEqual(self.profile.administrative_region, self.region)
        self.assertTrue(self.profile.profile_photo)
        self.assertTrue(self.profile.business_logo)

    def test_specialties_form_keeps_other_last(self):
        form = PhotographerSpecialtiesForm(instance=self.profile)
        self.assertEqual(form.fields["specialties"].queryset.last().slug, "other")

    def test_business_step_persists_travel_and_currency_settings(self):
        self.profile.onboarding_step = 4
        self.profile.save(update_fields=["onboarding_step", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("photographers:onboarding-business"),
            {
                "business_type": PhotographerProfile.BusinessType.STUDIO,
                "years_of_experience": 7,
                "travel_radius": "50",
                "willing_to_travel": "on",
                "destination_photographer": "on",
                "available_nationally": "on",
                "available_internationally": "on",
                "default_currency": "usd",
                "instagram_url": "https://instagram.com/lumis",
                "facebook_url": "",
                "tiktok_url": "",
                "linkedin_url": "",
                "youtube_url": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("photographers:onboarding-theme"),
            fetch_redirect_response=False,
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.default_currency, "USD")
        self.assertEqual(self.profile.travel_radius, 50)
        self.assertTrue(self.profile.willing_to_travel)
        self.assertTrue(self.profile.destination_photographer)
        self.assertTrue(self.profile.available_nationally)
        self.assertTrue(self.profile.available_internationally)

    def test_business_step_rejects_travel_without_coverage(self):
        self.profile.onboarding_step = 4
        self.profile.save(update_fields=["onboarding_step", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("photographers:onboarding-business"),
            {
                "business_type": PhotographerProfile.BusinessType.STUDIO,
                "years_of_experience": 7,
                "willing_to_travel": "on",
                "default_currency": "usd",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_step, 4)

    def test_finished_photographer_redirects_from_onboarding(self):
        self.profile.onboarding_completed = True
        self.profile.save(update_fields=["onboarding_completed", "updated_at"])
        self.client.force_login(self.user)

        for name in (
            "photographers:onboarding-welcome",
            "photographers:onboarding-profile",
            "photographers:onboarding-specialties",
            "photographers:onboarding-business",
            "photographers:onboarding-theme",
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response,
                    reverse("photographer_workspace:dashboard"),
                    fetch_redirect_response=False,
                )

    def test_photographer_routing_does_not_create_client_profile(self):
        PhotographerProfile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:post-login-redirect"))

        self.assertRedirects(
            response,
            reverse("photographers:setup-dashboard"),
            fetch_redirect_response=False,
        )
        self.assertTrue(PhotographerProfile.objects.filter(user=self.user).exists())
        self.assertFalse(ClientProfile.objects.filter(user=self.user).exists())


class PhotographerThemeBehaviorTests(TestCase):
    def setUp(self):
        self.user = make_user(
            email="theme-photo@example.com",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user,
            slug="theme-photo",
            onboarding_step=5,
        )
        self.client.force_login(self.user)

    def test_theme_selection_exposes_all_defined_theme_routes_and_defaults(self):
        response = self.client.get(reverse("photographers:onboarding-theme"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(THEME_DEFINITIONS), 6)
        for definition in THEME_DEFINITIONS.values():
            with self.subTest(theme=definition["slug"]):
                self.assertContains(
                    response,
                    reverse("photographers:theme-preview", args=[definition["slug"]]),
                )
                self.assertContains(
                    response,
                    f'data-default-sections="{",".join(definition["sections"])}"',
                )

    def test_theme_defaults_encode_availability_and_equipment_rules(self):
        for theme in THEME_DEFINITIONS.values():
            self.assertNotIn("availability", theme["sections"])
        for key in ("modern_studio", "cinematic", "sports_events"):
            self.assertIn("equipment", THEME_DEFINITIONS[key]["sections"])
        for key in ("basic", "elegant", "portfolio_editorial"):
            self.assertNotIn("equipment", THEME_DEFINITIONS[key]["sections"])

    def test_each_completed_preview_matches_declared_section_order(self):
        for definition in THEME_DEFINITIONS.values():
            with self.subTest(theme=definition["slug"]):
                response = self.client.get(
                    reverse("photographers:theme-preview", args=[definition["slug"]])
                )
                self.assertEqual(response.status_code, 200)
                content = response.content.decode()
                included = definition["sections"]
                for key in included:
                    self.assertIn(f'id="{key}"', content)
                for key in set(SECTION_LIBRARY) - set(included):
                    self.assertNotIn(f'id="{key}"', content)
                positions = [content.index(f'id="{key}"') for key in included]
                self.assertEqual(positions, sorted(positions))

    def test_theme_selection_persists_selected_theme(self):
        response = self.client.post(
            reverse("photographers:onboarding-theme"),
            {
                "website_theme": PhotographerProfile.WebsiteTheme.MODERN_STUDIO,
                "action": "continue_to_content",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.website_theme,
            PhotographerProfile.WebsiteTheme.MODERN_STUDIO,
        )

    def test_theme_preview_rejects_unknown_theme(self):
        response = self.client.get(
            reverse("photographers:theme-preview", args=["not-a-real-theme"])
        )
        self.assertEqual(response.status_code, 404)
