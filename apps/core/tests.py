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
        self.assertContains(response, "lp-photo-page-heading")
        self.assertContains(response, "Photography is hard enough")
        self.assertContains(response, "One Platform")
        self.assertContains(response, "Core platform")
        self.assertContains(response, "AI throughout LumisPixel")
        self.assertContains(response, "A day in the life")
        self.assertContains(response, "Replace Tools With One Workflow")
        self.assertContains(response, "Built for every photographer")
        self.assertContains(response, "Our vision")
        self.assertContains(response, "Photographer notes")
        self.assertContains(response, "Ready to Simplify Your Studio")
        self.assertContains(response, "Questions Before Switching")
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
