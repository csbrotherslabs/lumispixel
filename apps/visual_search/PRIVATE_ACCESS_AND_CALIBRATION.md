# Private-gallery access requests and consented calibration

## Privacy-preserving private access requests (development only)

The private-gallery request workflow is **not connected to selfie search**. Face search does not return private gallery IDs, identities, event metadata, match counts, or access-request links.

Photographers can create a time-limited opaque invitation for an existing private/password-protected, published gallery, then share the token with an intended recipient **outside face search**. The token is stored only as a SHA-256 digest in the database. The authenticated recipient submits it; the API always responds with the same generic message regardless of token validity. The photographer can review a request. On approval, the existing GalleryInvitation and AccessToken flow is used to send a secure gallery link to the verified requester. GalleryPermission and the existing access views continue to enforce viewing and download rights. Delivery errors leave the request pending for retry.

Endpoints (authenticated, POST, JSON unless otherwise noted):
- `/api/visual-search/private-access/galleries/<gallery_id>/invite/` — photographer owner only, issues 48-hour token (returned once).
- `/api/visual-search/private-access/request/` — `{"invitation_token": "..."}`; generic 202 response.
- `/api/visual-search/private-access/requests/<request_id>/review/` — owner only; `{"decision": "approved"|"denied"}`. Approval uses existing invitation email delivery.\n- `/api/visual-search/private-access/inbox/` — owner-only GET, newest 100 requests.\n- `/api/visual-search/private-access/invitations/<invitation_id>/revoke/` — owner-only POST; prevents future requests using that token.

All endpoints require `VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True`, which is **false by default**. CSRF/session authentication continues to apply. This is a backend-only first slice; there is no photographer UI, email dispatch, gallery permission grant, or token revocation endpoint yet. Mutation endpoints require VISUAL_SEARCH_PRIVATE_ACCESS_SHARED_CACHE=True and an operational shared atomic cache; default false fails closed. Configure VISUAL_SEARCH_PRIVATE_ACCESS_RATE_LIMIT and VISUAL_SEARCH_PRIVATE_ACCESS_RATE_WINDOW as needed. Before enabling, independently verify shared-cache deployment, notification security, mail delivery idempotency, approval/revocation races, UI integration, and abuse monitoring. Revoking a request invitation does not revoke previously issued gallery AccessTokens; revoke those through the gallery access system.

## Real-world similarity calibration: protocol, not a claim of completion

**Do not collect, upload, or process real customer faces solely for calibration without explicit, informed, revocable permission.** Confirm model commercial licensing, applicable biometric privacy laws, data retention/deletion, and independent privacy/security review first.

1. Recruit an appropriately consented evaluation cohort with representation across lighting, devices, pose, skin tones, age ranges, and relevant usage scenarios. Avoid minors unless separately reviewed and legally authorized.
2. Use a separately isolated dataset with access controls, purpose-limited retention, audit trail, and a withdrawal/deletion mechanism. Never reuse production client photos by default.
3. Split by **person**, not by photo, into development and independent holdout sets; prevent near-duplicate leakage.
4. Extract embeddings using the exact commercially licensed production candidate model and preprocessing. Record model version and capture conditions without retaining unnecessary identifiers.
5. Generate genuine and impostor comparison distances, then run:
   `python manage.py calibrate_selfie_threshold consented_distances.csv --max-false-match-rate 0.001 --min-nonmatches 1000`.
6. Validate on the untouched holdout: FMR, false nonmatch rate, precision at expected gallery sizes, subgroup performance, and false discovery per search across the full index. Report confidence intervals. Do not select thresholds on the holdout.
7. Document a go/no-go decision with model version, evaluation date, consent provenance, threshold, retention/deletion sign-off, and rollback plan. Do not enable flags until approved.

The calibration command only reports a **candidate** threshold. No real consented dataset or validated production threshold has been supplied or used in this PR.

## Local verification

```bash
python manage.py test apps.visual_search.test_private_access --settings=config.settings_test
python manage.py makemigrations --check --dry-run visual_search --settings=config.settings_test
```

No production data, biometric indexing, or production environment flags are changed.
