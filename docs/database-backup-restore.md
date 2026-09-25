# LumisPixel PostgreSQL backup and restore runbook

Production database backups are an operational requirement, not an application-level substitute for the hosting provider's snapshots/PITR.

## Required production policy

- Enable automated PostgreSQL backups with point-in-time recovery (PITR) at the database provider.
- Keep backups in a separate failure domain/account where the provider supports it.
- Retain enough history to recover from delayed discovery of accidental deletion or corruption.
- Restrict backup credentials and restore privileges to production operators.
- Monitor backup success and storage consumption.

## Logical backup

Run from an authorized environment with the production connection string supplied securely:

    pg_dump --format=custom --no-owner --no-acl --file=lumispixel.dump "$DATABASE_URL"

Do not commit dumps or credentials to the repository.

## Restore drill

Restore into an isolated, non-production PostgreSQL database:

    createdb lumispixel_restore_test
    pg_restore --clean --if-exists --no-owner --no-acl --dbname=lumispixel_restore_test lumispixel.dump

Then point a non-production LumisPixel instance at the restored database and run:

    python manage.py migrate --check
    python manage.py check

Verify representative photographer, gallery, client, booking, contract/invoice, invitation/token, and audit records. Verify row counts and recent timestamps against the backup source when available.

Never test a restore over the live production database.

## Cadence

Perform a documented restore drill before private beta and after material database/provider changes. Repeat on a regular operating cadence. A backup is not considered recovery-ready until a restore has succeeded.
