import base64

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User

from .models import AccessToken, Gallery, GalleryActivity, GalleryInvitation
from .templatetags.gallery_qr import _qr_code, qr_png_data_uri, qr_svg_data_uri


class GalleryQrGenerationTests(TestCase):
    def test_qr_encoder_uses_exact_secure_gallery_url(self):
        secure_url = "https://lumispixel.com/galleries/access/secure-token-123/"

        qr = _qr_code(secure_url)

        self.assertEqual(len(qr.data_list), 1)
        self.assertEqual(qr.data_list[0].data, secure_url.encode())

    def test_qr_helpers_return_downloadable_png_and_svg_data_uris(self):
        secure_url = "https://lumispixel.com/galleries/access/secure-token-123/"

        png_uri = qr_png_data_uri(secure_url)
        svg_uri = qr_svg_data_uri(secure_url)

        self.assertTrue(png_uri.startswith("data:image/png;base64,"))
        png_bytes = base64.b64decode(png_uri.split(",", 1)[1])
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")

        self.assertTrue(svg_uri.startswith("data:image/svg+xml;base64,"))
        svg_bytes = base64.b64decode(svg_uri.split(",", 1)[1])
        self.assertIn(b"<svg", svg_bytes)

    def test_empty_value_does_not_generate_qr_asset(self):
        self.assertEqual(qr_png_data_uri(""), "")
        self.assertEqual(qr_svg_data_uri(""), "")


class GalleryQrSharePageTests(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user(
            email="qr-owner@example.com",
            password="testpass",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.owner = PhotographerProfile.objects.create(
            user=self.owner_user,
            slug="qr-owner",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.owner,
            name="QR Delivery",
            slug="qr-delivery",
            status=Gallery.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Jordan Reed",
            email="jordan@example.com",
        )
        self.old_token, _ = AccessToken.issue(self.invitation)
        self.client.force_login(self.owner_user)

    def test_share_link_page_renders_qr_for_new_secure_invitation_url(self):
        response = self.client.post(
            reverse(
                "galleries:issue_client_gallery_share_link",
                args=[self.gallery.pk, self.invitation.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        share_url = response.context["share_url"]
        self.assertIn("/galleries/access/", share_url)
        self.assertContains(response, 'id="client-gallery-qr"')
        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, "data:image/svg+xml;base64,")
        self.assertContains(response, "Download PNG")
        self.assertContains(response, "Download SVG")
        self.assertContains(response, "Print QR")
        self.assertContains(response, "data-share-gallery-link")
        self.assertContains(response, share_url)

        self.old_token.refresh_from_db()
        self.assertIsNotNone(self.old_token.revoked_at)
        self.assertTrue(
            GalleryActivity.objects.filter(
                gallery=self.gallery,
                event_type=GalleryActivity.EventType.GALLERY_SHARED,
            ).exists()
        )

    def test_unpublished_gallery_still_cannot_issue_qr_share_link(self):
        self.gallery.status = Gallery.Status.READY
        self.gallery.save(update_fields=["status"])

        response = self.client.post(
            reverse(
                "galleries:issue_client_gallery_share_link",
                args=[self.gallery.pk, self.invitation.pk],
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Gallery QR Code", status_code=403)
