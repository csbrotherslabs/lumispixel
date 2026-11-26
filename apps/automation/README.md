# Platform automation foundation

Mandatory platform jobs are separate from photographer-configurable apps.workflows rules.
Use enqueue inside the originating business transaction. Beat dispatches committed jobs.
Handlers must scope every target lookup by photographer_id and perform only transactional
database effects. Never send email, charge a card, or call external APIs inside a handler:
use a durable domain outbox and provider idempotency keys instead.

Guiding principles: idempotency, retries, durable execution history, tenant isolation,
reconciliation, permission-controlled manual recovery, auditability, and workload isolation.

This initial implementation provides database-backed identity, retry scheduling, execution
history and transactional serialization on PostgreSQL. It does not yet provide an admin
recovery interface, external-effect delivery, business reconciliation, or legacy task migration.
Worker crashes roll back the attempt; hard-crash telemetry requires separate instrumentation.
PROTECT retains history and requires an explicit retention/account deletion policy before rollout.

Dedicated routing uses the existing CELERY_DEDICATED_QUEUES_ENABLED flag. When enabled,
provision a worker consuming automation before deployment; keep media/visual workers separate.
When disabled jobs use the existing default queue. Verify migrations, PostgreSQL concurrency,
broker recovery, and tenant-scoped handlers before enabling business producers.
