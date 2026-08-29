from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import ClientProfile, PhotographerProfile, User
from apps.accounts.services import EmailDeliveryError, email_verification_token


VALID = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ADA@Example.COM",
    "password": "StrongPass123!",
    "password_confirmation": "StrongPass123!",
    "accept_terms": "on",
    "accept_privacy": "on",
}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EntrySignupVerificationTests(TestCase):
    def test_get_started_links_and_next_safety(self):
        response = self.client.get(reverse("accounts:get-started") + "?next=/galleries/")
        self.assertContains(response, "Choose what you want to do next.")
        self.assertContains(response, "One account can hold your personal photos")
        self.assertContains(response, "css/get_started_polish.")
        self.assertContains(response, 'id="get-started-photographer"', count=1)
        self.assertContains(response, 'id="get-started-photos"', count=1)
        self.assertContains(response, 'id="get-started-hire"', count=1)
        self.assertContains(response, reverse("accounts:photographer-signup") + "?next=/galleries/")
        self.assertContains(response, reverse("accounts:client-signup") + "?intent=find_photos&amp;next=/galleries/")
        self.assertContains(response, reverse("accounts:client-signup") + "?intent=marketplace&amp;next=/galleries/")
        self.assertContains(response, reverse("accounts:login") + "?next=/galleries/")
        unsafe = self.client.get(reverse("accounts:get-started") + "?next=https://evil.example/")
        self.assertNotContains(unsafe, 'href="/signup/photographer/?next=https://evil.example/')
        self.assertNotContains(unsafe, 'href="/signup/client/?intent=find_photos&next=https://evil.example/')

    def test_authenticated_get_started_hides_sign_in_and_uses_capabilities(self):
        user = User.objects.create_user(
            email="signed-in@example.com",
            password="StrongPass123!",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        ClientProfile.objects.create(user=user, onboarding_completed=True)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:get-started"))

        self.assertNotContains(response, "Already have an account?")
        self.assertNotContains(response, reverse("accounts:login"))
        self.assertContains(response, "Signed in as")
        self.assertContains(response, "Open my photo space")
        self.assertContains(response, "Create photography workspace")

    def test_client_signup_creates_pending_client_and_sends_email(self):
        response = self.client.post(reverse("accounts:client-signup") + "?intent=find_photos", VALID)
        self.assertRedirects(response, reverse("accounts:verification-pending"), fetch_redirect_response=False)
        user = User.objects.get(email="ada@example.com")
        self.assertEqual(user.primary_role, User.PrimaryRole.CLIENT)
        self.assertEqual(user.account_status, User.AccountStatus.PENDING_EMAIL_VERIFICATION)
        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.terms_accepted_at)
        self.assertIsNotNone(user.privacy_policy_accepted_at)
        self.assertTrue(ClientProfile.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn("One quick step, Ada.", html_body)
        self.assertIn("Verify my email", html_body)
        self.assertIn("http://testserver/static/img/lumis_favicon_v1.", html_body)
        self.assertIn(".png", html_body)
        self.assertIn("LUMISPIXEL", html_body)
        self.assertIn("http://testserver/accounts/verify-email/", html_body)

    def test_client_signup_validation(self):
        User.objects.create_user(email="ada@example.com", password="StrongPass123!")
        duplicate = self.client.post(reverse("accounts:client-signup"), VALID)
        self.assertContains(duplicate, "Please log in to continue")
        data = VALID | {"email": "new@example.com", "password_confirmation": "Different123!"}
        self.assertContains(self.client.post(reverse("accounts:client-signup"), data), "Passwords do not match")
        weak = VALID | {"email": "weak@example.com", "password": "password", "password_confirmation": "password"}
        self.assertContains(self.client.post(reverse("accounts:client-signup"), weak), "too common")
        missing = VALID.copy(); missing.pop("accept_terms")
        self.assertContains(self.client.post(reverse("accounts:client-signup"), missing), "accept the terms")

    def test_photographer_signup_creates_photographer_without_client_profile(self):
        response = self.client.post(reverse("accounts:photographer-signup"), VALID | {"email": "photo@example.com"})
        self.assertRedirects(response, reverse("accounts:verification-pending"), fetch_redirect_response=False)
        user = User.objects.get(email="photo@example.com")
        self.assertEqual(user.primary_role, User.PrimaryRole.PHOTOGRAPHER)
        self.assertEqual(user.last_active_workspace, User.Workspace.PHOTOGRAPHER)
        self.assertFalse(ClientProfile.objects.filter(user=user).exists())
        profile = PhotographerProfile.objects.get(user=user)
        self.assertEqual(profile.verification_status, PhotographerProfile.VerificationStatus.NOT_STARTED)
        self.assertEqual(profile.onboarding_step, 1)
        self.assertFalse(profile.onboarding_completed)

    def test_verification_success_single_use_and_redirects(self):
        self.client.post(reverse("accounts:client-signup") + "?intent=marketplace", VALID | {"email": "verify@example.com"})
        user = User.objects.get(email="verify@example.com")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        response = self.client.get(reverse("accounts:verify-email", kwargs={"uidb64": uid, "token": token}))
        self.assertRedirects(response, reverse("clients:setup-dashboard"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertFalse(email_verification_token.check_token(user, token))
        invalid = self.client.get(reverse("accounts:verify-email", kwargs={"uidb64": uid, "token": token}))
        self.assertRedirects(invalid, reverse("clients:setup-dashboard"), fetch_redirect_response=False)

    def test_invalid_token_fails_safely(self):
        user = User.objects.create_user(email="badtoken@example.com", password="StrongPass123!")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        response = self.client.get(reverse("accounts:verify-email", kwargs={"uidb64": uid, "token": "bad-token"}))
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_photographer_verification_redirects_to_onboarding(self):
        self.client.post(reverse("accounts:photographer-signup"), VALID | {"email": "photoverify@example.com"})
        user = User.objects.get(email="photoverify@example.com")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        response = self.client.get(reverse("accounts:verify-email", kwargs={"uidb64": uid, "token": token}))
        self.assertRedirects(response, reverse("photographers:setup-dashboard"), fetch_redirect_response=False)

    def test_resend_post_only_cooldown_and_verified_skip(self):
        self.client.post(reverse("accounts:client-signup"), VALID | {"email": "resend@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.get(reverse("accounts:resend-verification")).status_code, 405)
        self.client.post(reverse("accounts:resend-verification"))
        self.assertEqual(len(mail.outbox), 2)
        self.client.post(reverse("accounts:resend-verification"))
        self.assertEqual(len(mail.outbox), 2)
        user = User.objects.get(email="resend@example.com")
        user.mark_email_verified()
        self.client.post(reverse("accounts:resend-verification"))
        self.assertEqual(len(mail.outbox), 2)

    def test_resend_email_delivery_failure_does_not_error_or_start_cooldown(self):
        self.client.post(reverse("accounts:client-signup"), VALID | {"email": "resendfailure@example.com"})
        with patch("apps.accounts.views.send_verification_email", side_effect=EmailDeliveryError):
            response = self.client.post(reverse("accounts:resend-verification"))
        self.assertRedirects(response, reverse("accounts:verification-pending"), fetch_redirect_response=False)
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("We could not send the verification email right now. Please try again.", messages)

        self.client.post(reverse("accounts:resend-verification"))
        self.assertEqual(len(mail.outbox), 2)

    def test_signup_email_delivery_failure_still_shows_pending_page(self):
        with patch("apps.accounts.views.send_verification_email", side_effect=EmailDeliveryError):
            response = self.client.post(reverse("accounts:client-signup"), VALID | {"email": "signupfailure@example.com"})
        self.assertRedirects(response, reverse("accounts:verification-pending"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email="signupfailure@example.com").exists())
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("We could not send the verification email right now. Please try again.", messages)

    def test_authenticated_signup_redirects_without_new_user(self):
        user = User.objects.create_user(email="existing@example.com", password="StrongPass123!", email_verified=True, account_status=User.AccountStatus.ACTIVE)
        ClientProfile.objects.create(user=user)
        self.client.force_login(user)
        before = User.objects.count()
        self.assertRedirects(self.client.get(reverse("accounts:photographer-signup")), reverse("clients:setup-dashboard"), fetch_redirect_response=False)
        self.assertEqual(User.objects.count(), before)
