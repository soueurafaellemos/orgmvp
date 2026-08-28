# NAVE V28.7.3 — Current Governed Checkpoint

## Current phase

Latest functional checkpoint: **V28.7.3B2.11 — Governed Response Recall Review Projection**.

B2.11 is a **read-only projection phase**. It combines the governed response contract from B2.7.1 with calibrated recall from B2.10.1. It does not persist Human Review, alter Truth, change served consumers, or perform cutover.

## Completed governed shadow chain

- B2.1 — Requirement Identity Compatibility
- B2.2 — Relational Consumer Shadow
- B2.3 — Matrix requirements canary projection
- B2.4 / B2.4.x — Unified requirement reconciliation, input/semantic/evidence-role/residual audits
- B2.4.6 — Cross-Domain Residual Placement
- B2.5 — Semantic Ownership & Response Evidence Shadow
- B2.6 — Response Entailment Shadow
- B2.7.1 — Requirement Response Contract denominator correction
- B2.8 — Response Evidence Recall Shadow
- B2.9 — Multilingual Semantic Recall Bridge Shadow
- B2.10 — Obligation Atom Gate Golden run; superseded for precision by B2.10.1
- B2.10.1 — Canonical requirement-title atom calibration
- B2.11 — Governed Response Recall Review Projection

## B2.10.1 Golden result accepted for progression

### Chambinho

10 requirements were scanned in recall scope.
Best disposition per requirement:
- 1 `HIGH_CONFIDENCE_REVIEW_CANDIDATE`;
- 2 `PARTIAL_OBLIGATION_COVERAGE`;
- 7 `NO_CANDIDATE`.

Controls passed:
- `Item para ser incluído no press kit / Seeding` → high-confidence review;
- `Promotores e monitores` → partial with promoter missing;
- `Cobertura de foto e vídeo` → partial with video missing;
- `Restrição de verba e estrutura` → no candidate;
- direct cenography payment requirement → no candidate.

### JOVI

75 requirements were scanned in recall scope.
Best disposition per requirement:
- 3 `HIGH_CONFIDENCE_REVIEW_CANDIDATE`;
- 30 `PARTIAL_OBLIGATION_COVERAGE`;
- 8 `REJECT_SOURCE_ROLE_NON_RESPONSE`;
- 8 `REJECT_GENERIC_OVERLAP`;
- 26 `NO_CANDIDATE`.

The three high-confidence requirements are semantically defensible review candidates:
- graphic materials: invitation + Save the Date + Reminder;
- venue with plenary space;
- detailed storytelling.

Important negative controls also passed:
- Gift Out requiring 3+ options remained partial because quantity was missing;
- registration/no-queue/foreign constraints remained partial;
- streaming/recording/next-day did not become high-confidence;
- premium portrait lighting remained partial;
- movement performance remained partial;
- satisfaction survey remained partial;
- generic creative/logistics overlap did not become high-confidence;
- insights/results/report rejected unrelated agenda overlap;
- BRIEF RECAP / OUR GOAL candidates became `REJECT_SOURCE_ROLE_NON_RESPONSE`.

## B2.11 contract

B2.11 projects one status per Current Domain requirement:

- `verified_response`
- `response_review_high_confidence`
- `response_review_visual_or_structured_evidence`
- `response_review_partial`
- `response_review_existing_evidence`
- `false_positive_excluded`
- `no_safely_verified_response`

Critical governance rule:

**Only B2.7.1 `verified_response` remains verified.**

No B2.10.1 recall result can create Truth. Even `STRICT_SAFE_AUTO_PRESERVED` is projected as review-only in B2.11.

Cross-domain semantic responses remain preserved separately and are not converted into requirement compliance.

## Governance freeze

Until a later explicit phase is separately designed and approved:

- do **not** set or activate `domain_primary`;
- do **not** change the governed `read_mode` from `shadow_compare` for requirements;
- do **not** treat PASS/PASS_WITH_REVIEW as cutover approval;
- do **not** persist B2.10.1/B2.11 review candidates as Truth automatically;
- do **not** synthesize Human Review from algorithmic review classes;
- do **not** change active briefing/matrix canaries;
- do **not** relax matcher thresholds to increase recall;
- do **not** reprocess Golden masters as part of this phase;
- do **not** auto-merge identity concepts such as Pelúcia ↔ Chaveiro.

Current requirement Truth remains constrained to valid provenance and the Current Domain reader only surfaces requirement truth rows in `verified` or `human_confirmed` state.

## Golden run required now

Run `Governed Response Recall Review Projection` for both Golden projects.

Expected UI/version marker:

`V28.7.3B2.11`

Expected CSV name:

`NAVE_B2_11_RESPONSE_RECALL_REVIEW_<project_id>.csv`

Export the CSV for Chambinho and JOVI. Inspect every `response_review_high_confidence` row manually before designing persistence.

## Next phase — not yet implemented

Only after B2.11 Golden outputs are manually reviewed and semantically clean should a separate **Human Review adjudication/persistence contract** be designed.

That future phase must require explicit human decisions and provenance. It must not convert B2.11 review classes into Truth automatically.

## Repository files for the current checkpoint

- `project_requirement_response_recall_review_projection.py`
- `pages/30_Governed_Response_Recall_Review_Projection.py`
- `tests/test_v28_7_3b2_11_response_recall_review_projection.py`
- `GUIA_NAVE_V28_7_3B2_11_RESPONSE_RECALL_REVIEW_PROJECTION.md`
- `project_requirement_obligation_atom_gate.py`
- `pages/29_Requirement_Obligation_Atom_Gate.py`
- `tests/test_v28_7_3b2_10_1_atom_gate.py`
- `GUIA_NAVE_V28_7_3B2_10_1_CANONICAL_ATOM_FIX.md`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

The Home navigation now points to page 30 for B2.11.
