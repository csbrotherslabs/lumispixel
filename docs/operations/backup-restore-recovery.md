# LumisPixel Backup, Restore & Data Recovery

## Objective

A backup is not considered healthy until LumisPixel can restore it into an isolated environment and verify that the restored application data is usable.

## Recovery objectives

Initial production targets:

- PostgreSQL RPO: 24 hours maximum until point-in-time recovery is configured; target 1 hour or better with WAL/PITR.
- PostgreSQL RTO: 4 hours for a full database recovery drill.
- Gallery media: B2 is the hot copy. A separate archive copy must exist before archived media is considered disaster-recoverable.
- Restore drills: at least monthly and after material backup/storage architecture changes.

These are application recovery targets, not claims about provider guarantees. Production infrastructure must be configured to meet them.

## PostgreSQL backup contract

1. Backups must run automatically outside the application process.
2. Backup credentials must be read-only where possible and must never be committed to Git.
3. Dumps/snapshots must be encrypted at rest and access restricted to production operations identities.
4. Keep multiple recovery points. A suggested starting policy is 7 daily, 4 weekly, and 6 monthly recovery points, subject to provider cost and compliance requirements.
5. Backup-job success alone is insufficient. A recent backup must periodically be restored and verified.
6. Never restore a production dump over the live production database as a drill.

## PostgreSQL restore drill

1. Select a real recent production backup.
2. Provision a new isolated PostgreSQL database with no production traffic.
3. Restore the selected backup into that database.
4. Point a temporary LumisPixel environment at the restored database.
5. Run:

   `python manage.py verify_database_restore`

6. Verify representative application records and relationships: users, photographer profiles, clients, galleries, gallery photos and invitations.
7. Confirm expected migrations are current.
8. Record backup timestamp, restore start/end time, verifier result, discrepancies and operator.
9. Destroy the isolated restore environment after the evidence is retained.

A failed drill makes backup readiness degraded until corrected and a subsequent drill passes.

## Media recovery contract

PostgreSQL recovery and image recovery are separate concerns. Restoring database rows does not restore the objects referenced by GalleryPhoto file keys.

For production media:

- B2 object/version retention must be configured deliberately; application deletion must not be assumed recoverable forever.
- The archival pipeline to Glacier Deep Archive must record which immutable object key/version was archived and whether the archive operation completed.
- Destructive cleanup must not claim an archived recovery copy exists unless archive completion is durable and verifiable.
- A recovery drill must periodically select representative media, retrieve it from the recovery source, validate that bytes are non-empty/expected, and verify that its database reference can be reconciled.

## Accidental deletion / corruption procedure

1. Stop the destructive worker or affected write path if deletion/corruption is ongoing.
2. Establish the incident time window before changing data.
3. Preserve database backup/WAL and B2 versions relevant to that window.
4. Restore into isolation first; do not experiment against production.
5. Determine whether the database, media, or both require recovery.
6. Recover immutable media keys before repairing database references when practical.
7. Verify tenant ownership and gallery/photo relationships before promoting recovered data.
8. Resume cleanup workers only after reconciliation.

## Required recovery evidence

Each drill should retain non-sensitive evidence containing:

- backup identifier and timestamp
- restore target/environment identifier
- restore duration
- `verify_database_restore` result
- representative integrity-check result
- media recovery result when applicable
- RPO/RTO achieved
- failures and remediation

Do not place database dumps, customer data, signed media URLs, passwords, provider credentials, access keys or secrets in CI artifacts or logs.

## Production readiness rule

LumisPixel backup/recovery is PASS only when a recent real backup has been restored into isolation and verified. Merely enabling provider backups, creating a dump, or testing mocks does not satisfy this control.
