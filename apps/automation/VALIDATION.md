# Automation release gate

Status: NOT VERIFIED. No deployment or merge authorized.

Run on a disposable checkout of PR 1175 with installed dependencies, isolated
database and broker, test-only encryption keys, and no real provider credentials.
Do not run against production.

```sh
python -m unittest discover -s scripts/tests -p test_email_architecture.py
python scripts/check_email_architecture.py
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py migrate
python manage.py test apps.automation apps.notifications apps.workflows apps.clients apps.accounts apps.galleries apps.internal_ops apps.dashboard apps.marketplace --noinput
```

Repeat migration on sanitized staging snapshot; verify PostgreSQL concurrency,
worker interruption, broker recovery, tenant isolation, queue routing and all
business flows. Record exact commit, environment, test counts and failures.
Live Brevo sandbox/controlled-recipient verification is a separate approved gate.
SMTP remains default. Never paste secrets into logs or tickets.

Known open issues: full source scan not executed; domain recovery and intent
coverage incomplete; webhook message-ID/header behavior unverified; legacy
sensitive rows and retention policy unresolved; account token timeout alignment,
gallery activation race, contract replacement overlap, multi-recipient delivery
semantics, and historical migration compatibility need verification.

## Local PostgreSQL

Configure TEST_DB_HOST (loopback only), TEST_DB_PORT, TEST_DB_NAME,
TEST_DB_USER and TEST_DB_PASSWORD in the local .env. The local role needs
CREATEDB. Use config.settings_test explicitly for all automated Django tests:

```sh
python manage.py test apps.automation apps.notifications --settings=config.settings_test --noinput --verbosity=2
```

The test module overrides the default database, disables inherited Brevo API
credentials and uses Django's in-memory email backend. Existing CI loopback
PostgreSQL and explicit SQLite mode remain supported. Other external services
still require isolation before running broader integration tests.
