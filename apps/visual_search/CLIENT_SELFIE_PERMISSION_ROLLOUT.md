# Client selfie-search permission foundation

This change creates account-scoped authorization for **ephemeral public-gallery selfie queries only**. It does **not** authorize photographer gallery indexing, global/private gallery discovery, AI training, or collection of real-person calibration data.

## Rollout controls

- `VISUAL_SEARCH_CLIENT_CONSENT_COLLECTION_ENABLED` defaults to **False** when unset. Do not enable until legal/privacy review approves the notice and the user-facing authorization experience.
- `VISUAL_SEARCH_CLIENT_CONSENT_POLICY_VERSION` defaults to an empty value when unset; a nonempty approved policy version is required to grant and use permission.
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
