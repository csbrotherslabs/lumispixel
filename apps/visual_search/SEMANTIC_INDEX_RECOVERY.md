# Semantic indexing recovery

Semantic photo indexing is consent-gated and writes embeddings only after an authorized upload completes. If Redis or a worker is unavailable at dispatch time, the database job can remain pending.

## Recovery

A new Celery task, `apps.visual_search.semantic_tasks.reconcile_semantic_jobs`, calls the existing Django reconciliation command every ten minutes **when enabled**. The command redelivers only jobs that are at least ten minutes old and still pending/failed, with active gallery authorization and no gallery archive/deletion. It skips `processing` jobs to avoid competing with live GPU inference. Photo source and consent are revalidated inside the indexing task before any vector write.

This is an **at-least-once** repair mechanism, not exactly-once delivery. Duplicate messages remain possible; indexing is designed to be idempotent. Long-running processing jobs are deliberately not automatically reset: investigate them separately before a controlled retry.

## Local commands

Preview eligible jobs (no dispatch):

```cmd
python manage.py reconcile_semantic_index --dry-run
```

Recover up to 100 aged jobs:

```cmd
python manage.py reconcile_semantic_index --limit 100 --min-age-minutes 10
```

Start one Windows worker:

```cmd
python -m celery -A config worker --pool=solo --concurrency=1 -n semantic_worker@%h --loglevel=INFO
```

## Scheduling

Set `SEMANTIC_INDEX_RECONCILIATION_ENABLED=True` in the **Beat** environment and run exactly one monitored Celery Beat instance:

```cmd
python -m celery -A config beat --loglevel=INFO
```

A worker must also be running. Do not run multiple Beat instances for the same deployment. The scheduler is off by default, and no production infrastructure is changed by this PR.

## Verification

Run Django tests, then upload an authorized photo and verify the job reaches `completed` and is searchable. Stop the worker during a test upload, confirm a pending job, restart it, and verify the scheduled recovery task eventually dispatches the job. Confirm revocation prevents indexing. Monitor old `processing` jobs and task failures; these are intentionally not automatically replayed.
