from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User


class SharedAccountSettingsTests(TestCase):
    def make_user(self, email="person@example.com"):
        return User.objects.create_user(
            email=email,
            password="TestPass123!",
            first_name="Amara",
            last_name="Reed",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )

    def test_photographer_account_settings_is_person_level(self):
        user = self.make_user()
        PhotographerProfile.objects.create(
            user=user,
            business_name="North & Pine",
            onboarding_completed=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:account-settings"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/account_settings.html")
        self.assertContains(response, 'id="account-settings-title"')
        self.assertContains(response, 'id="profile"')
        self.assertContains(response, 'id="preferences"')
        self.assertContains(response, 'id="security"')
        self.assertContains(response, reverse("photographer_workspace:settings"))

    def test_client_legacy_settings_redirects_to_shared_settings(self):
        user = self.make_user("client@example.com")
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("clients:account-settings"))

        self.assertRedirects(
            response,
            reverse("accounts:account-settings"),
            fetch_redirect_response=False,
        )

    def test_personal_settings_do_not_change_photographer_business_name(self):
        user = self.make_user("owner@example.com")
        studio = PhotographerProfile.objects.create(
            user=user,
            business_name="North & Pine",
            onboarding_completed=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:account-settings"))

        self.assertEqual(response.status_code, 200)
        studio.refresh_from_db()
        self.assertEqual(studio.business_name, "North & Pine")

    def test_valid_photo_upload_persists_after_signing_back_in(self):
        import io
        import tempfile
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from apps.accounts.models import Country

        user = self.make_user("photo@example.com")
        country = Country.objects.create(name="Testland", iso2="TT", iso3="TTT", source_id=99001)
        self.client.force_login(user)
        image = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(image, format="PNG")
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(reverse("accounts:account-settings"), {
                "first_name": "Amara", "last_name": "Reed",
                "country_record": country.pk, "city": "Test City", "timezone": "UTC",
                "profile_photo": SimpleUploadedFile("avatar.png", image.getvalue(), content_type="image/png"),
            })
            self.assertEqual(response.status_code, 302)
            profile = ClientProfile.objects.get(user=user)
            self.assertTrue(profile.profile_photo.storage.exists(profile.profile_photo.name))
            self.client.logout()
            self.client.force_login(user)
            response = self.client.get(reverse("accounts:account-settings"))
            self.assertContains(response, profile.profile_photo.url)

    def test_failed_validation_explains_why_photo_changes_were_not_saved(self):
        user = self.make_user("invalid-photo@example.com")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:account-settings"), {
            "first_name": "Amara", "last_name": "Reed", "timezone": "UTC",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your changes were not saved.")
        self.assertContains(response, 'href="#id_country_record"')
        self.assertContains(response, 'href="#id_city"')
        self.assertContains(response, "select your photo again")
