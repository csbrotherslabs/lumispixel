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

## Tests and pull request gate

Before opening or merging a pull request into `dev`, run the same checks enforced
by GitHub Actions:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
```

Pull requests targeting `dev` run `.github/workflows/django-tests.yml`. The
`Django tests` job must pass before merge once that status check is configured as
required in the `dev` branch ruleset/protection settings.
