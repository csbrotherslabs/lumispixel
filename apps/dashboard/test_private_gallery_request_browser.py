"""Real Chromium journeys for the feature-gated photographer request inbox.

Uses Django LiveServerTestCase and synthetic invitation records. No face data.
"""
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections, connections
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from apps.accounts.models import PhotographerProfile
from apps.billing.models import Plan
from apps.galleries.models import Gallery
from apps.visual_search.access_requests import PrivateGalleryAccessRequest, PrivateGalleryInvitation


@override_settings(
    VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True,
    VISUAL_SEARCH_PRIVATE_ACCESS_SHARED_CACHE=True,
)
class PrivateGalleryInboxBrowserTests(LiveServerTestCase):
    serialized_rollback = True

    def setUp(self):
        Plan.objects.get_or_create(
            code="free", defaults={"name": "Free", "is_active": True},
        )
        self.owner = self._user("owner", photographer=True)
        self.other = self._user("other", photographer=True)
        self.visitor = self._user("visitor")
        self.gallery = Gallery.objects.create(
            photographer=self.owner.photographer_profile,
            name="Private invitation browser test",
            slug=f"inbox-{uuid4().hex}",
            status=Gallery.Status.PUBLISHED,
            visibility=Gallery.Visibility.PRIVATE,
            published_at=timezone.now(),
        )
        invite, _ = PrivateGalleryInvitation.issue(
            gallery=self.gallery, user=self.owner,
        )
        self.access_request = PrivateGalleryAccessRequest.objects.create(
            invitation=invite, requester=self.visitor,
        )
        self.path = reverse("photographer_workspace:private_gallery_requests")
        self.review_path = reverse(
            "visual_search:private-access-review", args=[self.access_request.pk],
        )
        cache.clear()
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()
        cache.clear()

    def _user(self, label, photographer=False):
        User = get_user_model()
        user = User.objects.create_user(
            primary_role=User.PrimaryRole.PHOTOGRAPHER if photographer else User.PrimaryRole.CLIENT,
            email=f"{label}-{uuid4().hex}@example.test",
            password="BrowserTestOnly123!",
            email_verified=True,
            account_status="active",
        )
        if photographer:
            PhotographerProfile.objects.create(
                user=user, slug=f"studio-{uuid4().hex}",
                onboarding_completed=True,
            )
        return user

    def _db(self, operation):
        """Keep synchronous Django database calls off Playwright's event loop."""
        def execute():
            close_old_connections()
            try:
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(execute).result()

    def _login(self, user):
        def create_session():
            self.client.force_login(user)
            return self.client.cookies["sessionid"].value
        session_key = self._db(create_session)
        self.context.clear_cookies()
        self.context.add_cookies([{
            "name": "sessionid",
            "value": session_key,
            "url": self.live_server_url,
        }])

    def _open(self):
        return self.page.goto(self.live_server_url + self.path)

    def test_sidebar_navigation_and_owner_only_records(self):
        self._login(self.owner)
        response = self.page.goto(
            self.live_server_url + reverse("photographer_workspace:galleries")
        )
        self.assertEqual(response.status, 200)
        link = self.page.get_by_role("link", name="Access requests")
        self.assertTrue(link.is_visible())
        link.click()
        self.page.wait_for_url("**/galleries/access-requests/")
        self.assertTrue(self.page.get_by_role(
            "heading", name="Private gallery access requests",
        ).is_visible())
        self.assertTrue(self.page.get_by_text(self.visitor.email).is_visible())
        self._login(self.other)
        self._open()
        self.assertFalse(self.page.get_by_text(self.visitor.email).is_visible())

    def test_approve_and_deny_via_browser(self):
        self._login(self.owner)
        self._open()
        with patch(
            "apps.visual_search.private_access_api.send_gallery_invitation_email"
        ) as email:
            self.page.once("dialog", lambda dialog: dialog.accept())
            with self.page.expect_response(lambda resp: self.review_path in resp.url and resp.request.method == "POST") as approval:
                self.page.get_by_role("button", name="Approve & email access").click()
            self.assertEqual(approval.value.status, 200)
        self.assertEqual(self._db(lambda: PrivateGalleryAccessRequest.objects.get(pk=self.access_request.pk).status), "approved")
        email.assert_called_once()

        def make_second_request():
            second_invite, _ = PrivateGalleryInvitation.issue(
                gallery=self.gallery, user=self.owner,
            )
            return PrivateGalleryAccessRequest.objects.create(
                invitation=second_invite, requester=self.visitor,
            ).pk
        second_id = self._db(make_second_request)
        self._open()
        with self.page.expect_response(lambda resp: self.review_path.replace(str(self.access_request.pk), str(second_id)) in resp.url and resp.request.method == "POST") as denial:
            self.page.get_by_role("button", name="Deny").click()
        self.assertEqual(denial.value.status, 200)
        self.assertEqual(self._db(lambda: PrivateGalleryAccessRequest.objects.get(pk=second_id).status), "denied")

    def test_mobile_layout_and_filters(self):
        self._login(self.owner)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self._open()
        self.assertTrue(self.page.get_by_role(
            "heading", name="Private gallery access requests",
        ).is_visible())
        self.assertTrue(self.page.get_by_role("button", name="Deny").is_visible())
        self.page.get_by_role("link", name="Approved (0)").click()
        self.assertTrue(self.page.get_by_text(
            "No approved access requests", exact=False,
        ).is_visible())
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            410,
        )

    def test_anonymous_and_non_owner_denied(self):
        response = self._open()
        self.assertEqual(response.status, 200)  # login redirect followed
        self.assertIn("/accounts/login", self.page.url)
        self._login(self.visitor)
        self._open()
        self.assertNotIn(self.visitor.email, self.page.locator(
            ".lp-access-table"
        ).inner_text() if self.page.locator(".lp-access-table").count() else "")
        self.assertNotIn("/galleries/access-requests/", self.page.url)

    @override_settings(VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=False)
    def test_disabled_feature_hidden_in_navigation(self):
        self._login(self.owner)
        self.page.goto(
            self.live_server_url + reverse("photographer_workspace:galleries")
        )
        self.assertEqual(
            self.page.get_by_role("link", name="Access requests").count(), 0,
        )
        self.assertEqual(self._open().status, 404)
