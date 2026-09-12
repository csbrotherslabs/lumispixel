from html.parser import HTMLParser

from django.conf import settings
from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse

from . import views


class _MarketingNavParser(HTMLParser):
    """Collect primary-nav links without depending on serialized HTML whitespace."""

    def __init__(self):
        super().__init__()
        self.in_primary_nav = False
        self.nav_depth = 0
        self.current_li = None
        self.current_link = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "Primary navigation":
            self.in_primary_nav = True
            self.nav_depth = 1
            return
        if not self.in_primary_nav:
            return
        if tag == "nav":
            self.nav_depth += 1
        elif tag == "li":
            self.current_li = {"classes": set((attrs.get("class") or "").split())}
        elif tag == "a" and self.current_li is not None:
            self.current_link = {
                "href": attrs.get("href"),
                "aria_current": attrs.get("aria-current"),
                "aria_haspopup": attrs.get("aria-haspopup"),
                "text": "",
            }

    def handle_data(self, data):
        if self.current_link is not None:
            self.current_link["text"] += data

    def handle_endtag(self, tag):
        if not self.in_primary_nav:
            return
        if tag == "a" and self.current_link is not None:
            item = dict(self.current_link)
            item["text"] = item["text"].strip()
            item["classes"] = set(self.current_li.get("classes", set()))
            self.items.append(item)
            self.current_link = None
        elif tag == "li":
            self.current_li = None
        elif tag == "nav":
            self.nav_depth -= 1
            if self.nav_depth <= 0:
                self.in_primary_nav = False


class MarketingContractTestCase(TestCase):
    def primary_nav(self, response):
        parser = _MarketingNavParser()
        parser.feed(response.content.decode(response.charset or "utf-8"))
        return parser.items

    def nav_item(self, response, route_name):
        href = reverse(route_name)
        matches = [item for item in self.primary_nav(response) if item["href"] == href]
        self.assertEqual(len(matches), 1, f"Expected one primary-nav link to {href}")
        return matches[0]

    def assert_nav_active(self, response, route_name, *, aria_current=False):
        item = self.nav_item(response, route_name)
        self.assertIn("active", item["classes"])
        self.assertIn("current", item["classes"])
        if aria_current:
            self.assertEqual(item["aria_current"], "page")
        self.assertIsNone(item["aria_haspopup"])

    def assert_nav_inactive(self, response, route_name):
        item = self.nav_item(response, route_name)
        self.assertNotIn("active", item["classes"])
        self.assertNotIn("current", item["classes"])


class HomePageTests(MarketingContractTestCase):
    def test_start_free_ctas_use_get_started_route(self):
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        get_started = reverse("accounts:get-started")
        self.assertContains(response, f'href="{get_started}"')
        self.assertContains(response, "home-start-free-cta", count=4)
        self.assertNotContains(response, 'home-start-free-cta" href="#"')

    def test_hero_carousel_keeps_four_distinct_stories_and_sources(self):
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode(response.charset or "utf-8")

        # Scope the count to the hero's unique component, not every Swiper on the page.
        self.assertEqual(html.count('class="wptb-slider--item"'), 4)
        for marker in (
            "Photography, Powered by AI.",
            "Find Your Photos in Seconds.",
            "One Workspace. Your Entire Business.",
            "The Right Photographer, Easier to Find.",
            "--desktop-image:",
            "--mobile-image:",
            "wptb-bottom-pane justify-content-center",
        ):
            self.assertIn(marker, html)
        for mobile_placeholder in ("24.jpg", "25.jpg", "26.jpg", "27.jpg"):
            self.assertIn(f"img/slider/{mobile_placeholder}", html)

        responsive_css = (settings.BASE_DIR / "static/css/home_responsive.css").read_text()
        # Test durable responsive hooks/selectors rather than individual pixel values.
        for selector in (
            ".wptb-hero-subheadline",
            ".lumis-pricing-card",
            ".lumis-photo-match__panel-header",
            ".wptb-swiper-navigation.style3 .swiper-button-next",
            ".swiper-slide:not(.swiper-slide-active) .wptb-heading",
            ".swiper-slide-active .wptb-heading",
        ):
            self.assertIn(selector, responsive_css)


class AboutPageTests(MarketingContractTestCase):
    def test_about_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:about"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "about.html")
        self.assertContains(response, reverse("core:products"))
        self.assertContains(response, reverse("accounts:get-started"))
        self.assertContains(response, "css/company_pages_concise.")


