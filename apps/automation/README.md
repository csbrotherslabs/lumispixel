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

Operational controls: /internal/automation/ is initially restricted to active superusers.
Failed jobs can be retried with a mandatory reason and an atomic InternalAuditEvent.
Attempt numbers remain monotonic. Metrics are all-time job counts, not attempt success rates.
Overdue means eligible for dispatch for more than 15 minutes. Alerts and drill-down remain pending.

Reconciliation scans every five minutes on the default queue, independently of the dedicated
execution queue. It also runs during manual System Monitor checks. Aggregate alerts use
stable keys and notify engineering (and executive recipients for critical alerts) through
the existing internal inbox on opening, reopening, or escalation. Healthy checks resolve
existing alerts. No financial or gallery domain records are repaired by this scanner.
The 15-minute overdue threshold and five-minute cadence are initial operational defaults.
A broker-wide outage prevents Celery-based monitoring; external uptime monitoring is needed.

External delivery: reuse notifications.EmailDelivery as the email outbox. A committed
SENDING claim excludes competing workers. Explicit SMTP rejection may be retried under
the existing policy; ambiguous exceptions and stale claims become UNCERTAIN, never
blindly retried. SENT means SMTP acceptance, not inbox delivery. Reconciliation scans
pending emails every minute and alerts on uncertain/dead records. Provider verification
and authorized resolution UI remain pending. SMTP cannot guarantee exactly-once delivery.
Payment integrations must use provider idempotency keys and verified provider events;
no payment adapter is introduced here. Existing direct-send paths still need migration.
Deploy only after draining old email workers and applying the status migration.

Active superusers can record manually verified uncertain email outcomes in the Automation Center.
Evidence is an operator-supplied provider reference, not automatic provider verification.
Resolution is audited and never resends; confirmed non-acceptance remains terminal.
Late worker completion cannot overwrite an operator resolution. Existing direct-send producers
and provider correlation/verification still require integration.

Brevo callback: POST /api/webhooks/brevo/transactional/ with Authorization: Bearer
matching BREVO_WEBHOOK_TOKEN. Empty configuration disables the receiver. SMTP messages
carry X-Mailin-custom lp:<outbox key>; test actual Brevo echo before rollout. Events
are deduplicated by message, recipient hash, event and timestamp (not webhook ID).
Only request/delivered evidence for every expected recipient resolves uncertain acceptance.
Bounce/deferred/complaint evidence is stored separately; no automatic resend. Unmatched
events are retained for investigation; delivery metrics and retention policy are pending.
Do not subscribe to open/click tracking for this initial rollout. Configure TLS and
request body limit at the reverse proxy; never log authorization headers.

Email Operations (/internal/automation/email/operations/) is a superuser-only read-only
report. Rolling 1/7/30/90-day outbox cohorts show current status and any-recipient
provider evidence; event counts use received_at instead. All-time exception backlog
remains visible regardless of period. Evidence categories overlap; coverage is not a
recipient-level delivery rate. No raw email bodies, addresses or provider IDs are shown.
Rejected/duplicate webhook request telemetry and producer attribution remain future work.

Invoice create/send/resend and bulk reminders now use the durable outbox. Invoice SENT
and sent_at retain legacy business issuance semantics, not proof of transport acceptance.
Issue is once per invoice; explicit resend/reminder are deduplicated per purpose per day.
An earlier unresolved submission blocks a different send. Invoice email snapshots are
rendered at enqueue; cancellation of already queued snapshots and complete producer
inventory remain follow-up work. Existing invoice tests need regression verification.
