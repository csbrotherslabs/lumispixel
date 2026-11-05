"""Selfie API contract tests: no biometric processing when disabled."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.visual_search.models import ClientSelfieSearchPermission


@override_settings(VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION="selfie-api-test-v1")
class SelfieSearchAPITests(TestCase):
    def setUp(self):
        self.url = reverse("visual_search:selfie")
        self.user = get_user_model().objects.create_user(
            email="selfie-api@example.com", password="safe-test-password-123"
        )
        ClientSelfieSearchPermission.objects.create(
            user=self.user, purpose="public_gallery_selfie_search",
            policy_version="selfie-api-test-v1", granted_at=timezone.now(),
        )

    def test_anonymous_request_is_not_allowed(self):
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_disabled_feature_does_not_infer(self):
        self.client.force_login(self.user)
        with patch("apps.visual_search.api.extract_face_embeddings") as inference:
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)
        inference.assert_not_called()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
    )
    def test_explicit_consent_required_before_inference(self):
        self.client.force_login(self.user)
        with patch("apps.visual_search.api.extract_face_embeddings") as inference:
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "consent_required")
        inference.assert_not_called()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
    )
    def test_invalid_upload_rejected_before_inference(self):
        self.client.force_login(self.user)
        with patch("apps.visual_search.api.extract_face_embeddings") as inference:
            response = self.client.post(
                self.url, {"biometric_search_consent": "yes"}
            )
        self.assertEqual(response.status_code, 400)
        inference.assert_not_called()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT=1,
    )
    def test_rate_limit_blocks_second_request_before_inference(self):
        from django.core.cache import cache
        cache.clear()
        self.client.force_login(self.user)
        with patch("apps.visual_search.api.extract_face_embeddings") as inference:
            first = self.client.post(self.url)
            second = self.client.post(self.url)
        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 429)
        inference.assert_not_called()
        cache.clear()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=False,
    )
    def test_missing_shared_cache_fails_closed(self):
        self.client.force_login(self.user)
        with patch("apps.visual_search.api.extract_face_embeddings") as inference:
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)
        inference.assert_not_called()

    @override_settings(VISUAL_SEARCH_SELFIE_MAX_DISTANCE=None)
    def test_missing_calibration_fails_closed(self):
        from apps.visual_search.search import calibrated_max_distance
        with self.assertRaises(RuntimeError):
            calibrated_max_distance()

    @override_settings(VISUAL_SEARCH_SELFIE_MAX_DISTANCE=0.4)
    def test_explicit_calibration_value(self):
        from apps.visual_search.search import calibrated_max_distance
        self.assertEqual(calibrated_max_distance(), 0.4)

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
    )
    def test_http_upload_inference_search_response_contract(self):
        from django.core.cache import cache
        from django.core.files.uploadedfile import SimpleUploadedFile
        cache.clear()
        self.client.force_login(self.user)
        selfie = SimpleUploadedFile(
            "selfie.jpg", b"test-image-bytes", content_type="image/jpeg"
        )
        with patch("apps.visual_search.api.extract_face_embeddings", return_value=[[0.0] * 512]) as infer:
            with patch("apps.visual_search.api.find_public_matches", return_value=[{"gallery_id": 17}]) as search:
                response = self.client.post(self.url, {
                    "biometric_search_consent": "yes",
                    "selfie": selfie,
                })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": [{"gallery_id": 17}]})
        infer.assert_called_once()
        search.assert_called_once()
        cache.clear()

    @override_settings(
        VISUAL_SEARCH_FACE_INDEXING_ENABLED=True,
        VISUAL_SEARCH_SELFIE_API_ENABLED=True,
        VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=True,
    )
    def test_multiple_faces_do_not_reach_vector_search(self):
        from django.core.cache import cache
        from django.core.files.uploadedfile import SimpleUploadedFile
        cache.clear()
        self.client.force_login(self.user)
        selfie = SimpleUploadedFile(
            "selfie.jpg", b"test-image-bytes", content_type="image/jpeg"
        )
        with patch("apps.visual_search.api.extract_face_embeddings", return_value=[[0] * 512, [0] * 512]):
            with patch("apps.visual_search.api.find_public_matches") as search:
                response = self.client.post(self.url, {
                    "biometric_search_consent": "yes", "selfie": selfie,
                })
        self.assertEqual(response.status_code, 400)
        search.assert_not_called()
        cache.clear()
