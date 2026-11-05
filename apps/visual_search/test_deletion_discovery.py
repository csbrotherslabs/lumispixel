from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ClientBiometricDeletionRequest,
    BiometricDeletionDiscoveryGrant,
)


class DeletionDiscoveryPermissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="erasure-discovery@example.test", password="test-password",
        )
        self.client.force_login(self.user)
        self.deletion = ClientBiometricDeletionRequest.objects.create(user=self.user)
        self.url = reverse("visual_search:deletion-discovery-permission")

    def test_discovery_is_separately_disabled_by_default(self):
        response = self.client.post(
            self.url,
            data='{"agree":true,"policy_version":"v1"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(BiometricDeletionDiscoveryGrant.objects.exists())

    @override_settings(
        VISUAL_SEARCH_DELETION_DISCOVERY_ENABLED=True,
        VISUAL_SEARCH_DELETION_DISCOVERY_LEGAL_APPROVED=True,
        VISUAL_SEARCH_DELETION_DISCOVERY_POLICY_VERSION="v1",
        VISUAL_SEARCH_DELETION_DISCOVERY_NOTICE_URL="https://example.test/notice",
    )
    def test_explicit_deletion_only_grant_and_withdrawal(self):
        response = self.client.post(
            self.url,
            data='{"agree":true,"policy_version":"v1"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.get(self.url).json()["authorized"])
        self.assertEqual(self.client.delete(self.url).status_code, 200)
        self.assertFalse(self.client.get(self.url).json()["authorized"])

    def test_other_user_cannot_view_grant(self):
        second = get_user_model().objects.create_user(
            email="erasure-other@example.test", password="test-password",
        )
        self.client.force_login(second)
        self.assertEqual(self.client.get(self.url).status_code, 404)
