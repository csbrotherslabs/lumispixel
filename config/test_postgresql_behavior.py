"""PostgreSQL-specific contracts that SQLite cannot faithfully exercise."""

from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.test import TransactionTestCase

from apps.accounts.models import PhotographerProfile, User
from apps.billing.models import Plan
from apps.galleries.models import Gallery


class PostgreSQLBehaviorTests(TransactionTestCase):
    """Exercise locking and transaction semantics on the production database engine."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("This contract intentionally runs only against PostgreSQL.")

        # The billing catalog is seeded by migrations. TransactionTestCase may
        # preserve that migrated reference data between tests, so make this fixture
        # idempotent: reuse the production free plan when present and recreate the
        # minimum required row only if a flush removed it.
        Plan.objects.get_or_create(
            code="free",
            defaults={
                "name": "Free",
                "is_active": True,
                "is_public": True,
                "customer_selectable": True,
            },
        )

        user = User.objects.create_user(
            email="postgres-contract@example.com", password="testpass"
        )
        owner = PhotographerProfile.objects.create(user=user, slug="postgres-contract")
        self.gallery = Gallery.objects.create(
            photographer=owner,
            name="PostgreSQL Contract",
            slug="postgres-contract",
        )

    def test_select_for_update_requires_an_explicit_transaction(self):
        with self.assertRaises(TransactionManagementError):
            Gallery.objects.select_for_update().get(pk=self.gallery.pk)

    def test_select_for_update_succeeds_inside_atomic_transaction(self):
        with transaction.atomic():
            locked = Gallery.objects.select_for_update().get(pk=self.gallery.pk)
            self.assertEqual(locked.pk, self.gallery.pk)

    def test_database_reports_postgresql_16(self):
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            version = int(cursor.fetchone()[0])
        self.assertGreaterEqual(version, 160000)
        self.assertLess(version, 170000)
