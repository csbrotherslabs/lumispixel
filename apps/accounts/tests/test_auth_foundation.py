from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.decorators import client_profile_required, photographer_profile_required, staff_required, verified_photographer_required
from apps.accounts.models import ClientProfile, PhotographerProfile

User = get_user_model()


def make_user(**kwargs):
    password = kwargs.pop("password", "TestPass123!")
    kwargs.setdefault("account_status", User.AccountStatus.ACTIVE)
    kwargs.setdefault("email_verified", True)
    kwargs.setdefault("onboarding_completed", True)
    return User.objects.create_user(password=password, **kwargs)


class UserManagerTests(TestCase):
    def test_creates_regular_user(self):
        user = User.objects.create_user(email="client@example.com", password="secret123")
        self.assertEqual(user.email, "client@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(email="USER@Example.COM", password="secret123")
        self.assertEqual(user.email, "user@example.com")
        self.assertNotEqual(user.password, "secret123")
        self.assertTrue(user.check_password("secret123"))

    def test_rejects_missing_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="secret123")

    def test_creates_valid_superuser(self):
        user = User.objects.create_superuser(email="admin@example.com", password="secret123")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.email_verified)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)

    def test_rejects_invalid_superuser_flags(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="admin@example.com", password="secret123", is_staff=False)
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="admin2@example.com", password="secret123", is_superuser=False)


class UserModelTests(TestCase):
    def test_full_name_and_display_name(self):
        user = make_user(email="name@example.com", first_name="Ada", last_name="Lovelace")
        self.assertEqual(user.full_name, "Ada Lovelace")
        self.assertEqual(user.display_name, "Ada Lovelace")
        user.first_name = ""
        user.last_name = ""
        self.assertEqual(user.display_name, "name@example.com")

    def test_account_login_eligibility(self):
        user = make_user(email="active@example.com")
        self.assertTrue(user.can_login)
        user.account_status = User.AccountStatus.SUSPENDED
        self.assertFalse(user.can_login)

    def test_email_verification_activation(self):
        user = User.objects.create_user(email="pending@example.com", password="secret123")
        user.mark_email_verified()
        self.assertTrue(user.email_verified)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertIsNotNone(user.email_verified_at)

    def test_profile_capability_detection(self):
        user = make_user(email="profiles@example.com")
        self.assertFalse(user.has_client_profile)
        self.assertFalse(user.has_photographer_profile)
        ClientProfile.objects.create(user=user)
        PhotographerProfile.objects.create(user=user, slug="profiles")
        self.assertTrue(user.has_client_profile)
        self.assertTrue(user.has_photographer_profile)
        self.assertTrue(user.can_use_marketplace_as_client)
        self.assertTrue(user.can_use_photographer_workspace)


class PhotographerProfileTests(TestCase):
    def test_approved_photographer_is_verified(self):
        user = make_user(email="photo@example.com")
        profile = PhotographerProfile.objects.create(user=user, slug="photo", verification_status=PhotographerProfile.VerificationStatus.APPROVED)
        self.assertTrue(profile.is_verified)

    def test_expired_verification_is_not_valid(self):
        user = make_user(email="expired@example.com")
        profile = PhotographerProfile.objects.create(user=user, slug="expired", verification_status=PhotographerProfile.VerificationStatus.APPROVED, verification_expires_at=timezone.now() - timedelta(days=1))
        self.assertFalse(profile.is_verified)

    def test_marketplace_listing_requires_verification(self):
        user = make_user(email="market@example.com")
        profile = PhotographerProfile.objects.create(user=user, slug="market", public_profile_enabled=True, accepts_marketplace_requests=True)
        self.assertFalse(profile.can_publish_marketplace_listing)
        profile.verification_status = PhotographerProfile.VerificationStatus.APPROVED
        self.assertTrue(profile.can_publish_marketplace_listing)

    def test_payouts_require_verification_and_payout_setup(self):
        user = make_user(email="payout@example.com")
        profile = PhotographerProfile.objects.create(user=user, slug="payout", verification_status=PhotographerProfile.VerificationStatus.APPROVED)
        self.assertFalse(profile.can_receive_payouts)
        profile.payout_setup_completed = True
        self.assertTrue(profile.can_receive_payouts)


