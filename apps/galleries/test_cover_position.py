"""Persisted gallery framing and shared client cover rendering."""
from types import SimpleNamespace
from django.test import TestCase
from django.template.loader import render_to_string
from apps.accounts.models import User, PhotographerProfile
from .forms import GalleryForm
from .models import Gallery


class GalleryCoverPositionTests(TestCase):
    def setUp(self):
        self.owner = PhotographerProfile.objects.create(
            user=User.objects.create_user(email='cover-owner@example.test'), slug='cover-owner')
        self.data = {'name': 'Cover framing', 'status': 'draft', 'visibility': 'private',
                     'design_template': Gallery.DesignTemplate.KIMONO_MASONRY,
                     'cover_position_x': 0, 'cover_position_y': 23}

    def test_create_edit_and_omitted_positions_retain_saved_framing(self):
        form = GalleryForm(self.data, photographer=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        gallery = form.save()
        gallery.refresh_from_db()
        self.assertEqual((gallery.cover_position_x, gallery.cover_position_y), (0, 23))
        data = dict(self.data, cover_position_x=100, cover_position_y=80)
        form = GalleryForm(data, instance=gallery, photographer=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        data.pop('cover_position_x'); data.pop('cover_position_y')
        form = GalleryForm(data, instance=gallery, photographer=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(); gallery.refresh_from_db()
        self.assertEqual((gallery.cover_position_x, gallery.cover_position_y), (100, 80))
        self.assertEqual(Gallery(photographer=self.owner).cover_position_y, 50)

    def test_out_of_bounds_positions_are_rejected_and_bound_values_preserved(self):
        for value in [-1, 101, 'invalid']:
            form = GalleryForm(dict(self.data, cover_position_y=value), photographer=self.owner)
            self.assertFalse(form.is_valid())
            self.assertIn('cover_position_y', form.errors)
            self.assertEqual(str(form['cover_position_x'].value()), '0')

    def test_all_designs_render_saved_cover_position(self):
        from .test_tiled_watermarks import gallery_context, DESIGNS
        context = gallery_context()
        context['gallery'].cover_image = SimpleNamespace(url='/cover.jpg')
        context['gallery'].cover_position_x = 0
        context['gallery'].cover_position_y = 23
        for design in DESIGNS:
            html = render_to_string(f'galleries/designs/{design}.html', context)
            self.assertIn('background-position:0% 23%', html)
