# LumisPixel media Worker

Development Cloudflare Worker for retrieving private gallery objects from Backblaze B2.

## Security model

- Accepts only GET and HEAD.
- Restricts origin access to `B2_ALLOWED_PREFIX` (development: `private/dev/`).
- Uses a dedicated read-only Backblaze B2 application key.
- Requires every media request to carry an expiring LumisPixel signature.
- Rejects missing, malformed, expired, overlong, or invalid signatures before requesting B2.
- Responses remain `private, no-store`; edge caching is intentionally deferred until authorization is validated.

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

Django signing support will be added separately so application code can mint these URLs without exposing the signing secret to browsers.
