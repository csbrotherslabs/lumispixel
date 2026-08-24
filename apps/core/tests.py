from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse

from . import views


class AboutPageTests(TestCase):
    def test_about_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "about.html")
        self.assertContains(response, "Built for Modern Photography")
        self.assertContains(response, "Why LumisPixel")
        self.assertContains(response, "10+")
        self.assertContains(response, "Ready to simplify your photography business?")
        self.assertContains(response, reverse("core:pricing"))
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
        self.assertContains(response, "static/css/privacy-policy.css")


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
        self.assertContains(response, "static/css/cookie-policy.css")


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
        self.assertContains(response, "static/css/accessibility.css")


class CareersPageTests(TestCase):
    def test_careers_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:careers"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "careers.html")
        self.assertContains(response, "Why Work With Us")
        self.assertContains(response, "Our Values")
        self.assertContains(response, "Open Positions")
        self.assertContains(response, "Full Stack Software Engineer")
        self.assertContains(response, '<i class="bi bi-geo-alt" aria-hidden="true"></i> Remote', count=3)
        self.assertContains(response, '<i class="bi bi-clock" aria-hidden="true"></i> Full-Time', count=3)
        self.assertContains(response, "Don't See the Right Role?")
        self.assertContains(response, "static/css/careers.css")


class PartnersPageTests(TestCase):
    def test_partners_page_uses_dedicated_marketing_layout(self):
        response = self.client.get(reverse("core:partners"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partners.html")
        self.assertContains(response, "Partnership Opportunities")
        self.assertContains(response, "Why Partner With LumisPixel")
        self.assertContains(response, "How It Works")
        self.assertContains(response, "Partner FAQ")
        self.assertContains(response, "Let's Grow Together")
        self.assertContains(response, "static/css/partners.css")


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


class SolutionsOverviewTests(TestCase):
    def test_solutions_page_uses_condensed_specialty_overview(self):
        response = self.client.get(reverse("core:solutions"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "solutions.html")
        self.assertContains(response, "Different shoots")
        self.assertContains(response, "Ten specialties")
        self.assertContains(response, "Find your way of working")
        self.assertContains(response, "css/solutions_concise.")

        routes = (
            "core:solution_wedding_photography",
            "core:solution_portrait_photography",
            "core:solution_sports_photography",
            "core:solution_school_photography",
            "core:solution_corporate_photography",
            "core:solution_event_photography",
            "core:solution_real_estate_photography",
            "core:solution_commercial_photography",
            "core:solution_studio_photography",
            "core:solution_destination_photography",
        )
        for route_name in routes:
            with self.subTest(route_name=route_name):
                self.assertContains(response, reverse(route_name))

    def test_primary_navigation_links_directly_to_solutions_overview(self):
        response = self.client.get(reverse("core:index"))

        self.assertContains(
            response,
            f'<li class="menu-item"><a href="{reverse("core:solutions")}">Solutions</a></li>',
            html=True,
        )
        self.assertNotContains(
            response,
            f'<a href="{reverse("core:solutions")}" aria-haspopup="true">Solutions</a>',
            html=True,
        )


class SolutionDeepDiveTests(TestCase):
    def test_each_solution_is_concise_distinct_and_returns_to_overview(self):
        pages = (
            ("core:solution_wedding_photography", "wedding", "Hold the whole day"),
            ("core:solution_portrait_photography", "portrait", "Make room for the person"),
            ("core:solution_sports_photography", "sports", "Catch the action"),
            ("core:solution_school_photography", "school", "Every student matters"),
            ("core:solution_corporate_photography", "corporate", "Meet the brief"),
            ("core:solution_event_photography", "event", "Cover the room"),
            ("core:solution_real_estate_photography", "real-estate", "Make every property"),
            ("core:solution_commercial_photography", "commercial", "Protect the idea"),
            ("core:solution_studio_photography", "studio", "Every session enters"),
            ("core:solution_destination_photography", "destination", "Follow the story"),
        )

        for route_name, theme, headline in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"sol-detail--{theme}")
                self.assertContains(response, headline)
                self.assertContains(response, 'class="sol-back"')
                self.assertContains(response, "All Solutions")
                self.assertContains(response, reverse("core:solutions"))
                self.assertContains(response, "css/solutions_concise.")
                self.assertNotContains(response, "Frequently Asked Questions")
                self.assertNotContains(response, "Testimonials")
                self.assertNotContains(response, "Placeholder")


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

    def test_public_marketing_navbar_links_to_business_guides_once(self):
        business_guides_link = (
            f'<a href="{reverse("core:resources_business_guides")}">'
            "Business Guides</a>"
        )
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
                self.assertContains(response, business_guides_link, count=1, html=True)


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
