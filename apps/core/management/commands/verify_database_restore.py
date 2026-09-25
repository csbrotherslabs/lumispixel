"""Verify that a restored PostgreSQL database is structurally usable by LumisPixel."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


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

        required_tables = {
            "accounts_user",
            "accounts_photographerprofile",
            "clients_client",
            "galleries_gallery",
            "galleries_galleryphoto",
            "galleries_galleryinvitation",
        }
        existing = set(connection.introspection.table_names())
        missing = sorted(required_tables - existing)
        if missing:
            raise CommandError("Restored database is missing required tables: " + ", ".join(missing))

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise CommandError("PostgreSQL restore health query failed.")

        self.stdout.write(self.style.SUCCESS(
            "Restore verification passed: PostgreSQL is reachable, migrations are current, and core tables exist."
        ))
