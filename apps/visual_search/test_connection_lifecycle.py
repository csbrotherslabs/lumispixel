from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from .connection_lifecycle import release_inference_connection


class InferenceConnectionTests(SimpleTestCase):
    def check_release(self, *, connected=True, atomic=False, autocommit=True, expected=False):
        conn = Mock()
        conn.connection = object() if connected else None
        conn.in_atomic_block = atomic
        conn.get_autocommit.return_value = autocommit
        with patch("apps.visual_search.connection_lifecycle.connections", {"default": conn}):
            release_inference_connection()
        self.assertEqual(conn.close.called, expected)

    def test_idle_connection_is_closed(self):
        self.check_release(expected=True)

    def test_atomic_connection_is_preserved(self):
        self.check_release(atomic=True)

    def test_manual_transaction_is_preserved(self):
        self.check_release(autocommit=False)

    def test_disconnected_connection_is_ignored(self):
        self.check_release(connected=False)
