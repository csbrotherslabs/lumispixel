"""Exercise Celery's actual router without a broker, models, or database."""
import importlib.util
from pathlib import Path
import unittest

from celery import Celery

spec = importlib.util.spec_from_file_location(
    "ai_task_routing", Path(__file__).with_name("ai_task_routing.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AIQueueRoutingTests(unittest.TestCase):
    def route(self, task, enabled=True):
        app = Celery("routing-test", broker="memory://", set_as_current=False)
        self.addCleanup(app.close)
        app.conf.task_routes = module.ai_task_routes(enabled)
        return app.amqp.router.route({}, task)["queue"].name

    def test_semantic_index_and_deletion_use_semantic_queue(self):
        for task in ("index_semantic_photo", "index_semantic_gallery",
                     "purge_semantic_photo", "purge_semantic_gallery"):
            with self.subTest(task=task):
                self.assertEqual(self.route("apps.visual_search.semantic_tasks." + task), "ai.semantic")

    def test_face_index_reconciliation_and_deletion_use_face_queue(self):
        for task in ("process_face_index_job", "reconcile_face_index",
                     "process_vector_purge", "reconcile_vector_purges",
                     "retry_pending_face_deletions"):
            with self.subTest(task=task):
                self.assertEqual(self.route("apps.visual_search.tasks." + task), "ai.face")

    def test_ordinary_jobs_keep_default_queue(self):
        self.assertEqual(self.route("apps.notifications.tasks.send_email"), "celery")

    def test_disabled_routing_preserves_existing_workers(self):
        self.assertEqual(self.route("apps.visual_search.semantic_tasks.index_semantic_photo", False), "celery")
