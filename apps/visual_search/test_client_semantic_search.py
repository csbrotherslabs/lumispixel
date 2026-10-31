"""Client search rendering, ranked authorization, and browser interaction contracts."""
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


# The ordinary browser CI installs Chromium. Local environments can run the API
# contracts without installing a browser; the dedicated semantic CI installs it.
with sync_playwright() as _playwright:
    HAS_CHROMIUM = Path(_playwright.chromium.executable_path).exists()


@skipUnless(HAS_CHROMIUM, "Install Playwright Chromium for client search browser tests")
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
        self.page.route("https://client.example.test/", lambda route: route.fulfill(content_type="text/html", body=html))
        self.page.goto("https://client.example.test/")
        self.input = self.page.get_by_role("searchbox")

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
        # Leave the request unanswered until the user clears the search.
        requests = []
        self.page.route("**/api/visual-search/**", lambda route: requests.append(route))
        self.input.fill("decorations")
        self.input.press("Enter")
        expect(self.page.get_by_role("button", name="Searching…", exact=True)).to_be_disabled()
        self.page.get_by_role("button", name="Clear search").click()
        expect(self.page.locator('[data-semantic-results]')).to_be_hidden()
        expect(self.page.get_by_role("status")).to_have_text("")
        expect(self.page.get_by_role("button", name="Search photos", exact=True)).to_be_enabled()
