import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("email_architecture", Path(__file__).resolve().parents[1] / "check_email_architecture.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

class GuardTests(unittest.TestCase):
    def test_direct_import_rejected(self):
        self.assertTrue(guard.violations("from django.core.mail import send_mail as send", "apps/example.py"))
    def test_smtp_module_rejected(self):
        self.assertTrue(guard.violations("import smtplib as smtp", "apps/example.py"))
    def test_adapter_allowed(self):
        self.assertFalse(guard.violations("from django.core.mail import EmailMessage", "apps/notifications/email_delivery.py"))
    def test_queue_allowed(self):
        self.assertFalse(guard.violations("from apps.notifications.email_delivery import queue_transactional_email", "apps/example.py"))
