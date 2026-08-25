from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.accounts.onboarding import get_client_onboarding_resume_url, get_photographer_onboarding_resume_url


def make_user(email, role=User.PrimaryRole.CLIENT):
    return User.objects.create_user(
        email=email,
        password="pass12345",
        primary_role=role,
        last_active_workspace=User.Workspace.PHOTOGRAPHER if role == User.PrimaryRole.PHOTOGRAPHER else User.Workspace.CLIENT,
        email_verified=True,
        account_status=User.AccountStatus.ACTIVE,
    )


class SetupDashboardTests(TestCase):
    def test_incomplete_users_land_on_setup_dashboards_and_completed_users_leave(self):
        client_user = make_user("client-setup@example.com")
        ClientProfile.objects.create(user=client_user, onboarding_completed=False)
        self.client.force_login(client_user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("clients:setup-dashboard"), fetch_redirect_response=False)
        setup_response = self.client.get(reverse("clients:setup-dashboard"))
        self.assertContains(setup_response, "Continue Setup")
        self.assertContains(setup_response, 'class="client-setup__dashboard"')
        self.assertContains(setup_response, 'role="progressbar"')
        self.assertContains(setup_response, get_client_onboarding_resume_url(client_user.client_profile))

        client_user.client_profile.onboarding_completed = True
        client_user.client_profile.save(update_fields=["onboarding_completed", "updated_at"])
        self.assertRedirects(self.client.get(reverse("clients:setup-dashboard")), reverse("clients:dashboard"), fetch_redirect_response=False)
        self.client.logout()

        photo_user = make_user("photo-setup@example.com", User.PrimaryRole.PHOTOGRAPHER)
        PhotographerProfile.objects.create(user=photo_user, slug="photo-setup", onboarding_completed=False)
        self.client.force_login(photo_user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("photographers:setup-dashboard")), "Continue Setup")

        photo_user.photographer_profile.onboarding_completed = True
        photo_user.photographer_profile.save(update_fields=["onboarding_completed", "updated_at"])
        self.assertRedirects(self.client.get(reverse("photographers:setup-dashboard")), reverse("photographer_workspace:dashboard"), fetch_redirect_response=False)

    def test_skip_preserves_data_and_incomplete_state(self):
        user = make_user("skip-client@example.com")
        profile = ClientProfile.objects.create(user=user, display_name="Saved", onboarding_completed=False, onboarding_step=2)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("clients:onboarding-skip")), reverse("clients:setup-dashboard"), fetch_redirect_response=False)
        profile.refresh_from_db()
        self.assertEqual(profile.display_name, "Saved")
        self.assertFalse(profile.onboarding_completed)
        self.assertEqual(profile.onboarding_step, 2)
        self.client.logout()

        photo_user = make_user("skip-photo@example.com", User.PrimaryRole.PHOTOGRAPHER)
        photo_profile = PhotographerProfile.objects.create(user=photo_user, slug="skip-photo", display_name="Photo", onboarding_completed=False, onboarding_step=4)
        self.client.force_login(photo_user)
        self.assertRedirects(self.client.get(reverse("photographers:onboarding-skip")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)
        photo_profile.refresh_from_db()
        self.assertEqual(photo_profile.display_name, "Photo")
        self.assertFalse(photo_profile.onboarding_completed)
        self.assertEqual(photo_profile.onboarding_step, 4)

    def test_resume_helpers_and_access_rules(self):
        user = make_user("resume-client@example.com")
        profile = ClientProfile.objects.create(user=user, onboarding_step=3)
        self.assertEqual(get_client_onboarding_resume_url(profile), reverse("clients:onboarding-how-it-works"))
        profile.onboarding_step = 99
        self.assertEqual(get_client_onboarding_resume_url(profile), reverse("clients:onboarding-welcome"))

        photo_user = make_user("resume-photo@example.com", User.PrimaryRole.PHOTOGRAPHER)
        photo_profile = PhotographerProfile.objects.create(user=photo_user, slug="resume-photo", onboarding_step=5)
        self.assertEqual(get_photographer_onboarding_resume_url(photo_profile), reverse("photographers:onboarding-theme"))
        photo_profile.onboarding_step = 99
        self.assertEqual(get_photographer_onboarding_resume_url(photo_profile), reverse("photographers:onboarding-welcome"))

        self.assertRedirects(self.client.get(reverse("clients:setup-dashboard")), f'{reverse("accounts:login")}?next={reverse("clients:setup-dashboard")}', fetch_redirect_response=False)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("photographers:setup-dashboard")), reverse("clients:setup-dashboard"), fetch_redirect_response=False)
        self.client.logout()
        self.client.force_login(photo_user)
        self.assertRedirects(self.client.get(reverse("clients:setup-dashboard")), reverse("photographers:setup-dashboard"), fetch_redirect_response=False)

    def test_validation_failure_does_not_advance_step(self):
        user = make_user("invalid-client@example.com")
        profile = ClientProfile.objects.create(user=user, onboarding_step=2)
        self.client.force_login(user)
        self.client.post(reverse("clients:onboarding-profile"), {"first_name": "", "last_name": ""})
        profile.refresh_from_db()
        self.assertEqual(profile.onboarding_step, 2)
