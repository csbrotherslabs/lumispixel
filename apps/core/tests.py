from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class ForPhotographersRoutingTests(TestCase):
    def test_named_url_resolves_to_public_marketing_page(self):
        self.assertEqual(reverse("core:for_photographers"), "/for-photographers/")

        response = self.client.get(reverse("core:for_photographers"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "for_photographers.html")
        self.assertContains(response, "lp-photo-hero")
        self.assertContains(response, "Photography is hard enough")
        self.assertContains(response, "One Platform")
        self.assertContains(response, "Core platform")
        self.assertContains(response, "AI throughout LumisPixel")
        self.assertContains(response, "A day in the life")
        self.assertContains(response, "Replace disconnected tools")
        self.assertContains(response, "Built for every photographer")
        self.assertContains(response, "Our vision")
        self.assertContains(response, "Photographer notes")
        self.assertContains(response, "Ready to transform your photography business")
        self.assertContains(response, "Questions photographers ask before switching")
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
