# Reliability CI gate

Run the targeted reliability gate before the full test suite:

```bash
python manage.py test config.test_reliability_gate --verbosity 2
```

The gate collects the failure-injection and invariant tests for:

- support transaction failure isolation;
- B2/network retry budgets and timeouts;
- Celery acknowledgement, retry, visibility, and worker/beat contracts;
- multipart completion idempotency;
- storage-deletion outage recovery, retry exhaustion, and durable reconciliation;
- stale multipart abort degradation;
- storage-deletion queue idempotency.

These tests also remain part of normal Django discovery. The dedicated command
exists so CI can fail quickly and so reliability guarantees cannot silently
disappear into the larger application suite.

A reliability change is not complete when only the happy path passes. New
external dependencies, background jobs, durable queues, counters, or
check-then-write flows should add a targeted failure-injection or concurrency
regression test and include it in this gate.
