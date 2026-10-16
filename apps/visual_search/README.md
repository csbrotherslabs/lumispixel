# Visual search (initial scaffolding)

This milestone provides consent-gated durable indexing jobs only. It does **not**
extract faces, store embeddings, perform search, or expose a mobile/web API.

* `VISUAL_SEARCH_FACE_INDEXING_ENABLED` defaults to false.
* GalleryFaceSearchPolicy must explicitly authorize biometric processing.
* Global discovery is a separate opt-in, default false.
* Both direct B2 multipart completion and conventional Django uploads schedule
  via the same service.
* Jobs are recorded in the application database; the Celery task is currently
  a non-processing stub. Pending jobs can be redispatched using
  `python manage.py dispatch_face_index_jobs` after the inference worker is built.
* Do not enable indexing for real customers until consent, deletion, retention,
  licensed model weights, worker isolation, and security reviews are complete.
* The migration targets the latest galleries migration because GalleryPhoto was
  added after the galleries initial migration.
