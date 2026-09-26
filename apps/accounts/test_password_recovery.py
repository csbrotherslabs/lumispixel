from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordRecoverySecurityTests(TestCase):
    password = "Strong-recovery-password-941!"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="recovery@example.com", password=self.password)
        self.user.email_verified = True
        self.user.account_status = User.AccountStatus.ACTIVE
        self.user.save(update_fields=["email_verified", "account_status"])

    def _reset_url(self, token):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        return reverse("accounts:password-reset-confirm", kwargs={"uidb64": uid, "token": token})

    def test_reset_request_does_not_disclose_account_existence(self):
        existing = self.client.post(reverse("accounts:password-reset"), {"email": self.user.email})
        missing = self.client.post(reverse("accounts:password-reset"), {"email": "missing@example.com"})
        self.assertEqual(existing.status_code, 302)
        self.assertEqual(missing.status_code, 302)
        self.assertEqual(existing.url, missing.url)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_requests_are_rate_limited(self):
        client = Client(REMOTE_ADDR="203.0.113.50")
        url = reverse("accounts:password-reset")
        for _ in range(5):
            self.assertEqual(client.post(url, {"email": self.user.email}).status_code, 302)
        self.assertEqual(client.post(url, {"email": self.user.email}).status_code, 429)

    def test_password_change_invalidates_previously_issued_reset_token(self):
        token = default_token_generator.make_token(self.user)
        self.assertTrue(default_token_generator.check_token(self.user, token))
        self.user.set_password("A-new-strong-password-842!")
        self.user.save(update_fields=["password"])
        self.assertFalse(default_token_generator.check_token(self.user, token))

    def test_reset_token_cannot_be_reused_after_successful_reset(self):
        token = default_token_generator.make_token(self.user)
        url = self._reset_url(token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(response.url, {
            "new_password1": "Replacement-password-842!",
            "new_password2": "Replacement-password-842!",
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(default_token_generator.check_token(self.user, token))
        replay = self.client.get(url)
        self.assertEqual(replay.status_code, 200)
        self.assertContains(replay, "not valid")

    def test_password_reset_does_not_authenticate_an_anonymous_session(self):
        token = default_token_generator.make_token(self.user)
        response = self.client.get(self._reset_url(token))
        response = self.client.post(response.url, {
            "new_password1": "Replacement-password-743!",
            "new_password2": "Replacement-password-743!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_malformed_reset_link_is_rejected_without_state_change(self):
        old_password = self.user.password
        response = self.client.get(reverse(
            "accounts:password-reset-confirm",
            kwargs={"uidb64": "%%%", "token": "not-a-token"},
        ))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)

    def test_required_password_reset_flag_does_not_bypass_recovery(self):
        self.user.required_password_reset = True
        self.user.save(update_fields=["required_password_reset"])
        response = self.client.post(reverse("accounts:password-reset"), {"email": self.user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)


class AccountIdentityRecoveryContractTests(TestCase):
    def test_account_settings_does_not_directly_mutate_sign_in_email(self):
        source = open("apps/accounts/account_settings.py", encoding="utf-8").read()
        self.assertNotIn("user.email =", source)
        self.assertNotIn("request.user.email =", source)

    def test_email_identity_has_case_insensitive_database_uniqueness(self):
        constraints = {constraint.name for constraint in User._meta.constraints}
        self.assertIn("accounts_user_email_lower_unique", constraints)
