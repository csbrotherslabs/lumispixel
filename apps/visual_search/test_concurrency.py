"""Real PostgreSQL concurrency checks using independent database sessions.

Uses ONLY VISUAL_SEARCH_INTEGRATION_DATABASE_URL, which must name a disposable
lumispixel_visual_search_test* database. Does not touch research embeddings.
These tests exercise PostgreSQL locking/fencing protocols, not a live Celery
broker or Django model lifecycle.
"""
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.test import SimpleTestCase


@unittest.skipUnless(
    os.environ.get("VISUAL_SEARCH_INTEGRATION_DATABASE_URL"),
    "Set VISUAL_SEARCH_INTEGRATION_DATABASE_URL to a disposable PostgreSQL test DB",
)
class PostgreSQLConcurrencyTests(SimpleTestCase):
    databases = set()

    def setUp(self):
        import psycopg
        self.psycopg = psycopg
        self.url = os.environ["VISUAL_SEARCH_INTEGRATION_DATABASE_URL"]
        with self.psycopg.connect(self.url, connect_timeout=10) as conn:
            db = conn.execute("SELECT current_database()").fetchone()[0]
            if not db.startswith("lumispixel_visual_search_test"):
                self.fail("Refusing concurrency tests on non-disposable database: " + db)
            conn.execute("""CREATE TABLE IF NOT EXISTS visual_search.concurrency_test_jobs (
                id uuid PRIMARY KEY, status text NOT NULL, claim_token uuid,
                consent boolean NOT NULL DEFAULT true, generation integer NOT NULL DEFAULT 0
            )""")
            self.job_id = uuid4()
            conn.execute(
                "INSERT INTO visual_search.concurrency_test_jobs (id,status) VALUES (%s,'pending')",
                (self.job_id,),
            )

    def tearDown(self):
        with self.psycopg.connect(self.url, connect_timeout=10) as conn:
            conn.execute("DELETE FROM visual_search.concurrency_test_jobs WHERE id=%s", (self.job_id,))

    def _claim(self):
        token = uuid4()
        with self.psycopg.connect(self.url, connect_timeout=10) as conn:
            with conn.transaction():
                row = conn.execute(
                    "SELECT status,consent FROM visual_search.concurrency_test_jobs WHERE id=%s FOR UPDATE",
                    (self.job_id,),
                ).fetchone()
                if row != ("pending", True):
                    return None
                conn.execute(
                    """UPDATE visual_search.concurrency_test_jobs
                       SET status='processing',claim_token=%s,generation=generation+1
                       WHERE id=%s""",
                    (token, self.job_id),
                )
        return token

    def test_two_connections_only_one_can_claim(self):
        barrier = threading.Barrier(2, timeout=10)
        def compete():
            barrier.wait()
            return self._claim()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: compete(), range(2)))
        self.assertEqual(sum(token is not None for token in results), 1)

    def test_stale_worker_token_cannot_finalize_reclaimed_job(self):
        old_token = self._claim()
        self.assertIsNotNone(old_token)
        with self.psycopg.connect(self.url, connect_timeout=10) as conn:
            conn.execute(
                """UPDATE visual_search.concurrency_test_jobs
                   SET status='pending',claim_token=NULL WHERE id=%s""",
                (self.job_id,),
            )
        new_token = self._claim()
        self.assertNotEqual(old_token, new_token)
        with self.psycopg.connect(self.url, connect_timeout=10) as conn:
            old = conn.execute(
                """UPDATE visual_search.concurrency_test_jobs SET status='completed'
                   WHERE id=%s AND status='processing' AND claim_token=%s RETURNING id""",
                (self.job_id, old_token),
            ).fetchone()
            self.assertIsNone(old)
            new = conn.execute(
                """UPDATE visual_search.concurrency_test_jobs SET status='completed'
                   WHERE id=%s AND status='processing' AND claim_token=%s RETURNING id""",
                (self.job_id, new_token),
            ).fetchone()
            self.assertIsNotNone(new)

    def test_revocation_blocks_worker_finalization(self):
        token = self._claim()
        self.assertIsNotNone(token)
        worker_ready = threading.Event()
        revocation_complete = threading.Event()
        errors = []
        def revoke():
            try:
                with self.psycopg.connect(self.url, connect_timeout=10) as conn:
                    worker_ready.wait(timeout=10)
                    with conn.transaction():
                        conn.execute(
                            """UPDATE visual_search.concurrency_test_jobs
                               SET consent=false,status='cancelled',claim_token=NULL
                               WHERE id=%s""",
                            (self.job_id,),
                        )
                revocation_complete.set()
            except Exception as exc:
                errors.append(exc)
                revocation_complete.set()
        thread = threading.Thread(target=revoke)
        thread.start()
        try:
            worker_ready.set()
            self.assertTrue(revocation_complete.wait(timeout=15))
            if errors:
                raise errors[0]
            with self.psycopg.connect(self.url, connect_timeout=10) as conn:
                result = conn.execute(
                    """UPDATE visual_search.concurrency_test_jobs SET status='completed'
                       WHERE id=%s AND status='processing' AND claim_token=%s AND consent=true
                       RETURNING id""",
                    (self.job_id, token),
                ).fetchone()
                self.assertIsNone(result)
                status, consent = conn.execute(
                    "SELECT status,consent FROM visual_search.concurrency_test_jobs WHERE id=%s",
                    (self.job_id,),
                ).fetchone()
                self.assertEqual((status, consent), ("cancelled", False))
        finally:
            thread.join(timeout=15)
