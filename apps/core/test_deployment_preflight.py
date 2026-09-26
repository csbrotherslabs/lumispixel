from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class DeploymentPreflightTests(SimpleTestCase):
    @patch("apps.core.management.commands.deployment_preflight.MigrationExecutor")
    @patch("apps.core.management.commands.deployment_preflight.connection")
    def test_passes_when_database_and_migrations_are_current(self, connection, executor_cls):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        executor = executor_cls.return_value
        executor.loader.graph.leaf_nodes.return_value = []
        executor.migration_plan.return_value = []
        output = StringIO()

        call_command("deployment_preflight", stdout=output)

        self.assertIn("Deployment preflight passed", output.getvalue())

    @patch("apps.core.management.commands.deployment_preflight.connection")
    def test_fails_closed_when_database_is_unavailable(self, connection):
        connection.cursor.side_effect = RuntimeError("database outage")

        with self.assertRaisesMessage(CommandError, "Database is unavailable"):
            call_command("deployment_preflight")

    @patch("apps.core.management.commands.deployment_preflight.MigrationExecutor")
    @patch("apps.core.management.commands.deployment_preflight.connection")
    def test_fails_when_migrations_are_pending(self, connection, executor_cls):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        migration = type("Migration", (), {"app_label": "galleries", "name": "0042_release"})()
        executor = executor_cls.return_value
        executor.loader.graph.leaf_nodes.return_value = [("galleries", "0042_release")]
        executor.migration_plan.return_value = [(migration, False)]

        with self.assertRaisesMessage(CommandError, "unapplied migrations"):
            call_command("deployment_preflight")
