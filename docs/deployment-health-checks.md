# Deployment health checks

LumisPixel exposes two intentionally small unauthenticated endpoints for the hosting platform.

- `/health/live/` checks only that the Django/Gunicorn process can answer HTTP. It does not call PostgreSQL, Redis, B2, Cloudflare, or email. A dependency outage must not cause the platform to kill every otherwise-live web process.
- `/health/ready/` checks PostgreSQL with `SELECT 1` and the Redis/Celery broker with `PING`. It returns HTTP 200 only when the web application can reach the stateful infrastructure required for normal operation.

Both endpoints return only `{"status":"ok"}` or `{"status":"unavailable"}`, set `Cache-Control: no-store`, and never expose hostnames, credentials, exception text, versions, table names, or provider details.

Configure the hosting platform's liveness probe against `/health/live/` and its readiness/traffic probe against `/health/ready/`.

B2 and Cloudflare are intentionally not called on every web readiness probe. Their configuration is fail-fast at startup and media-origin behavior is isolated in the Worker. Repeatedly calling external object storage/CDN from the web health endpoint would make Django availability depend on a media-path outage and could generate unnecessary external traffic.

Email is also excluded from readiness: SMTP failure should degrade notification delivery, not remove the web application from service.

Use provider monitoring and application alerts for B2, Cloudflare, SMTP, Celery worker, and Beat health separately.
