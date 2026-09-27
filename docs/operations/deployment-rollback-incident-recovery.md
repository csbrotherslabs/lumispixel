# LumisPixel Deployment Rollback & Incident Recovery

## Purpose

Keep a failed release or provider outage from becoming data loss or a prolonged full-site outage. The default response is: contain, preserve data, restore the last known-good service state, verify, then reconcile asynchronous work.

## Deployment safety contract

A release is healthy only after application startup, migrations, `/health/live/`, `/health/ready/`, representative authenticated requests, and worker processing are verified.

Before production deployment:

1. Record the exact currently deployed commit/release identifier.
2. Confirm a recent database recovery point exists before any schema-changing release.
3. Run `python manage.py migrate --plan` and review destructive/irreversible operations.
4. Prefer expand/contract migrations: add nullable/new structures first, deploy compatible code, backfill, then remove old structures in a later release.
5. Do not combine an irreversible destructive migration with code that requires the destroyed data in the same rollback window.
6. Static/media configuration changes must be independently reversible from application code.

## Failed deployment

If readiness, smoke checks, error rate, or core workflows fail immediately after deploy:

1. Stop further rollout.
2. Preserve logs and the failed release identifier.
3. If no incompatible database migration completed, redeploy the previous known-good application release.
4. Verify `/health/live/`, `/health/ready/`, login, dashboard and one representative gallery/client workflow.
5. Restart/verify Celery workers only after web/database compatibility is established.
6. Do not purge queues merely to make the system appear healthy.

## Migration failure / rollback safety

Migration rollback is a data operation, not simply a Git rollback.

- If migration failed before changing schema/data: correct the migration and redeploy.
- If an additive migration completed: old code may be redeployed only when it remains compatible with the new schema.
- If a destructive or data-transforming migration completed: do not blindly run reverse migration or old code. Put writes into maintenance/degraded mode, restore/reconcile from the pre-deploy recovery point when required, and follow the backup/restore runbook.
- Never fake a migration in production to clear an incident unless the actual database state has been independently verified.

## Dependency outage matrix

### PostgreSQL

Impact: application reads/writes are unsafe; readiness must fail.

Action: stop writes/traffic to affected application instances, preserve database state, use provider recovery/failover where configured, then run application restore/integrity verification before reopening traffic. Do not treat Redis or application restart as a database recovery mechanism.

### Redis / Celery broker

Impact: web requests that do not require queued work may remain usable, but asynchronous email, cleanup and background jobs cannot be trusted to enqueue/process normally.

Action: keep synchronous core workflows available where safe; fail queue-dependent operations explicitly or persist durable work for later dispatch. Do not lose business state because `.delay()` failed. After recovery, verify workers and reconcile durable pending work before declaring the incident resolved.

### Celery workers

Impact: broker may be healthy while jobs accumulate.

Action: do not fail web readiness solely because workers are temporarily absent unless the requested workflow requires synchronous completion. Restore workers, inspect queue depth/failures, then reconcile idempotent jobs. Never bulk replay non-idempotent jobs without duplicate-delivery analysis.

### Backblaze B2

Impact: gallery upload/download/original delivery and cleanup can degrade while database/CRM/account workflows may remain usable.

Action: disable or fail media operations cleanly; never convert a provider failure into database deletion success. Preserve pending deletion/upload/recovery state. When B2 returns, reconcile multipart uploads, pending deletions and delivery state before resuming automated cleanup.

### Cloudflare / media edge

Impact: cached/signed delivery may fail while origin objects remain intact.

Action: distinguish edge outage from B2 loss before changing storage records. Do not delete/re-upload objects as an edge-outage workaround. Restore/bypass the delivery layer only through the configured safe origin path, then verify signed URL behavior and cache headers.

## Degraded-operation principle

Dependency failure should disable the smallest unsafe capability, not automatically the entire product. Database failure is generally site-critical. B2 failure should primarily affect media. Redis/Celery failure should primarily affect asynchronous work. Cloudflare failure should primarily affect delivery. The application must not claim success for an operation whose durable side effect was not recorded.

## Incident recovery sequence

1. Detect and declare the incident; record start time, release SHA and affected dependency/workflow.
2. Contain: stop deployment, destructive workers or unsafe writes as appropriate.
3. Preserve: logs, database recovery points, object versions and durable queue/work records.
4. Recover the dependency or roll application code back to a schema-compatible known-good release.
5. Verify liveness/readiness and representative workflows.
6. Reconcile durable pending work: email deliveries, storage deletions, multipart uploads and other idempotent jobs.
7. Verify no cross-tenant or duplicate side effects occurred during replay.
8. Re-enable cleanup/background automation.
9. Record timeline, customer impact, root cause, recovery actions and prevention work.

## Rollback acceptance criteria

A rollback is complete only when:

- the deployed code and database schema are compatible;
- health/readiness pass;
- core authenticated workflows pass;
- media behavior matches the current dependency state;
- Celery workers can process a controlled test job;
- durable pending work has been reconciled rather than discarded;
- no migration/data loss is hidden by simply reverting Git.

## Production readiness rule

Before launch, perform at least one controlled rollback exercise: deploy a reversible test release in a production-like environment, simulate failed readiness, return to the prior release, and prove database, gallery, Redis/Celery and media behavior remain consistent. Documentation alone does not satisfy this control.
