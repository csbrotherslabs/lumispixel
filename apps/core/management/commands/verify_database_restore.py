"""Verify that a restored PostgreSQL database is structurally usable by LumisPixel."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


REQUIRED_TABLES = {
    "accounts_user",
    "accounts_photographerprofile",
    "clients_client",
    "galleries_gallery",
    "galleries_galleryphoto",
    "galleries_galleryinvitation",
}

# Foreign-key checks deliberately use SQL rather than importing application models.
# This keeps the verifier useful even when a partially restored database would make
# normal ORM traversal unsafe.
RELATIONSHIP_CHECKS = (
    (
        "gallery owner references",
        """
        SELECT COUNT(*)
        FROM galleries_gallery g
        LEFT JOIN accounts_photographerprofile p ON p.id = g.photographer_id
        WHERE g.photographer_id IS NOT NULL AND p.id IS NULL
        """,
    ),
    (
        "gallery photo references",
        """
        SELECT COUNT(*)
        FROM galleries_galleryphoto gp
        LEFT JOIN galleries_gallery g ON g.id = gp.gallery_id
        WHERE gp.gallery_id IS NOT NULL AND g.id IS NULL
        """,
    ),
    (
        "gallery invitation references",
        """
        SELECT COUNT(*)
        FROM galleries_galleryinvitation gi
        LEFT JOIN galleries_gallery g ON g.id = gi.gallery_id
        WHERE gi.gallery_id IS NOT NULL AND g.id IS NULL
        """,
    ),
)


class Command(BaseCommand):
    help = "Verify an isolated restored PostgreSQL database before it is accepted as recovery-ready."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Restore verification must run against PostgreSQL.")

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            pending = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _ in plan[:10])
            raise CommandError(f"Restored database has unapplied migrations: {pending}")

        existing = set(connection.introspection.table_names())
        missing = sorted(REQUIRED_TABLES - existing)
        if missing:
            raise CommandError("Restored database is missing required tables: " + ", ".join(missing))

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise CommandError("PostgreSQL restore health query failed.")

            for label, query in RELATIONSHIP_CHECKS:
                cursor.execute(query)
                result = cursor.fetchone()
                broken = result[0] if result else None
                if broken is None:
                    raise CommandError(f"Restore integrity check could not verify {label}.")
                if broken:
                    raise CommandError(
                        f"Restore integrity check failed: {broken} broken {label}."
                    )

        self.stdout.write(self.style.SUCCESS(
            "Restore verification passed: PostgreSQL is reachable, migrations are current, "
            "core tables exist, and critical gallery relationships are intact."
        ))
