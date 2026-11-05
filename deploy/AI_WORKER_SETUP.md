# Dedicated AI worker rollout

The worker shares the production application database, vector database, Redis
broker/result backend, and private B2 gallery storage. Do not run migrations from
this worker. The web release owns schema changes. Do not use the integration/test
vector database. Add the worker to the managed services' trusted sources and
use private network endpoints where supported. Never expose Redis publicly.

## Private configuration

Edit `/srv/lumispixel/.env` directly on the worker with mode 600, owned by
`lumispixel`. Use `deploy/ai-worker.env.example` as a field checklist, replacing
placeholders privately. Preserve existing model paths. Use percent-encoded
credentials in URLs. Do not paste secrets into chat, shell command arguments,
logs, or Git. Use a separate Django worker secret; use the existing production
media signing secret for consistent signed media configuration.

Install the Redis provider's trusted CA at
`/srv/lumispixel/certs/redis-ca.crt`. If the provider uses public trust, reference
the OS trust bundle instead. Both Redis URLs must verify TLS, with the CA path
URL-encoded. For vector PostgreSQL use `sslmode=verify-full` and the provider CA
via `sslrootcert` where needed. Keep all discovery feature flags disabled during
connection validation. B2 keys must access the existing production gallery
bucket, including the existing cleanup permissions if deletion jobs are used.

Django loads `app/.env` for manual commands, whereas systemd loads
`/srv/lumispixel/.env`. For manual checks use the virtualenv's python-dotenv runner
so values are present before importing `config` (Celery validates TLS early):

```bash
/srv/lumispixel/venv/bin/python - <<'PY'
from dotenv import load_dotenv
load_dotenv('/srv/lumispixel/.env', override=True)
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'check'])
PY
```

This check validates configuration, not database, broker, or object-store
connectivity. Verify those independently without displaying connection strings.

## Routing and service activation

1. Deploy the routing code on every producer: web, normal workers, Beat and
   management jobs. Routing defaults off for backward compatibility.
2. Install `deploy/systemd/lumispixel-ai-worker.service` on the AI host. It consumes
   only `ai.semantic,ai.face` with concurrency 1. Do not install the ordinary
   `lumispixel-celery.service` there. Do not start Beat on this host.
3. Set `CELERY_AI_QUEUES_ENABLED=True` on all producers and the AI worker. Restart
   the relevant services in a coordinated window while discovery remains off.
4. Verify worker active queues and a harmless broker round trip. Existing tasks
   already in `celery` do not move automatically: inspect and drain them with the
   old compatible worker before enabling model processing. Do not purge queues.
5. Enable semantic indexing only after schema, vector store, model/storage access,
   and gallery authorization are verified. Keep face flags off until the face
   model is configured and approved. Query inference currently runs in Django;
   offloading it needs a separate implementation before enabling web search on
   the small production droplet.

The two queues isolate model work from ordinary application jobs. They do not
provide priority between semantic and face work on this single-process worker.
Split consumers later if interactive latency requires it. After tasks have been
routed to AI queues, do not disable routing or stop their consumers until those
queues have drained; existing messages retain their destinations.
