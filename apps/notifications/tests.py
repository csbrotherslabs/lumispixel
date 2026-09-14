from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile
from apps.galleries.models import Gallery, GalleryInvitation

from .models import Notification
from .services import notify_user

User = get_user_model()


def make_user(email):
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        account_status=User.AccountStatus.ACTIVE,
        email_verified=True,
        onboarding_completed=True,
    )


class NotificationInboxTests(TestCase):
    def setUp(self):
        self.user = make_user("client-notifications@example.com")
        self.other_user = make_user("other-notifications@example.com")
        self.client.force_login(self.user)
        self.gallery = notify_user(
            recipient=self.user,
            title="Your gallery is ready",
            message="The final gallery is available.",
            category=Notification.Category.GALLERY,
            action_url="/client/dashboard/",
            action_label="View gallery",
        )
        self.read_notice = notify_user(
            recipient=self.user,
            title="Download complete",
            message="Your download is ready.",
            category=Notification.Category.DOWNLOAD,
        )
        self.read_notice.mark_read()
        notify_user(recipient=self.other_user, title="Private", message="Not visible")

    def test_inbox_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("notifications:index"))
        self.assertEqual(response.status_code, 302)

    def test_inbox_is_user_isolated(self):
        response = self.client.get(reverse("notifications:index"))
        self.assertContains(response, "Your gallery is ready")
        self.assertContains(response, "Download complete")
        self.assertNotContains(response, "Private")

    def test_filters_by_status_and_category(self):
        unread = self.client.get(reverse("notifications:index"), {"status": "unread"})
        self.assertContains(unread, "Your gallery is ready")
        self.assertNotContains(unread, "Download complete")
        downloads = self.client.get(reverse("notifications:index"), {"category": "download"})
        self.assertContains(downloads, "Download complete")
        self.assertNotContains(downloads, "Your gallery is ready")

    def test_mark_read_and_unread(self):
        self.client.post(reverse("notifications:mark-read", args=[self.gallery.pk]))
        self.gallery.refresh_from_db()
        self.assertTrue(self.gallery.is_read)
        self.assertIsNotNone(self.gallery.read_at)
        self.client.post(reverse("notifications:mark-read", args=[self.gallery.pk]), {"state": "unread"})
        self.gallery.refresh_from_db()
        self.assertFalse(self.gallery.is_read)
        self.assertIsNone(self.gallery.read_at)

    def test_mark_all_read(self):
        self.client.post(reverse("notifications:mark-all-read"))
        self.assertFalse(Notification.objects.filter(recipient=self.user, is_read=False).exists())

    def test_cannot_mutate_another_users_notification(self):
        other_notice = Notification.objects.get(recipient=self.other_user)
        response = self.client.post(reverse("notifications:mark-read", args=[other_notice.pk]))
        self.assertEqual(response.status_code, 404)

    def test_dismiss_removes_notification(self):
        response = self.client.post(reverse("notifications:dismiss", args=[self.gallery.pk]))
        self.assertRedirects(response, reverse("notifications:index"), fetch_redirect_response=False)
        self.assertFalse(Notification.objects.filter(pk=self.gallery.pk).exists())

    def test_only_relative_action_urls_are_rendered(self):
        unsafe = notify_user(recipient=self.user, title="Unsafe", message="No external action", action_url="https://example.com")
        response = self.client.get(reverse("notifications:index"))
        self.assertNotContains(response, 'href="https://example.com"')
        self.assertEqual(unsafe.safe_action_url, "")


class GalleryInvitationNotificationSignalTests(TestCase):
    def setUp(self):
        self.photographer_user = User.objects.create_user(
            email="notification-photographer@example.com",
            password="TestPass123!",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.photographer = PhotographerProfile.objects.create(
            user=self.photographer_user,
            display_name="Avery Stone",
            slug="notification-photographer",
            onboarding_completed=True,
        )
        self.gallery = Gallery.objects.create(
            photographer=self.photographer,
            name="Coastal Wedding",
            slug="coastal-wedding-notification",
            status=Gallery.Status.PUBLISHED,
        )
        self.client_user = User.objects.create_user(
            email="existing-client@example.com",
            password="TestPass123!",
            primary_role=User.PrimaryRole.CLIENT,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        ClientProfile.objects.create(user=self.client_user, display_name="Existing Client")

    def test_creating_invitation_for_existing_client_uses_gallery_name(self):
        invitation = GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Existing Client",
            email="existing-client@example.com",
        )

        notification = Notification.objects.get(
            recipient=self.client_user,
            category=Notification.Category.GALLERY,
        )
        self.assertEqual(notification.title, "Coastal Wedding was shared with you")
        self.assertEqual(notification.message, "Avery Stone invited you to view a gallery.")
        self.assertEqual(notification.action_url, reverse("clients:dashboard"))
        self.assertEqual(notification.metadata["gallery_id"], self.gallery.pk)
        self.assertEqual(notification.metadata["invitation_id"], invitation.pk)

    def test_photographer_primary_user_with_client_profile_is_notified(self):
        dual_role_user = User.objects.create_user(
            email="dual-role-client@example.com",
            password="TestPass123!",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        ClientProfile.objects.create(user=dual_role_user, display_name="Dual Role Client")

        GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Dual Role Client",
            email="dual-role-client@example.com",
        )

        self.assertTrue(
            Notification.objects.filter(
                recipient=dual_role_user,
                category=Notification.Category.GALLERY,
                title="Coastal Wedding was shared with you",
            ).exists()
        )

    def test_matching_user_without_client_profile_is_not_notified(self):
        photographer_only_user = User.objects.create_user(
            email="photographer-only@example.com",
            password="TestPass123!",
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )

        GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Photographer Only",
            email="photographer-only@example.com",
        )

        self.assertFalse(
            Notification.objects.filter(
                recipient=photographer_only_user,
                category=Notification.Category.GALLERY,
            ).exists()
        )

    def test_invitation_for_unknown_email_does_not_create_notification(self):
        before = Notification.objects.count()
        GalleryInvitation.objects.create(
            gallery=self.gallery,
            client_name="Unknown Client",
            email="unknown-client@example.com",
        )
        self.assertEqual(Notification.objects.count(), before)
