"""Tests for default-off, owner-scoped AI Photo Discovery controls."""
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.visual_search.models import GallerySemanticSearchPolicy

class SemanticPolicyDefaultsTests(TestCase):
    def test_default_off(self):
        field=GallerySemanticSearchPolicy._meta.get_field("processing_authorized")
        self.assertIs(field.get_default(),False)

    def test_biometric_policy_is_independent(self):
        from apps.visual_search.models import GalleryFaceSearchPolicy
        self.assertIs(GalleryFaceSearchPolicy._meta.get_field("processing_authorized").get_default(),False)

    @override_settings(VISUAL_SEARCH_SEMANTIC_ENABLED=False)
    def test_semantic_processing_disabled_by_default(self):
        from apps.visual_search.semantic import semantic_enabled
        self.assertFalse(semantic_enabled())

    def test_semantic_routes_exist(self):
        self.assertTrue(reverse("visual_search:ai-discovery-settings",args=[1]).endswith("/galleries/1/ai-discovery/"))
        self.assertTrue(reverse("visual_search:semantic-search",args=[1]).endswith("/galleries/1/semantic-search/"))

    def test_client_search_does_not_use_owner_only_endpoint(self):
        from django.urls import resolve
        self.assertEqual(resolve(reverse("visual_search:public-semantic-search",args=["00000000-0000-0000-0000-000000000001"])).url_name,"public-semantic-search")
        self.assertEqual(resolve(reverse("visual_search:invited-semantic-search",args=["test-token"])).url_name,"invited-semantic-search")

    def test_unauthorized_client_search_is_not_disclosed(self):
        from django.http import Http404
        from apps.visual_search.semantic_api import public_semantic_search
        from django.test import RequestFactory
        with self.assertRaises(Http404):
            public_semantic_search(RequestFactory().get("/?q=first+dance"),"00000000-0000-0000-0000-000000000001")

    def test_unapproved_semantic_model_fails_closed(self):
        from apps.visual_search.semantic_tasks import schedule_semantic_photo
        with override_settings(VISUAL_SEARCH_SEMANTIC_ENABLED=False,VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=False):
            self.assertIsNone(schedule_semantic_photo(123456789))
