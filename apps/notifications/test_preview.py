from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User
from .models import Notification


class NotificationPreviewTests(TestCase):
    def test_preview_requires_login(self):
        self.assertEqual(self.client.get(reverse('notifications:preview')).status_code, 302)

    def test_preview_is_limited_ordered_and_recipient_isolated(self):
        user = User.objects.create_user(email='preview@example.com', password='password')
        other = User.objects.create_user(email='other-preview@example.com', password='password')
        Notification.objects.create(recipient=other, title='Other user private notice', message='Private')
        records = [Notification.objects.create(recipient=user, title=f'Notice {i}', message='<script>bad()</script>') for i in range(32)]
        self.client.force_login(user)
        response = self.client.get(reverse('notifications:preview'))
        self.assertEqual(list(response.context['notifications']), list(reversed(records[-30:])))
        self.assertNotContains(response, 'Other user private notice')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertFalse(Notification.objects.filter(recipient=user, is_read=True).exists())

    def test_empty_preview_and_unsafe_action(self):
        user = User.objects.create_user(email='empty-preview@example.com', password='password')
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('notifications:preview')), 'No notifications yet')
        Notification.objects.create(recipient=user, title='Unsafe', message='Message', action_url='https://evil.example/')
        self.assertNotContains(self.client.get(reverse('notifications:preview')), 'https://evil.example/')
