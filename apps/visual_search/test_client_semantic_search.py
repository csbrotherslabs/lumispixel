"""Client search rendering, ranked authorization, and browser interaction contracts."""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright, expect

from apps.accounts.models import PhotographerProfile
from apps.galleries.models import AccessToken, Gallery, GalleryInvitation, GalleryPermission, GalleryPhoto
from .models import GallerySemanticSearchPolicy


@override_settings(VISUAL_SEARCH_SEMANTIC_ENABLED=True, VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=True, MEDIA_SIGNING_SECRET="client-search-test-only-signing-secret")
class ClientSemanticSearchTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(email="client-search@example.test", password="test")
        self.profile = PhotographerProfile.objects.create(user=owner, slug="client-search")
        self.gallery = Gallery.objects.create(photographer=self.profile, name="Client search", slug="client-search", status=Gallery.Status.PUBLISHED, visibility=Gallery.Visibility.PUBLIC)
        self.permission, _ = GalleryPermission.objects.update_or_create(gallery=self.gallery, defaults={"view_gallery": True})
        self.policy = GallerySemanticSearchPolicy.objects.create(gallery=self.gallery, processing_authorized=True)
        invitation = GalleryInvitation.objects.create(gallery=self.gallery, client_name="Test client", email="invited@example.test")
        self.token_record, self.token = AccessToken.issue(invitation)
        self.public_url = reverse("visual_search:public-semantic-search", args=[self.gallery.public_id])
        self.invited_url = reverse("visual_search:invited-semantic-search", args=[self.token])

    def test_search_shows_on_every_invited_design_and_uses_token_endpoint(self):
        for design in [*Gallery.DesignTemplate.values, "legacy"]:
            with self.subTest(design=design):
                Gallery.objects.filter(pk=self.gallery.pk).update(design_template=design)
                response = self.client.get(reverse("galleries:client_gallery_access", args=[self.token]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-semantic-client-form")
                self.assertContains(response, self.invited_url)
                self.assertNotContains(response, self.public_url)
        self.policy.processing_authorized = False
        self.policy.save()
        response = self.client.get(reverse("galleries:client_gallery_access", args=[self.token]))
        self.assertNotContains(response, "data-semantic-client-form")

    def test_public_page_uses_public_endpoint(self):
        response = self.client.get(reverse("galleries:stable_gallery_access", args=[self.gallery.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.public_url)

    def test_ranked_results_exclude_hidden_incomplete_and_other_gallery(self):
        def photo(gallery, **kwargs):
            return GalleryPhoto.objects.create(gallery=gallery, photographer=self.profile, file="test.jpg", status=kwargs.pop("status", GalleryPhoto.Status.COMPLETED), **kwargs)
        first, second = photo(self.gallery), photo(self.gallery)
        hidden = photo(self.gallery, is_visible=False)
        incomplete = photo(self.gallery, status=GalleryPhoto.Status.QUEUED)
        other = Gallery.objects.create(photographer=self.profile, name="Other", slug="other-search")
        foreign = photo(other)
        ranked = [second.pk, hidden.pk, foreign.pk, incomplete.pk, first.pk]
        with patch("apps.visual_search.semantic_api._semantic_results", return_value=ranked):
            for url in [self.public_url, self.invited_url]:
                response = self.client.get(url, {"q": "cake on a table"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([p["photo_id"] for p in response.json()["results"]], [second.pk, first.pk])
                self.assertTrue(all(p["thumbnail_url"] for p in response.json()["results"]))

    def test_revoked_private_and_disabled_access_never_searches(self):
        with patch("apps.visual_search.semantic_api._semantic_results") as search:
            self.token_record.revoked_at = timezone.now()
            self.token_record.save()
            self.assertEqual(self.client.get(self.invited_url, {"q": "cake"}).status_code, 404)
            Gallery.objects.filter(pk=self.gallery.pk).update(visibility=Gallery.Visibility.PRIVATE)
            self.assertEqual(self.client.get(self.public_url, {"q": "cake"}).status_code, 404)
            search.assert_not_called()

    def test_disabled_permission_and_policy_deny_search(self):
        with patch("apps.visual_search.semantic_api._semantic_results") as search:
            self.permission.view_gallery = False
            self.permission.save()
            self.assertEqual(self.client.get(self.invited_url, {"q": "cake"}).status_code, 404)
            self.permission.view_gallery = True
            self.permission.save()
            self.policy.processing_authorized = False
            self.policy.save()
            self.assertEqual(self.client.get(self.invited_url, {"q": "cake"}).status_code, 403)
            search.assert_not_called()

    def test_results_page_keeps_rank_and_all_photo_controls_for_every_design(self):
        self.permission.favorite_photos = True
        self.permission.comment = True
        self.permission.download_images = True
        self.permission.download_originals = True
        self.permission.save()
        photos = GalleryPhoto.objects.bulk_create([GalleryPhoto(
            gallery=self.gallery, photographer=self.profile, file="test.jpg",
            status=GalleryPhoto.Status.COMPLETED, is_visible=True,
        ) for _ in range(100)])
        ranked = [photo.pk for photo in reversed(photos)]
        url = reverse('galleries:invited_semantic_results', args=[self.token])
        with patch('apps.visual_search.semantic_api._semantic_results', return_value=ranked):
            for design in Gallery.DesignTemplate.values:
                Gallery.objects.filter(pk=self.gallery.pk).update(design_template=design)
                response = self.client.get(url, {'q': 'people dancing'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([photo.pk for photo in response.context['photos']], ranked)
                self.assertEqual(response.content.count(b'data-client-photo'), 100)
                for marker in ['data-favorite-form', 'data-comment-form', 'data-photo-download', 'data-full-view', 'data-photo-lightbox', 'data-gallery-watermark']:
                    self.assertContains(response, marker)
                self.assertIn('no-store', response.headers['Cache-Control'])

    def test_results_page_preserves_visibility_and_public_read_only_access(self):
        visible = GalleryPhoto.objects.create(gallery=self.gallery, photographer=self.profile, file='test.jpg', status=GalleryPhoto.Status.COMPLETED)
        hidden = GalleryPhoto.objects.create(gallery=self.gallery, photographer=self.profile, file='hidden.jpg', status=GalleryPhoto.Status.COMPLETED, is_visible=False)
        other = Gallery.objects.create(photographer=self.profile, name='Other result', slug='other-result')
        foreign = GalleryPhoto.objects.create(gallery=other, photographer=self.profile, file='foreign.jpg', status=GalleryPhoto.Status.COMPLETED)
        url = reverse('galleries:public_semantic_results', args=[self.gallery.public_id])
        with patch('apps.visual_search.semantic_api._semantic_results', return_value=[foreign.pk, hidden.pk, visible.pk]):
            response = self.client.get(url, {'q': 'celebration'})
        self.assertEqual([photo.pk for photo in response.context['photos']], [visible.pk])
        self.assertNotContains(response, 'data-favorite-form')
        self.assertNotContains(response, 'data-photo-download')
        self.assertNotContains(response, 'data-comment-form')

    def test_results_page_rechecks_policy_and_denies_revoked_access(self):
        url = reverse('galleries:invited_semantic_results', args=[self.token])
        with patch('apps.visual_search.semantic_api._semantic_results') as search:
            self.assertEqual(self.client.get(url, {'q': 'x'}).status_code, 400)
            self.policy.processing_authorized = False
            self.policy.save()
            self.assertEqual(self.client.get(url, {'q': 'cake'}).status_code, 403)
            self.token_record.revoked_at = timezone.now()
            self.token_record.save()
            self.assertEqual(self.client.get(url, {'q': 'cake'}).status_code, 404)
            search.assert_not_called()



# The ordinary browser CI installs Chromium. Local environments can run the API
# contracts without installing a browser; the dedicated semantic CI installs it.
with sync_playwright() as _playwright:
    HAS_CHROMIUM = Path(_playwright.chromium.executable_path).exists()


@skipUnless(HAS_CHROMIUM or os.getenv("REQUIRE_CLIENT_SEARCH_BROWSER") == "1", "Install Playwright Chromium for client search browser tests")
class ClientSemanticBrowserTests(SimpleTestCase):
    def setUp(self):
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.browser = self.playwright.chromium.launch()
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        html = render_to_string("galleries/components/semantic_search.html", {
            "semantic_search_available": True,
            "gallery": SimpleNamespace(public_id=uuid4()),
        })
        css = (settings.BASE_DIR / "static/css/client_gallery_semantic_search.css").read_text()
        js = (settings.BASE_DIR / "static/js/client_gallery_semantic_search.js").read_text()
        import re
        html = re.sub(r'<link[^>]+>', lambda _: '<style>' + css + '</style>', html)
        html = re.sub(r'<script[^>]+></script>', lambda _: '<script>' + js + '</script>', html)
        self.page.route("https://client.example.test/", lambda route: route.fulfill(content_type="text/html", body='<!doctype html><meta charset="utf-8">' + html))
        self.search_html = html
        self.page.goto("https://client.example.test/")
        self.input = self.page.get_by_role("searchbox")
        self.page.get_by_role("button", name="AI photo search", exact=True).click()

    def test_floating_search_hover_keyboard_and_touch(self):
        toggle = self.page.get_by_role("button", name="AI photo search", exact=True)
        self.input.press("Escape")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(self.input).not_to_be_visible()
        self.page.mouse.move(20, 20)
        toggle.hover()
        expect(self.input).to_be_visible()
        dock = self.page.locator('.lp-semantic-client__dock')
        self.assertGreater(dock.bounding_box()['width'], 580)
        self.assertAlmostEqual(self.page.locator('form').bounding_box()['x'] + self.page.locator('form').bounding_box()['width'], toggle.bounding_box()['x'], delta=1)
        self.input.fill('people dancing')
        self.page.mouse.move(20, 20)
        expect(self.input).to_have_value('people dancing')
        expect(self.input).to_be_visible()
        self.input.press('Escape')
        expect(self.input).not_to_be_visible()
        # Clicking the icon reopens without discarding the prompt.
        toggle.click()
        expect(self.input).to_be_focused()
        expect(self.input).to_have_value('people dancing')
        self.page.set_viewport_size({'width': 390, 'height': 800})
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)
        bounds = self.page.locator('[data-semantic-client]').bounding_box()
        self.assertAlmostEqual(bounds['x'] + bounds['width'], 374, delta=1)
        self.assertAlmostEqual(bounds['y'] + bounds['height'], 784, delta=1)

    def test_top_ten_results_and_page_link_preserve_rank_and_clear(self):
        ids = [20, 3, 18, 9, 2, 31, 5, 4, 30, 12, 8, 1]
        self.page.route('**/api/visual-search/**', lambda route: route.fulfill(json={'results': [
            {'photo_id': photo_id, 'thumbnail_url': '/photo.jpg'} for photo_id in ids]}))
        for width in [1440, 390]:
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.input.fill('baby shower')
            self.input.press('Enter')
            visible = self.page.locator('[data-semantic-results] > li:visible')
            expect(visible).to_have_count(10)
            self.assertEqual(visible.evaluate_all('rows => rows.map(row => Number(row.dataset.photoId))'), ids[:10])
            expect(self.page.get_by_role('heading', name='Top 10 matches')).to_be_visible()
            panel = self.page.locator('[data-semantic-panel]')
            dock = self.page.locator('.lp-semantic-client__dock')
            bounds, field = panel.bounding_box(), dock.bounding_box()
            self.assertLessEqual(bounds['y'] + bounds['height'] + 12, field['y'])
            self.assertEqual(len(self.page.locator('[data-semantic-results]').evaluate('el => getComputedStyle(el).gridTemplateColumns').split()), 2)
            if width == 1440:
                self.assertGreater(field['width'], bounds['width'])
                self.assertGreater(self.page.locator('[data-semantic-results] img').first.bounding_box()['height'], 100)
            link = self.page.get_by_role('link', name='View all matches', exact=True)
            expect(link).to_have_attribute('href', __import__('re').compile(r'/galleries/g/.+/search/\?q=baby\+shower|/galleries/g/.+/search/\?q=baby%20shower'))
            # The normal anchor performs same-tab navigation; existing cards are
            # rendered and authorization checked by the destination Django view.
            self.assertNotIn('aria-pressed', link.evaluate('el => el.outerHTML'))
            self.page.get_by_role('button', name='Clear search', exact=True).click()
            expect(panel).to_be_hidden()
            expect(self.page.locator('[data-semantic-view-all]')).to_be_hidden()

    def test_view_all_navigates_to_results_page(self):
        self.page.route('**/api/visual-search/**', lambda route: route.fulfill(json={'results': [
            {'photo_id': index, 'thumbnail_url': '/photo.jpg'} for index in range(1, 13)]}))
        self.page.route('**/galleries/g/**/search/**', lambda route: route.fulfill(body='<h1>Ordered search results</h1>'))
        self.input.fill('baby shower')
        self.input.press('Enter')
        link = self.page.get_by_role('link', name='View all matches', exact=True)
        expect(link).to_be_visible()
        link.click()
        expect(self.page).to_have_url(__import__('re').compile(r'/search/\?q=baby\+shower'))
        expect(self.page.get_by_role('heading', name='Ordered search results')).to_be_visible()

    def test_touch_opens_input_without_hover(self):
        page = self.browser.new_page(has_touch=True, viewport={'width': 390, 'height': 800})
        self.addCleanup(page.close)
        page.route('https://client.example.test/', lambda route: route.fulfill(content_type='text/html', body=self.search_html))
        page.goto('https://client.example.test/')
        field = page.get_by_role('searchbox')
        expect(field).not_to_be_visible()
        page.get_by_role('button', name='AI photo search', exact=True).tap()
        expect(field).to_be_focused()
        field.fill('birthday cake')
        expect(field).to_have_value('birthday cake')

    def test_rank_order_preview_clear_and_responsive_layout(self):
        self.page.route("**/api/visual-search/**", lambda route: route.fulfill(json={"results": [
            {"photo_id": 20, "thumbnail_url": "https://client.example.test/20.jpg"},
            {"photo_id": 3, "thumbnail_url": "https://client.example.test/3.jpg"},
        ]}))
        for width in [1440, 390]:
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 900})
                self.input.fill("baby shower decorations")
                self.page.get_by_role("button", name="Search photos", exact=True).click()
                rows = self.page.locator('[data-semantic-results] li')
                expect(rows).to_have_count(2)
                self.assertEqual(rows.evaluate_all("rows => rows.map(row => row.dataset.photoId)"), ["20", "3"])
                self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
                self.page.get_by_role("button", name="View result 1 for baby shower decorations").click()
                expect(self.page.get_by_role("dialog")).to_be_visible()
                self.page.keyboard.press("Escape")
                expect(self.page.get_by_role("dialog")).not_to_be_visible()
                self.page.get_by_role("button", name="Clear search").click()
                expect(rows).to_have_count(0)
                expect(self.input).to_have_value("")

    def test_empty_and_access_error(self):
        self.page.route("**/api/visual-search/**", lambda route: route.fulfill(json={"results": []}))
        self.input.fill("a cake")
        self.input.press("Enter")
        expect(self.page.get_by_role("status")).to_contain_text("No searchable photos found")
        self.page.unroute("**/api/visual-search/**")
        self.page.route("**/api/visual-search/**", lambda route: route.fulfill(status=403, json={"error": "disabled"}))
        self.input.press("Enter")
        expect(self.page.get_by_role("status")).to_contain_text("no longer available")
        expect(self.page.get_by_role("button", name="Search photos", exact=True)).to_be_enabled()

    def test_clear_cancels_pending_results(self):
        # Resolve a stale response after clearing, even if a transport ignores
        # cancellation. The UI must reject it and abort the request signal.
        self.page.evaluate("""() => {
            window.fetch = (url, options) => {
                window.searchSignal = options.signal;
                return new Promise(resolve => { window.resolveSearch = resolve; });
            };
        }""")
        self.input.fill("decorations")
        self.input.press("Enter")
        expect(self.page.get_by_role("button", name="Searching…", exact=True)).to_be_disabled()
        self.page.get_by_role("button", name="Clear search").click()
        expect(self.page.locator('[data-semantic-results]')).to_be_hidden()
        expect(self.page.locator("[data-semantic-status]")).to_have_text("")
        expect(self.page.locator("[data-semantic-panel]")).to_be_hidden()
        expect(self.page.get_by_role("button", name="Search photos", exact=True)).to_be_enabled()
        self.assertTrue(self.page.evaluate("window.searchSignal.aborted"))
        self.page.evaluate("""() => window.resolveSearch({
            ok: true, json: async () => ({results: [{photo_id: 99, thumbnail_url: '/stale.jpg'}]})
        })""")
        expect(self.page.locator('[data-semantic-results] li')).to_have_count(0)
