from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class VerifyDatabaseRestoreCommandTests(SimpleTestCase):
    @patch("apps.core.management.commands.verify_database_restore.connection")
    def test_rejects_non_postgresql_database(self, connection):
        connection.vendor = "sqlite"
        with self.assertRaisesMessage(CommandError, "must run against PostgreSQL"):
            call_command("verify_database_restore")

    @patch("apps.core.management.commands.verify_database_restore.MigrationExecutor")
    @patch("apps.core.management.commands.verify_database_restore.connection")
    def test_rejects_pending_migrations(self, connection, executor_cls):
        connection.vendor = "postgresql"
        migration = type("Migration", (), {"app_label": "galleries", "name": "9999_pending"})()
        executor = executor_cls.return_value
        executor.loader.graph.leaf_nodes.return_value = [("galleries", "9999_pending")]
        executor.migration_plan.return_value = [(migration, False)]
        with self.assertRaisesMessage(CommandError, "unapplied migrations"):
            call_command("verify_database_restore")

    @patch("apps.core.management.commands.verify_database_restore.MigrationExecutor")
    @patch("apps.core.management.commands.verify_database_restore.connection")
    def test_accepts_current_restore_with_core_tables(self, connection, executor_cls):
        connection.vendor = "postgresql"
        executor = executor_cls.return_value
        executor.loader.graph.leaf_nodes.return_value = []
        executor.migration_plan.return_value = []
        connection.introspection.table_names.return_value = [
            "accounts_user", "accounts_photographerprofile", "clients_client",
            "galleries_gallery", "galleries_galleryphoto", "galleries_galleryinvitation",
        ]
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        output = StringIO()
        call_command("verify_database_restore", stdout=output)
        self.assertIn("Restore verification passed", output.getvalue())
