from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse

from . import views


class AboutPageTests(TestCase):
    def test_about_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "about.html")
        self.assertContains(response, "Built for the work")
        self.assertContains(response, "Less repetition")
        self.assertContains(response, "One platform. Four connected layers")
        self.assertContains(response, "Read Our Story")
        self.assertContains(response, reverse("core:products"))
        self.assertContains(response, reverse("accounts:get-started"))


class PrivacyPolicyPageTests(TestCase):
    def test_privacy_policy_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:privacy_policy"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "privacy_policy.html")
        self.assertContains(response, "Privacy First")
        self.assertContains(response, "Table of Contents")
        self.assertContains(response, 'class="privacy-sections"')
        self.assertContains(response, "Questions About Privacy?")
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, "css/privacy-policy.")


class CookiePolicyPageTests(TestCase):
    def test_cookie_policy_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:cookie_policy"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cookie_policy.html")
        self.assertContains(response, "Your Privacy, Your Choice")
        self.assertContains(response, "Table of Contents")
        self.assertContains(response, 'class="cookie-type-grid"')
        self.assertContains(response, "Essential Cookies")
        self.assertContains(response, "Questions About Cookies?")
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, "css/cookie-policy.")


class AccessibilityPageTests(TestCase):
    def test_accessibility_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:accessibility"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accessibility.html")
        self.assertContains(response, "Our Accessibility Commitment")
        self.assertContains(response, "Table of Contents")
        self.assertContains(response, 'class="feature-grid"')
        self.assertContains(response, "Keyboard Navigation")
        self.assertContains(response, "How You Can Help")
        self.assertContains(response, "Help Us Improve Accessibility")
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, "css/accessibility.")


class CareersPageTests(TestCase):
    def test_careers_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:careers"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "careers.html")
        self.assertContains(response, "Small team")
        self.assertContains(response, "Own the outcome")
        self.assertContains(response, "Current areas of interest")
        self.assertContains(response, "Full Stack Engineering")
        self.assertContains(response, "Roles and hiring status may change")
        self.assertContains(response, "Send Your Resume")
        self.assertContains(response, "css/company_pages_concise.")


class PartnersPageTests(TestCase):
    def test_partners_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:partners"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partners.html")
        self.assertContains(response, "Shared audience")
        self.assertContains(response, "A simple partnership path")
        self.assertContains(response, "Partnership paths")
        self.assertContains(response, "Technology Integrations")
        self.assertContains(response, "Tell us the value")
        self.assertContains(response, "css/company_pages_concise.")


