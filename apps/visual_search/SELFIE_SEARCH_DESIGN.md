# Selfie search API — development only

POST /api/visual-search/selfie/ (authenticated, multipart/form-data)
- selfie: JPEG, PNG or WebP, max 5 MiB
- biometric_search_consent: literal `yes`

Feature gates: VISUAL_SEARCH_FACE_INDEXING_ENABLED and VISUAL_SEARCH_SELFIE_API_ENABLED (both default false). No production rollout is authorized. Do not use real customer biometric data until model licensing, consent, retention, privacy, abuse-prevention, and end-to-end testing are complete.

The endpoint requires exactly one detectable face, computes an ephemeral embedding, performs exact cosine-distance search against application-only vectors, and rechecks publication, public visibility, and explicit global discovery consent in the Django DB. Results contain public gallery IDs and distance only; private matches are neither returned nor counted.

**Private galleries:** Face matching alone must never disclose whether a private gallery exists or who appears in it. A future access-request flow must use a separate non-biometric invitation or photographer-controlled channel, with generic responses that do not confirm matches.

**Not yet ready:** request rate limits, anti-enumeration controls, dedicated inference isolation, threshold calibration, retention/privacy review, model license, and production end-to-end tests. Keep both feature flags false until these are addressed. This initial endpoint is for controlled development only.
