from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .services import email_verification_token

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailVerificationLifecycleTests(TestCase):
    password = "Strong-verification-password-941!"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="pending-verification@example.com",
            password=self.password,
            account_status=User.AccountStatus.PENDING_EMAIL_VERIFICATION,
            email_verified=False,
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))

    def _url(self, token=None, uid=None):
        return reverse(
            "accounts:verify-email",
            kwargs={"uidb64": uid or self.uid, "token": token or email_verification_token.make_token(self.user)},
        )

    def _remember_pending(self):
        session = self.client.session
        session["pending_verification_user_id"] = str(self.user.pk)
        session.save()

    def test_valid_token_activates_and_logs_in_user(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIsNotNone(self.user.email_verified_at)
        self.assertEqual(self.user.account_status, User.AccountStatus.ACTIVE)
        self.assertEqual(str(self.client.session["_auth_user_id"]), str(self.user.pk))

    def test_token_is_invalid_after_successful_verification(self):
        token = email_verification_token.make_token(self.user)
        self.client.get(self._url(token))
        self.user.refresh_from_db()
        self.assertFalse(email_verification_token.check_token(self.user, token))

    def test_replayed_link_is_safe_for_already_verified_account(self):
        token = email_verification_token.make_token(self.user)
        self.client.get(self._url(token))
        verified_at = User.objects.get(pk=self.user.pk).email_verified_at
        self.client.logout()
        response = self.client.get(self._url(token))
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email_verified_at, verified_at)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_malformed_uid_and_token_fail_without_state_change(self):
        response = self.client.get(self._url(token="not-a-token", uid="%%%"))
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
        self.assertEqual(self.user.account_status, User.AccountStatus.PENDING_EMAIL_VERIFICATION)

    @override_settings(EMAIL_VERIFICATION_TIMEOUT_SECONDS=60)
    def test_expired_token_is_rejected(self):
        issued = timezone.now() - timedelta(seconds=61)
        with patch.object(email_verification_token, "_now", return_value=issued):
            token = email_verification_token.make_token(self.user)
        response = self.client.get(self._url(token))
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_resend_requires_pending_session_and_does_not_accept_email_input(self):
        response = self.client.post(reverse("accounts:resend-verification"), {"email": self.user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_is_throttled_and_only_sends_once_per_window(self):
        self._remember_pending()
        url = reverse("accounts:resend-verification")
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_resend_for_verified_user_sends_nothing(self):
        self.user.mark_email_verified()
        self._remember_pending()
        response = self.client.post(reverse("accounts:resend-verification"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_page_without_session_does_not_disclose_account(self):
        response = self.client.get(reverse("accounts:verification-pending"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.user.email)

    def test_signup_persists_pending_account_when_email_delivery_fails(self):
        with patch("apps.accounts.views.send_verification_email", side_effect=__import__("apps.accounts.services", fromlist=["EmailDeliveryError"]).EmailDeliveryError()):
            response = self.client.post(reverse("accounts:client-signup"), {
                "first_name": "Pending",
                "last_name": "User",
                "email": "smtp-outage@example.com",
                "password": self.password,
                "password_confirmation": self.password,
                "accept_terms": "on",
                "accept_privacy": "on",
            })
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(email="smtp-outage@example.com")
        self.assertFalse(created.email_verified)
        self.assertEqual(created.account_status, User.AccountStatus.PENDING_EMAIL_VERIFICATION)
        self.assertEqual(self.client.session["verification_email_delivery_status"], "failed")
