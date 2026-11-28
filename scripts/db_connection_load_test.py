"""Run from repository root with the development environment activated."""
import argparse
import concurrent.futures
import csv
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connections

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    p.add_argument("--seconds", type=int, default=120, choices=range(10, 601))
    p.add_argument("--output", default="db-load-baseline.csv")
    a = p.parse_args()
    db = connections["default"]
    if not settings.DEBUG or db.vendor != "postgresql":
        p.error("Requires DEBUG and PostgreSQL database lumispixel_dev; never run on production.")
    try:
        with db.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != "lumispixel_dev":
                p.error("Refusing workload outside lumispixel_dev.")
    finally:
        db.close()
    deadline = time.monotonic() + a.seconds
    def worker(i):
        rows = []
        conn = connections["default"]
        try:
            while time.monotonic() < deadline:
                start = time.monotonic()
                error = ""
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = %s", ["public"])
                        cur.fetchone()
                except Exception as exc:
                    error = type(exc).__name__
                finally:
                    conn.close()
                rows.append((i, round(time.time(), 3), round((time.monotonic()-start)*1000, 2), error))
                time.sleep(0.5)
        finally:
            conn.close()
        return rows
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as executor:
        rows = [row for batch in executor.map(worker, range(a.workers)) for row in batch]
    with open(a.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["worker", "epoch", "elapsed_ms", "error_type"])
        writer.writerows(rows)
    good = sorted(r[2] for r in rows if not r[3])
    print("Attempts:", len(rows), "Errors:", len(rows)-len(good))
    if good:
        print("p50 ms:", good[int((len(good)-1)*.5)], "p95 ms:", good[int((len(good)-1)*.95)])
    print("CSV:", a.output)
    return int(not good or len(good) != len(rows))

if __name__ == "__main__":
    sys.exit(main())
