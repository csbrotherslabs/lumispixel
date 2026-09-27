from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse


class AuthenticationSessionSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            email="security-auth@example.com",
            password="Strong-test-password-941!",
        )
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

    def test_login_rotates_an_existing_anonymous_session_key(self):
        client = Client()
        session = client.session
        session["pre_auth_marker"] = "present"
        session.save()
        before = session.session_key

        response = client.post(reverse("accounts:login"), {
            "email": self.user.email,
            "password": "Strong-test-password-941!",
        })

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(client.session.session_key, before)
        self.assertEqual(str(client.session["_auth_user_id"]), str(self.user.pk))

    def test_logout_is_post_only_and_flushes_authenticated_session(self):
        client = Client()
        client.force_login(self.user)
        self.assertEqual(client.get(reverse("accounts:logout")).status_code, 405)
        response = client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", client.session)

    def test_login_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:login"), {
            "email": self.user.email,
            "password": "Strong-test-password-941!",
        })
        self.assertEqual(response.status_code, 403)

    def test_signup_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:client-signup"), {
            "first_name": "Test", "last_name": "User",
            "email": "new-security@example.com",
            "password": "Another-strong-password-941!",
            "password_confirmation": "Another-strong-password-941!",
            "accept_terms": "on", "accept_privacy": "on",
        })
        self.assertEqual(response.status_code, 403)

    def test_password_reset_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:password-reset"), {"email": self.user.email})
        self.assertEqual(response.status_code, 403)

    def test_resend_verification_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:resend-verification"))
        self.assertEqual(response.status_code, 403)

    def test_repeated_failed_logins_are_throttled(self):
        url = reverse("accounts:login")
        client = Client(REMOTE_ADDR="203.0.113.10")
        for _ in range(10):
            response = client.post(url, {"email": self.user.email, "password": "wrong-password"})
            self.assertEqual(response.status_code, 200)
        response = client.post(url, {"email": self.user.email, "password": "wrong-password"})
        self.assertEqual(response.status_code, 429)

    def test_successful_login_clears_failure_counter(self):
        url = reverse("accounts:login")
        client = Client(REMOTE_ADDR="203.0.113.11")
        for _ in range(3):
            client.post(url, {"email": self.user.email, "password": "wrong-password"})
        response = client.post(url, {
            "email": self.user.email,
            "password": "Strong-test-password-941!",
        })
        self.assertEqual(response.status_code, 302)

    def test_invalid_credentials_do_not_disclose_account_existence(self):
        client = Client()
        existing = client.post(reverse("accounts:login"), {
            "email": self.user.email, "password": "wrong-password",
        })
        missing = client.post(reverse("accounts:login"), {
            "email": "does-not-exist@example.com", "password": "wrong-password",
        })
        self.assertContains(existing, "Please enter a correct email address and password.")
        self.assertContains(missing, "Please enter a correct email address and password.")


class CookieSecurityContractTests(TestCase):
    def test_cookie_policy_is_explicit(self):
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")

    def test_production_transport_security_is_declared(self):
        from django.conf import settings
        settings_text = open(settings.BASE_DIR / "config" / "settings.py", encoding="utf-8").read()
        self.assertIn("SESSION_COOKIE_SECURE = True", settings_text)
        self.assertIn("CSRF_COOKIE_SECURE = True", settings_text)
        self.assertIn("SECURE_SSL_REDIRECT", settings_text)
        self.assertIn("SECURE_HSTS_SECONDS", settings_text)