class ForPhotographersRoutingTests(TestCase):
    def test_named_url_resolves_to_public_marketing_page(self):
        self.assertEqual(reverse("core:for_photographers"), "/for-photographers/")

        response = self.client.get(reverse("core:for_photographers"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "for_photographers.html")
        self.assertContains(response, "The studio runs")
        self.assertContains(response, "Four jobs")
        self.assertContains(response, "Run the business")
        self.assertContains(response, "Move through photos faster")
        self.assertContains(response, "Deliver beautifully")
        self.assertContains(response, "Grow with clarity")
        self.assertContains(response, "One client journey")
        self.assertContains(response, "lp-phe-lens")
        self.assertNotContains(response, "lp-pb-studio")
        self.assertNotContains(response, "lp-pb-outcome-grid")
        self.assertNotContains(response, "lp-pb-finish__panel")
        self.assertContains(response, reverse("core:products"))
        self.assertNotContains(response, "Photography is hard enough")
        self.assertNotContains(response, "Made for Every Specialty")
        self.assertNotContains(response, "Questions Before Switching")
        self.assertNotContains(response, "public_landing")

    def test_homepage_and_navigation_links_use_single_named_route(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("core:for_photographers")}"')
        self.assertNotContains(response, "photographer/for-photographers")

    def test_obsolete_photographer_namespace_route_is_retired(self):
        with self.assertRaises(NoReverseMatch):
            reverse("photographers:for_photographers")

        response = self.client.get("/photographer/for-photographers/")

        self.assertEqual(response.status_code, 404)


class PricingPageTests(TestCase):
    def test_pricing_page_is_concise_and_decision_focused(self):
        response = self.client.get(reverse("core:pricing"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pricing.html")
        self.assertContains(response, "Start with what fits")
        self.assertContains(response, "The useful differences")
        self.assertContains(response, "Essential answers")
        self.assertContains(response, "css/pricing_concise.")
        self.assertContains(response, 'data-plan-price="pro"')
        self.assertContains(response, reverse("accounts:get-started"))
        self.assertContains(response, reverse("core:contact"))
        self.assertContains(response, 'class="pc-plan"', count=3)
        self.assertContains(response, 'class="pc-plan pc-plan--featured"', count=1)
        self.assertContains(response, 'class="pricing-faq__item', count=5)
        self.assertNotContains(response, "Replace disconnected tools")
        self.assertNotContains(response, "Compare every plan")
        self.assertNotContains(response, "Built with photographers")


class CompanyMarketingTests(TestCase):
    child_pages = (
        "core:about", "core:our_story", "core:careers", "core:partners",
        "core:contact", "core:privacy_policy", "core:terms_of_service",
        "core:cookie_policy", "core:accessibility",
    )

    def test_company_overview_uses_concise_directory(self):
        response = self.client.get(reverse("core:company"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "company.html")
        self.assertContains(response, "Photography keeps moving")
        self.assertContains(response, "Company directory")
        self.assertContains(response, "css/company_concise.")
        for route_name in self.child_pages:
            self.assertContains(response, reverse(route_name))

    def test_company_children_use_concise_or_policy_specific_systems(self):
        for route_name in self.child_pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<li class="menu-item active current"><a href="/company/">Company</a></li>')
                self.assertContains(response, reverse("core:company"))

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

        self.assertContains(response, '<li class="menu-item active current"><a href="/company/">Company</a></li>')
        self.assertNotContains(response, 'href="/company/" aria-haspopup="true"')

    def test_about_page_does_not_publish_unverified_testimonials(self):
        response = self.client.get(reverse("core:about"))

        self.assertNotContains(response, "Photographer stories")
        self.assertNotContains(response, "Maya R.")

    def test_legal_pages_keep_their_substantive_sections(self):
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


class ResourcesOverviewTests(TestCase):
    def test_resources_page_uses_focused_library_overview(self):
        response = self.client.get(reverse("core:resources"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources.html")
        self.assertContains(response, "Learn what matters")
        self.assertContains(response, "Four ways forward")
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


class ResourceDetailConciseTests(TestCase):
    pages = (
        ("core:resources_blog", "blog", "Ideas for better work"),
        ("core:resources_photography_guides", "photo", "Understand the technique"),
        ("core:resources_business_guides", "business", "Run the business"),
        ("core:resources_ai_learning_center", "ai", "Use AI with clarity"),
        ("core:resources_templates", "templates", "Skip the blank page"),
        ("core:resources_help_center", "help", "Find the answer"),
        ("core:resources_video_tutorials", "video", "See the workflow"),
        ("core:resources_webinars_events", "events", "Join the session"),
        ("core:resources_success_stories", "stories", "See the challenge"),
        ("core:resources_free_downloads", "downloads", "Download the starting point"),
        ("core:resources_release_notes", "updates", "Follow the progress"),
        ("core:resources_learning_hub", "learning", "Choose what to learn"),
    )

    def test_each_resource_page_uses_the_concise_detail_system(self):
        for route_name, theme, marker in self.pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"rd--{theme}")
                self.assertContains(response, marker)
                self.assertContains(response, "css/resource_detail_concise.")
                self.assertContains(response, 'class="rd-back"')
                self.assertContains(response, reverse("core:resources"))
                self.assertContains(response, 'class="rd-feature"')
                self.assertContains(response, 'class="rd-library"')
                self.assertContains(response, 'class="rd-topics"')
                self.assertContains(response, 'class="rd-final"')
                self.assertNotContains(response, "Placeholder testimonial")
                self.assertNotContains(response, "Frequently Asked Questions")

    def test_help_center_retains_direct_search(self):
        response = self.client.get(reverse("core:resources_help_center"))

        self.assertContains(response, 'class="rd-search"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, "Search LumisPixel help")


class MarketingNavigationActiveStateTests(TestCase):
    def test_only_home_is_active_on_homepage(self):
        response = self.client.get(reverse("core:index"))

        self.assertContains(response, '<li class="menu-item active current"><a href="/" aria-current="page">Home</a></li>')
        self.assertNotContains(response, 'href="/resources/" aria-haspopup="true" aria-current="page"')

    def test_top_level_page_marks_its_own_navigation_item_active(self):
        response = self.client.get(reverse("core:pricing"))

        self.assertContains(response, '<li class="menu-item active current"><a href="/pricing/" aria-current="page">Pricing</a></li>')
        self.assertNotContains(response, '<li class="menu-item active current"><a href="/" aria-current="page">Home</a></li>')

    def test_resource_child_marks_child_and_resources_parent_active(self):
        response = self.client.get(reverse("core:resources_business_guides"))

        self.assertContains(response, '<li class="menu-item active current"><a href="/resources/">Resources</a></li>')
        self.assertNotContains(response, '<li class="menu-item active current"><a href="/" aria-current="page">Home</a></li>')

    def test_resources_navigation_has_no_dropdown(self):
        response = self.client.get(reverse("core:resources"))

        self.assertContains(response, '<li class="menu-item active current"><a href="/resources/">Resources</a></li>')
        self.assertNotContains(response, 'href="/resources/" aria-haspopup="true"')


class ProductsOverviewTests(TestCase):
    def test_products_page_uses_condensed_platform_overview(self):
        response = self.client.get(reverse("core:products"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products.html")
        self.assertContains(response, "Every part of the photography journey")
        self.assertContains(response, "Six capabilities")
        self.assertContains(response, "From discovery to payment")
        self.assertContains(response, "lp-products-command")
        self.assertContains(response, "Workspace + Website")
        self.assertNotContains(response, "lp-products-console")
        self.assertContains(response, "Photographer Workspace")
        self.assertContains(response, "Client Galleries")
        self.assertContains(response, "AI Photo Tools")
        self.assertContains(response, "Photographer Websites")
        self.assertContains(response, "Client Experience")
        self.assertContains(response, "Marketplace")
        self.assertContains(response, "css/products.")

    def test_primary_navigation_links_directly_to_products_overview(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<li class="menu-item"><a href="{reverse("core:products")}">Products</a></li>',
            html=True,
        )
        self.assertNotContains(
            response,
            '<a href="/products/" aria-haspopup="true">Products</a>',
            html=True,
        )


class RemainingProductDeepDiveTests(TestCase):
    def test_each_product_page_is_concise_and_visually_distinct(self):
        pages = (
            ("galleries:client_galleries", "dpp-gallery", "dpg-frames", "Turn a finished shoot"),
            ("ai_engine:photo_search", "dpp-search", "dps-radar", "Skip the scroll"),
            ("photographers:websites", "dpp-websites", "dpw-canvas", "your work feels"),
            ("clients:for_clients", "dpp-clients", "dpc-memory", "Without the work"),
            ("marketplace:find_photographer", "dpp-market", "dpm-search", "sees it your way"),
        )

        for url_name, page_class, signature_class, headline in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, page_class)
                self.assertContains(response, signature_class)
                self.assertContains(response, headline)
                self.assertContains(response, reverse("core:products"))
                self.assertContains(response, "dpp-back")
                self.assertContains(response, "css/product_deep_diverse.")
                self.assertNotContains(response, "Frequently Asked Questions")
                self.assertNotContains(response, "Placeholder testimonial")
                self.assertNotContains(response, "Looking Ahead")

    def test_light_product_heroes_use_navbar_safe_return_controls(self):
        for url_name in (
            "galleries:client_galleries",
            "photographers:websites",
            "clients:for_clients",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, 'class="dpp-back"')
                self.assertContains(response, "css/product_deep_diverse.")


class BusinessHubOverviewTests(TestCase):
    def test_business_hub_uses_condensed_tool_overview(self):
        response = self.client.get(reverse("core:business_hub"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "business_hub.html")
        self.assertContains(response, "The business moves")
        self.assertContains(response, "The complete business layer")
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
        self.assertContains(response, f'<li class="menu-item"><a href="{reverse("core:business_hub")}">Business Hub</a></li>', html=True)
        self.assertNotContains(response, f'<a href="{reverse("core:business_hub")}" aria-haspopup="true">Business Hub</a>', html=True)


class BusinessHubDeepDiveTests(TestCase):
    def test_each_business_hub_page_is_concise_and_returns_to_overview(self):
        pages = (
            ("core:business_hub_dashboard", "dashboard", "See the whole business"),
            ("core:business_hub_client_crm", "crm", "Know every client"),
            ("core:business_hub_booking_calendar", "calendar", "Make time visible"),
            ("core:business_hub_ai_business_assistant", "assistant", "Think with context"),
            ("core:business_hub_contracts", "contracts", "Set expectations"),
            ("core:business_hub_invoices_payments", "payments", "Make payment clear"),
            ("core:business_hub_workflow_automation", "automation", "Repeat the standard"),
            ("core:business_hub_analytics_reports", "analytics", "See the pattern"),
            ("core:business_hub_marketing_growth", "marketing", "Create attention"),
            ("core:business_hub_team_operations", "team", "Give everyone clarity"),
        )
        for route_name, theme, headline in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"bhd--{theme}")
                self.assertContains(response, headline)
                self.assertContains(response, 'class="bhd-back"')
                self.assertContains(response, "All Business Hub")
                self.assertContains(response, reverse("core:business_hub"))
                self.assertContains(response, "css/business_hub_concise.")
                self.assertNotContains(response, "Testimonials")


class LearningHubNavigationTests(TestCase):
    def test_learning_hub_route_renders_marketing_template(self):
        learning_hub_url = reverse("core:resources_learning_hub")

        self.assertEqual(learning_hub_url, "/resources/learning-hub/")
        response = self.client.get(learning_hub_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "resources_learning_hub.html")

    def test_marketing_navbar_links_to_learning_hub(self):
        response = self.client.get(reverse("core:index"))
        learning_hub_link = (
            f'<a href="{reverse("core:resources_learning_hub")}">'
            "Newsletter / Learning Hub</a>"
        )

        self.assertContains(response, learning_hub_link, html=True)
        self.assertNotContains(
            response,
            f'<a href="{reverse("core:resources_newsletter")}">'
            "Newsletter / Learning Hub</a>",
            html=True,
        )

    def test_resources_card_links_to_learning_hub(self):
        response = self.client.get(reverse("core:resources"))

        self.assertContains(
            response,
            f'href="{reverse("core:resources_learning_hub")}"',
        )


class BusinessGuidesNavigationTests(TestCase):
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
        self.assertContains(
            response,
            "Learn pricing, marketing, finance, workflows, and studio operations.",
        )

    def test_public_marketing_navbar_uses_resources_overview_without_child_dropdown(self):
        public_pages = (
            "core:index",
            "core:resources",
            "core:resources_learning_hub",
            "core:resources_release_notes",
            "core:resources_success_stories",
            "core:products",
            "core:solutions",
            "core:business_hub",
            "core:pricing",
        )

        for route_name in public_pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'href="{reverse("core:resources")}"')
                self.assertNotContains(response, 'href="/resources/" aria-haspopup="true"')
