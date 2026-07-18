from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, PhotographerSpecialty

User = get_user_model()


def make_user(**kwargs):
    password = kwargs.pop("password", "TestPass123!")
    kwargs.setdefault("account_status", User.AccountStatus.ACTIVE)
    kwargs.setdefault("email_verified", True)
    return User.objects.create_user(password=password, **kwargs)


@override_settings(MEDIA_ROOT="/tmp/lumispixel-test-media")
class PhotographerOnboardingTests(TestCase):
    def setUp(self):
        self.user = make_user(email="photo@example.com", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER)
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="photo")
        self.client_user = make_user(email="client@example.com", primary_role=User.PrimaryRole.CLIENT)
        ClientProfile.objects.create(user=self.client_user)
        self.wedding = PhotographerSpecialty.objects.get(slug="wedding")
        self.sports = PhotographerSpecialty.objects.get(slug="sports")

    def test_anonymous_user_redirects_to_login(self):
        response = self.client.get(reverse("photographers:onboarding-welcome"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_client_is_redirected_from_photographer_onboarding(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("photographers:onboarding-welcome"))
        self.assertRedirects(response, reverse("clients:onboarding-welcome"), fetch_redirect_response=False)

    def test_photographer_can_access_all_steps(self):
        self.client.force_login(self.user)
        for name in (
            "photographers:onboarding-welcome",
            "photographers:onboarding-profile",
            "photographers:onboarding-specialties",
            "photographers:onboarding-business",
            "photographers:onboarding-theme",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)

    def test_profile_step_saves_user_profile_and_uploads(self):
        self.client.force_login(self.user)
        image = SimpleUploadedFile("avatar.gif", b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif")
        logo = SimpleUploadedFile("logo.gif", image.read(), content_type="image/gif")
        image.seek(0)
        response = self.client.post(reverse("photographers:onboarding-profile"), {
            "first_name": "Pat", "last_name": "Pixel", "display_name": "Pat Pixel", "business_name": "Lumis Studio", "phone_number": "+1 555 1212", "website": "https://example.com", "country": "United States", "state": "CA", "city": "Oakland", "timezone": "America/Los_Angeles", "profile_photo": image, "business_logo": logo,
        })
        self.assertRedirects(response, reverse("photographers:onboarding-specialties"), fetch_redirect_response=False)
        self.user.refresh_from_db(); self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Pat")
        self.assertEqual(self.profile.display_name, "Pat Pixel")
        self.assertTrue(self.profile.profile_photo)
        self.assertTrue(self.profile.business_logo)

    def test_specialties_business_and_theme_save_and_reload(self):
        self.client.force_login(self.user)
        self.client.post(reverse("photographers:onboarding-specialties"), {"specialties": [self.wedding.pk, self.sports.pk]})
        self.assertEqual(set(self.profile.specialties.values_list("slug", flat=True)), {"wedding", "sports"})
        self.client.post(reverse("photographers:onboarding-business"), {"business_type": PhotographerProfile.BusinessType.STUDIO, "years_of_experience": 7, "service_area": "Bay Area", "willing_to_travel": "on", "default_currency": "usd", "instagram_url": "https://instagram.com/lumis", "facebook_url": "", "tiktok_url": "", "linkedin_url": "", "youtube_url": ""})
        self.client.post(reverse("photographers:onboarding-theme"), {"website_theme": PhotographerProfile.WebsiteTheme.SPORTS})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.business_type, PhotographerProfile.BusinessType.STUDIO)
        self.assertEqual(self.profile.default_currency, "USD")
        self.assertTrue(self.profile.willing_to_travel)
        self.assertEqual(self.profile.website_theme, PhotographerProfile.WebsiteTheme.SPORTS)
        self.assertTrue(self.profile.onboarding_completed)
        self.assertRedirects(self.client.get(reverse("photographers:onboarding-theme")), reverse("accounts:photographer-dashboard"), fetch_redirect_response=False)

    def test_validation_errors_are_inline(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("photographers:onboarding-profile"), {"first_name": "", "last_name": "", "website": "not-a-url"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lumis-onboarding__error")

    def test_finished_photographer_redirects_from_all_onboarding_steps(self):
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
                self.assertRedirects(response, reverse("accounts:photographer-dashboard"), fetch_redirect_response=False)

    def test_client_profile_is_not_created_for_photographer_routing(self):
        PhotographerProfile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:post-login-redirect"))

        self.assertRedirects(response, reverse("photographers:onboarding-welcome"), fetch_redirect_response=False)
        self.assertTrue(PhotographerProfile.objects.filter(user=self.user).exists())
        self.assertFalse(ClientProfile.objects.filter(user=self.user).exists())
