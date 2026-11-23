# LumisPixel media Worker

Cloudflare Worker for retrieving private gallery objects from Backblaze B2.

## Security model

- Accepts only GET and HEAD.
- Restricts origin access to `B2_ALLOWED_PREFIX` (development: `private/dev/`).
- Uses a dedicated read-only Backblaze B2 application key.
- Requires every media request to carry an expiring LumisPixel signature.
- Rejects missing, malformed, expired, overlong, or invalid signatures before requesting B2.
- Authorization is validated before every cache lookup, including cache hits.
- Successful full GET responses are cached at the Cloudflare edge by pathname only; signature query parameters are never part of the cache key.
- Browser-facing responses remain private/non-cacheable while the Worker's internal edge cache can retain the object.
- Range requests and HEAD requests bypass the edge cache so partial responses cannot poison a full-object cache entry.

### Cloudflare secrets

Configure these as encrypted Worker secrets and never commit their values:

- `B2_ACCESS_KEY_ID`
- `B2_SECRET_ACCESS_KEY`
- `MEDIA_SIGNING_SECRET`

`MEDIA_SIGNING_SECRET` must be a new random secret dedicated to media URL signing. Do not reuse a B2 credential, Django `SECRET_KEY`, or Cloudflare API token.

### Signed URL contract

A valid request has:

`https://media-dev.lumispixel.com/<object-path>?expires=<unix-seconds>&signature=<base64url-hmac>`

The HMAC is SHA-256 over the exact string:

`<URL pathname>\n<expires>`

using `MEDIA_SIGNING_SECRET`, encoded as unpadded base64url.

The Worker also enforces `MEDIA_MAX_SIGNED_URL_TTL` (default: 3600 seconds) so a stolen signing client cannot mint arbitrarily long-lived URLs.

## Development configuration

Non-secret origin settings live in `wrangler.jsonc`. B2 credentials and the media-signing secret must be configured in the Cloudflare dashboard.

Django generates signed URLs without exposing the signing secret to browsers.

## Edge caching

`MEDIA_EDGE_CACHE_TTL` controls the Worker's internal Cloudflare cache lifetime and defaults to 86400 seconds (24 hours in development).

The Worker validates the HMAC and expiry before calling `cache.match()`. Therefore an unsigned, invalid, or expired URL cannot retrieve an object even when that object is already cached.

The normalized cache key contains the media origin plus pathname and deliberately excludes `expires` and `signature`. This allows separate valid signed URLs for the same immutable gallery object to share a cached copy.

Responses include `x-lumispixel-cache` during this phase:
- `MISS`: authorized full GET fetched from B2.
- `HIT`: authorized full GET served from Cloudflare cache.
- `BYPASS`: Range request fetched directly from B2.

Cache invalidation/purge should be added before object replacement under an existing key is supported. UUID/immutable object keys remain the preferred long-term design.


## Production environment

Production is a separate Wrangler environment named `production` and deploys as
`lumispixel-media-prod`. It is restricted to `private/prod/`; development
remains restricted to `private/dev/`.

The three encrypted Worker secrets must be configured separately for the
production environment:

- `B2_ACCESS_KEY_ID`
- `B2_SECRET_ACCESS_KEY`
- `MEDIA_SIGNING_SECRET`

Use a dedicated, read-only B2 application key whose bucket/prefix permissions
are limited as narrowly as Backblaze permits. Never copy development secrets
into production merely to make a deployment pass.

Production deployment is manual through the GitHub production environment so
repository environment approvals/protection can gate releases. The workflow
deploys with `wrangler deploy --env production`.

A B2 network exception is converted to a 502 response and is never cached.
Only complete HTTP 200 GET responses enter the edge cache. Authorization still
runs before every cache lookup.

## Gallery image variants (v2): private B2 + Images binding

The Worker first retrieves the original from private B2 with AWS Signature V4,
then passes the authenticated response body to Cloudflare's `IMAGES` binding.
Do not use `cf.image` on the signed B2 fetch: the resizing subrequest may fail
with HTTP 401. The binding is configured as `images.binding=IMAGES` in
`wrangler.jsonc` and must be available on the Cloudflare account.

Supported variants: thumbnail (640px maximum width, WebP quality 82), preview
(2560px maximum width, WebP quality 85), and original (untouched bytes).
Authorized cache keys include the variant and version, preventing original/
thumbnail cache collisions. Every request is authorized before cache lookup.

**Important limitation:** Cloudflare's Images binding accepts source images
up to 20 MB. For an image with `Content-Length > 20,000,000`, transformed
requests return HTTP 413 with a clear error; an unknown-length oversized input
may fail with 502. Original downloads still work. Since LumisPixel accepts
images over 20 MB, this is a *partial fix*, not a complete gallery-performance
solution. Before rollout, implement an oversized-image derivative pipeline
(e.g. generate a small preview/thumbnail once using Celery/Pillow and store it
in B2) or choose a resizing service that accepts the largest allowed uploads.
Do not merge or deploy this as a complete fix until large images render.

The Images binding may incur charges for unique transformations. Confirm
account entitlement and pricing before enabling in dev.

Manual verification: original still returns original bytes; thumbnail and
preview return WebP for inputs <=20 MB; oversized images return 413 for
variants; invalid/expired signed URLs return 403; variants have distinct
cache keys; test all gallery designs on desktop and mobile. No CI run requested.


## Pre-generated derivatives (Celery + Pillow)

Gallery originals remain private and unchanged in B2. When a completed
`GalleryPhoto` is saved, a post-save hook schedules
`generate_gallery_photo_derivatives` on transaction commit. The task
generates two deterministic private objects:
- `galleries/<photographer>/<gallery>/variants/thumbnail/<stem>.webp`
- `galleries/<photographer>/<gallery>/variants/preview/<stem>.webp`

The Worker first fetches the variant object directly with authenticated B2
requests. If the derivative is not present yet, it falls back to the existing
Cloudflare Images binding for small originals. Large originals without a
generated derivative still return 413 until the background job finishes.

Backfill existing photos in bounded batches, after deploying Django and
confirming Celery is running:

```bash
python manage.py backfill_gallery_derivatives --gallery-id 1 --limit 100
```

For additional batches, use the reported `--after-id` value. Monitor
worker CPU/RAM, B2 requests and storage before raising concurrency.
The upload-completion path must be verified to call `GalleryPhoto.save()`;
bulk queryset updates bypass Django post-save signals. If uploads use bulk
updates, explicitly enqueue the task in that completion path before rollout.

Storage cleanup now schedules derivative deletion alongside originals.
Do not deploy this as a complete production fix until end-to-end validation
covers upload completion, backfill, large photos, deletion, privacy and all
four gallery designs. No CI or production deployment was requested.
