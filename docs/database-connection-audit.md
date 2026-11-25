# Database connection audit — pre-PgBouncer

## Incident and scope
Development request failed with PostgreSQL reserved-slot error. User measured max_connections=25, superuser_reserved_connections=3, client backends=5 after incident. Nominal ordinary capacity is at most 22, subject to provider/role reservations and other sessions. Root cause is not proven by this later snapshot. No endpoint or runtime configuration is changed in this PR.

## Verified on dev
- config/settings.py: DATABASE_URL parsed with DB_CONN_MAX_AGE default 60 seconds and health checks enabled; DEBUG fallback SQLite. Persistent connections are per Django execution thread, not a shared pool.
- gunicorn.conf.py: default worker count min(2*CPU+1,4), gthread, two threads. Up to eight request-thread connections per instance at default maximum, excluding other processes. Environment overrides and deployed instance count unknown.
- config/settings.py and config/celery.py: Redis broker, optional dedicated queue routing, prefetch multiplier default 1; no explicit worker concurrency in inspected settings. Prefetch is not a concurrency cap. Actual worker commands and Celery beat process count must be collected from deployment.
- apps/visual_search/vector_store.py: context-managed psycopg.connect(VISUAL_SEARCH_DATABASE_URL, connect_timeout=10). Separate connection path from Django; Django CONN_MAX_AGE does not control it. Context manager closes connection on exit. semantic.py uses same helper.
- apps/visual_search/tasks.py and semantic_tasks.py: inference occurs outside explicit atomic blocks, but ORM connection may remain open during inference. Vector writes occur inside main DB authorization/row-lock transactions; preserve these privacy safeguards and measure cross-database wait times.
- semantic_tasks.py uses QuerySet.iterator() for gallery scheduling: transaction pooling requires DISABLE_SERVER_SIDE_CURSORS=True for the pooled Django alias or a proven transaction-bound alternative. Measure memory on large galleries.
- requirements.txt uses psycopg[binary]; verify installed version and prepared statement behavior before pooling raw psycopg connections.
- Code search returned no matches for several known terms, so absence of other session-level features cannot be established. Deployment workflow path attempted was not found. This is a targeted audit, not exhaustive certification.

## Read-only incident diagnostics
Run on each actual cluster via direct admin connection; do not terminate sessions indiscriminately.

```sql
SELECT current_database(), inet_server_addr(), inet_server_port();
SHOW max_connections;
SHOW superuser_reserved_connections;
SELECT datname, usename, application_name, client_addr, state,
       count(*) AS connections
FROM pg_stat_activity WHERE backend_type='client backend'
GROUP BY 1,2,3,4,5 ORDER BY 6 DESC;
SELECT pid, datname, application_name, state,
       now()-backend_start AS connection_age,
       now()-xact_start AS transaction_age,
       wait_event_type, wait_event
FROM pg_stat_activity WHERE backend_type='client backend'
ORDER BY xact_start NULLS LAST;
```

Capture before startup, after web startup, after each worker startup, during representative traffic and after idle. Confirm cluster mapping for dev/prod and vector endpoints without sharing credentials. Record actual Gunicorn workers/threads, Celery worker pool/concurrency/replicas, beat, admin and monitoring sessions. Inspect systemd/container deployment configuration and effective env locally (never dump secrets).

## Staged proposal (not enabled)
1. Test DB_CONN_MAX_AGE=0 locally with current direct endpoint; compare peak sessions and request latency. This existing setting requires no code change.
2. Confirm actual available pool capacity with provider. If dev and prod share the 22-slot cluster, provisional 5 dev + 10 prod backend slots leaves 7 nominal ordinary slots for other clients/headroom; adjust for provider overhead and measured demand. If separate clusters, budget separately.
3. Add explicit opt-in transaction-pooling configuration for Django; preserve direct URL for migrations/admin. Disable server-side cursors and verify prepared statement compatibility. Do not add a second client-side pool by default.
4. Keep visual search direct until raw psycopg/pgvector registration, prepared statements, transaction behavior and query performance are tested. Audit session SET, advisory locks, LISTEN/NOTIFY, temp tables, named cursors and migration commands across full checkout.
5. Test dev login, CRM, website studio, gallery permissions, upload/download, concurrent indexing, face/semantic search, consent revocation/purge, task retries and large gallery iteration. Compare p50/p95 latency, errors, pool wait time, peak backend count and memory against baseline.
6. Roll out production only after dev validation and explicit approval. Rollback by restoring prior endpoint/settings and restarting affected services in a controlled sequence; ensure direct connection budget before rollback.

## Acceptance gates
No reserved-slot errors during representative concurrency; no privacy or transaction regressions; acceptable p95 latency and pool queue time; sufficient admin headroom; documented direct migration path. Runtime tests, actual deployment inventory and provider configuration remain outstanding.

## Worker lifecycle optimization
Face and semantic indexing now release the main ORM connection immediately before file reading/inference, after the claim transaction exits. The helper skips caller-owned atomic blocks and disabled autocommit. Final authorization, claim checks, locks and vector writes are unchanged. Celery's normal Django task cleanup remains in place. Test with real asynchronous workers; eager tests inside transactions intentionally skip release.

## Worker budget verification
On the production host, inspect running processes with `ps -eo pid,ppid,comm | grep -E 'gunicorn|celery'` and inspect service definitions locally for worker/thread/concurrency counts (do not share secrets). Use distinct DB_APPLICATION_NAME values per service. Budget maximum web workers × threads plus all Celery execution slots that access the main database, other services and administrative headroom; include overlapping workers during restarts. Do not lower deployed concurrency blindly. For a local single GPU worker, start with concurrency 1 using the existing queue and pool arguments; verify throughput and queue delay before increasing. Production defaults remain unchanged.

## Development pool integration
Create a transaction-mode pool for lumispixel_dev, provisional size 5 subject to provider capacity. Keep DATABASE_URL unchanged; set DB_POOL_URL to the provider's pool connection URI (including TLS options), DB_TRANSACTION_POOLING=1. Restart web and workers. For migrations and Django test database creation use a separate terminal with DB_TRANSACTION_POOLING=0; direct endpoint remains authoritative. Never commit either URI. Rollback: disable flag and restart services, checking direct connection headroom. Pooled settings force CONN_MAX_AGE=0, disable server-side cursors and psycopg automatic prepared statements. Visual search stays direct. Repeat 1/4/8-client and combined benchmarks; provider pool URI may expose pool name instead of database name, so benchmark must verify current_database() before load. Facial recognition excluded from current release scope per owner; semantic indexing, uploads, derivatives, HTTP and authorization regression tests remain required.
