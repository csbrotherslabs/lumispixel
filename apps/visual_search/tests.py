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
