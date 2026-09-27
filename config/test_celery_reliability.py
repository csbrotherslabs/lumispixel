from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.galleries.tasks import cleanup_gallery_storage_objects, cleanup_stale_gallery_multipart_uploads
from apps.workflows.tasks import execute_automation, scan_scheduled_automations


ROOT = Path(__file__).resolve().parents[1]


class CeleryReliabilityContractTests(SimpleTestCase):
    def test_worker_loss_redelivers_unacknowledged_tasks(self):
        self.assertTrue(settings.CELERY_TASK_ACKS_LATE)
        self.assertTrue(settings.CELERY_TASK_REJECT_ON_WORKER_LOST)
        self.assertFalse(settings.CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT)
        self.assertEqual(settings.CELERY_WORKER_PREFETCH_MULTIPLIER, 1)

    def test_broker_reconnect_and_visibility_are_bounded(self):
        self.assertTrue(settings.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP)
        self.assertTrue(settings.CELERY_BROKER_CONNECTION_RETRY)
        self.assertGreater(settings.CELERY_BROKER_TRANSPORT_OPTIONS["visibility_timeout"], settings.CELERY_TASK_TIME_LIMIT)

    def test_soft_limit_precedes_hard_limit(self):
        self.assertGreater(settings.CELERY_TASK_SOFT_TIME_LIMIT, 0)
        self.assertGreater(settings.CELERY_TASK_TIME_LIMIT, settings.CELERY_TASK_SOFT_TIME_LIMIT)

    def test_periodic_and_execution_tasks_have_bounded_retries(self):
        for task in (
            cleanup_gallery_storage_objects,
            cleanup_stale_gallery_multipart_uploads,
            execute_automation,
            scan_scheduled_automations,
        ):
            self.assertEqual(task.max_retries, 5)
            self.assertTrue(task.retry_backoff)

    def test_beat_runs_as_separate_process(self):
        procfile = (ROOT / "Procfile").read_text(encoding="utf-8")
        self.assertIn("worker: celery -A config worker", procfile)
        self.assertIn("beat: celery -A config beat", procfile)
        self.assertNotIn(" worker --beat", procfile)
