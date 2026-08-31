# NAVE V28.7.3 — Current Governed Checkpoint

## Current phase

Latest functional checkpoint: **V28.7.3B2.12.1 — Automated Response Adjudication Recommendations**.

B2.12 proved the explicit Human Response Adjudication provenance contract, but the row-by-row workflow is not acceptable as the default operating model. B2.12.1 therefore evaluates the entire B2.12 review queue automatically and emits **machine recommendations only**.

`recommend_confirm` is **not** `verified_response`, is **not** Human Review, has **no Truth effect**, performs **no persistence**, and does **not** approve cutover.

The B2.12 manual page remains available only as an optional audit/provenance mechanism.

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
- B2.12.1 — Automated Response Adjudication Recommendations

## Golden baseline entering B2.12.1

### JOVI

B2.11 projected:
- 75 Current Domain requirements;
- 0 `verified_response`;
- 3 `response_review_high_confidence`;
- 30 `response_review_partial`;
- 42 `no_safely_verified_response`.

B2.12 manual queue size: **33 rows** = 3 high-confidence + 30 partial.

Known precision controls that must remain conservative include Gift Out 3+, registration qualifiers, streaming/next-day, satisfaction survey, direct-payment obligations, co-investment, bilingual promoters, independence without partnerships, platform-format constraints, backstage and recap-video obligations.

### Chambinho

B2.11 projected:
- 13 Current Domain requirements;
- 3 `verified_response`;
- 1 `response_review_high_confidence`;
- 2 `response_review_partial`;
- 1 `false_positive_excluded`;
- 6 `no_safely_verified_response`.

B2.12 manual queue size: **3 rows**:
- Press kit / Seeding → high-confidence review;
- Cobertura de foto e vídeo → partial, `video` missing;
- Promotores e monitores → partial, `promoter` missing.

`Restrição de verba e estrutura` remains excluded as a false positive and must not be silently reintroduced.

## B2.12.1 contract

Every B2.12 review candidate receives exactly one machine recommendation:

- `recommend_confirm`
- `recommend_partial`
- `recommend_reject`
- `recommend_visual_review`
- `recommend_defer`

The engine applies high-precision semantic guards before governed obligation coverage/anchor signals. The output preserves the full candidate/provenance snapshot plus machine confidence, rule id and rationale.

### Governance semantics

Machine recommendation is deliberately separated from Human Review and Truth:

- `adjudicator_type = machine_rule_engine`
- `human_review_created = false`
- `truth_changed = false`
- `persistence_performed = false`
- `cutover_approved = false`

A `recommend_confirm` row therefore means only that the evidence is strong enough for this **shadow machine recommendation layer**. It must never be consumed as `verified_response` by convention.

## Governance freeze

Until a later explicit phase is separately designed and approved:

- do **not** set or activate `domain_primary`;
- do **not** change the governed requirements `read_mode` away from `shadow_compare`;
- do **not** treat PASS, recommendation output, or any B2.12/B2.12.1 package as cutover approval;
- do **not** persist machine recommendations as Human Review;
- do **not** synthesize Human Review from algorithmic classes;
- do **not** change active briefing/matrix requirement canaries;
- do **not** relax matcher thresholds just to increase recall;
- do **not** reprocess Golden masters as part of this phase;
- do **not** auto-merge identity concepts such as Pelúcia ↔ Chaveiro.

Current requirement Truth remains constrained to valid provenance and the Current Domain reader only surfaces requirement truth rows in `verified` or `human_confirmed` state.

## Golden run required now

Open **Automated Adjudication Recommendations** for both Golden projects.

Expected version marker:

`V28.7.3B2.12.1`

Expected queue sizes:
- JOVI: 33
- Chambinho: 3

No reviewer, dropdown or row-by-row justification is required.

Run **Chambinho first**, inspect/export the automated result, then run JOVI. Review the recommendation distribution and obvious precision controls before designing any Truth-effect or persistence layer.

## Next phase — not yet implemented

Only after both Golden B2.12.1 outputs are accepted should the next governed phase be designed.

That next phase must remain **read-only first** and explicitly define how machine recommendations, optional Human Review, and valid provenance may be projected without silently mutating requirement-response Truth. No persistence path is approved by this checkpoint.

## Repository files for the current checkpoint

- `project_requirement_auto_adjudication_recommendation.py`
- `pages/32_Automated_Adjudication_Recommendations.py`
- `tests/test_v28_7_3b2_12_1_auto_adjudication.py`
- `GUIA_NAVE_V28_7_3B2_12_1_AUTO_ADJUDICATION.md`
- `project_requirement_human_response_adjudication_contract.py`
- `pages/31_Human_Response_Adjudication_Contract.py`
- `project_requirement_response_recall_review_projection.py`
- `pages/30_Governed_Response_Recall_Review_Projection.py`
- `project_requirement_obligation_atom_gate.py`
- `pages/29_Requirement_Obligation_Atom_Gate.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

The Home navigation must expose page 32 as **Automated Adjudication Recommendations**. Page 31 remains visible only as the optional/manual audit path.
