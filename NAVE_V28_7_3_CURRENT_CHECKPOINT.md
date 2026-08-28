# NAVE V28.7.3 — Current Governed Checkpoint

## Current phase

Latest functional checkpoint: **V28.7.3B2.12 — Human Response Adjudication Contract**.

B2.12 is a **human review contract and export phase**. It converts B2.11 review rows into explicit human decisions with provenance, but it does **not** persist Human Review, alter Truth, change served consumers, or perform cutover.

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
- B2.12 — Human Response Adjudication Contract

## B2.11 Golden result accepted for B2.12

### JOVI

B2.11 projected:
- 75 Current Domain requirements;
- 0 `verified_response`;
- 3 `response_review_high_confidence`;
- 30 `response_review_partial`;
- 42 `no_safely_verified_response`;
- 8 source-role rejections;
- 8 generic-overlap rejections;
- 0 strict-safe recall candidates;
- `cutover_approved=false`;
- `persistence_performed=false`.

High-confidence candidates manually accepted as defensible **review**, not Truth:
- graphic materials: invitation + Save the Date + Reminder;
- venue with plenary space;
- detailed storytelling.

Important negative controls remained conservative:
- Gift Out requiring 3+ options remained partial because `minqty:3` was missing;
- registration remained partial with queue-free/foreign/communication qualifiers missing;
- streaming remained no-safe-response with live/recording/streaming/next-day missing;
- satisfaction survey remained partial rather than being inferred from gift distribution;
- insights/results/report rejected irrelevant overlap.

B2.12 expected editable JOVI queue: **33 rows** = 3 high-confidence + 30 partial.

### Chambinho

B2.11 projected:
- 13 Current Domain requirements;
- 3 `verified_response`;
- 1 `response_review_high_confidence`;
- 2 `response_review_partial`;
- 1 `false_positive_excluded`;
- 6 `no_safely_verified_response`;
- `cutover_approved=false`;
- `persistence_performed=false`.

Controls:
- Press kit / Seeding → high-confidence review;
- Cobertura de foto e vídeo → partial, video missing;
- Promotores e monitores → partial, promoter missing;
- Restrição de verba e estrutura → false positive remains excluded.

B2.12 expected editable Chambinho queue: **3 rows**.

## B2.12 contract

Only B2.11 review statuses enter the editable adjudication queue:

- `response_review_high_confidence`
- `response_review_visual_or_structured_evidence`
- `response_review_partial`
- `response_review_existing_evidence`

Already-verified responses are not re-adjudicated. `false_positive_excluded` and `no_safely_verified_response` remain visible as non-editable audit context and are not silently promoted into a review queue.

### Allowed explicit human decisions

- `confirm_response` — Confirmar resposta
- `partial_response` — Resposta parcial
- `reject_match` — Rejeitar correspondência
- `visual_structured_review` — Requer revisão visual/estruturada
- `defer` — Adiar decisão

Nothing is selected by default. The UI placeholder `— Selecione —` is not a decision.

Any explicit decision requires a reviewer identity. Confirm/partial/reject also require a human rationale.

### Provenance

Every B2.12 candidate gets a stable `candidate_id` and exports a frozen snapshot containing:
- project and requirement identity;
- canonical requirement title;
- current Truth state at review time;
- B2.11 projected status/reason;
- current response evidence snapshot;
- recall evidence id/source/page/text;
- obligation atoms, shared/missing/hard-missing atoms;
- B2.11, B2.10.1 and B2.7.1 algorithm versions;
- human decision, rationale, reviewer and timestamp.

Every exported row explicitly contains `truth_effect_applied=false` and `persistence_performed=false`.

### Package states

- `EMPTY_DRAFT`
- `PARTIAL_DRAFT`
- `INVALID_DRAFT`
- `COMPLETE_REVIEW_PACKAGE`

`COMPLETE_REVIEW_PACKAGE` means every review row received an explicit valid human decision. It still does **not** mean Truth changed.

## Governance freeze

Until a later explicit phase is separately designed and approved:

- do **not** set or activate `domain_primary`;
- do **not** change the governed `read_mode` from `shadow_compare` for requirements;
- do **not** treat PASS or COMPLETE_REVIEW_PACKAGE as cutover approval;
- do **not** persist B2.12 decisions into Truth automatically;
- do **not** synthesize Human Review from algorithmic review classes;
- do **not** change active briefing/matrix canaries;
- do **not** relax matcher thresholds to increase recall;
- do **not** reprocess Golden masters as part of this phase;
- do **not** auto-merge identity concepts such as Pelúcia ↔ Chaveiro.

Current requirement Truth remains constrained to valid provenance and the Current Domain reader only surfaces requirement truth rows in `verified` or `human_confirmed` state.

## Golden run required now

Open `Human Response Adjudication Contract` for both Golden projects.

Expected version marker:

`V28.7.3B2.12`

Expected queue sizes:
- JOVI: 33
- Chambinho: 3

Adjudicate every review row explicitly. Use `defer` where the evidence cannot responsibly support a decision yet. Do not confirm a response merely because B2.11 called it high-confidence.

Expected exports:

`NAVE_B2_12_HUMAN_ADJUDICATION_<project_id>.csv`

`NAVE_B2_12_HUMAN_ADJUDICATION_<project_id>.json`

Only a `COMPLETE_REVIEW_PACKAGE` should be used as input for designing the next phase.

## Next phase — not yet implemented

After both Golden B2.12 packages are manually reviewed, design a separate **V28.7.3B2.13 — Human Review Truth-Effect Projection**.

B2.13 must begin read-only. It may project what effect explicit B2.12 decisions would have on requirement-response Truth, but must not persist those effects until a later separately approved write path exists.

## Repository files for the current checkpoint

- `project_requirement_human_response_adjudication_contract.py`
- `pages/31_Human_Response_Adjudication_Contract.py`
- `tests/test_v28_7_3b2_12_human_response_adjudication_contract.py`
- `GUIA_NAVE_V28_7_3B2_12_HUMAN_RESPONSE_ADJUDICATION.md`
- `project_requirement_response_recall_review_projection.py`
- `pages/30_Governed_Response_Recall_Review_Projection.py`
- `project_requirement_obligation_atom_gate.py`
- `pages/29_Requirement_Obligation_Atom_Gate.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

The Home navigation now points to page 31 for B2.12.
