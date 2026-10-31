"""Tiled display-watermark contracts for all four gallery designs."""
import os
import re
from pathlib import Path
from types import SimpleNamespace
from unittest import skipUnless
from uuid import uuid4
from urllib.parse import urlparse

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from playwright.sync_api import sync_playwright, expect

DESIGNS = ['standard_filterable', 'story', 'masonry', 'cinematic']


def gallery_context(watermark='preview'):
    return {
        'gallery': SimpleNamespace(pk=1, name='Watermark test', public_id=uuid4(), photographer='Studio', description='', cover_image=None, event_date=None, story_title='Our story'),
        'gallery_brand': 'Magdalene Golomeke',
        'gallery_settings': SimpleNamespace(accent_color='#c51b48', watermark_position='bottom_right'),
        'permissions': SimpleNamespace(watermark=watermark),
        'photos': [SimpleNamespace(pk=1, delivery_url='/photo.svg', is_client_favorite=False, client_filter_categories='')],
        'albums': [],
    }


class TiledWatermarkTemplateTests(SimpleTestCase):
    def test_all_designs_share_grid_and_lightbox_watermarks(self):
        for design in DESIGNS:
            with self.subTest(design=design):
                html = render_to_string(f'galleries/designs/{design}.html', gallery_context())
                self.assertIn('client_gallery_watermark.js', html)
                self.assertIn('client_gallery_watermark.css', html)
                self.assertEqual(html.count('data-gallery-watermark '), 2)
                self.assertNotIn('class="lp-client-photo__watermark"', html)

    def test_watermark_none_removes_all_overlays(self):
        for design in DESIGNS:
            with self.subTest(design=design):
                html = render_to_string(f'galleries/designs/{design}.html', gallery_context('none'))
                self.assertNotIn('data-gallery-watermark ', html)

    def test_brand_is_escaped_and_not_repeated_for_screen_readers(self):
        context = gallery_context()
        context['gallery_brand'] = '\"><script>alert(1)</script> & Studio'
        html = render_to_string('galleries/components/tiled_watermark.html', context)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('aria-hidden="true"', html)


with sync_playwright() as _playwright:
    HAS_CHROMIUM = Path(_playwright.chromium.executable_path).exists()


@skipUnless(HAS_CHROMIUM or os.getenv('REQUIRE_CLIENT_SEARCH_BROWSER') == '1', 'Requires Playwright Chromium')
class TiledWatermarkBrowserTests(SimpleTestCase):
    def setUp(self):
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.browser = self.playwright.chromium.launch()
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.html = ''
        self.page.route('https://gallery.example.test/**', self.serve)

    def serve(self, route):
        path = urlparse(route.request.url).path
        if path.startswith('/static/'):
            file = settings.BASE_DIR / 'static' / path.removeprefix('/static/')
            if file.is_file():
                mime = 'text/css' if file.suffix == '.css' else 'application/javascript'
                route.fulfill(body=file.read_bytes(), content_type=mime)
            else:
                route.abort()
        elif path == '/photo.svg':
            route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1000"><rect width="800" height="1000" fill="#526477"/></svg>')
        else:
            route.fulfill(body=self.html, content_type='text/html; charset=utf-8')

    def test_tiles_cover_each_photo_without_blocking_preview(self):
        for design in DESIGNS:
            for width in [1440, 390]:
                with self.subTest(design=design, width=width):
                    self.html = render_to_string(f'galleries/designs/{design}.html', gallery_context())
                    self.page.set_viewport_size({'width': width, 'height': 900})
                    self.page.goto('https://gallery.example.test/')
                    media = self.page.locator('[data-client-photo] a').first
                    overlay = media.locator('[data-gallery-watermark]')
                    expect(overlay).to_have_css('pointer-events', 'none')
                    expect(overlay).to_have_css('background-repeat', 'repeat')
                    self.assertIn('data:image/svg+xml', overlay.evaluate('el => el.style.backgroundImage'))
                    # The repeated background must fill its media parent, not the page.
                    bounds = overlay.bounding_box()
                    parent = media.bounding_box()
                    self.assertAlmostEqual(bounds['width'], parent['width'], delta=1)
                    self.assertAlmostEqual(bounds['height'], parent['height'], delta=1)
                    self.page.get_by_role('button', name='View photo full screen', exact=True).click()
                    dialog = self.page.locator('[data-photo-lightbox]')
                    expect(dialog).to_be_visible()
                    expect(dialog.locator('[data-gallery-watermark]')).to_be_visible()
                    self.page.get_by_role('button', name='Close full view', exact=True).click()
                    expect(dialog).not_to_be_visible()

    def test_dynamic_search_watermarks_are_initialized_and_brand_is_svg_text(self):
        self.html = '<!doctype html><meta charset="utf-8"><body><script src="/static/js/client_gallery_watermark.js" defer></script></body>'
        self.page.goto('https://gallery.example.test/')
        self.page.evaluate('''() => {
            const overlay = document.createElement('span');
            overlay.dataset.galleryWatermark = '';
            overlay.dataset.watermarkLabel = '<script>alert(1)</script> & Studio';
            document.body.append(overlay);
        }''')
        overlay = self.page.locator('[data-gallery-watermark]')
        expect(overlay).to_have_attribute('style', re.compile('data:image/svg'))
        xml = overlay.evaluate('el => decodeURIComponent(el.style.backgroundImage)')
        self.assertIn('&lt;script&gt;', xml)
        self.assertNotIn('<script>', xml)
