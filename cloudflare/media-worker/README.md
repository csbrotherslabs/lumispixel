# LumisPixel media Worker

Development Cloudflare Worker for retrieving private gallery objects from Backblaze B2.

## Security model

- Accepts only GET and HEAD.
- Restricts origin access to `B2_ALLOWED_PREFIX` (development: `private/dev/`).
- Uses a dedicated read-only Backblaze B2 application key.
- B2 credentials must be configured as Cloudflare secrets:
  - `B2_ACCESS_KEY_ID`
  - `B2_SECRET_ACCESS_KEY`
- Responses are deliberately `private, no-store` during the initial connectivity phase. CDN caching and LumisPixel authorization will be added separately after private-origin retrieval is validated.

Never commit B2 credentials.

## Development configuration

Non-secret origin settings live in `wrangler.jsonc`. The Cloudflare dashboard must contain the two B2 secrets before deployment/testing.
