#!/usr/bin/env python3
"""Fail CI when LumisPixel's required PR-to-dev gates are weakened or removed."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    file_path = ROOT / path
    if not file_path.exists():
        raise AssertionError(f"Required CI file is missing: {path}")
    return file_path.read_text(encoding="utf-8")


def require(text, needles, label):
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{label} is missing required contract markers: {missing}")


def main():
    django = read(".github/workflows/django-tests.yml")
    operations = read(".github/workflows/p2-operations-reliability.yml")
    contract = read(".github/workflows/required-ci-contract.yml")

    require(django, [
        "pull_request:",
        "- dev",
        "Run Django system checks",
        "python manage.py check",
        "makemigrations --check --dry-run",
        "Run Django test suite",
        "python manage.py test --verbosity 2",
        "postgres:16",
        "Run critical customer workflows on PostgreSQL",
        "apps.galleries.test_critical_workflows",
        "Run full Django suite on PostgreSQL",
        "P3 Playwright Chromium golden paths",
        "test_delivery_golden_path.py",
        "test_client_permission_browser_matrix.py",
    ], "Django CI")

    require(operations, [
        "pull_request:",
        "branches: [dev]",
        "Health, recovery and production contracts",
        "PostgreSQL migration and restore gate",
        "postgres:16",
        "deployment_preflight",
        "verify_database_restore",
    ], "Operations reliability CI")

    require(contract, [
        "name: Production Readiness",
        "pull_request:",
        "branches: [dev]",
        "name: Required CI Contract",
        "Verify required CI definition",
        "python scripts/verify_required_ci_contract.py",
        "Django CI / Django tests (fast SQLite feedback)",
        "Django CI / PostgreSQL 16 first-class test suite",
        "Django CI / P3 Playwright Chromium golden paths",
        "P2 Operations Reliability Gate / Health, recovery and production contracts",
        "P2 Operations Reliability Gate / PostgreSQL migration and restore gate",
    ], "Required CI contract")

    print("Required CI contract is intact.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"CI CONTRACT VIOLATION: {exc}", file=sys.stderr)
        raise SystemExit(1)
