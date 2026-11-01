"""Saved watermark density, permission UI and workspace isolation."""
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.accounts.models import User, PhotographerProfile
from apps.dashboard.models import StudioMembership
from .models import Gallery, GalleryPermission


@override_settings(MEDIA_SIGNING_SECRET='density-test-secret')
class WatermarkDensityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='density-owner@example.test', primary_role=User.PrimaryRole.PHOTOGRAPHER, last_active_workspace=User.Workspace.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE)
        self.studio = PhotographerProfile.objects.create(user=self.user, slug='density-owner', onboarding_completed=True, business_name='Golden Studio')
        StudioMembership.objects.create(studio=self.studio, user=self.user, role=StudioMembership.Role.OWNER, status=StudioMembership.Status.ACTIVE)
        self.gallery = Gallery.objects.create(photographer=self.studio, name='Density gallery', slug='density-gallery')
        self.permission = GalleryPermission.objects.create(gallery=self.gallery)
        self.client.force_login(self.user)
        self.url = reverse('photographer_workspace:gallery_workspace', args=[self.gallery.pk]) + '?tab=client-access'

    def payload(self, value):
        return {'action': 'save_access', 'visibility': 'private', 'view_gallery': 'on', 'watermark': 'preview', 'watermark_density': value}

    def test_ui_and_save_round_trip(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        for text in ['Access &amp; sharing', 'Downloads &amp; prints', 'Client feedback', 'Watermark density', 'data-permissions-reset', 'Golden Studio']:
            self.assertContains(page, text)
        for value in [1, 3, 5]:
            self.assertEqual(self.client.post(self.url, self.payload(value)).status_code, 302)
            self.permission.refresh_from_db()
            self.assertEqual(self.permission.watermark_density, value)
        self.assertEqual(self.client.get(self.url).context['gallery_permissions'].watermark_density, 5)

    def test_invalid_density_changes_nothing(self):
        for value in ['bad', 0, 6, '1.5']:
            data = self.payload(value); data['visibility'] = 'public'
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
            self.permission.refresh_from_db(); self.gallery.refresh_from_db()
            self.assertEqual(self.permission.watermark_density, 3)
            self.assertEqual(self.gallery.visibility, 'private')

    def test_other_studio_cannot_change_density(self):
        other = User.objects.create_user(email='density-other@example.test', primary_role=User.PrimaryRole.PHOTOGRAPHER, email_verified=True, account_status=User.AccountStatus.ACTIVE, last_active_workspace=User.Workspace.PHOTOGRAPHER)
        studio = PhotographerProfile.objects.create(user=other, slug='density-other', onboarding_completed=True)
        StudioMembership.objects.create(studio=studio, user=other, role=StudioMembership.Role.OWNER, status=StudioMembership.Status.ACTIVE)
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, self.payload(5)).status_code, 404)
        self.permission.refresh_from_db(); self.assertEqual(self.permission.watermark_density, 3)

    def test_all_client_surfaces_receive_saved_density(self):
        from .test_tiled_watermarks import gallery_context, DESIGNS
        from django.template.loader import render_to_string
        context = gallery_context()
        context['permissions'].watermark_density = 5
        context.update(semantic_search_available=True, search_query='portraits', back_url='/gallery/')
        for template in [*[f'galleries/designs/{design}.html' for design in DESIGNS], 'galleries/semantic_results.html', 'galleries/components/semantic_search.html', 'galleries/components/photo_viewer.html']:
            self.assertIn('data-watermark-density="5"', render_to_string(template, context))
