# Contributed face-matching calibration: implementation gate

This phase follows the isolated synthetic pgvector tests. It does **not** establish an operational biometric threshold.

## Prerequisites before collecting data
- Confirm the exact embedding model and commercial redistribution/use license.
- Obtain legal/privacy review for the relevant biometric laws, including notice, consent, retention, deletion, and withdrawal.
- Enroll adults with specific, informed, revocable consent for model evaluation; do not repurpose existing customer galleries.
- Keep data in a separately permissioned evaluation environment with audit logs, encrypted storage, short retention, and documented deletion.
- Maintain provenance and consent records separately from embeddings and evaluation scores.

## Evaluation design
- Split subjects into development and untouched holdout cohorts before generating genuine/impostor pairs.
- Include capture diversity (camera, lighting, pose, image quality) and representative demographic groups.
- Record model version, preprocessing version, dataset version, consent scope, collection date, and withdrawal status.
- Run the existing calibrate_selfie_threshold management command on development distances only. Record sample sizes, target false match rate, threshold candidate and genuine acceptance rate.
- Evaluate holdout at realistic gallery/search index sizes, report per-query false discoveries and false nonmatch rates, confidence intervals and subgroup performance. Do not tune on the holdout.
- Test revoked consent, removal of evaluation subjects, face quality rejection and no-face/multiple-face cases.
- Obtain documented go/no-go approval before configuring VISUAL_SEARCH_SELFIE_MAX_DISTANCE or enabling either face indexing or selfie API.

## Operational status
No consented real-person evaluation dataset is available in this repository. No calibration measurements have been performed. Production biometric flags remain disabled.

## UI milestone
The photographer workspace now has a server-rendered, owner-filtered inbox at /photographer/workspace/galleries/access-requests/. It requires VISUAL_SEARCH_PRIVATE_ACCESS_REQUESTS_ENABLED=True. Review buttons call the existing CSRF-protected, rate-limited approval endpoint. The page is not exposed when the feature is disabled. Photographer navigation placement and complete browser E2E verification remain follow-up work.
