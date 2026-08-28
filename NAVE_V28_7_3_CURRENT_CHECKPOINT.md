# NAVE V28.7.3 — Current Governed Checkpoint

## Current phase

Latest functional checkpoint: **V28.7.3B2.10.1 — Canonical Obligation Atom Calibration**.

B2.10.1 is a **read-only review-precision correction**. It does not persist responses, alter Truth, change consumers, or perform cutover.

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
- B2.10 — Obligation Atom Gate Golden run; **superseded for precision by B2.10.1**
- B2.10.1 — Canonical requirement-title atom calibration

## Why B2.10 was superseded

Golden outputs showed that B2.10 could build requirement obligation atoms from surrounding `description` / `source_excerpt` context. This contaminated canonical requirement identity and produced false `HIGH_CONFIDENCE_REVIEW_CANDIDATE` classifications, especially in JOVI.

B2.10.1 therefore:

- derives requirement obligation atoms from the canonical requirement title only;
- treats quantity, options, language, deadline and similar qualifiers as hard constraints;
- rejects `BRIEF RECAP`, `OUR GOAL` and equivalent briefing restatements as non-response source roles;
- prevents long requirements from becoming high-confidence on generic overlap;
- limits surfaced review candidates per requirement;
- keeps every `HIGH_CONFIDENCE_REVIEW_CANDIDATE` as **REVIEW ONLY**.

## Governance freeze

Until a later explicit cutover phase is separately designed and approved:

- do **not** set or activate `domain_primary`;
- do **not** change the governed `read_mode` from `shadow_compare` for requirements;
- do **not** treat PASS/PASS_WITH_REVIEW as cutover approval;
- do **not** persist B2.10.1 review candidates as Truth automatically;
- do **not** change active briefing/matrix canaries;
- do **not** relax matcher thresholds to increase recall;
- do **not** reprocess Golden masters as part of this phase;
- do **not** auto-merge identity concepts such as Pelúcia ↔ Chaveiro.

Current requirement Truth remains constrained to valid provenance and the Current Domain reader only surfaces requirement truth rows in `verified` or `human_confirmed` state.

## Golden rerun required now

Run the existing `Requirement Obligation Atom Gate` page for both Golden projects after deploying B2.10.1.

Expected UI/version marker:

`V28.7.3B2.10.1`

Expected CSV name:

`NAVE_B2_10_1_OBLIGATION_ATOMS_<project_id>.csv`

### Expected Chambinho controls

- `Item para ser incluído no press kit / Seeding` → defensible HIGH_CONFIDENCE REVIEW candidate when press-kit + influencer sendout are both supported.
- `Promotores e monitores` → PARTIAL if only monitores are evidenced.
- `Cobertura de foto e vídeo` → PARTIAL if only foto is evidenced.
- `Restrição de verba e estrutura` → must not recover from unrelated activation evidence.

### Expected JOVI controls

- convite + STD + Reminder ↔ Save the Date + Online invitation + Reminder → defensible HIGH_CONFIDENCE REVIEW candidate.
- `Storytelling detalhado` ↔ deeper storytelling → defensible HIGH_CONFIDENCE REVIEW candidate, never auto-Truth.
- Gift Out requiring 3+ options → PARTIAL unless quantity/options are actually evidenced.
- registration/no-queue/foreign-language constraints → PARTIAL unless all required qualifiers are evidenced.
- F&B vegan/vegetarian → PARTIAL unless dietary requirements are explicit.
- streaming/recording/next-day delivery → not high-confidence unless the full obligation is evidenced.
- generic camera/content/guests/plenary overlap → must not create high-confidence response evidence.
- BRIEF RECAP / OUR GOAL → `REJECT_SOURCE_ROLE_NON_RESPONSE` when used as candidate response evidence.

## Next phase — not yet implemented

Only after B2.10.1 Golden outputs are manually reviewed and semantically clean should the architecture move to a possible **V28.7.3B2.11 — Governed Response Recall Review Projection**.

That future phase should remain read-only and project client-facing response status such as:

- existing `verified_response`;
- `response_review_high_confidence`;
- `response_review_partial`;
- `false_positive_excluded`;
- `no_safely_verified_response`.

It must not relabel high-confidence review as `verified_response`, and persistence/Human Review adjudication must be designed separately.

## Repository files for the current checkpoint

- `project_requirement_obligation_atom_gate.py`
- `pages/29_Requirement_Obligation_Atom_Gate.py`
- `tests/test_v28_7_3b2_10_1_atom_gate.py`
- `GUIA_NAVE_V28_7_3B2_10_1_CANONICAL_ATOM_FIX.md`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

The Home navigation already points to page 29; no navigation rewrite is required for B2.10.1.
