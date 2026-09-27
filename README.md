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


## Gallery media storage

Gallery originals use a provider-neutral storage boundary in `apps/galleries/storage.py`.
Local development and CI use the private local filesystem. Production can use
Backblaze B2 through its S3-compatible API without changing `GalleryPhoto`.

For B2, configure deployment secrets/environment variables (never commit real
credentials):

```text
GALLERY_STORAGE_BACKEND=b2
GALLERY_STORAGE_ENVIRONMENT=prod
B2_ACCESS_KEY_ID=<restricted application key id>
B2_SECRET_ACCESS_KEY=<restricted application key>
B2_BUCKET_NAME=lumispixel-production-media
B2_REGION=<bucket region>
B2_ENDPOINT_URL=<bucket S3 endpoint>
B2_SIGNED_URL_TTL=900
```

The B2 application key should be restricted to the production media bucket.
The bucket remains private; Django storage URLs are signed and expire according
to `B2_SIGNED_URL_TTL`. The object namespace remains
`private/<environment>/galleries/<photographer>/<gallery>/originals/`.

