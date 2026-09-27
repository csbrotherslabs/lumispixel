from datetime import timedelta

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path, reverse
from django.utils import timezone

from apps.accounts.decorators import (
    client_profile_required,
    photographer_profile_required,
    staff_required,
    verified_photographer_required,
)
from apps.accounts.models import ClientProfile, PhotographerProfile

User = get_user_model()


def make_user(**kwargs):
    password = kwargs.pop("password", "TestPass123!")
    kwargs.setdefault("account_status", User.AccountStatus.ACTIVE)
    kwargs.setdefault("email_verified", True)
    kwargs.setdefault("onboarding_completed", True)
    return User.objects.create_user(password=password, **kwargs)


class UserBehaviorTests(TestCase):
    def test_user_manager_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(email="USER@Example.COM", password="secret123")
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password("secret123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_user_manager_rejects_missing_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="secret123")

    def test_superuser_flags_are_enforced(self):
        user = User.objects.create_superuser(email="admin@example.com", password="secret123")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.email_verified)
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="bad@example.com", password="secret123", is_staff=False)

    def test_display_name_and_login_eligibility(self):
        user = make_user(email="name@example.com", first_name="Ada", last_name="Lovelace")
        self.assertEqual(user.full_name, "Ada Lovelace")
        self.assertEqual(user.display_name, "Ada Lovelace")
        self.assertTrue(user.can_login)
        user.account_status = User.AccountStatus.SUSPENDED
        self.assertFalse(user.can_login)

    def test_email_verification_activation(self):
        user = User.objects.create_user(email="pending@example.com", password="secret123")
        user.mark_email_verified()
        self.assertTrue(user.email_verified)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertIsNotNone(user.email_verified_at)

    def test_profile_capabilities_follow_persisted_profiles(self):
        user = make_user(email="profiles@example.com")
        self.assertFalse(user.has_client_profile)
        self.assertFalse(user.has_photographer_profile)
        ClientProfile.objects.create(user=user)
        PhotographerProfile.objects.create(user=user, slug="profiles")
        self.assertTrue(user.has_client_profile)
        self.assertTrue(user.has_photographer_profile)
        self.assertTrue(user.can_use_marketplace_as_client)
        self.assertTrue(user.can_use_photographer_workspace)


class PhotographerProfileBehaviorTests(TestCase):
    def test_verification_and_payout_capabilities(self):
        user = make_user(email="photo@example.com")
        profile = PhotographerProfile.objects.create(
            user=user,
            slug="photo",
            verification_status=PhotographerProfile.VerificationStatus.APPROVED,
        )
        self.assertTrue(profile.is_verified)
        self.assertFalse(profile.can_receive_payouts)
        profile.payout_setup_completed = True
        self.assertTrue(profile.can_receive_payouts)

    def test_expired_verification_is_not_valid(self):
        user = make_user(email="expired@example.com")
        profile = PhotographerProfile.objects.create(
            user=user,
            slug="expired",
            verification_status=PhotographerProfile.VerificationStatus.APPROVED,
            verification_expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(profile.is_verified)


class LoginRoutingTests(TestCase):
    def test_valid_login_uses_post_login_router(self):
        make_user(email="login@example.com", password="secret123")
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "login@example.com", "password": "secret123"},
        )
        self.assertRedirects(
            response,
            reverse("accounts:post-login-redirect"),
            fetch_redirect_response=False,
        )

    def test_invalid_and_suspended_logins_do_not_authenticate(self):
        invalid = self.client.post(
            reverse("accounts:login"),
            {"email": "missing@example.com", "password": "bad"},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        make_user(
            email="suspended@example.com",
            password="secret123",
            account_status=User.AccountStatus.SUSPENDED,
        )
        suspended = self.client.post(
            reverse("accounts:login"),
            {"email": "suspended@example.com", "password": "secret123"},
        )
        self.assertEqual(suspended.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_safe_next_is_preserved_and_external_next_is_rejected(self):
        make_user(email="next@example.com", password="secret123")
        safe = self.client.post(
            reverse("accounts:login") + "?next=/galleries/",
            {"email": "next@example.com", "password": "secret123"},
        )
        self.assertRedirects(
            safe,
            reverse("accounts:post-login-redirect") + "?next=/galleries/",
            fetch_redirect_response=False,
        )

        self.client.logout()
        external = self.client.post(
            reverse("accounts:login") + "?next=https://evil.example/",
            {"email": "next@example.com", "password": "secret123"},
        )
        self.assertRedirects(
            external,
            reverse("accounts:post-login-redirect"),
            fetch_redirect_response=False,
        )

    def test_unverified_user_routes_to_verification(self):
        user = make_user(email="verify@example.com", email_verified=False)
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("accounts:post-login-redirect")),
            reverse("accounts:email-verification-required"),
        )

    def test_photographer_routes_to_photographer_onboarding(self):
        user = make_user(
            email="photo-role@example.com",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("accounts:post-login-redirect")),
            reverse("photographers:setup-dashboard"),
            fetch_redirect_response=False,
        )

    def test_client_profile_is_created_and_incomplete_client_routes_to_onboarding(self):
        user = make_user(email="missing-client-profile@example.com", onboarding_completed=False)
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("accounts:post-login-redirect")),
            reverse("clients:setup-dashboard"),
            fetch_redirect_response=False,
        )
        self.assertTrue(ClientProfile.objects.filter(user=user).exists())

    def test_completed_client_routes_to_dashboard(self):
        user = make_user(email="completed-client@example.com")
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:post-login-redirect"))
        self.assertRedirects(
            response,
            reverse("clients:dashboard"),
            fetch_redirect_response=False,
        )
        dashboard = self.client.get(reverse("clients:dashboard"))
        self.assertEqual(dashboard.status_code, 200)

    def test_photographer_with_client_profile_still_uses_photographer_routing(self):
        user = make_user(
            email="photo-not-client@example.com",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        ClientProfile.objects.create(user=user, onboarding_completed=False)
        PhotographerProfile.objects.create(user=user, slug="photo-not-client")
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("accounts:post-login-redirect")),
            reverse("photographers:setup-dashboard"),
            fetch_redirect_response=False,
        )

    def test_logout_requires_post_and_clears_session(self):
        user = make_user(email="logout@example.com")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class ClientOnboardingBehaviorTests(TestCase):
    def test_anonymous_client_routes_require_login(self):
        for name in (
            "clients:dashboard",
            "clients:onboarding-welcome",
            "clients:onboarding-profile",
            "clients:onboarding-how-it-works",
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response,
                    f"{reverse('accounts:login')}?next={reverse(name)}",
                    fetch_redirect_response=False,
                )

    def test_finishing_setup_persists_completion(self):
        user = make_user(email="finish-client@example.com")
        profile = ClientProfile.objects.create(user=user, onboarding_completed=False)
        self.client.force_login(user)
        response = self.client.post(reverse("clients:onboarding-how-it-works"))
        self.assertRedirects(
            response,
            reverse("clients:dashboard"),
            fetch_redirect_response=False,
        )
        profile.refresh_from_db()
        self.assertTrue(profile.onboarding_completed)

    def test_completed_onboarding_steps_redirect_to_dashboard(self):
        user = make_user(email="completed-onboarding@example.com")
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)
        for name in (
            "clients:onboarding-welcome",
            "clients:onboarding-profile",
            "clients:onboarding-how-it-works",
        ):
            with self.subTest(name=name):
                self.assertRedirects(
                    self.client.get(reverse(name)),
                    reverse("clients:dashboard"),
                    fetch_redirect_response=False,
                )

    def test_incomplete_dashboard_redirects_to_onboarding(self):
        user = make_user(email="incomplete-dashboard@example.com")
        ClientProfile.objects.create(user=user, onboarding_completed=False)
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("clients:dashboard")),
            reverse("clients:setup-dashboard"),
            fetch_redirect_response=False,
        )

    def test_legacy_client_settings_always_redirects_to_shared_settings(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                user = make_user(email=f"settings-{completed}@example.com")
                ClientProfile.objects.create(user=user, onboarding_completed=completed)
                self.client.force_login(user)
                self.assertRedirects(
                    self.client.get(reverse("clients:account-settings")),
                    reverse("accounts:account-settings"),
                    fetch_redirect_response=False,
                )
                self.client.logout()

    def test_shared_account_settings_renders_for_completed_client(self):
        user = make_user(email="client-settings@example.com")
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:account-settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/account_settings.html")

    def test_user_without_client_profile_cannot_access_client_dashboard(self):
        user = make_user(
            email="photo-client-dashboard@example.com",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            last_active_workspace=User.Workspace.PHOTOGRAPHER,
        )
        PhotographerProfile.objects.create(user=user, slug="photo-client-dashboard")
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("clients:dashboard")),
            reverse("accounts:post-login-redirect"),
            fetch_redirect_response=False,
        )


