from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ClientProfile, PhotographerProfile, User

from .models import AccessToken, Gallery, GalleryInvitation, GalleryPermission


class VerifiedClientGalleryAccountTests(TestCase):
    def setUp(self):
        self.photographer_user = User.objects.create_user(
            email="photographer@example.com",
            password="testpass123!",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.photographer_user,
            display_name="Avery Stone",
            business_name="Avery Stone Photography",
            slug="avery-stone-account-gallery",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.photographer,
            name="Coastal Wedding",
            slug="coastal-wedding-account-gallery",
            status=Gallery.Status.PUBLISHED,
            image_count=42,
        )
        GalleryPermission.objects.create(gallery=self.gallery, view_gallery=True)
        self.invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Samuel Golomeke",
            email="Samuel@Example.com",
        )
        self.client_user = User.objects.create_user(
            email="samuel@example.com",
            password="testpass123!",
            primary_role=User.PrimaryRole.CLIENT,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        ClientProfile.objects.create(
            user=self.client_user,
            display_name="Samuel Golomeke",
            onboarding_completed=True,
            onboarding_step=3,
        )

    def test_verified_matching_email_sees_invited_gallery_on_dashboard(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("clients:dashboard"))

        self.assertEqual(response.status_code, 200)
        invitations = list(response.context["invited_galleries"])
        self.assertEqual([item.pk for item in invitations], [self.invitation.pk])
        self.assertEqual(response.context["invited_gallery_count"], 1)
        self.assertContains(response, reverse("galleries:client_account_gallery_access", args=[self.invitation.pk]))

    def test_unverified_account_does_not_inherit_gallery_access(self):
        self.client_user.email_verified = False
        self.client_user.save(update_fields=["email_verified"])
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("clients:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invited_gallery_count"], 0)

        access = self.client.get(reverse("galleries:client_account_gallery_access", args=[self.invitation.pk]))
        self.assertEqual(access.status_code, 403)

    def test_different_verified_email_cannot_open_invitation(self):
        other = User.objects.create_user(
            email="other@example.com",
            password="testpass123!",
            primary_role=User.PrimaryRole.CLIENT,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        ClientProfile.objects.create(user=other, onboarding_completed=True, onboarding_step=3)
        self.client.force_login(other)

        response = self.client.get(reverse("galleries:client_account_gallery_access", args=[self.invitation.pk]))
        self.assertEqual(response.status_code, 404)

    def test_account_open_issues_fresh_token_without_revoking_existing_email_link(self):
        existing_token, _ = AccessToken.issue(self.invitation)
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("galleries:client_account_gallery_access", args=[self.invitation.pk]))

        self.assertEqual(response.status_code, 302)
        existing_token.refresh_from_db()
        self.assertIsNone(existing_token.revoked_at)
        self.assertEqual(AccessToken.objects.filter(invitation=self.invitation, revoked_at__isnull=True).count(), 2)
        self.assertIn("/galleries/access/", response["Location"])

    def test_disabled_expired_and_unpublished_invitations_are_not_available(self):
        self.client.force_login(self.client_user)

        self.invitation.status = GalleryInvitation.Status.DISABLED
        self.invitation.save(update_fields=["status"])
        response = self.client.get(reverse("clients:dashboard"))
        self.assertEqual(response.context["invited_gallery_count"], 0)

        self.invitation.status = GalleryInvitation.Status.PENDING
        self.invitation.save(update_fields=["status"])
        self.gallery.status = Gallery.Status.DRAFT
        self.gallery.save(update_fields=["status"])
        response = self.client.get(reverse("clients:dashboard"))
        self.assertEqual(response.context["invited_gallery_count"], 0)

        self.gallery.status = Gallery.Status.PUBLISHED
        self.gallery.expires_at = timezone.now() - timedelta(minutes=1)
        self.gallery.save(update_fields=["status", "expires_at"])
        response = self.client.get(reverse("clients:dashboard"))
        self.assertEqual(response.context["invited_gallery_count"], 0)

    def test_view_permission_prevents_account_open(self):
        permissions = GalleryPermission.objects.get(gallery=self.gallery)
        permissions.view_gallery = False
        permissions.save(update_fields=["view_gallery"])
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("galleries:client_account_gallery_access", args=[self.invitation.pk]))
        self.assertEqual(response.status_code, 404)
