"""Private gallery login notice and safe return URL contracts."""
from urllib.parse import parse_qs, urlsplit
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.accounts.models import User, PhotographerProfile
from .models import AccessToken, Gallery, GalleryInvitation, GalleryPermission, GalleryAnalyticsEvent


@override_settings(MEDIA_SIGNING_SECRET='private-notice-test-secret')
class PrivateGalleryLoginNoticeTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email='studio@example.test', first_name='Samuel', last_name='Golomeke')
        self.studio = PhotographerProfile.objects.create(user=user, business_name='Golden Light Studio', slug='notice-studio')
        self.gallery = Gallery.objects.create(photographer=self.studio, name='Private event', slug='private-notice', status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE)
        GalleryPermission.objects.create(gallery=self.gallery, view_gallery=True)
        invitation = GalleryInvitation.objects.create(gallery=self.gallery, email='client@example.test')
        self.token_record, self.token = AccessToken.issue(invitation)

    def test_gallery_and_results_routes_show_studio_contact_on_login(self):
        urls = [reverse('galleries:client_gallery_access', args=[self.token]),
                reverse('galleries:invited_semantic_results', args=[self.token]) + '?q=people+dancing',
                reverse('galleries:stable_gallery_access', args=[self.gallery.public_id]),
                reverse('galleries:public_semantic_results', args=[self.gallery.public_id]) + '?q=baby+portraits']
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(parse_qs(urlsplit(response.url).query)['next'], [url])
                login = self.client.get(response.url)
                self.assertContains(login, 'This is a private gallery.')
                for text in ['Golden Light Studio', 'Samuel Golomeke', 'studio@example.test', 'approval']:
                    self.assertContains(login, text)
        self.assertFalse(GalleryAnalyticsEvent.objects.filter(gallery=self.gallery).exists())

    def test_notice_is_not_shown_on_unrelated_login_and_contact_is_escaped(self):
        self.studio.business_name = '<script>unsafe</script>'
        self.studio.save(update_fields=['business_name'])
        response = self.client.get(reverse('galleries:client_gallery_access', args=[self.token]))
        login = self.client.get(response.url)
        self.assertContains(login, '&lt;script&gt;unsafe&lt;/script&gt;')
        self.assertNotContains(login, '<script>unsafe</script>')
        self.assertNotContains(self.client.get(reverse('accounts:login')), 'Private gallery access')

    def test_invalid_or_revoked_token_does_not_disclose_contact(self):
        for token in ['invalid', self.token]:
            self.token_record.revoked_at = __import__('django').utils.timezone.now()
            self.token_record.save(update_fields=['revoked_at'])
            response = self.client.get(reverse('galleries:client_gallery_access', args=[token]))
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('private_gallery_notice', self.client.session)

    def test_public_gallery_does_not_redirect_or_create_private_notice(self):
        self.gallery.visibility = Gallery.Visibility.PUBLIC
        self.gallery.save(update_fields=['visibility'])
        response = self.client.get(reverse('galleries:client_gallery_access', args=[self.token]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('private_gallery_notice', self.client.session)
