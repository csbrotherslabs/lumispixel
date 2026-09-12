# LumisPixel

## Local development

The database is created locally and is intentionally not committed to Git. After
cloning or pulling changes that add models, apply migrations before opening the
site:

```bash
python manage.py migrate
python manage.py runserver
```

The CRM tables (`clients_lead`, `clients_client`, and related tables) are created
by the committed migrations in `apps/clients/migrations/`. An error such as
`no such table: clients_lead` means the local database has not received those
migrations. Stop the development server, run `python manage.py migrate`, and
restart it.

For convenience, the development startup scripts apply all pending migrations,
run Django's system checks, and then start the server:

- Windows: `scripts\start-dev.bat`
- macOS/Linux: `./scripts/start-dev.sh`

To verify a setup without starting the server:

```bash
python manage.py showmigrations clients
python manage.py check
```

Every clients migration should be marked with `[X]`.

## Tests and CI

Before opening or merging a pull request into `dev`, run the same checks used by
GitHub Actions:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
```

The `Django CI` workflow runs these checks automatically for every pull request
targeting `dev` and again after changes land on `dev`. CI intentionally uses the
normal development-safe defaults: SQLite, local/in-memory email behavior, and no
production database, Redis, Spaces, or email credentials.

Repository rules for `dev` should require the `Django CI / checks-and-tests`
status check before a pull request can merge.
