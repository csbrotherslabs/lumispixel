"""Privacy contract for invitation-only access requests."""
import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile
from apps.billing.models import Plan
from apps.galleries.models import Gallery
from apps.visual_search.access_requests import PrivateGalleryAccessRequest


class PrivateAccessRequestTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"name": "Free", "is_active": True})
        self.owner = get_user_model().objects.create_user(email=f"owner-{uuid4().hex}@example.test", password="test-only")
        self.visitor = get_user_model().objects.create_user(email=f"visitor-{uuid4().hex}@example.test", password="test-only")
        photographer = PhotographerProfile.objects.create(user=self.owner, slug=f"studio-{uuid4().hex}")
        self.gallery = Gallery.objects.create(
            photographer=photographer, name="Private test", slug=f"private-{uuid4().hex}",
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        self.invite_url = reverse("visual_search:private-access-invite", args=[self.gallery.pk])
        self.submit_url = reverse("visual_search:private-access-request")

    def _post(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type="application/json")

    def test_feature_disabled_by_default(self):
        self.client.force_login(self.owner)
        self.assertEqual(self._post(self.invite_url, {}).status_code, 503)

    @override_settings(VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True)
    def test_only_owner_can_issue_and_request_never_grants_access(self):
        self.client.force_login(self.visitor)
        self.assertEqual(self._post(self.invite_url, {}).status_code, 404)
        self.client.force_login(self.owner)
        issued = self._post(self.invite_url, {})
        self.assertEqual(issued.status_code, 201)
        token = issued.json()["token"]
        self.assertNotIn(token, str(self.gallery.pk))
        self.client.force_login(self.visitor)
        response = self._post(self.submit_url, {"invitation_token": token})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(PrivateGalleryAccessRequest.objects.count(), 1)
        self.assertNotIn("gallery", response.json())
        # Repeat requests do not create duplicate pending records.
        self._post(self.submit_url, {"invitation_token": token})
        self.assertEqual(PrivateGalleryAccessRequest.objects.count(), 1)
        item = PrivateGalleryAccessRequest.objects.get()
        self.assertEqual(item.status, "pending")
        self.client.force_login(self.owner)
        reviewed = self._post(
            reverse("visual_search:private-access-review", args=[item.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertFalse(reviewed.json()["access_granted"])

    @override_settings(VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True)
    def test_invalid_invitation_is_indistinguishable(self):
        self.client.force_login(self.visitor)
        valid_format = "X" * 50
        invalid = self._post(self.submit_url, {"invitation_token": valid_format})
        missing = self._post(self.submit_url, {})
        self.assertEqual(invalid.status_code, 202)
        self.assertEqual(invalid.json(), missing.json())
        self.assertEqual(PrivateGalleryAccessRequest.objects.count(), 0)