class LoginTests(TestCase):
    def test_valid_email_and_password_login(self):
        make_user(email="login@example.com", password="secret123")
        response = self.client.post(reverse("accounts:login"), {"email": "login@example.com", "password": "secret123"})
        self.assertRedirects(response, reverse("accounts:post-login-redirect"), fetch_redirect_response=False)

    def test_invalid_credentials(self):
        response = self.client.post(reverse("accounts:login"), {"email": "missing@example.com", "password": "bad"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct email address and password")

    def test_suspended_account_rejection(self):
        make_user(email="suspended@example.com", password="secret123", account_status=User.AccountStatus.SUSPENDED)
        response = self.client.post(reverse("accounts:login"), {"email": "suspended@example.com", "password": "secret123"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account cannot log in")

    def test_safe_next_redirect(self):
        make_user(email="next@example.com", password="secret123")
        response = self.client.post(reverse("accounts:login") + "?next=/galleries/", {"email": "next@example.com", "password": "secret123"})
        self.assertRedirects(response, reverse("accounts:post-login-redirect") + "?next=/galleries/", fetch_redirect_response=False)

    def test_external_next_url_rejection(self):
        make_user(email="external@example.com", password="secret123")
        response = self.client.post(reverse("accounts:login") + "?next=https://evil.example/", {"email": "external@example.com", "password": "secret123"})
        self.assertRedirects(response, reverse("accounts:post-login-redirect"), fetch_redirect_response=False)

    def test_email_verification_redirect(self):
        user = make_user(email="verify@example.com", email_verified=False)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("accounts:email-verification-required"))

    def test_role_aware_redirect(self):
        user = make_user(email="photo-role@example.com", primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:post-login-redirect")), reverse("accounts:photographer-dashboard"))


    def test_logout_requires_post(self):
        user = make_user(email="logout-get@example.com")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

    def test_logout_post_redirects_home_and_clears_session(self):
        user = make_user(email="logout-post@example.com")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:index"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


from django.http import HttpResponse
from django.urls import path


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
class PermissionTests(TestCase):

    def test_guest_redirection(self):
        self.assertEqual(self.client.get("/client/").status_code, 302)

    def test_client_access(self):
        user = make_user(email="clientaccess@example.com")
        ClientProfile.objects.create(user=user)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/client/").status_code, 200)

    def test_photographer_access(self):
        user = make_user(email="photoaccess@example.com")
        PhotographerProfile.objects.create(user=user, slug="photoaccess")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/photo/").status_code, 200)

    def test_verified_photographer_access(self):
        user = make_user(email="verifiedaccess@example.com")
        PhotographerProfile.objects.create(user=user, slug="verifiedaccess", verification_status=PhotographerProfile.VerificationStatus.APPROVED)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/verified/").status_code, 200)

    def test_staff_access(self):
        user = User.objects.create_superuser(email="staff@example.com", password="secret123")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/staff/").status_code, 200)

    def test_unauthorized_access_rejection(self):
        user = make_user(email="noaccess@example.com")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/photo/").status_code, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:password-reset"))
        self.assertContains(response, "Forgot password?")

    def test_password_reset_sends_email_for_email_login_user(self):
        from django.core import mail

        make_user(email="reset@example.com", password="OldPass123!")
        response = self.client.post(reverse("accounts:password-reset"), {"email": "reset@example.com"})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("LumisPixel", mail.outbox[0].subject)
        self.assertRegex(mail.outbox[0].body, r"/accounts/reset/[A-Za-z0-9_-]+/[A-Za-z0-9:._-]+/")

    def test_password_reset_response_does_not_reveal_missing_account(self):
        from django.core import mail

        response = self.client.post(reverse("accounts:password-reset"), {"email": "missing@example.com"})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 0)
