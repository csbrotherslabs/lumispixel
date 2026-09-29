# Redis Cloud / Celery production deployment

LumisPixel production uses a managed Redis-compatible service for the Celery broker and result backend. The web and worker processes must not depend on a local `redis-server.service`.

## TLS contract

Production Redis URLs must use `rediss://` and must verify the server certificate against the provider CA. The production environment example uses Celery/redis-py URL parameters:

- `ssl_cert_reqs=required`
- `ssl_ca_certs=/etc/lumispixel/certs/redis_ca.pem` (URL-encoded in the connection URL)

Never use `ssl_cert_reqs=none`, `CERT_NONE`, or an unencrypted `redis://` production URL. Keep the Redis password only in `/srv/lumispixel/.env` (or the deployment secret store), never in source control.

Install the provider CA with root ownership and world-readable certificate permissions:

```bash
sudo mkdir -p /etc/lumispixel/certs
sudo chown root:root /etc/lumispixel/certs
sudo chmod 755 /etc/lumispixel/certs
sudo chown root:root /etc/lumispixel/certs/redis_ca.pem
sudo chmod 644 /etc/lumispixel/certs/redis_ca.pem
```

Passwords and certificate paths must be URL-encoded when embedded in the Redis URL.

## systemd

Use `deploy/systemd/lumispixel-celery.service` as the production worker template. The worker waits for `network-online.target`; it does not `Require=` or start after a local Redis daemon.

After changing the unit:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lumispixel-celery
sudo systemctl status lumispixel-celery --no-pager -l
```

The worker log should report a masked `rediss://` connection and finish startup with `ready`.

## Verification

Verify the worker through Celery remote control:

```bash
sudo -u lumispixel bash -c '
set -a
source /srv/lumispixel/.env
set +a
cd /srv/lumispixel/app
/srv/lumispixel/venv/bin/celery -A config inspect ping
'
```

Expected result: one online node returning `pong`.

The application readiness endpoint `/health/ready/` also checks the Redis/Celery broker with `PING` in addition to PostgreSQL.

After changing `/srv/lumispixel/.env`, restart both Celery and Gunicorn so the worker and Django task producers load the same broker settings. Verify the public site and `/health/ready/` before considering the cutover complete.

## Local Redis retirement and rollback

After managed Redis is verified, stop and disable the local daemon if it is still installed:

```bash
sudo systemctl stop redis-server
sudo systemctl disable redis-server
```

Do not uninstall the package during the initial cutover window. Keeping it installed provides a simple rollback option while the managed service is being observed. A rollback requires restoring the prior environment configuration, starting local Redis, and restarting Celery and Gunicorn.
