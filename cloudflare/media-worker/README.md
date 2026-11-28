# LumisPixel gallery media Worker

Private gallery delivery from Backblaze B2. Development uses the shared
`lumispixel-production-media` bucket with prefix `private/dev/`; production
uses `private/prod/`. Use separate prefix-restricted, read-only Worker keys.

## Signed URLs

Django generates URLs with exactly one expires, signature and variant parameter.
The signature is unpadded base64url HMAC-SHA256 over
`pathname + "\\n" + expires + "\\n" + variant`.
Variants are original, thumbnail and preview; none is implicit.
Development maximum lifetime is 3600 seconds; production is 900 seconds.
Authorization precedes cache access. Only canonical gallery paths are allowed.

Thumbnail and preview requests map an originals filename to the corresponding
`variants/thumbnail/<stem>.webp` or `variants/preview/<stem>.webp` object.
There is no runtime image resizing or fallback to original bytes.
Missing derivatives return 404 when B2 returns 404. Derivatives must be WebP.
Range requests are allowed only for originals.

## Local development

Install with npm ci; run npm test. Create an ignored .dev.vars file containing
B2_ACCESS_KEY_ID, B2_SECRET_ACCESS_KEY and MEDIA_SIGNING_SECRET.
The signing secret must match Django and be at least 32 characters.
Never commit secrets. Run:

```sh
npm run dev -- --ip 127.0.0.1 --port 8787
```

Set Django MEDIA_DELIVERY_BASE_URL to http://127.0.0.1:8787 for local testing.
Use synthetic development objects and clean them up after validation.
Do not use production bindings or remote mode for local tests.

## Origin and cache policy

Only the configured HTTPS B2 endpoint is allowed. Signed origin requests use
manual redirect mode because Cloudflare does not support error mode.
All 3xx responses are rejected with 502; redirects are never followed.
Other unsuccessful origin responses return 502 except 404.
Client responses remain private, no-store on cache hits and misses.
The internal cache uses delivery=v3, pathname and variant, excluding credentials.
Only complete successful GETs are cached; HEAD and Range bypass the cache.
Use immutable object keys; replacement requires a cache invalidation strategy.

## Deployment

Production is a separate Wrangler environment named production, Worker
lumispixel-media-prod. Configure separate encrypted secrets in each environment.
Never copy development credentials to production. Deploy only after approval
and live development validation of signatures, derivatives, cache and isolation.
Local cache tests do not establish deployed edge-cache behavior.
