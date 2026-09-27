"""Fail fast on unsafe deployment conditions before production traffic changes."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Verify database reachability and migration state before/after deployment."

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise CommandError("Database preflight query failed.")
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError("Database is unavailable for deployment preflight.") from exc

        executor = MigrationExecutor(connection)
        leaf_nodes = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(leaf_nodes)
        if plan:
            pending = ", ".join(
                f"{migration.app_label}.{migration.name}"
                for migration, backwards in plan[:20]
                if not backwards
            )
            if pending:
                raise CommandError(f"Deployment has unapplied migrations: {pending}")

        self.stdout.write(self.style.SUCCESS(
            "Deployment preflight passed: database reachable and migrations current."
        ))
