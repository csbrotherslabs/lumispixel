# LumisPixel public site media Worker

Serves allowlisted site images from a private B2 origin without gallery HMAC
authorization. Development uses lumispixel-dev-site-media and site/dev/;
production uses lumispixel-prod-site-media and site/prod/. Use separate
read-only, prefix-restricted Worker credentials.

Allowed paths are client-profiles, photographer_profiles/photos,
photographer_profiles/logos, photographer-covers and photographer_websites.
Only supported image extensions and origin image MIME types are accepted.
Private uploads and gallery objects are not served.

## Local validation

Run npm ci and node --test. Create an ignored .dev.vars containing
B2_ACCESS_KEY_ID and B2_SECRET_ACCESS_KEY for the development site bucket.
These correspond to Django's B2_SITE_ACCESS_KEY_ID and B2_SITE_SECRET_ACCESS_KEY.
Never commit secrets.

```sh
npm run dev -- --ip 127.0.0.1 --port 8788
```

For local Django site delivery use SITE_MEDIA_DELIVERY_BASE_URL=http://127.0.0.1:8788.
Test synthetic development images, HEAD, public cache headers and namespace
rejection, then clean up synthetic objects. Do not use remote or production mode.

## Origin and caching

Only the configured HTTPS B2 endpoint is accepted. Signed origin fetches use
manual redirect mode; all 3xx responses return 502 without following redirects.
Only complete successful GET responses enter the versioned v3 cache.
HEAD and Range bypass cache. Successful public responses use max-age=3600.
Use immutable object keys and plan cache invalidation for replacement.

Deploy only after approval and live development validation. Local tests do not
establish deployed edge-cache behavior. Production uses the separate production
Wrangler environment and separately configured encrypted secrets.
