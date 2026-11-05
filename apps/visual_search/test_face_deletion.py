"""Face-level erasure must fail closed until safe review is enabled."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from apps.visual_search.models import ClientBiometricDeletionRequest


class FaceDeletionSafetyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="face-erasure-safety@example.test", password="test-password",
        )
        self.client.force_login(self.user)
        self.request = ClientBiometricDeletionRequest.objects.create(user=self.user)

    def test_photographer_confirmation_disabled_by_default(self):
        with patch("apps.visual_search.vector_store.delete_confirmed_face") as erase:
            response = self.client.post(
                reverse("visual_search:face-deletion-confirm", args=[self.request.pk]),
                data='{"gallery_id":1,"photo_id":1,"face_index":0}',
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        erase.assert_not_called()

    @override_settings(VISUAL_SEARCH_FACE_DELETION_REVIEW_ENABLED=True)
    def test_unrelated_account_cannot_erase_by_guessing_ids(self):
        with patch("apps.visual_search.vector_store.delete_confirmed_face") as erase:
            response = self.client.post(
                reverse("visual_search:face-deletion-confirm", args=[self.request.pk]),
                data='{"gallery_id":99999,"photo_id":99999,"face_index":0}',
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 404)
        erase.assert_not_called()

    def test_inbox_does_not_expose_unlinked_client_requests(self):
        response = self.client.get(reverse("visual_search:face-deletion-inbox"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["requests"], [])

    def test_anonymous_cannot_view_or_confirm(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("visual_search:face-deletion-inbox")).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("visual_search:face-deletion-confirm", args=[self.request.pk]),
            ).status_code,
            302,
        )
