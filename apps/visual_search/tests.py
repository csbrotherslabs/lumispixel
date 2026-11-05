from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.visual_search.models import FaceIndexJob
from apps.visual_search.services import schedule_face_indexing


class SchedulingSafetyTests(TestCase):
    @override_settings(VISUAL_SEARCH_FACE_INDEXING_ENABLED=False)
    def test_feature_flag_prevents_scheduling(self):
        with patch("apps.visual_search.services.GalleryPhoto.objects") as photos:
            self.assertIsNone(schedule_face_indexing(123))
            photos.select_related.assert_not_called()
        self.assertEqual(FaceIndexJob.objects.count(), 0)

    @override_settings(VISUAL_SEARCH_FACE_INDEXING_ENABLED=True)
    def test_nonexistent_photo_does_not_schedule(self):
        self.assertIsNone(schedule_face_indexing(999999999))
        self.assertEqual(FaceIndexJob.objects.count(), 0)


class ConsentInvariantTests(TestCase):
    def test_discovery_cleared_when_processing_not_authorized(self):
        from apps.visual_search.models import GalleryFaceSearchPolicy
        from apps.visual_search.signals import discovery_requires_consent

        policy = GalleryFaceSearchPolicy(
            processing_authorized=False,
            global_discovery_enabled=True,
        )
        discovery_requires_consent(
            sender=GalleryFaceSearchPolicy, instance=policy
        )
        self.assertFalse(policy.global_discovery_enabled)

    @override_settings(VISUAL_SEARCH_DATABASE_URL="")
    def test_reconciliation_skips_unconfigured_database(self):
        from apps.visual_search.tasks import reconcile_face_index
        self.assertEqual(reconcile_face_index.run(), "not_configured")


class ConsentPersistenceTests(TestCase):
    def setUp(self):
        from uuid import uuid4
        from django.contrib.auth import get_user_model
        from apps.accounts.models import PhotographerProfile
        from apps.billing.models import Plan
        from apps.galleries.models import Gallery
        from apps.visual_search.models import GalleryFaceSearchPolicy

        Plan.objects.get_or_create(code="free", defaults={"name": "Free", "is_active": True})
        user = get_user_model().objects.create(email=f"consent-{uuid4().hex}@example.test")
        photographer = PhotographerProfile.objects.create(user=user, slug=f"consent-{uuid4().hex}")
        gallery = Gallery.objects.create(
            photographer=photographer, name="Consent test", slug=f"consent-{uuid4().hex}"
        )
        self.policy = GalleryFaceSearchPolicy.objects.create(
            gallery=gallery, processing_authorized=True, global_discovery_enabled=True
        )

    def test_partial_save_revocation_also_clears_discovery(self):
        from apps.visual_search.models import GalleryFaceSearchPolicy
        with patch("apps.visual_search.purges.dispatch_purge"):
            self.policy.processing_authorized = False
            self.policy.save(update_fields=["processing_authorized"])
        self.policy.refresh_from_db()
        self.assertFalse(self.policy.processing_authorized)
        self.assertFalse(self.policy.global_discovery_enabled)

    def test_queryset_update_cannot_enable_discovery_without_consent(self):
        from django.db import IntegrityError, transaction
        from apps.visual_search.models import GalleryFaceSearchPolicy
        with patch("apps.visual_search.purges.dispatch_purge"):
            self.policy.processing_authorized = False
            self.policy.save(update_fields=["processing_authorized"])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GalleryFaceSearchPolicy.objects.filter(pk=self.policy.pk).update(
                    global_discovery_enabled=True
                )
        self.policy.refresh_from_db()
        self.assertFalse(self.policy.global_discovery_enabled)

    def test_queryset_cannot_bypass_revocation_signal(self):
        from apps.visual_search.models import GalleryFaceSearchPolicy
        with self.assertRaisesMessage(ValueError, "Use GalleryFaceSearchPolicy.save()"):
            GalleryFaceSearchPolicy.objects.filter(pk=self.policy.pk).update(
                processing_authorized=False
            )
        self.policy.refresh_from_db()
        self.assertTrue(self.policy.processing_authorized)

    def test_bulk_update_cannot_bypass_revocation_signal(self):
        from apps.visual_search.models import GalleryFaceSearchPolicy
        self.policy.processing_authorized = False
        with self.assertRaisesMessage(ValueError, "Use GalleryFaceSearchPolicy.save()"):
            GalleryFaceSearchPolicy.objects.bulk_update(
                [self.policy], ["processing_authorized"]
            )
