# Face indexing worker — development only

This branch adds a functional inference adapter and pgvector writer, but the
rollout is **not yet ready for real-user biometric data**. The pretrained
InsightFace model pack must be separately licensed for commercial use. Do not
enable the flag until licensing, consent collection, deletion/revocation hooks,
and isolation of the vector database have been verified.

## Development setup

1. Use an isolated PostgreSQL database for `VISUAL_SEARCH_DATABASE_URL` with
   pgvector available. Never point it at production or at a benchmark database
   unless that is explicitly intended.
2. Install `requirements-visual-search.txt` on the dedicated indexing worker.
3. Provision a licensed InsightFace model pack offline. Configure
   `VISUAL_SEARCH_MODEL_PATH` to the InsightFace model root, and
   `VISUAL_SEARCH_MODEL_PACK=buffalo_l` only if that exact pack is licensed.
4. Run `python manage.py setup_face_vector_store` on the isolated dev database.
   This creates `visual_search.app_face_embeddings`, not the experimental table.
5. Leave `VISUAL_SEARCH_FACE_INDEXING_ENABLED=false` until consent and purge
   paths are complete. `GalleryFaceSearchPolicy.processing_authorized` must
   be true for each eligible gallery; the global discovery flag remains false.
6. Run Celery on a dedicated queue/worker after configuring appropriate
   resource limits. The indexing task currently uses the default queue.
7. Pending jobs can be redispatched with
   `python manage.py dispatch_face_index_jobs --limit 100`.

## Limitations before production

- No selfie-search API or global discovery endpoint exists.
- A separate database transaction cannot be atomically committed together
  with the Django app database. Deletion and consent revocation need a durable
  purge workflow, including handling in-flight jobs, before real use.
- The model adapter assumes 512-dimensional normalized embeddings.
- Do not create an ANN index before evaluating real-data recall and costs.
- The model is loaded for each task in this first iteration; add a worker-level
  singleton after validating concurrency and memory usage.
- No mobile-specific inference code is needed; clients will call backend APIs.
