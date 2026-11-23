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

## Gallery image variants (v2)

Authenticated requests accept `variant=thumbnail`, `variant=preview`, or
`variant=original` (default). The Worker requests Cloudflare Image Resizing
for thumbnail (maximum width 640 px, WebP quality 82) and preview (maximum
width 2560 px, WebP quality 85); original bytes are never transformed.
`scale-down` avoids upscaling small source images.

**Deployment prerequisite:** Cloudflare Image Resizing must be enabled and
supported for the Worker account/zone, including authenticated B2 origin fetches.
The Worker returns HTTP 502 if a transformed response is not WebP instead of
silently returning a multi-megabyte original. Verify with a real signed image
before switching client traffic. Check Cloudflare transformation billing/limits.

The internal edge cache uses a versioned pathname + variant key (`delivery=v2`)
so cached originals from the previous path-only implementation cannot be
reused as thumbnails. Signatures and expiry are still validated before cache
lookup; they are not part of the cache key. Range requests are permitted only
for original images. Gallery grids use thumbnails; full-screen viewers use
previews. Photographer originals remain in B2 without new stored variants.

### Manual verification before deployment

1. Confirm the Image Resizing entitlement and Worker origin compatibility.
2. In dev, load a gallery with DevTools Network open and disable browser cache.
3. Confirm thumbnail and preview requests return `image/webp`, with thumbnail
   bytes significantly smaller than the original, and full-screen preview crisp.
4. Confirm `original` still returns the original file bytes, and different
   variants never share the same cached response.
5. Confirm invalid/expired signatures return 403 even after a cache hit.
6. Compare image transfer sizes and page load on desktop/mobile across all
   four designs. Do not deploy to production before this passes.
