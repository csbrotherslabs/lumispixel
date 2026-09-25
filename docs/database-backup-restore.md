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
    python manage.py verify_database_restore

Verify representative photographer, gallery, client, booking, contract/invoice, invitation/token, and audit records. Verify row counts and recent timestamps against the backup source when available.

Never test a restore over the live production database.

## Cadence

Perform a documented restore drill before private beta and after material database/provider changes. Repeat on a regular operating cadence. A backup is not considered recovery-ready until a restore has succeeded.

## Restore evidence

For every restore drill, record the backup timestamp, restore start/end time, PostgreSQL version, source environment, isolated restore target, operator, verification-command result, representative record checks, and any remediation required. Do not record credentials or connection strings.

A drill is successful only when the restore completes, `verify_database_restore` passes, application system checks pass, and representative business records are confirmed. Provider dashboard status alone is not proof that a usable restore exists.

## Recovery objectives

Before production launch, document the provider-backed recovery point objective (RPO) and recovery time objective (RTO) that LumisPixel will operate against. The values must come from the selected PostgreSQL provider and the team's measured restore drill; do not assume them from this repository.
