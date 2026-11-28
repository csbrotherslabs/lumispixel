# Local infrastructure validation

Ordinary regression tests use config.settings_test: memory broker/results,
local storage, local cache, locmem email and no default vector URL.
The real-photo suite explicitly uses VISUAL_SEARCH_INTEGRATION_DATABASE_URL
and SEMANTIC_REAL_PHOTO_MANIFEST; retain its dedicated database guard.

For worker integration use config.settings_integration only with synthetic data.
Create a separate local PostgreSQL database named lumispixel_integration,
grant the local test user access, and set TEST_DB_NAME=lumispixel_integration.
Start a separate loopback-only Redis instance on port 6380, with persistence
disabled, using an empty dedicated directory. Do not reuse or flush port 6379.
Set LUMISPIXEL_INTEGRATION_ENABLED=1 and generate one Fernet key using
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())".
Set LUMISPIXEL_INTEGRATION_EMAIL_KEY to that same test-only key in every
process. Never commit the key or use a deployed key. Set DJANGO_DEBUG=True.
Set CELERY_DEDICATED_QUEUES_ENABLED=True before starting processes.
Use local storage and synthetic recipients only. File email output is in
.integration-email; do not commit its contents. Remove synthetic output
after validation. Do not run Beat until the isolated database is migrated
and the worker queues and task registry have been inspected.

Run:
    python manage.py test config.test_infrastructure_isolation --settings=config.settings_test --noinput
    python manage.py test --settings=config.settings_test --noinput

Run the real-photo suite separately with its explicit manifest and vector URL.
Cloud storage, provider delivery, TLS and Linux worker recovery require
separate controlled validation; this settings module does not authorize them.
