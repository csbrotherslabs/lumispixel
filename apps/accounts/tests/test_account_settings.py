from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User


class SharedAccountSettingsTests(TestCase):
    def make_user(self, email="person@example.com"):
        return User.objects.create_user(email=email,password="TestPass123!",first_name="Amara",last_name="Reed",account_status=User.AccountStatus.ACTIVE,email_verified=True)

    def test_photographer_account_settings_is_person_level(self):
        user=self.make_user()
        PhotographerProfile.objects.create(user=user,business_name="North & Pine",onboarding_completed=True)
        self.client.force_login(user)
        response=self.client.get(reverse("accounts:account-settings"))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,"Account settings")
        self.assertContains(response,"Workspace settings")
        self.assertContains(response,reverse("photographer_workspace:settings"))

    def test_client_legacy_settings_redirects_to_shared_settings(self):
        user=self.make_user("client@example.com")
        ClientProfile.objects.create(user=user,onboarding_completed=True)
        self.client.force_login(user)
        response=self.client.get(reverse("clients:account-settings"))
        self.assertRedirects(response,reverse("accounts:account-settings"),fetch_redirect_response=False)

    def test_personal_settings_do_not_change_photographer_business_name(self):
        user=self.make_user("owner@example.com")
        studio=PhotographerProfile.objects.create(user=user,business_name="North & Pine",onboarding_completed=True)
        self.client.force_login(user)
        response=self.client.get(reverse("accounts:account-settings"))
        self.assertEqual(response.status_code,200)
        studio.refresh_from_db()
        self.assertEqual(studio.business_name,"North & Pine")
