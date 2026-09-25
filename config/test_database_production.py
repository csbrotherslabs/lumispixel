"""Production database contract tests.

These tests are intentionally database-backend aware. CI runs them against PostgreSQL
so SQLite cannot hide PostgreSQL-specific migration or constraint behavior.
"""
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from apps.accounts.models import PhotographerProfile, User
from apps.galleries.models import Gallery


class ProductionDatabaseContractTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="db-contract@example.com", password="testpass")
        self.owner = PhotographerProfile.objects.create(user=user, slug="db-contract")

    def test_gallery_owner_slug_uniqueness_is_database_enforced(self):
        Gallery.objects.create(photographer=self.owner, name="One", slug="same")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Gallery.objects.create(photographer=self.owner, name="Two", slug="same")

    def test_gallery_expiry_constraint_is_database_enforced(self):
        from django.utils import timezone
        now = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Gallery.objects.create(
                    photographer=self.owner, name="Invalid", slug="invalid",
                    published_at=now, expires_at=now,
                )

    def test_database_connections_have_health_checks_enabled(self):
        self.assertTrue(settings.DATABASES["default"].get("CONN_HEALTH_CHECKS"))
