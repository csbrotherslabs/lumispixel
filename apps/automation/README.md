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

Second migration batch: account verification, marketplace booking acknowledgment and
support ticket emails use the outbox. Support recipients are submitted individually.
Account verification deduplicates by generated link digest; booking by booking ID;
support by ticket/comment or transition timestamp. Existing token validation is unchanged.
Password reset, gallery and contract rotation, and employee invitations require a
separate token lifecycle review before migration. Runtime tests remain outstanding.

Secure email lifecycle foundation: optional expiry, explicit domain guard, queued-only
cancellation, terminal sensitive body purge, dashboard cancellation/expiry counts.
Account verification is the first guarded producer. Unknown guard kinds fail closed.
Domain callers must authorize cancellation; external submissions cannot be recalled.
Pre-claim checks do not eliminate the race with subsequent domain revocation; links
must still be validated at redemption. Sensitive payloads remain plaintext until
terminal purge; encryption, uncertain payload retention, supersession and gallery
replacement activation are pending. Legacy queued emails are not retroactively guarded.

Sensitive payload encryption: provision EMAIL_PAYLOAD_KEYS (comma-separated Fernet keys,
newest first) in web and worker environments before enabling. Retain old keys until
all corresponding ciphertext is purged; no automatic re-encryption yet. Recipient
addresses and lifecycle metadata remain plaintext. Supersession is scoped by a
server-generated domain identity; only newly created events advance the pointer.
Already claimed messages cannot be recalled; supersession is not token revocation.
Migration 0008 irreversibly redacts previously flagged sensitive payloads and cancels
queued ones; drain workers first and arrange fresh links if needed. Existing unflagged
legacy messages are not covered. Account verification tokens now bind email address,
invalidating previously issued verification links. Tests not executed.

Gallery invitation replacement now queues encrypted email with a 24-hour dispatch
window (or earlier gallery expiry). Existing valid tokens remain valid until the
latest replacement is used by an authenticated, verified matching recipient; anonymous
GETs and provider acceptance alone do not retire older links. Explicit manual link
rotation remains unchanged. Public anonymous galleries retain overlapping links until
expiry or explicit revocation. Superseded unsent tokens are not individually revoked;
normal redemption permissions still apply. Contract replacement remains pending.

Password recovery uses DurablePasswordResetForm with Django's existing user selection,
token generator, confirmation view and rate limiter. Reset email links use PUBLIC_BASE_URL.
Dispatch expiry derives from the original token timestamp and PASSWORD_RESET_TIMEOUT;
state guard covers Django token mutable inputs. Supersession cancels queued messages,
not already delivered Django tokens. Queue failures retain generic public response and
log a sanitized error; no persistent failure row exists if enqueue itself fails.
Django private token hash helper is a compatibility dependency. Tests not run.

Contract review and signed-copy emails now use encrypted outbox and trusted origin.
One previous review token is retained across replacement requests for the same recipient;
intermediate replacements may become invalid. Explicit signing POST retires the alternate
link and preserves the redeemed token for signed PDF access. GET does not retire links.
Global revocation and recipient change deny both links. SENT denotes issuance, not transport.
Signed-copy queue remains best effort after signature/PDF generation; reconciliation of
missing copies is pending. Migration 0028 required. Runtime tests not executed.

Employee access invitations use encrypted outbox, trusted origin, 24-hour dispatch
window capped by Django password token timeout for setup, and employee-scoped
supersession. Actual usable-password state selects setup vs login. Active internal
access, recipient, password state, title, role and department checked before dispatch.
Existing provisioning and redemption permissions unchanged; previously delivered setup
links are not independently revoked on employee suspension. Login notices use unique
request IDs, not cross-request deduplication. Provisioning precedes enqueue; failures
before outbox creation still require operator resend. Tests written, not executed.

Studio invitations: encrypted outbox, trusted origin, membership-scoped supersession,
seven-day token lifetime, one-minute resend cooldown. Retain one previous valid token
across resends; intermediate tokens may become invalid. Acceptance/decline/revocation
invalidate both via membership status; explicit actions clear both digests. Legacy
SENT/RESENT audit labels denote issuance, not transport. Initial membership creation
precedes queue transaction; failed enqueue leaves a recoverable pending membership.
Migration dashboard 0008 required. Runtime and concurrency tests pending.

