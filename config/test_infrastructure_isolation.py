from celery import Celery
from django.conf import settings
from django.test import SimpleTestCase, override_settings


class InfrastructureIsolationTests(SimpleTestCase):
    def test_regression_defaults(self):
        self.assertEqual(settings.CELERY_BROKER_URL, "memory://")
        self.assertEqual(settings.CELERY_RESULT_BACKEND, "cache+memory://")
        self.assertEqual(settings.USER_UPLOAD_STORAGE_BACKEND, "local")
        self.assertEqual(settings.GALLERY_STORAGE_BACKEND, "local")
        self.assertEqual(settings.VISUAL_SEARCH_DATABASE_URL, "")
        self.assertFalse(settings.BREVO_API_KEY)
        self.assertEqual(settings.EMAIL_BACKEND, "django.core.mail.backends.locmem.EmailBackend")
        self.assertEqual(settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.locmem.LocMemCache")

    def test_effective_routes(self):
        # Read the actual production route definition, even if local dedicated
        # queues are disabled. No broker connection is made.
        import inspect
        import ast
        from config import settings as base
        tree = ast.parse(inspect.getsource(base))
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "CELERY_TASK_ROUTES" for t in n.targets))
        routes = ast.literal_eval(assignment.value.body)
        app = Celery("routing-test", broker="memory://", set_as_current=False)
        try:
            app.conf.task_routes = routes
            expected = {
                "apps.automation.tasks.reconcile_jobs": "celery",
                "apps.automation.tasks.scan_due_jobs": "automation",
                "apps.automation.tasks.execute_job": "automation",
                "apps.notifications.tasks.reconcile_pending_transactional_emails": "celery",
                "apps.galleries.tasks.generate_gallery_photo_derivatives": "media",
                "apps.visual_search.semantic_tasks.index_semantic_photo": "visual_index",
            }
            for task, queue in expected.items():
                with self.subTest(task=task):
                    self.assertEqual(app.amqp.router.route({}, task)["queue"].name, queue)
        finally:
            app.close()
