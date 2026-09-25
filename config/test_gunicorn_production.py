import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


def load_config():
    spec = importlib.util.spec_from_file_location("lumispixel_gunicorn_config", ROOT / "gunicorn.conf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GunicornProductionContractTests(SimpleTestCase):
    def test_procfile_uses_versioned_gunicorn_config(self):
        procfile = (ROOT / "Procfile").read_text(encoding="utf-8")
        self.assertIn("gunicorn config.wsgi:application --config gunicorn.conf.py", procfile)

    def test_resilience_defaults_are_bounded(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        self.assertEqual(config.worker_class, "gthread")
        self.assertGreaterEqual(config.workers, 1)
        self.assertGreaterEqual(config.threads, 1)
        self.assertLessEqual(config.timeout, 120)
        self.assertGreater(config.graceful_timeout, 0)
        self.assertGreater(config.max_requests, 0)
        self.assertGreater(config.max_requests_jitter, 0)
        self.assertFalse(config.preload_app)
        self.assertEqual(config.accesslog, "-")
        self.assertEqual(config.errorlog, "-")

    def test_request_limits_are_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        self.assertLessEqual(config.limit_request_line, 8190)
        self.assertLessEqual(config.limit_request_fields, 100)
        self.assertLessEqual(config.limit_request_field_size, 16384)

    def test_environment_can_tune_capacity_without_code_change(self):
        with patch.dict(os.environ, {"WEB_CONCURRENCY": "5", "GUNICORN_THREADS": "4"}, clear=True):
            config = load_config()
        self.assertEqual(config.workers, 5)
        self.assertEqual(config.threads, 4)
