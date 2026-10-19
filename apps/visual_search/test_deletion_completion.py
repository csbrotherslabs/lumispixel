"""Deletion completion is fail-closed without verified scope."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .deletion_service import try_complete_deletion
from .models import ClientBiometricDeletionRequest


class DeletionCompletionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="scope-requester@example.test", password="password",
        )
        self.item = ClientBiometricDeletionRequest.objects.create(user=self.user)

    def test_no_attestation_never_completes(self):
        self.assertFalse(try_complete_deletion(self.item.pk))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "pending")

    def test_non_staff_cannot_attest(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("visual_search:deletion-complete", args=[self.item.pk]),
            data='{"scope_verified":true,"scope_note":"Reviewed all linked galleries and known discovery candidates."}',
            content_type="application/json",
        )
        self.assertNotEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.scope_verified_at)

    def test_staff_attestation_requires_explicit_scope(self):
        staff = get_user_model().objects.create_user(
            email="scope-staff@example.test", password="password",
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        self.client.force_login(staff)
        response = self.client.post(
            reverse("visual_search:deletion-complete", args=[self.item.pk]),
            data='{"scope_verified":false,"scope_note":"Reviewed all linked galleries and known discovery candidates."}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("apps.visual_search.deletion_service.send_deletion_notice")
    def test_explicit_verified_empty_scope_can_close(self, notify):
        self.item.scope_verified_at = timezone.now()
        self.item.scope_verified_by = self.user
        self.item.resolution_note = "No known eligible galleries; staff verified the scope."
        self.item.save()
        self.assertTrue(try_complete_deletion(self.item.pk))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "completed")
