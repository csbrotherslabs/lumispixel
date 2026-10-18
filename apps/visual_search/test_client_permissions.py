"""Durable client authorization and withdrawal contracts; no real biometrics."""
import json
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.visual_search.client_permissions import PURPOSE
from apps.visual_search.models import ClientSelfieSearchPermission


@override_settings(
    VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED=True,
    VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION="test-notice-v1",
    VISUAL_SEARCH_CLIENT_CONSENT_NOTICE_URL="/privacy/biometric-test-notice/",
)
class ClientSelfiePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            email=f"alice-{uuid4().hex}@example.test",
            password="test-only", email_verified=True,
        )
        self.bob = User.objects.create_user(
            email=f"bob-{uuid4().hex}@example.test",
            password="test-only", email_verified=True,
        )
        self.url = reverse("visual_search:selfie-permission")
        self.client.force_login(self.alice)

    def grant(self, version="test-notice-v1", agree=True):
        return self.client.post(
            self.url,
            data=json.dumps({
                "purpose": PURPOSE, "policy_version": version, "agree": agree,
            }),
            content_type="application/json",
        )

    def test_explicit_opt_in_is_required_and_recorded(self):
        self.assertFalse(self.client.get(self.url).json()["authorized"])
        self.assertEqual(self.grant(agree=False).status_code, 400)
        self.assertEqual(self.grant(version="old").status_code, 400)
        self.assertEqual(ClientSelfieSearchPermission.objects.count(), 0)
        self.assertEqual(self.grant().status_code, 200)
        self.assertTrue(self.client.get(self.url).json()["authorized"])
        record = ClientSelfieSearchPermission.objects.get(user=self.alice)
        self.assertEqual(record.policy_version, "test-notice-v1")
        self.assertIsNotNone(record.granted_at)
        self.assertIsNone(record.withdrawn_at)
        self.assertEqual(self.grant().status_code, 200)
        self.assertEqual(ClientSelfieSearchPermission.objects.count(), 1)

    def test_withdrawal_blocks_search_and_preserves_history(self):
        self.grant()
        self.assertEqual(self.client.delete(self.url).status_code, 200)
        self.assertFalse(self.client.get(self.url).json()["authorized"])
        old = ClientSelfieSearchPermission.objects.get(user=self.alice)
        self.assertIsNotNone(old.withdrawn_at)
        self.assertEqual(self.client.delete(self.url).json()["withdrawn"], False)
        self.assertEqual(self.grant().status_code, 200)
        self.assertEqual(ClientSelfieSearchPermission.objects.filter(user=self.alice).count(), 2)
        self.assertEqual(
            ClientSelfieSearchPermission.objects.filter(
                user=self.alice, withdrawn_at__isnull=True,
            ).count(), 1,
        )

    def test_client_cannot_change_other_clients_permission(self):
        self.grant()
        self.client.force_login(self.bob)
        self.assertFalse(self.client.get(self.url).json()["authorized"])
        self.assertFalse(self.client.delete(self.url).json()["withdrawn"])
        self.assertEqual(
            ClientSelfieSearchPermission.objects.filter(
                user=self.alice, withdrawn_at__isnull=True,
            ).count(), 1,
        )

    def test_notice_change_invalidates_old_permission(self):
        self.grant()
        with override_settings(VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION="test-notice-v2"):
            self.assertFalse(self.client.get(self.url).json()["authorized"])
            self.assertEqual(self.grant(version="test-notice-v1").status_code, 400)
            self.assertEqual(self.grant(version="test-notice-v2").status_code, 200)
        self.assertEqual(
            ClientSelfieSearchPermission.objects.filter(
                user=self.alice, withdrawn_at__isnull=True,
            ).count(), 1,
        )

    @override_settings(VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED=False)
    def test_collection_disabled_but_withdrawal_still_works(self):
        self.assertEqual(self.grant().status_code, 503)
        self.assertEqual(self.client.delete(self.url).status_code, 200)

    def test_anonymous_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.delete(self.url).status_code, 302)

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
    )
    def test_selfie_endpoint_denies_before_face_inference_without_permission(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        with patch("apps.visual_search.api.extract_face_embeddings") as inference:
            response = self.client.post(reverse("visual_search:selfie"), {
                "biometric_search_consent": "yes",
            })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "client_permission_required")
        inference.assert_not_called()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=False,
        VISUAL_SEARCH_SELFIE_API_ENABLED=False,
    )
    def test_search_remains_disabled_even_after_permission(self):
        self.grant()
        response = self.client.post(reverse("visual_search:selfie"), {
            "biometric_search_consent": "yes",
        })
        self.assertEqual(response.status_code, 503)

    def test_privacy_page_exposes_withdrawal_even_when_enrollment_disabled(self):
        page = reverse("visual_search:selfie-privacy")
        with override_settings(VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED=False):
            response = self.client.get(page)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Withdraw selfie search permission")
        self.assertNotContains(response, 'id="grant"')

    def test_privacy_page_requires_authentication_and_sets_csrf_cookie(self):
        page = reverse("visual_search:selfie-privacy")
        response = self.client.get(page)
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
        self.client.logout()
        self.assertEqual(self.client.get(page).status_code, 302)

    @override_settings(VISUAL_SEARCH_CLIENT_CONSENT_NOTICE_URL="")
    def test_no_approved_notice_blocks_new_authorization(self):
        self.assertEqual(self.grant().status_code, 503)
        self.assertEqual(self.client.delete(self.url).status_code, 200)

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
    )
    def test_withdrawal_during_search_suppresses_results(self):
        from django.core.cache import cache
        from django.core.files.uploadedfile import SimpleUploadedFile
        cache.clear()
        self.addCleanup(cache.clear)
        self.grant()

        def withdraw_during_match(*args, **kwargs):
            ClientSelfieSearchPermission.objects.filter(
                user=self.alice, withdrawn_at__isnull=True,
            ).update(withdrawn_at=__import__("django.utils.timezone", fromlist=["now"]).now())
            return [{"gallery_id": 999}]

        with patch("apps.visual_search.api.extract_face_embeddings", return_value=[[0.0] * 512]):
            with patch("apps.visual_search.api.find_public_matches", side_effect=withdraw_during_match):
                response = self.client.post(reverse("visual_search:selfie"), {
                    "biometric_search_consent": "yes",
                    "selfie": SimpleUploadedFile(
                        "selfie.jpg", b"synthetic", content_type="image/jpeg",
                    ),
                })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "client_permission_withdrawn")
        self.assertNotIn("results", response.json())
