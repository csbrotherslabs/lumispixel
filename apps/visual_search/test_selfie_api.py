"""Selfie API contract tests: no biometric processing when disabled."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class SelfieSearchAPITests(TestCase):
    def setUp(self):
        self.url = reverse("visual_search:selfie")
        self.user = get_user_model().objects.create_user(
            email="selfie-api@example.com", password="safe-test-password-123"
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
