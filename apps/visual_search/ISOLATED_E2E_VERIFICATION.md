# Isolated selfie-search end-to-end verification

This PR adds two distinct test layers:

1. `test_selfie_isolated_journey.py`: HTTP multipart request -> mocked licensed-model inference -> vector adapter -> **real Django ORM authorization**. Uses synthetic vectors, covers public/private, revoked consent, hidden photos, expired and unpublished galleries, spoofed photo/gallery links, and immediate revocation with stale vectors. Runs without model weights or external pgvector.
2. `test_selfie_pgvector_e2e.py`: **opt-in real pgvector** insert -> exact similarity SQL -> real Django authorization -> consent revocation. Uses synthetic normalized vectors and cleans up test embeddings.

## Local/CI isolated verification

```bash
python manage.py test apps.visual_search.test_selfie_isolated_journey apps.visual_search.test_selfie_api --settings=config.settings_test
```

For real pgvector, provision a **disposable** PostgreSQL database whose name begins with `lumispixel_visual_search_test` and which has pgvector installed. Configure `VISUAL_SEARCH_INTEGRATION_DATABASE_URL` to point to that disposable DB. Do **not** use `lumispixel_dev`, production, the research vector store, or a shared database. The test refuses other names. Configure Django's primary `DATABASE_URL` to a database/user authorized to create a separate disposable Django test database, or explicitly enable the project's SQLite test override.

```bash
python manage.py test apps.visual_search.test_selfie_pgvector_e2e --settings=config.settings_test
```

The real pgvector test is skipped when `VISUAL_SEARCH_INTEGRATION_DATABASE_URL` is missing. A skipped test is **not** evidence of successful end-to-end verification.

## Required sign-off

- Confirm isolated Django test and real pgvector test results separately.
- Confirm the vector URL's actual database name and test database isolation (do not paste credentials).
- Validate cache throttling against a shared cache under concurrent requests.
- Calibrate the distance threshold using consented evaluation data and independent holdout.
- Confirm the licensed inference adapter against approved synthetic/test imagery, plus deletion/retry paths.
- Keep `VISUAL_SEARCH_FACE_INDEXING_ENABLED=false` and `VISUAL_SEARCH_SELFIE_API_ENABLED=false` for real users.

No changes to production flags or database connections are included.