Photographer workflow email actions use durable outbox. Workflow completion and domain
writes commit atomically with queue records; success means queued, not delivered.
Invoice reminders reuse daily invoice email dedupe and validate current balance, currency,
due date, recipient and status before dispatch. Existing pre-migration invoice rows have
no lifecycle guard. Gallery publication preserves existing tokens; expiration notices
use individual envelopes and validate current expiration and invitation eligibility.
Existing RUNNING workflow rows require reconciliation; initial broker dispatch recovery
and full workflow retry testing remain pending. Invoice preparation unchanged pending
financial integrity milestone. No new migration. Tests not executed.

Hardening: new SMTP attempts persist numbered history; legacy attempts not reconstructed.
Audited CLI recovery requires active superuser ID and reason, preserves counts, adds one
attempt allowance; OS operator identity is not independently authenticated. Sensitive and
superseded dead letters excluded. Decryption errors defer 15 minutes and alert rather
than immediately destroying ciphertext. Expiry still applies. Business reconciliation
checks invoice issue, contract review and signed copy missing outbox evidence after a
15-minute grace period, report-only. Configure EMAIL_RECONCILIATION_START to an aware
ISO timestamp at actual cutover; disabled by default. Historical/manual sends may need
review. Other domains, webhook/stale attempt finalization, retention and tests pending.

Follow-up hardening: stale sending attempts close as uncertain atomically. Queued
workflow dispatch is recovered periodically; legacy stale RUNNING executions are
quarantined and alerted, not replayed. Booking acknowledgment now encrypted and
eligibility-guarded. Missing-email checks add pending account verification, booking
acknowledgment and studio invitations. Account check is prefix-based, not recipient
or current-token proof. Verification dispatch lifetime capped by both Django timeouts.
Remaining: provider attempt correlation, employee/gallery intent provenance, secure
manual domain recovery, retention policy and runtime tests. No new migration.

Email intent registry (migration 0010): require_email can be called within a domain
transaction before a later enqueue transaction; queue service links the same intent
atomically. Queue-only callers cannot detect failures before queue invocation; domain
producers must explicitly persist intent for that guarantee. Existing rows not backfilled.
Missing intents alert after 15 minutes; authenticated superusers may cancel with a
recorded reason. No automatic regeneration or resend. Optional terminal accepted
payload purge via EMAIL_TERMINAL_PAYLOAD_RETENTION_DAYS (default 0); preserves recipient
metadata, event keys, attempts and provider evidence. Legal retention, recipient
anonymization, backups and domain-specific recovery remain pending. Tests not run.

Domain intent integration: signed-copy obligation commits with signature before PDF
creation; explicit gallery email actions register intent before queue, not manual link
creation; employee send requests persist independent intent before rendering; account
verification registers before rendering (outer transactions may still roll back).
Employee request keys are unique per explicit request, not per password token.
Missing intent recovery remains investigation/cancellation and authorized domain resend;
no generic secret reconstruction. Failed gallery tokens are revoked; replacement sends
create new intents and old missing obligations require reviewed cancellation. Static AST
guard scans production Python in apps/config/scripts and allows only central adapter;
CI workflow added, not run or required by branch protection yet. Existing violations
may surface; dynamic imports, external HTTP mail APIs and other directories not covered.
No new migration. Tests not run.

Brevo API transport: TRANSACTIONAL_EMAIL_TRANSPORT=smtp (default) or brevo;
BREVO_API_KEY required for brevo. Fixed HTTPS endpoint, no redirects or network
retries, no SMTP fallback. API accepts HTML or plain body (HTML preferred).
201 with messageId is acceptance, not delivery. 429 retries with bounded numeric
Retry-After; definite validation rejects dead-letter; auth errors retry within
attempt budget; timeout/5xx/malformed acceptance uncertain. Attempt number and
provider message ID correlate webhooks, with recipient validation. Custom header
and message-ID behavior require live verification, especially multi-recipient
messages; unresolved evidence stays uncertain. Migration 0011 required. Mock tests
written, not run. Sender must be authorized in Brevo. Never log or commit API key.
Architecture guard does not yet detect arbitrary HTTP provider calls. Existing SMTP
remains default, not disabled. No production configuration changed.
