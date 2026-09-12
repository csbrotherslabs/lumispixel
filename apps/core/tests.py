from html.parser import HTMLParser

from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse

from . import views


class _PrimaryNavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_nav = False
        self.current_li = None
        self.current_link = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "Primary navigation":
            self.in_nav = True
            return
        if not self.in_nav:
            return
        if tag == "li":
            self.current_li = set((attrs.get("class") or "").split())
        elif tag == "a" and self.current_li is not None:
            self.current_link = {
                "href": attrs.get("href"),
                "aria_current": attrs.get("aria-current"),
                "aria_haspopup": attrs.get("aria-haspopup"),
            }

    def handle_endtag(self, tag):
        if not self.in_nav:
            return
        if tag == "a" and self.current_link is not None:
            item = dict(self.current_link)
            item["classes"] = set(self.current_li or set())
            self.items.append(item)
            self.current_link = None
        elif tag == "li":
            self.current_li = None
        elif tag == "nav":
            self.in_nav = False


class MarketingBehaviorTests(TestCase):
    top_level_routes = (
        "core:index",
        "core:products",
        "core:solutions",
        "core:business_hub",
        "core:pricing",
        "core:resources",
        "core:company",
    )

    company_routes = (
        "core:about",
        "core:our_story",
        "core:careers",
        "core:partners",
        "core:contact",
        "core:privacy_policy",
        "core:terms_of_service",
        "core:cookie_policy",
        "core:accessibility",
    )

    resource_routes = (
        "core:resources_blog",
        "core:resources_photography_guides",
        "core:resources_business_guides",
        "core:resources_ai_learning_center",
        "core:resources_templates",
        "core:resources_free_downloads",
        "core:resources_video_tutorials",
        "core:resources_webinars_events",
        "core:resources_success_stories",
        "core:resources_help_center",
        "core:resources_release_notes",
        "core:resources_learning_hub",
    )

    business_hub_routes = (
        "core:business_hub_dashboard",
        "core:business_hub_client_crm",
        "core:business_hub_booking_calendar",
        "core:business_hub_ai_business_assistant",
        "core:business_hub_contracts",
        "core:business_hub_invoices_payments",
        "core:business_hub_workflow_automation",
        "core:business_hub_analytics_reports",
        "core:business_hub_marketing_growth",
        "core:business_hub_team_operations",
    )

    def primary_nav(self, response):
        parser = _PrimaryNavParser()
        parser.feed(response.content.decode(response.charset or "utf-8"))
        return parser.items

    def nav_item(self, response, route_name):
        href = reverse(route_name)
        matches = [item for item in self.primary_nav(response) if item["href"] == href]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_public_top_level_routes_render(self):
        expected_templates = {
            "core:index": "index.html",
            "core:products": "products.html",
            "core:solutions": "solutions.html",
            "core:business_hub": "business_hub.html",
            "core:pricing": "pricing.html",
            "core:resources": "resources.html",
            "core:company": "company.html",
        }
        for route_name in self.top_level_routes:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, expected_templates[route_name])

    def test_primary_navigation_routes_are_unique_and_not_dropdowns(self):
        response = self.client.get(reverse("core:index"))
        for route_name in self.top_level_routes:
            with self.subTest(route_name=route_name):
                item = self.nav_item(response, route_name)
                self.assertEqual(item["href"], reverse(route_name))
                self.assertIsNone(item["aria_haspopup"])

    def test_home_and_pricing_active_state_is_semantic(self):
        home = self.client.get(reverse("core:index"))
        home_item = self.nav_item(home, "core:index")
        self.assertIn("active", home_item["classes"])
        self.assertIn("current", home_item["classes"])
        self.assertEqual(home_item["aria_current"], "page")

        pricing = self.client.get(reverse("core:pricing"))
        pricing_item = self.nav_item(pricing, "core:pricing")
        self.assertIn("active", pricing_item["classes"])
        self.assertIn("current", pricing_item["classes"])
        self.assertEqual(pricing_item["aria_current"], "page")
        self.assertNotIn("active", self.nav_item(pricing, "core:index")["classes"])

    def test_company_children_keep_company_navigation_active(self):
        for route_name in self.company_routes:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                item = self.nav_item(response, "core:company")
                self.assertIn("active", item["classes"])
                self.assertIn("current", item["classes"])

    def test_resource_routes_render_and_keep_resources_active(self):
        for route_name in self.resource_routes:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                item = self.nav_item(response, "core:resources")
                self.assertIn("active", item["classes"])
                self.assertIn("current", item["classes"])
                self.assertIsNone(item["aria_haspopup"])

    def test_business_hub_deep_links_render(self):
        for route_name in self.business_hub_routes:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, reverse("core:business_hub"))

    def test_learning_hub_and_business_guides_resolve_to_expected_views(self):
        learning = reverse("core:resources_learning_hub")
        guides = reverse("core:resources_business_guides")
        self.assertEqual(self.client.get(learning).status_code, 200)
        self.assertIs(resolve(guides).func, views.resources_business_guides)
        self.assertEqual(self.client.get(guides).status_code, 200)

    def test_home_routes_to_get_started_and_photographer_marketing(self):
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:get-started"))
        self.assertContains(response, reverse("core:for_photographers"))

    def test_obsolete_photographer_namespace_route_is_retired(self):
        with self.assertRaises(NoReverseMatch):
            reverse("photographers:for_photographers")
        self.assertEqual(self.client.get("/photographer/for-photographers/").status_code, 404)
