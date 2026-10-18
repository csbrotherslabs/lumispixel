"""Invitation -> request -> owner inbox -> decision -> access-token lifecycle.

All identities and invitations are synthetic. No face matching or biometric data.
"""
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile
from apps.billing.models import Plan
from apps.galleries.models import AccessToken, Gallery, GalleryInvitation
from apps.visual_search.access_requests import (
    PrivateGalleryAccessRequest,
    PrivateGalleryInvitation,
)


@override_settings(
    VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True,
    VISUAL_SEARCH_PRIVATE_ACCESS_SHARED_CACHE=True,
)
class PrivateGalleryLifecycleE2ETests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(
            code="free", defaults={"name": "Free", "is_active": True},
        )
        User = get_user_model()
        self.owner = User.objects.create_user(
            email=f"owner-{uuid4().hex}@example.test", password="test-only",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
        )
        self.other = User.objects.create_user(
            email=f"other-{uuid4().hex}@example.test", password="test-only",
            primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True,
        )
        self.requester = User.objects.create_user(
            email=f"requester-{uuid4().hex}@example.test", password="test-only",
            primary_role=User.PrimaryRole.CLIENT, email_verified=True,
        )
        self.owner_profile = PhotographerProfile.objects.create(
            user=self.owner, slug=f"studio-{uuid4().hex}",
            onboarding_completed=True,
        )
        PhotographerProfile.objects.create(
            user=self.other, slug=f"studio-{uuid4().hex}",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.owner_profile, name="Invitation-only gallery",
            slug=f"gallery-{uuid4().hex}", status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE, published_at=timezone.now(),
        )
        self.inbox_url = reverse("photographer_workspace:private_gallery_requests")
        self.issue_url = reverse(
            "visual_search:private-access-invite", args=[self.gallery.pk],
        )
        self.submit_url = reverse("visual_search:private-access-request")
        cache.clear()

    def tearDown(self):
        cache.clear()

    def post(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json",
        )

    def request_access(self):
        self.client.force_login(self.owner)
        issued = self.post(self.issue_url, {})
        self.assertEqual(issued.status_code, 201)
        invitation_id = issued.json()["invitation_id"]
        token = issued.json()["token"]
        self.client.force_login(self.requester)
        submitted = self.post(self.submit_url, {"invitation_token": token})
        self.assertEqual(submitted.status_code, 202)
        self.assertNotIn("gallery", submitted.json())
        item = PrivateGalleryAccessRequest.objects.get(
            invitation_id=invitation_id, requester=self.requester,
        )
        self.assertEqual(item.status, PrivateGalleryAccessRequest.Status.PENDING)
        self.assertEqual(AccessToken.objects.count(), 0)
        return invitation_id, item

    def test_approval_delivers_access_only_after_owner_review(self):
        _, item = self.request_access()
        self.client.force_login(self.other)
        self.assertNotContains(
            self.client.get(self.inbox_url), self.requester.email,
        )
        review_url = reverse("visual_search:private-access-review", args=[item.pk])
        self.assertEqual(
            self.post(review_url, {"decision": "approved"}).status_code, 404,
        )
        self.assertEqual(AccessToken.objects.count(), 0)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.inbox_url), self.requester.email)
        with patch(
            "apps.visual_search.private_access_api.send_gallery_invitation_email"
        ) as send_email:
            response = self.post(review_url, {"decision": "approved"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["access_granted"])
        send_email.assert_called_once()
        item.refresh_from_db()
        self.assertEqual(item.status, PrivateGalleryAccessRequest.Status.APPROVED)
        self.assertIsNotNone(item.reviewed_at)
        delivery = GalleryInvitation.objects.get(
            gallery=self.gallery, email=self.requester.email,
        )
        token = AccessToken.objects.get(invitation=delivery)
        self.assertIsNone(token.revoked_at)
        self.assertEqual(self.post(review_url, {"decision": "approved"}).status_code, 409)
        self.assertEqual(AccessToken.objects.count(), 1)
        self.assertContains(
            self.client.get(self.inbox_url + "?status=approved"),
            self.requester.email,
        )

    def test_denial_does_not_issue_access(self):
        _, item = self.request_access()
        self.client.force_login(self.owner)
        review_url = reverse("visual_search:private-access-review", args=[item.pk])
        with patch(
            "apps.visual_search.private_access_api.send_gallery_invitation_email"
        ) as send_email:
            response = self.post(review_url, {"decision": "denied"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["access_granted"])
        send_email.assert_not_called()
        item.refresh_from_db()
        self.assertEqual(item.status, PrivateGalleryAccessRequest.Status.DENIED)
        self.assertEqual(AccessToken.objects.count(), 0)
        self.assertContains(
            self.client.get(self.inbox_url + "?status=denied"),
            self.requester.email,
        )

    def test_revoked_invitation_cannot_be_approved(self):
        invitation_id, item = self.request_access()
        self.client.force_login(self.owner)
        revoke_url = reverse(
            "visual_search:private-access-revoke", args=[invitation_id],
        )
        self.assertEqual(self.post(revoke_url, {}).status_code, 200)
        with patch(
            "apps.visual_search.private_access_api.send_gallery_invitation_email"
        ) as send_email:
            response = self.post(
                reverse("visual_search:private-access-review", args=[item.pk]),
                {"decision": "approved"},
            )
        self.assertEqual(response.status_code, 400)
        send_email.assert_not_called()
        self.assertEqual(AccessToken.objects.count(), 0)

    def test_expired_invitation_cannot_be_approved(self):
        invitation_id, item = self.request_access()
        PrivateGalleryInvitation.objects.filter(pk=invitation_id).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.client.force_login(self.owner)
        response = self.post(
            reverse("visual_search:private-access-review", args=[item.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AccessToken.objects.count(), 0)
