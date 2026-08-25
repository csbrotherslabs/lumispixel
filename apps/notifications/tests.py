from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
