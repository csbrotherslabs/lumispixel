from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.billing.models import PlanAllowance
from apps.billing.services import ensure_subscription
from apps.dashboard.access import StudioAccess
from apps.dashboard.models import StudioMembership
from apps.dashboard.storage_summary import build_storage_summary
from apps.galleries.models import Gallery


class StorageSummaryTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="storage@example.com", password="TestPass123!")
        self.studio = PhotographerProfile.objects.create(user=user)
        self.access = StudioAccess(self.studio, StudioMembership.Role.OWNER)

    def test_free_limit_and_actual_usage(self):
        Gallery.objects.create(photographer=self.studio, name="One", slug="one", storage_used=1024**3)
        data = build_storage_summary(self.access)
        self.assertEqual(data["limit"], "5 GB")
        self.assertEqual(data["used"], "1 GB")
        self.assertEqual(data["remaining"], "4 GB")
        self.assertEqual(data["percent"], 20)

    def test_over_limit_is_clamped(self):
        Gallery.objects.create(photographer=self.studio, name="One", slug="one", storage_used=6*1024**3)
        data = build_storage_summary(self.access)
        self.assertEqual(data["percent"], 100)
        self.assertEqual(data["remaining"], "0 bytes")
        self.assertTrue(data["full"])

    def test_custom_allowance_has_no_misleading_progress(self):
        subscription = ensure_subscription(self.studio)
        PlanAllowance.objects.filter(plan=subscription.plan, key="storage_bytes").update(limit_type="custom", value=None)
        data = build_storage_summary(self.access)
        self.assertEqual(data["limit_description"], "Custom storage allowance")
        self.assertNotIn("percent", data)

    def test_member_cannot_see_studio_wide_usage(self):
        self.assertIsNone(build_storage_summary(StudioAccess(self.studio, StudioMembership.Role.MANAGER, object())))
