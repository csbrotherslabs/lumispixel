# B2 user-upload rollout

This change is opt-in until existing files are copied. Bundled static assets stay in Git.
Gallery originals keep their existing B2 storage and signed Cloudflare delivery.

## Storage and access

Create private buckets with separate application keys for each environment:

| Environment | Site images | Restricted uploads |
| --- | --- | --- |
| dev | lumispixel-dev-site-media | lumispixel-dev-private-media |
| prod | lumispixel-prod-site-media | lumispixel-prod-private-media |

Site images include account avatars, studio logos/covers, and photographer
website images. Only allowlisted raster-image paths are served publicly by the new
site-media Worker. Restricted files (including gallery/album covers, store images,
CRM client photos, support attachments, and signed contract documents) never enter that public bucket.
Restricted `.url` values are temporary B2 signed URLs; permission-checked download
views continue to authorize requests before streaming files. These temporary URLs
are bearer credentials and must not be stored in database fields or logs.

Keys retain existing upload folders underneath `site/dev/`, `site/prod/`,
`uploads/dev/`, or `uploads/prod/`. New uploads get UUID filenames; migrated uploads
retain their old names, so database references need no rewriting. Local upload files
are used only for temporary processing after cutover, not permanent storage.

Do not share production's database with localhost/dev. Object storage alone does
not prevent a development upload from changing a shared production profile row.

## Configure delivery before enabling storage

1. Create private B2 buckets in the same region as the current B2 endpoint. Scope the
   two Django upload keys, each restricted to one bucket with Read and Write access.
   Use separate credentials for dev/prod. Give the site-media Worker a read-only key
   restricted to its site bucket, never a key for private galleries.
2. In `cloudflare/site-media-worker/wrangler.jsonc`, set the actual region and endpoint.
   Keep dev and production configurations separate. Install dependencies with `npm ci`
   in that directory. Set `B2_ACCESS_KEY_ID` and `B2_SECRET_ACCESS_KEY` using Wrangler
   secrets (include `--env production` for production). Deploy the correct environment
   and attach `site-media-dev.lumispixel.com` or `site-media.lumispixel.com` as its domain.
   Do not point the public Worker at the private gallery bucket or reuse its route.
3. Configure these values in the corresponding environment; never commit credentials:

```dotenv
USER_UPLOAD_STORAGE_BACKEND=local
B2_SITE_BUCKET_NAME=lumispixel-prod-site-media
B2_PRIVATE_UPLOAD_BUCKET_NAME=lumispixel-prod-private-media
B2_SITE_ACCESS_KEY_ID=YOUR_SITE_UPLOAD_KEY_ID
B2_SITE_SECRET_ACCESS_KEY=YOUR_SITE_UPLOAD_KEY
B2_PRIVATE_UPLOAD_ACCESS_KEY_ID=YOUR_PRIVATE_UPLOAD_KEY_ID
B2_PRIVATE_UPLOAD_SECRET_ACCESS_KEY=YOUR_PRIVATE_UPLOAD_KEY
SITE_MEDIA_DELIVERY_BASE_URL=https://site-media.lumispixel.com
```

Dev uses `lumispixel-dev-*` buckets, the dev domain, and `GALLERY_STORAGE_ENVIRONMENT=dev`.
Existing `B2_REGION`, `B2_ENDPOINT_URL` and `MEDIA_SIGNED_URL_TTL` are reused. Existing
`B2_BUCKET_NAME`, gallery credentials, `MEDIA_DELIVERY_BASE_URL` and signing secret
continue to serve gallery originals; do not change those as part of this rollout.

## Copy and verify

Back up the database and both local upload roots. Keep services on local storage
while configuring and testing the new destinations. Dry-run:

```bash
python manage.py migrate_user_uploads_to_b2
```

Missing referenced files are reported and cause failure. Recover them from the
machine where uploaded or re-upload them; this command cannot recover deleted files.
During a maintenance window, stop upload writers (web and Celery) to prevent files
or references changing while copying. With all credentials configured, run:

```bash
USER_UPLOAD_STORAGE_BACKEND=b2 python manage.py migrate_user_uploads_to_b2 --apply
```

Use `--source-root` / `--private-source-root` if migrating a backup. The command
streams and SHA-256 verifies every copied file, verifies existing destination files
on reruns, refuses mismatched destination content, preserves database references,
and never deletes local originals. It skips gallery originals, which already have
an independent storage pipeline. No file is marked migrated based only on its name.

After verification, set `USER_UPLOAD_STORAGE_BACKEND=b2` in the service environment,
run `manage.py check` and restart web/Celery. Test upload → save → sign out → sign in,
website display, gallery covers/store images, and authorized/unauthorized support
and contract downloads. Keep the local backup and `/media/` route during verification.
Remove old local copies only after confirming all references resolve from B2.

For rollback, stop writers and copy any newly created B2 uploads back to their local
relative paths before switching to local storage; the old backup alone lacks post-cutover uploads.
No buckets, secrets, domains, or production data are created by the code change itself.
