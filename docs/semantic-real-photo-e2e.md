# Semantic Photo Search: real-photo verification

This is an **opt-in, isolated test**. It does not enable facial search or change production flags. CI still runs the standard regression suites; a real photograph and reviewed CLIP model must be supplied by the operator and are **not** committed to GitHub.

## Prerequisites

1. Use an isolated Django test/staging database and a **separate disposable pgvector database** whose name includes `test`, `e2e`, `scratch`, or `sandbox`. Never point this verification at production.
2. Use a photograph that you own or have permission to process. Keep the original outside the repository.
3. Install `pip install -r requirements-semantic-search.txt` on a CPU-capable test worker.
4. Provision a license-reviewed CLIP-compatible model **locally**. No runtime model downloads are allowed.
5. Set `VISUAL_SEARCH_SEMANTIC_ENABLED=true`, `VISUAL_SEARCH_SEMANTIC_POLICY_APPROVED=true`, `VISUAL_SEARCH_SEMANTIC_MODEL_PATH=/absolute/path/to/local/clip`, and `VISUAL_SEARCH_DATABASE_URL` to the disposable pgvector database. Do **not** set biometric indexing flags.
6. Initialize the disposable schema: `python manage.py setup_semantic_vector_store`.

## Model + real-photo + pgvector smoke

```bash
python manage.py verify_semantic_real_photo \
  --image /absolute/path/to/consented-photo.jpg \
  --query "first dance"
```

Expected: `PASS` with 512-dimensional image and text embeddings, a pgvector cosine distance, gallery-scoped retrieval, and deletion verification. The inserted test row is **rolled back**, even on success. This smoke checks pipeline operation, not search relevance; inspect returned rankings across multiple actual photos separately.

## Gallery-to-client manual end-to-end test

1. On isolated staging, create a gallery and leave Semantic Search off. Upload at least three different real, consented photos (e.g. dancing, cake, sunset).
2. In **Client Access**, turn Semantic Search on and save. Confirm that the API returns `semantic_enabled=true`; verify a semantic indexing job is created for each completed photo.
3. Run a dedicated Celery worker with semantic dependencies and the approved local model. Run `python manage.py reconcile_semantic_index` if a job was missed. Confirm jobs complete and semantic-only pgvector rows exist.
4. As the photographer, search descriptive phrases. Check rankings manually and confirm gallery-specific results; check unrelated descriptions too.
5. Open the gallery as an authorized public or invited client. Confirm only completed, visible photos appear. Check an unauthorized/private gallery and ensure no results or metadata are disclosed.
6. Disable Semantic Search and save. Wait for the purge worker; confirm its vectors are removed. Re-enable and confirm reindexing, then delete one photo and confirm its vector is removed.
7. Confirm `app_face_embeddings` is unchanged and biometric indexing stays disabled.

**Exit criteria:** No errors, no skipped checks, all expected authorized searches succeed, unauthorized access is denied, indexing/purge tasks complete, and there is no change to biometric data. Keep the feature unavailable in production until this checklist is signed off. Never commit real photos or model weights.
