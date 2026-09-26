# P3 browser/E2E CI gate

The P3 browser gate is the production-facing Chromium smoke layer for LumisPixel. It runs as a dedicated job in the existing Django CI workflow, separately from the broad Django suites, so browser failures are easy to diagnose and do not require using SQLite as a production surrogate.

## Environment

The gate runs with:

- Playwright + headless Chromium
- PostgreSQL 16
- Django test settings
- local gallery storage so CI never depends on B2/Cloudflare
- the complete committed migration graph applied before browser tests

## Required journeys

### Photographer-to-client golden path

`apps/galleries/tests/test_delivery_golden_path.py`

Exercises the rendered photographer login and gallery workflow, creates a gallery, uploads a real image, publishes it, configures client permissions, sends an invitation, opens the secure client delivery in a second browser context, favorites, comments and downloads, then verifies the persisted analytics/comment records and photographer-visible engagement.

### Mobile client gallery journey

`apps/galleries/tests/test_client_mobile_designs.py`

Exercises the real client gallery at a phone viewport across Standard, Story, Masonry and Cinematic designs. It checks viewport safety, lightbox behavior, AJAX favorite/comment behavior, downloads, share/QR controls and persisted engagement records.

### Access-control browser matrix

`apps/galleries/tests/test_client_permission_browser_matrix.py`

Checks that browser-visible controls agree with server authorization. Disabled permissions, download expiration and revoked tokens must hide the relevant UI and also block direct endpoint access.

### Photographer onboarding persistence

`apps.photographers.tests.PhotographerOnboardingBehaviorTests`

Runs the existing onboarding persistence contracts in the same PostgreSQL E2E environment so profile, location, business and theme/onboarding state changes remain covered alongside the browser journeys.

## Test-discovery policy

`apps/galleries` currently contains both a legacy `tests.py` module and a `tests/` directory. The browser modules are therefore invoked by filesystem path. This keeps Playwright out of broad test discovery while avoiding the `apps.galleries.tests` module/package collision.

## CI policy

The P3 browser job is intentionally targeted. It must not invoke the full Django suite. The complete PostgreSQL/SQLite suites remain the broad gates, while this job gives focused feedback for browser/client-delivery regressions.
