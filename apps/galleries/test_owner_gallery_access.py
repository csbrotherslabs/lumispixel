"""Owner client-view access must not broaden access for other accounts."""
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User, PhotographerProfile
from apps.visual_search.models import GallerySemanticSearchPolicy
from .models import AccessToken, Gallery, GalleryInvitation, GalleryPermission, GalleryAnalyticsEvent


@override_settings(MEDIA_SIGNING_SECRET='owner-access-test', VISUAL_SEARCH_SEMANTIC_ENABLED=True,
                   VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=True)
class GalleryOwnerAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='owner@example.test', email_verified=False)
        self.profile = PhotographerProfile.objects.create(user=self.owner, slug='owner-studio')
        self.gallery = Gallery.objects.create(photographer=self.profile, name='Private event', slug='owner-event',
            status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PRIVATE)
        self.permission = GalleryPermission.objects.create(gallery=self.gallery, view_gallery=True)
        self.invitation = GalleryInvitation.objects.create(gallery=self.gallery, email='client@example.test')
        self.record, self.token = AccessToken.issue(self.invitation)
        self.stable = reverse('galleries:stable_gallery_access', args=[self.gallery.public_id])
        self.invited = reverse('galleries:client_gallery_access', args=[self.token])
        self.api = reverse('visual_search:public-semantic-search', args=[self.gallery.public_id])
        GallerySemanticSearchPolicy.objects.create(gallery=self.gallery, processing_authorized=True)
        self.client.force_login(self.owner)

    def test_owner_can_view_without_invitation_or_verified_recipient_email(self):
        for url in [self.stable, self.invited]:
            self.assertContains(self.client.get(url), 'Private event')
        self.assertEqual(GalleryInvitation.objects.filter(gallery=self.gallery).count(), 1)
        self.invitation.refresh_from_db()
        self.record.refresh_from_db()
        self.assertIsNone(self.invitation.last_access_at)
        self.assertIsNone(self.record.last_used_at)
        self.assertFalse(GalleryAnalyticsEvent.objects.filter(gallery=self.gallery).exists())

    def test_owner_can_view_both_results_pages_and_search_api(self):
        urls = [reverse('galleries:public_semantic_results', args=[self.gallery.public_id]),
                reverse('galleries:invited_semantic_results', args=[self.token]), self.api,
                reverse('visual_search:invited-semantic-search', args=[self.token])]
        with patch('apps.visual_search.semantic_api._semantic_results', return_value=[]):
            for url in urls:
                self.assertEqual(self.client.get(url, {'q': 'dancing'}).status_code, 200, url)

    def test_other_photographer_is_not_an_owner(self):
        other = User.objects.create_user(email='other-studio@example.test', email_verified=True)
        PhotographerProfile.objects.create(user=other, slug='other-owner-studio')
        self.client.force_login(other)
        self.assertTemplateUsed(self.client.get(self.stable), 'galleries/stable_gallery_gate.html')
        self.assertEqual(self.client.get(self.invited).status_code, 403)
        with patch('apps.visual_search.semantic_api._semantic_results') as search:
            self.assertEqual(self.client.get(self.api, {'q': 'dancing'}).status_code, 404)
            search.assert_not_called()

    def test_logout_removes_owner_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.stable).status_code, 302)
        self.assertEqual(self.client.get(self.invited).status_code, 302)
        self.assertEqual(self.client.get(self.api, {'q': 'dancing'}).status_code, 404)

    def test_valid_recipient_still_has_private_access(self):
        user = User.objects.create_user(email=self.invitation.email, email_verified=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.invited).status_code, 200)

    def test_owner_does_not_bypass_revoked_or_disabled_invitation(self):
        self.record.revoked_at = timezone.now()
        self.record.save(update_fields=['revoked_at'])
        self.assertEqual(self.client.get(self.invited).status_code, 404)
        self.record.revoked_at = None
        self.record.save(update_fields=['revoked_at'])
        self.invitation.status = GalleryInvitation.Status.DISABLED
        self.invitation.save(update_fields=['status'])
        self.assertEqual(self.client.get(self.invited).status_code, 404)
        self.assertEqual(self.client.get(self.stable).status_code, 200)

    def test_owner_respects_gallery_availability_and_view_permission(self):
        self.permission.view_gallery = False
        self.permission.save(update_fields=['view_gallery'])
        for url in [self.stable, self.invited]:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.permission.view_gallery = True
        self.permission.automatic_gallery_lock = True
        self.permission.save()
        self.gallery.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.gallery.save(update_fields=['expires_at'])
        for url in [self.stable, self.invited]:
            self.assertEqual(self.client.get(url).status_code, 404)
