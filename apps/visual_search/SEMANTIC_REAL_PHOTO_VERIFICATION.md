# Semantic search acceptance test

Status: real-photo/CLIP and live broker verification have **not** been executed
by this change. Synthetic integration tests prove persistence and lifecycle
contracts, not photo relevance. Do not enable production flags based on them.

## Isolated environment

Use a disposable staging application database, local media or a dedicated test
bucket, a dedicated Redis broker, and a disposable pgvector database named
`lumispixel_visual_search_test_<suffix>`. Never use production customer photos,
production database URLs, or the research vector database. Record the model's
source, revision, license and approval, plus ownership/license/participant
permission for every photograph. Keep photographs and model weights out of git.

Install `python -m pip install -r requirements-semantic-search.txt` in **both**
the web and worker environments. Provision a reviewed CLIP checkpoint and its
processor/tokenizer locally (512-dimensional projection). No runtime model
downloads are allowed. The dependency range deliberately uses Transformers 4's
CLIP feature API. Freeze validated dependency versions in the staging build.

Set these on web and worker processes in staging only:

```sh
export DJANGO_SETTINGS_MODULE=config.settings_test
export DJANGO_DEBUG=1
export LUMISPIXEL_TEST_SQLITE=1  # automated harness only; staging UI uses PostgreSQL
export VISUAL_SEARCH_DATABASE_URL=postgresql://USER:PASSWORD@HOST/lumispixel_visual_search_test_acceptance
export VISUAL_SEARCH_INTEGRATION_DATABASE_URL="$VISUAL_SEARCH_DATABASE_URL"
export VISUAL_SEARCH_SEMANTIC_ENABLED=1
export VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=1  # only after test-environment policy approval
export VISUAL_SEARCH_SEMANTIC_MODEL_PATH=/absolute/path/to/reviewed-clip-model
export VISUAL_SEARCH_SEMANTIC_MODEL_VERSION=reviewed-checkpoint-revision
export VISUAL_SEARCH_FACE_INDEXING_ENABLED=0
export VISUAL_SEARCH_SELFIE_API_ENABLED=0
export CELERY_BROKER_URL=redis://127.0.0.1:6379/14
export CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/15
python manage.py setup_semantic_vector_store
```

The setup command creates only the isolated semantic table. Facial processing
remains independently disabled. The application itself must also use a
disposable database (`DATABASE_URL`) for the UI journey.

## Automated real-model harness

Create a JSON manifest beside at least four authorized photos, with distinct
scenes and recorded authorization. Each expected photo must rank within top_k;
use top_k=1 initially so returning every photo does not count as success.

```json
{
  "authorization": "Owned test photos; participants authorized this test on YYYY-MM-DD",
  "photos": [
    {"file": "ceremony.jpg", "query": "wedding ceremony", "top_k": 1},
    {"file": "dance.jpg", "query": "people dancing", "top_k": 1},
    {"file": "cake.jpg", "query": "birthday cake", "top_k": 1},
    {"file": "portrait.jpg", "query": "sunset portraits", "top_k": 1}
  ]
}
```

```sh
export SEMANTIC_REAL_PHOTO_MANIFEST=/absolute/path/to/authorized/manifest.json
python manage.py test apps.visual_search.test_semantic_journey.SemanticRealPhotoTests --verbosity 2
```

This creates test gallery/photo records with real files, runs actual CLIP
inference and pgvector ranking, asserts completed jobs, purges, reindexes and
checks deletion. It calls Celery task bodies synchronously; it does **not** prove
broker delivery or the browser upload path. Tests clean up their own semantic
rows. Django rolls back application records. Test media is temporary.

Run deterministic contracts separately:

```sh
python manage.py test apps.visual_search.test_semantic_policy apps.visual_search.test_semantic_journey.SemanticJourneyTests apps.visual_search.test_semantic_vectors --verbosity 2
```

CI retains all existing mandatory gates and adds a real pgvector persistence
job using synthetic vectors. Real photos/model weights are deliberately absent
from ordinary CI; a skipped real-photo test is not acceptance evidence.

## Browser and worker acceptance checklist

1. Remove the harness-only SQLite override; configure isolated PostgreSQL app DB,
   migrate, and start web plus `python -m celery -A config worker -l INFO`.
   Use `python -m celery -A config inspect registered` to confirm semantic tasks.
2. Create a gallery through `/photographer/workspace/galleries/create/`, leaving
   semantic search off. Confirm both Create Gallery buttons use validation and
   repeated clicks produce one submission. Retry after a validation error.
3. Upload the authorized real photos through the normal uploader. Confirm no
   semantic jobs/vectors exist before opt-in. Enable semantic search in Client
   Access and Save. Facial search must remain unavailable.
4. Observe worker logs and `SemanticIndexJob` records until every eligible photo
   is `completed`. Inspect `visual_search.app_semantic_embeddings` for the same
   photo IDs and configured model version. If dispatch failed, use
   `python manage.py reconcile_semantic_index` and investigate worker failures;
   do not treat queued/pending jobs as completed.
5. Search as owner at `/api/visual-search/galleries/<id>/semantic-search/?q=...`
   (confirm exact URL with Django `reverse('visual_search:semantic-search', args=[id])`).
   Search in the normal client gallery UI using all four manifest queries.
   Record top results and human relevance judgments; ranking alone is not an
   accuracy guarantee. Add distracting photos and paraphrases to evaluate quality.
6. Test a second photographer, an unrelated client, invalid/revoked invitation,
   private/public gallery, hidden photo, expired/locked gallery and disabled
   view permission. No unauthorized photo IDs, thumbnails or metadata may leak.
7. Reset semantic settings: verify status says Save is required and persisted
   settings stay unchanged until Save. Check 390px and 1440px layouts, keyboard,
   hover, focus, disabled/loading/error states and button text contrast.
8. Disable and Save; search must immediately deny access. Wait for purge and
   verify zero semantic rows for the gallery. Re-enable and Save; wait for jobs
   and vectors to return. Also test rapid disable/re-enable with queued workers.
9. Delete a photo, wait for cleanup and verify its vector is absent. Compare
   facial-table records before/after semantic operations; they must be unchanged.
   Synthetic pgvector tests also verify this using a face-vector sentinel.
10. Record commit, model revision, photo permissions, dependency versions,
    database/worker versions, job IDs, relevant logs and results. Keep sensitive
    data out of PRs. Mark acceptance passed only once every required step passes.

Production flags remain unchanged. Individual gallery opt-in and separate policy
approval remain required. Real-photo acceptance does not authorize deployment,
production flag changes, facial processing or merging.
