"""Tests for default-off, owner-scoped AI Photo Discovery controls."""
import json
from unittest.mock import patch
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