class PrivacyPolicyPageTests(MarketingContractTestCase):
    def test_privacy_policy_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:privacy_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "privacy_policy.html")
        self.assertContains(response, 'class="privacy-sections"')
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, "css/privacy-policy.")


class CookiePolicyPageTests(MarketingContractTestCase):
    def test_cookie_policy_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:cookie_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cookie_policy.html")
        self.assertContains(response, 'class="cookie-type-grid"')
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, "css/cookie-policy.")


class AccessibilityPageTests(MarketingContractTestCase):
    def test_accessibility_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:accessibility"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accessibility.html")
        self.assertContains(response, 'class="feature-grid"')
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, "css/accessibility.")


class CareersPageTests(MarketingContractTestCase):
    def test_careers_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:careers"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "careers.html")
        self.assertContains(response, "Full Stack Engineering")
        self.assertContains(response, "css/company_pages_concise.")


class PartnersPageTests(MarketingContractTestCase):
    def test_partners_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:partners"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partners.html")
        self.assertContains(response, "Technology Integrations")
        self.assertContains(response, "css/company_pages_concise.")


class ForPhotographersRoutingTests(MarketingContractTestCase):
    def test_named_url_resolves_to_public_marketing_page(self):
        self.assertEqual(reverse("core:for_photographers"), "/for-photographers/")
        response = self.client.get(reverse("core:for_photographers"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "for_photographers.html")
        self.assertContains(response, "lp-phe-lens")
        self.assertContains(response, reverse("core:products"))
        self.assertNotContains(response, "public_landing")

    def test_homepage_and_navigation_links_use_single_named_route(self):
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("core:for_photographers")}"')
        self.assertNotContains(response, "photographer/for-photographers")

    def test_obsolete_photographer_namespace_route_is_retired(self):
        with self.assertRaises(NoReverseMatch):
            reverse("photographers:for_photographers")
        self.assertEqual(self.client.get("/photographer/for-photographers/").status_code, 404)


