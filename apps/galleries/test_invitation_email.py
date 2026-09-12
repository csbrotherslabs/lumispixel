import re
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User

from .models import AccessToken, Gallery, GalleryInvitation
from .services import GalleryInvitationDeliveryError


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PUBLIC_BASE_URL="https://lumispixel.com",
)
class GalleryInvitationEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="photographer@example.com",
            password="testpass123!",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.user,
            display_name="Avery Stone",
            business_name="Avery Stone Photography",
            slug="avery-stone",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.photographer,
            name="Coastal Wedding",
            slug="coastal-wedding",
            status=Gallery.Status.PUBLISHED,
        )
        self.client.force_login(self.user)

    def test_prepare_invite_creates_secure_token_and_sends_branded_email(self):
        response = self.client.post(
            reverse("galleries:prepare_client_gallery_invitation", args=[self.gallery.pk]),
            {"client_name": "Samuel Golomeke", "email": "samuel@example.com"},
        )

        self.assertEqual(response.status_code, 302)
        invitation = GalleryInvitation.objects.get(gallery=self.gallery, email="samuel@example.com")
        self.assertEqual(invitation.client_name, "Samuel Golomeke")
        self.assertEqual(AccessToken.objects.filter(invitation=invitation, revoked_at__isnull=True).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["samuel@example.com"])
        self.assertIn("Coastal Wedding", mail.outbox[0].subject)

        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn("Avery Stone Photography", html_body)
        self.assertIn("https://lumispixel.com/galleries/access/", html_body)
        match = re.search(r"https://lumispixel\.com/galleries/access/([^/]+)/", html_body)
        self.assertIsNotNone(match)
        self.assertTrue(AccessToken.objects.filter(token_hash=AccessToken.digest(match.group(1))).exists())

    def test_resend_emails_fresh_token_and_revokes_previous_link(self):
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Samuel Golomeke",
            email="samuel@example.com",
        )
        old_token, _ = AccessToken.issue(invitation)

        response = self.client.post(
            reverse("galleries:resend_client_gallery_invitation", args=[self.gallery.pk, invitation.pk])
        )

        self.assertEqual(response.status_code, 302)
        old_token.refresh_from_db()
        invitation.refresh_from_db()
        self.assertIsNotNone(old_token.revoked_at)
        self.assertEqual(invitation.status, GalleryInvitation.Status.PENDING)
        self.assertIsNotNone(invitation.resent_at)
        self.assertEqual(AccessToken.objects.filter(invitation=invitation, revoked_at__isnull=True).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_failure_keeps_previous_secure_link_valid(self):
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Samuel Golomeke",
            email="samuel@example.com",
        )
        old_token, _ = AccessToken.issue(invitation)

        with patch(
            "apps.galleries.invitation_views.send_gallery_invitation_email",
            side_effect=GalleryInvitationDeliveryError,
        ):
            response = self.client.post(
                reverse("galleries:resend_client_gallery_invitation", args=[self.gallery.pk, invitation.pk])
            )

        self.assertEqual(response.status_code, 302)
        old_token.refresh_from_db()
        self.assertIsNone(old_token.revoked_at)
        self.assertEqual(AccessToken.objects.filter(invitation=invitation, revoked_at__isnull=True).count(), 1)

    def test_unpublished_gallery_does_not_send_invitation(self):
        self.gallery.status = Gallery.Status.DRAFT
        self.gallery.save(update_fields=["status"])

        response = self.client.post(
            reverse("galleries:prepare_client_gallery_invitation", args=[self.gallery.pk]),
            {"client_name": "Samuel Golomeke", "email": "samuel@example.com"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(GalleryInvitation.objects.filter(gallery=self.gallery).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_other_photographer_cannot_send_gallery_invitation(self):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123!",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        PhotographerProfile.objects.create(user=other_user, slug="other", onboarding_completed=True)
        self.client.force_login(other_user)

        response = self.client.post(
            reverse("galleries:prepare_client_gallery_invitation", args=[self.gallery.pk]),
            {"client_name": "Samuel Golomeke", "email": "samuel@example.com"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)