def ok(request):
    return HttpResponse("ok")


urlpatterns = [
    path("client/", client_profile_required(ok), name="client"),
    path("photo/", photographer_profile_required(ok), name="photo"),
    path("verified/", verified_photographer_required(ok), name="verified"),
    path("staff/", staff_required(ok), name="staff"),
    path("accounts/login/", lambda request: HttpResponse("login"), name="login"),
]


@override_settings(ROOT_URLCONF="apps.accounts.tests.test_auth_foundation", LOGIN_URL="/accounts/login/")
class PermissionDecoratorTests(TestCase):
    def test_guest_is_redirected(self):
        self.assertEqual(self.client.get("/client/").status_code, 302)

    def test_profile_decorators_grant_expected_access(self):
        client_user = make_user(email="clientaccess@example.com")
        ClientProfile.objects.create(user=client_user)
        self.client.force_login(client_user)
        self.assertEqual(self.client.get("/client/").status_code, 200)

        photo_user = make_user(email="photoaccess@example.com")
        PhotographerProfile.objects.create(user=photo_user, slug="photoaccess")
        self.client.force_login(photo_user)
        self.assertEqual(self.client.get("/photo/").status_code, 200)

    def test_verified_and_staff_decorators(self):
        verified = make_user(email="verifiedaccess@example.com")
        PhotographerProfile.objects.create(
            user=verified,
            slug="verifiedaccess",
            verification_status=PhotographerProfile.VerificationStatus.APPROVED,
        )
        self.client.force_login(verified)
        self.assertEqual(self.client.get("/verified/").status_code, 200)

        staff = User.objects.create_superuser(email="staff@example.com", password="secret123")
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/staff/").status_code, 200)

    def test_unauthorized_profile_access_is_rejected(self):
        user = make_user(email="noaccess@example.com")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/photo/").status_code, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    def test_login_page_exposes_password_reset_route(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:password-reset"))

    def test_password_reset_sends_one_email_for_existing_user(self):
        from django.core import mail

        make_user(email="reset@example.com", password="OldPass123!")
        response = self.client.post(
            reverse("accounts:password-reset"),
            {"email": "reset@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(
            mail.outbox[0].body,
            r"/accounts/reset/[A-Za-z0-9_-]+/[A-Za-z0-9:._-]+/",
        )

    def test_password_reset_does_not_reveal_missing_account(self):
        from django.core import mail

        response = self.client.post(
            reverse("accounts:password-reset"),
            {"email": "missing@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 0)
