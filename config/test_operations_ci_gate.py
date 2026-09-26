from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "p2-operations-reliability.yml"


class OperationsCIGateContractTests(SimpleTestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_gate_runs_on_dev_pull_requests_and_pushes(self):
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("push:", self.workflow)
        self.assertGreaterEqual(self.workflow.count("branches: [dev]"), 2)

    def test_gate_cannot_silently_drop_critical_operational_contracts(self):
        required = (
            "config.test_deployment_health",
            "apps.core.test_operations_observability",
            "config.test_reliability_failure_isolation",
            "apps.galleries.test_recovery_degraded",
            "apps.core.test_database_restore_verification",
            "apps.core.test_deployment_preflight",
            "config.test_celery_reliability",
            "config.test_production_configuration",
        )
        for contract in required:
            with self.subTest(contract=contract):
                self.assertIn(contract, self.workflow)

    def test_gate_uses_real_postgresql_for_migration_and_restore_checks(self):
        self.assertIn("image: postgres:16", self.workflow)
        self.assertIn("python manage.py migrate --noinput", self.workflow)
        self.assertIn("python manage.py makemigrations --check --dry-run", self.workflow)
        self.assertIn("python manage.py deployment_preflight", self.workflow)
        self.assertIn("python manage.py verify_database_restore", self.workflow)

    def test_gate_does_not_cancel_in_progress_operational_checks(self):
        self.assertIn("cancel-in-progress: false", self.workflow)
