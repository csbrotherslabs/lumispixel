# Client selfie-search permission foundation

This change creates account-scoped authorization for **ephemeral public-gallery selfie queries only**. It does **not** authorize photographer gallery indexing, global/private gallery discovery, AI training, or collection of real-person calibration data.

## Rollout controls

- `VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED` defaults to **False** when unset. Do not enable until legal/privacy review approves the notice and the user-facing authorization experience.
- `VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION` defaults to an empty value when unset; a nonempty approved policy version is required to grant and use permission.\n- `VISUAL_SEARCH_CLIENT_CONSENT_NOTICE_URL` must point to an approved, published notice before new permissions can be collected. The privacy page remains accessible for withdrawal when collection is disabled.
- Existing `VISUAL_SEARCH_FACE_INDEXING_ENABLED` and `VISUAL_SEARCH_SELFIE_API_ENABLED` gates remain unchanged and must remain **False** in customer environments pending review and calibration.
- The legacy per-request `biometric_search_consent=yes` check remains necessary, but is not sufficient without a persisted, active, current-version permission.

## Authenticated API

`GET /api/visual-search/selfie/permission/`: returns the current user's authorization status without exposing another user's records.

`POST /api/visual-search/selfie/permission/`: only when consent collection is enabled and a reviewed policy version configured, requires JSON:
```json
{"purpose":"public_gallery_selfie_search","policy_version":"<approved version>","agree":true}
```
Creates a timestamped, purpose-specific record. Idempotent for an active current-version record; a new policy version requires a new explicit agreement. Client email must be verified.

`DELETE /api/visual-search/selfie/permission/`: withdraws all active permissions for this purpose for the authenticated user, even when enrollment and search are disabled. It never changes another user's records. Withdrawn rows remain as audit evidence; a future reauthorization creates a new row.

The API requires Django authentication; unsafe requests are protected by the application's normal CSRF middleware. Only the authenticated account can grant or withdraw.

## Withdrawal and deletion boundary

The current selfie API processes uploaded query images in memory and does not create per-client persistent selfie embeddings. Withdrawal immediately prevents subsequent searches through the permission gate. **This is not a claim that all photographer-owned gallery face vectors have been deleted.** Existing gallery vector purge machinery is scoped to photo/gallery identifiers, not individuals. Individual face deletion, in-flight request cancellation, and propagation to every index/storage/backup must be implemented and verified before any customer biometric indexing rollout.

## Remaining release blockers

- Approved jurisdiction-specific biometric notices, consent text, retention/deletion policy, and client-facing UI.
- Proper end-to-end deletion of individual biometric data, including index membership and backups.
- Concurrency/in-flight processing cancellation guarantees.
- Consented evaluation dataset, calibrated threshold, privacy/security review, and separate release approval.

## Client self-service privacy page

Authenticated users can visit `/api/visual-search/selfie/privacy/` to view permission status and withdraw it even when enrollment is disabled. When an approved notice URL, policy version and collection flag are configured, the page also offers explicit opt-in. The page sets a CSRF cookie; the API uses standard same-origin CSRF protection. The page is not yet linked from the broader client navigation pending UX review.

## In-flight withdrawal

The selfie API rechecks authorization after embedding extraction and after vector matching, suppressing results when a completed withdrawal is observed. This narrows the race window but does not provide atomic cancellation of inference already in progress. Stronger job cancellation/deletion controls remain a launch blocker.

## Client biometric deletion requests

`GET /api/visual-search/selfie/deletion/` returns only the authenticated user's latest request status. `POST` creates an idempotent durable pending review request, withdraws active selfie-query permission atomically, and blocks reauthorization while the request remains pending/in review. The privacy page provides the action and status, and client Account Settings links to the privacy page.

**Important:** Current gallery vectors contain photo/gallery/photographer identifiers but no verified identity-to-face association. It is not technically safe to delete an individual's vector by using an uncalibrated similarity match, nor to purge entire customer galleries based on a client request. The durable deletion request is intentionally left `pending` for verified review; no automated individual gallery-vector deletion is claimed. Subject-scoped face identifiers, ownership/identity verification, erasure propagation, backup retention handling, and an authorized completion procedure are prerequisites for full erasure. No admin completion API is exposed.

## In-flight request handling

The search API checks active permission before inference, after inference and after matching before returning a response. This is best-effort suppression and **not** a linearizable cancellation guarantee. Strong cancellation will require an explicit request/lease state machine and coordination with biometric processing workers before the selfie API can be enabled.

## Photographer-mediated face-level erasure (draft implementation)

A photographer review inbox is available at `/api/visual-search/selfie/deletion/photographer/`. It lists requests **only** for explicitly account-linked CRM clients who have a gallery owned by the logged-in photographer. It does not enumerate a client's potential matches across private galleries.

A scoped confirmation endpoint takes `gallery_id`, `photo_id`, and `face_index`; it requires a matching deletion request, photographer ownership, and an explicit `Gallery.client.user` relationship to the requester. The pgvector deletion primitive targets only `photo_id + face_index`, not other faces in that photo. A durable review record suppresses that face from public search and blocks future indexing of that entire photo as a conservative anti-resurrection measure.

**Safety gate:** `VISUAL_SEARCH_FACE_DELETION_REVIEW_ENABLED` defaults to false. Do not enable until a verified visual face-slot selection UI and face-index stability/worker reconciliation have been implemented and validated. The current photographer inbox does not provide a reliable visual mapping between a face and its numeric `face_index`; permitting free-form slot entry now could delete the wrong person's embedding. This draft is not yet a production-ready erasure mechanism.

If a photographer cannot identify a requester, report **identity not verified / deletion unresolved**, never **no embeddings exist**. No global matching, automatic absence conclusion, or automatic closure is implemented. A request remains open until all relevant scopes are verified and erasure is confirmed.

The user asked to omit guaranteed in-progress search cancellation; this remains out of scope. Existing permission rechecks are retained.