class PricingPageTests(MarketingContractTestCase):
    def test_pricing_page_keeps_decision_structure(self):
        response = self.client.get(reverse("core:pricing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pricing.html")
        self.assertContains(response, "css/pricing_concise.")
        self.assertContains(response, 'data-plan-price="pro"')
        self.assertContains(response, reverse("accounts:get-started"))
        self.assertContains(response, reverse("core:contact"))
        html = response.content.decode(response.charset or "utf-8")
        self.assertGreaterEqual(html.count("pc-plan"), 3)
        self.assertIn("pc-plan--featured", html)
        self.assertIn("pricing-faq__item", html)


class CompanyMarketingTests(MarketingContractTestCase):
    child_pages = (
        "core:about", "core:our_story", "core:careers", "core:partners",
        "core:contact", "core:privacy_policy", "core:terms_of_service",
        "core:cookie_policy", "core:accessibility",
    )

    def test_company_overview_uses_concise_directory(self):
        response = self.client.get(reverse("core:company"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "company.html")
        self.assertContains(response, "css/company_concise.")
        for route_name in self.child_pages:
            self.assertContains(response, reverse(route_name))

    def test_company_children_keep_company_parent_active(self):
        for route_name in self.child_pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assert_nav_active(response, "core:company")
                self.assertContains(response, reverse("core:company"))

    def test_company_children_use_expected_page_systems(self):
        for route_name in ("core:about", "core:our_story", "core:careers", "core:partners", "core:contact"):
            response = self.client.get(reverse(route_name))
            self.assertContains(response, "css/company_pages_concise.")
            self.assertContains(response, 'class="cp-back"')
        for route_name in ("core:privacy_policy", "core:terms_of_service", "core:cookie_policy", "core:accessibility"):
            response = self.client.get(reverse(route_name))
            self.assertContains(response, "css/company_policy_concise.")
            self.assertContains(response, 'class="company-back"')

    def test_company_navigation_has_no_dropdown(self):
        response = self.client.get(reverse("core:company"))
        self.assert_nav_active(response, "core:company")

    def test_about_page_does_not_publish_unverified_testimonials(self):
        response = self.client.get(reverse("core:about"))
        self.assertNotContains(response, "Photographer stories")
        self.assertNotContains(response, "Maya R.")

    def test_legal_pages_keep_substantive_sections(self):
        expectations = (
            ("core:privacy_policy", "AI Features and Uploaded Images", "Your Privacy Rights"),
            ("core:terms_of_service", "User Content and Uploaded Photos", "Limitation of Liability"),
            ("core:cookie_policy", "Types of Cookies We Use", "Managing Cookie Preferences"),
            ("core:accessibility", "Known Limitations", "Feedback and Assistance"),
        )
        for route_name, first, second in expectations:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, first)
                self.assertContains(response, second)


class ResourcesOverviewTests(MarketingContractTestCase):
    def test_resources_page_uses_focused_library_overview(self):
        response = self.client.get(reverse("core:resources"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources.html")
        self.assertContains(response, "css/resources_concise.")
        self.assertContains(response, 'class="ro-groups"')
        for route_name in (
            "core:resources_blog", "core:resources_photography_guides",
            "core:resources_business_guides", "core:resources_ai_learning_center",
            "core:resources_templates", "core:resources_free_downloads",
            "core:resources_video_tutorials", "core:resources_webinars_events",
            "core:resources_success_stories", "core:resources_help_center",
            "core:resources_release_notes", "core:resources_learning_hub",
        ):
            self.assertContains(response, reverse(route_name))


class ResourceDetailConciseTests(MarketingContractTestCase):
    pages = (
        ("core:resources_blog", "blog"),
        ("core:resources_photography_guides", "photo"),
        ("core:resources_business_guides", "business"),
        ("core:resources_ai_learning_center", "ai"),
        ("core:resources_templates", "templates"),
        ("core:resources_help_center", "help"),
        ("core:resources_video_tutorials", "video"),
        ("core:resources_webinars_events", "events"),
        ("core:resources_success_stories", "stories"),
        ("core:resources_free_downloads", "downloads"),
        ("core:resources_release_notes", "updates"),
        ("core:resources_learning_hub", "learning"),
    )

    def test_each_resource_page_uses_concise_detail_system(self):
        for route_name, theme in self.pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"rd--{theme}")
                self.assertContains(response, "css/resource_detail_concise.")
                self.assertContains(response, 'class="rd-back"')
                self.assertContains(response, reverse("core:resources"))
                for component in ("rd-feature", "rd-library", "rd-topics", "rd-final"):
                    self.assertContains(response, f'class="{component}"')

    def test_help_center_retains_direct_search(self):
        response = self.client.get(reverse("core:resources_help_center"))
        self.assertContains(response, 'class="rd-search"')
        self.assertContains(response, 'name="q"')


class MarketingNavigationActiveStateTests(MarketingContractTestCase):
    def test_only_home_is_active_on_homepage(self):
        response = self.client.get(reverse("core:index"))
        self.assert_nav_active(response, "core:index", aria_current=True)
        for route_name in ("core:products", "core:solutions", "core:business_hub", "core:pricing", "core:resources", "core:company"):
            self.assert_nav_inactive(response, route_name)

    def test_top_level_page_marks_its_own_navigation_item_active(self):
        response = self.client.get(reverse("core:pricing"))
        self.assert_nav_active(response, "core:pricing", aria_current=True)
        self.assert_nav_inactive(response, "core:index")

    def test_resource_child_marks_resources_parent_active(self):
        response = self.client.get(reverse("core:resources_business_guides"))
        self.assert_nav_active(response, "core:resources")
        self.assert_nav_inactive(response, "core:index")

    def test_resources_navigation_has_no_dropdown(self):
        response = self.client.get(reverse("core:resources"))
        self.assert_nav_active(response, "core:resources")


class ProductsOverviewTests(MarketingContractTestCase):
    def test_products_page_uses_condensed_platform_overview(self):
        response = self.client.get(reverse("core:products"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products.html")
        self.assertContains(response, "lp-products-command")
        for marker in ("Photographer Workspace", "Client Galleries", "AI Photo Tools", "Photographer Websites", "Client Experience", "Marketplace"):
            self.assertContains(response, marker)
        self.assertContains(response, "css/products.")

    def test_primary_navigation_links_directly_to_products_overview(self):
        response = self.client.get(reverse("core:index"))
        item = self.nav_item(response, "core:products")
        self.assertEqual(item["href"], reverse("core:products"))
        self.assertIsNone(item["aria_haspopup"])


class RemainingProductDeepDiveTests(MarketingContractTestCase):
    def test_each_product_page_is_concise_and_visually_distinct(self):
        pages = (
            ("galleries:client_galleries", "dpp-gallery", "dpg-frames"),
            ("ai_engine:photo_search", "dpp-search", "dps-radar"),
            ("photographers:websites", "dpp-websites", "dpw-canvas"),
            ("clients:for_clients", "dpp-clients", "dpc-memory"),
            ("marketplace:find_photographer", "dpp-market", "dpm-search"),
        )
        for url_name, page_class, signature_class in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, page_class)
                self.assertContains(response, signature_class)
                self.assertContains(response, reverse("core:products"))
                self.assertContains(response, "dpp-back")
                self.assertContains(response, "css/product_deep_diverse.")

    def test_light_product_heroes_use_navbar_safe_return_controls(self):
        for url_name in ("galleries:client_galleries", "photographers:websites", "clients:for_clients"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, 'class="dpp-back"')
                self.assertContains(response, "css/product_deep_diverse.")


class BusinessHubOverviewTests(MarketingContractTestCase):
    def test_business_hub_uses_condensed_tool_overview(self):
        response = self.client.get(reverse("core:business_hub"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "business_hub.html")
        self.assertContains(response, "css/business_hub_concise.")
        for route_name in (
            "core:business_hub_dashboard", "core:business_hub_client_crm",
            "core:business_hub_booking_calendar", "core:business_hub_ai_business_assistant",
            "core:business_hub_contracts", "core:business_hub_invoices_payments",
            "core:business_hub_workflow_automation", "core:business_hub_analytics_reports",
            "core:business_hub_marketing_growth", "core:business_hub_team_operations",
        ):
            self.assertContains(response, reverse(route_name))

    def test_navigation_links_directly_to_business_hub(self):
        response = self.client.get(reverse("core:index"))
        item = self.nav_item(response, "core:business_hub")
        self.assertEqual(item["href"], reverse("core:business_hub"))
        self.assertIsNone(item["aria_haspopup"])


class BusinessHubDeepDiveTests(MarketingContractTestCase):
    def test_each_business_hub_page_is_concise_and_returns_to_overview(self):
        pages = (
            ("core:business_hub_dashboard", "dashboard"),
            ("core:business_hub_client_crm", "crm"),
            ("core:business_hub_booking_calendar", "calendar"),
            ("core:business_hub_ai_business_assistant", "assistant"),
            ("core:business_hub_contracts", "contracts"),
            ("core:business_hub_invoices_payments", "payments"),
            ("core:business_hub_workflow_automation", "automation"),
            ("core:business_hub_analytics_reports", "analytics"),
            ("core:business_hub_marketing_growth", "marketing"),
            ("core:business_hub_team_operations", "team"),
        )
        for route_name, theme in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"bhd--{theme}")
                self.assertContains(response, 'class="bhd-back"')
                self.assertContains(response, reverse("core:business_hub"))
                self.assertContains(response, "css/business_hub_concise.")


class LearningHubNavigationTests(MarketingContractTestCase):
    def test_learning_hub_route_renders_marketing_template(self):
        learning_hub_url = reverse("core:resources_learning_hub")
        self.assertEqual(learning_hub_url, "/resources/learning-hub/")
        response = self.client.get(learning_hub_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "resources_learning_hub.html")

    def test_marketing_navigation_exposes_learning_hub_route(self):
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, f'href="{reverse("core:resources_learning_hub")}"')
        self.assertNotContains(response, f'href="{reverse("core:resources_newsletter")}">Newsletter / Learning Hub</a>')

    def test_resources_card_links_to_learning_hub(self):
        response = self.client.get(reverse("core:resources"))
        self.assertContains(response, f'href="{reverse("core:resources_learning_hub")}"')


class BusinessGuidesNavigationTests(MarketingContractTestCase):
    def test_business_guides_route_renders_existing_marketing_template(self):
        business_guides_url = reverse("core:resources_business_guides")
        self.assertEqual(business_guides_url, "/resources/business-guides/")
        self.assertIs(resolve(business_guides_url).func, views.resources_business_guides)
        response = self.client.get(business_guides_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "resources_business_guides.html")

    def test_resources_card_links_to_business_guides(self):
        response = self.client.get(reverse("core:resources"))
        business_guides_url = reverse("core:resources_business_guides")
        self.assertContains(response, "Business Guides")
        self.assertContains(response, f'href="{business_guides_url}"')

    def test_public_marketing_navbar_uses_resources_overview_without_child_dropdown(self):
        public_pages = (
            "core:index", "core:resources", "core:resources_learning_hub",
            "core:resources_release_notes", "core:resources_success_stories",
            "core:products", "core:solutions", "core:business_hub", "core:pricing",
        )
        for route_name in public_pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                item = self.nav_item(response, "core:resources")
                self.assertEqual(item["href"], reverse("core:resources"))
                self.assertIsNone(item["aria_haspopup"])
