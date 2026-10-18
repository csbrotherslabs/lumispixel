# Consented real-world selfie-search calibration — execution plan

**Status: planning only.** No real-person data has been collected, no operational threshold has been validated, and no customer biometric feature is authorized for activation. This plan complements `CONSENTED_CALIBRATION_READINESS.md`.

## Phase 0 — written go/no-go prerequisites
1. Identify the exact face embedding model, preprocessing pipeline, versions, commercial licenses, deployment region and permitted uses. Record model hash and reproducibility instructions.
2. Obtain documented legal/privacy review for every intended jurisdiction, including biometric notice and informed, specific, revocable opt-in; minors excluded from the initial study. No scraping, repurposing customer galleries, or automatic enrollment.
3. Approve plain-language participant information: why face embeddings are used, who can access them, retention/deletion windows, withdrawal process, risks, whether any external processors are involved, and whom to contact.
4. Design a separately permissioned evaluation environment with encryption, least privilege, audit logs, data minimization, fixed deletion deadlines, and tested withdrawal/deletion propagation to derived embeddings, pairs, backups and exports.
5. Establish independent sign-off owners for privacy/legal, security, ML evaluation and product. No collection begins without all approvals.

## Phase 1 — protocol and consented recruitment
- Recruit consenting **adults** across realistic photographic conditions (pose, lighting, camera type, crowd size, occlusion and image quality). Record voluntary demographic attributes only where lawful, explicitly consented and needed for fairness evaluation.
- Store consent receipts, provenance, withdrawal status, retention deadline, model/dataset version and capture metadata separate from embeddings. Use pseudonymous subject identifiers.
- Set sample-size targets **before** analysis based on the desired false-match upper confidence bound; a tiny study cannot substantiate rare false-match rates.
- Partition **by individual** into development and locked holdout before any pair generation. No subject, image, near-duplicate or capture session may leak across partitions. Define genuine and impostor comparisons, including lookalikes and large gallery candidate sets.
- Pre-register target operating metrics, acceptable failure rates, subgroup minimum sample sizes and quality-rejection policy. Do not select these thresholds after seeing holdout results.

## Phase 2 — offline calibration (development partition only)
- Version and freeze face detection, quality checks, alignment, embedding and distance metric. Reject no-face, multiple-face and low-quality inputs safely.
- Evaluate distance distributions, genuine acceptance, false matches, false nonmatches and confidence intervals; document counts, gallery sizes and class balance.
- Use the existing `calibrate_selfie_threshold` management command **only on development distances** to propose a threshold. Preserve reproducible input manifests, command parameters and results.
- Test realistic *one-to-many* searches, not merely pairwise accuracy. Measure false discovery per selfie query at anticipated index sizes and whether search can infer membership.
- Independently assess subgroup disparities and uncertainty; do not claim fairness from small or nonrepresentative samples.

## Phase 3 — untouched holdout and adversarial checks
- Freeze threshold and pipeline before running holdout once. Report overall and subgroup false-match/false-nonmatch rates with confidence intervals and sample sizes, plus per-query false discoveries across gallery sizes.
- Include nonmembers, lookalikes, duplicate captures, low-quality/selfie spoof attempts, expired galleries, withdrawn consent, index deletion and stale embeddings.
- Assert privacy invariants: private galleries and their names, photographers, locations, event metadata and membership must never be revealed through selfie-search responses. Private access is available **only** through independently issued photographer invitation tokens.
- Test withdrawal end-to-end: prevent further matching, remove indexed data and derived artifacts, verify deletion and record audit evidence.

## Phase 4 — launch decision (separate change request)
Required evidence: model/license approval; consent and deletion audits; frozen protocol and manifests; development calibration report; untouched holdout report with uncertainty; privacy/security review; performance/cost test; incident response and kill-switch drills; named sign-offs.

**No-go** if any gate is missing, any private-gallery enumeration is possible, deletion is incomplete, or measured false-match risk exceeds the pre-registered target. If evidence is insufficient, gather a new independently consented dataset under a new approved protocol; never tune on the holdout.

A successful study would support a *separate*, explicitly reviewed configuration proposal for `VISUAL_SEARCH_SELFIE_MAX_DISTANCE` and biometric feature flags. This planning PR must not set that threshold or enable indexing/search.

## Current private-gallery verification
The new `test_private_gallery_lifecycle_e2e.py` exercises photographer-issued invitation, requester submission, owner inbox, cross-owner denial, approval and single access token, denial without token, and revocation/expiration failure. It uses synthetic accounts and mocked email delivery. The existing Chromium inbox suite verifies navigation, mobile and review UI; together these provide layered integration coverage, **not** a live end-user delivery test or biometric accuracy evidence.

## Next operational deliverables
1. Review the consent document and data-retention/deletion specification with counsel and security.
2. Produce a versioned evaluation dataset schema and collection protocol, with a deletion test plan.
3. Pre-register metrics, confidence-interval method, minimum cohort sizes and pass/fail gates.
4. Only after written approvals, recruit adult volunteers and perform offline development/holdout calibration.
