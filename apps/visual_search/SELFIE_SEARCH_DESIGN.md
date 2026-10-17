# Selfie search API — development only

POST /api/visual-search/selfie/ (authenticated, multipart/form-data)
- selfie: JPEG, PNG or WebP, max 5 MiB
- biometric_search_consent: literal `yes`

## Required deployment gates

- `VISUAL_SEARCH_FACE_INDEXING_ENABLED=false` by default.
- `VISUAL_SEARCH_SELFIE_API_ENABLED=false` by default.
- `VISUAL_SEARCH_SELFIE_RATE_LIMIT_SHARED_CACHE=false` by default; must be set true **only** after verifying a shared atomic cache backend (e.g. Redis) across every web worker. Local-memory cache is NOT acceptable for deployment.
- `VISUAL_SEARCH_SELFIE_RATE_LIMIT=5` attempts per `VISUAL_SEARCH_SELFIE_RATE_WINDOW=3600` seconds, keyed by authenticated user and connection IP. The limiter fails closed if cache fails.
- `VISUAL_SEARCH_SELFIE_MAX_DISTANCE` is intentionally **unset**. No results are possible until an independently validated, model-specific threshold is configured. Never use the prior uncalibrated 0.35 default.

## Privacy guarantees

Only completed, visible photos within currently public, published, nonexpired galleries whose owners explicitly opted in to processing **and** global discovery may contribute matches. The matched photo's gallery association is verified against the Django database, not trusted from pgvector. Return only public gallery IDs; no distances, private gallery counts, private identities, event metadata, or private membership hints. Selfies and embeddings are not intentionally persisted.

A separate, non-biometric, photographer-controlled invitation channel will be required for requesting private gallery access. Face matching must never confirm private-gallery existence.

## Threshold calibration

Use consented labeled positive/negative pairs with the **same model version**:

```bash
python manage.py calibrate_selfie_threshold path/to/consented_distances.csv --max-false-match-rate 0.001 --min-nonmatches 1000
```

CSV headers: `distance,label`; labels `match` or `nonmatch`. The command reports an empirical candidate, not a production-approved value. Evaluate on an independent holdout, different cameras, lighting, demographics, and gallery sizes; measure false matches at search-scale, not only per-pair FMR. No customer images are needed in the CSV.

## Verification plan (not yet executed in deployed environment)

1. Run `python manage.py test apps.visual_search.test_selfie_api --settings=config.settings_test` with an isolated test database.
2. Run the full visual-search test suite with PostgreSQL and optional disposable vector integration database.
3. In a disposable pgvector database, seed authorized public, expired, private, and revoked galleries with distinct matched photo vectors; verify only authorized public IDs appear.
4. Exercise authenticated and anonymous HTTP requests, invalid/multiple-face uploads, cache outage, concurrency and 429 responses.
5. Verify consent revocation during search and vector deletion retries; validate no private information appears in logs or responses.
6. Validate threshold calibration and recall against independent, consented holdout data.
7. Keep both feature flags disabled for real users until licensing, privacy, operational security and load review are complete.

**Current limitations:** rate limiting is per-user/IP and is not a complete anti-enumeration strategy; synchronous CPU inference can be expensive; a 500-row vector candidate cap may reduce recall; authorization changes between recheck and response are not transactionally locked across the two databases. This is a development implementation, not a production release.
