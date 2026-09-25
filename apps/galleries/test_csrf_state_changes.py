"""CSRF regression matrix for state-changing HTML and AJAX endpoints."""
import json

from django.test import Client as TestClient, TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.dashboard.models import StudioMembership
from apps.galleries.models import AccessToken, Gallery, GalleryInvitation, GalleryPermission, GalleryPhoto


class CsrfStateChangingEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="csrf-owner@example.com", password="test-pass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.studio = PhotographerProfile.objects.create(
            user=self.user, slug="csrf-owner", onboarding_completed=True,
        )
        StudioMembership.objects.create(
            studio=self.studio, user=self.user, role=StudioMembership.Role.OWNER,
            status=StudioMembership.Status.ACTIVE,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.studio, name="CSRF Gallery", slug="csrf-gallery",
            status=Gallery.Status.PUBLISHED,
        )
        GalleryPermission.objects.create(
            gallery=self.gallery, view_gallery=True, favorite_photos=True,
            comment=True, download_images=True, download_originals=True,
        )
        self.photo = GalleryPhoto.objects.create(
            gallery=self.gallery, photographer=self.studio,
            file="galleries/csrf/photo.jpg", original_name="photo.jpg",
            file_size=10, status=GalleryPhoto.Status.COMPLETED,
        )
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery, client_name="CSRF Client", email="client@example.com",
        )
        _, self.token = AccessToken.issue(self.invitation)
        self.csrf_client = TestClient(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.user)

    def assert_csrf_rejected(self, method, url, *, data=None, content_type=None):
        caller = getattr(self.csrf_client, method.lower())
        kwargs = {}
        if content_type:
            kwargs["content_type"] = content_type
        response = caller(url, data=data or {}, **kwargs)
        self.assertEqual(response.status_code, 403, f"{method} {url} was not CSRF protected")

    def test_workspace_form_mutations_reject_missing_csrf(self):
        cases = [
            ("post", reverse("photographer_workspace:gallery_actions"), {"action": "archive"}),
            ("post", reverse("photographer_workspace:gallery_photo_action", args=[self.photo.pk]), {"action": "cover"}),
            ("post", reverse("photographer_workspace:gallery_upload_queue_clear_completed"), {}),
            ("post", reverse("galleries:prepare_client_gallery_invitation", args=[self.gallery.pk]), {}),
            ("post", reverse("galleries:resend_client_gallery_invitation", args=[self.gallery.pk, self.invitation.pk]), {}),
        ]
        for method, url, data in cases:
            with self.subTest(url=url):
                self.assert_csrf_rejected(method, url, data=data)

    def test_json_ajax_mutations_reject_missing_csrf(self):
        cases = [
            (reverse("photographer_workspace:gallery_multipart_initiate"), {
                "gallery": self.gallery.pk, "name": "x.jpg", "content_type": "image/jpeg", "size": 10,
            }),
            (reverse("photographer_workspace:gallery_photo_bulk_action", args=[self.gallery.pk]), {
                "photo_ids": [self.photo.pk], "action": "hide",
            }),
        ]
        for url, payload in cases:
            with self.subTest(url=url):
                self.assert_csrf_rejected(
                    "post", url, data=json.dumps(payload), content_type="application/json"
                )

    def test_client_ajax_favorite_and_comment_reject_missing_csrf(self):
        cases = [
            (reverse("galleries:client_gallery_favorite", args=[self.token, self.photo.pk]), {}),
            (reverse("galleries:client_gallery_comment", args=[self.token, self.photo.pk]), {"comment": "forged"}),
        ]
        anonymous = TestClient(enforce_csrf_checks=True)
        for url, data in cases:
            with self.subTest(url=url):
                response = anonymous.post(
                    url, data=data, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
                )
                self.assertEqual(response.status_code, 403)

    def test_ajax_formdata_with_valid_csrf_is_accepted(self):
        anonymous = TestClient(enforce_csrf_checks=True)
        page = anonymous.get(reverse("galleries:client_gallery_access", args=[self.token]))
        self.assertEqual(page.status_code, 200)
        csrf = anonymous.cookies["csrftoken"].value
        response = anonymous.post(
            reverse("galleries:client_gallery_favorite", args=[self.token, self.photo.pk]),
            data={"csrfmiddlewaretoken": csrf},
            HTTP_X_CSRFTOKEN=csrf,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertNotEqual(response.status_code, 403)

    def test_state_changing_routes_do_not_accept_get(self):
        urls = [
            reverse("photographer_workspace:gallery_actions"),
            reverse("photographer_workspace:gallery_photo_action", args=[self.photo.pk]),
            reverse("photographer_workspace:gallery_photo_bulk_action", args=[self.gallery.pk]),
            reverse("photographer_workspace:gallery_multipart_initiate"),
            reverse("galleries:client_gallery_favorite", args=[self.token, self.photo.pk]),
            reverse("galleries:client_gallery_comment", args=[self.token, self.photo.pk]),
            reverse("galleries:prepare_client_gallery_invitation", args=[self.gallery.pk]),
            reverse("galleries:resend_client_gallery_invitation", args=[self.gallery.pk, self.invitation.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.csrf_client.get(url)
                self.assertEqual(response.status_code, 405)
