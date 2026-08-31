# NAVE V28.7.3 — Current Governed Checkpoint

## Current phase

Latest functional checkpoint: **V28.7.3B2.12.2 — Semantic Eligibility & Core Obligation Hardening**.

B2.12.1 proved that automatic adjudication can replace row-by-row manual classification, but the JOVI Golden exposed a more fundamental boundary problem: a historical Requirement identity can still appear as Current `verified` because it has Evidence/Occurrence even when C0/H3 has already classified the underlying signal as scope, attribute, context, reference or example.

B2.12.2 therefore hardens the **response-adjudication boundary** without mutating Requirement Truth.

`recommend_confirm` remains **not** `verified_response`, **not** Human Review, has **no Truth effect**, performs **no persistence**, and does **not** approve cutover.

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
- B2.12.2 — Semantic Eligibility & Core Obligation Hardening

## B2.12.1 Golden finding

### Chambinho

B2.12.1 was accepted:
- queue 3;
- Press kit / Seeding → `recommend_confirm`;
- Promotores e monitores → `recommend_partial`;
- Cobertura de foto e vídeo → `recommend_reject`;
- `Restrição de verba e estrutura` remained excluded.

### JOVI

B2.12.1 was **not** accepted as a Golden checkpoint:
- input queue 33;
- 3 `recommend_confirm`;
- 10 `recommend_partial`;
- 20 `recommend_reject`.

Critical findings:
- `Storytelling detalhado` received a false `recommend_confirm` even though the requirement semantic layer had previously defined platform/example/context signals as no-domain;
- travel product activation was incorrectly left partial from a travel-inspired press kit because a distant `PR activation` token contaminated the evidence window;
- a food-service mention was treated as partial support for a financial/budget-reduction obligation;
- physical stage semantics were vulnerable to the idiom `set the stage`;
- several display titles were truncated and therefore unsafe as the sole canonical atom source.

## B2.12.2 contract

### 1. Semantic Eligibility

Response adjudication reuses C0/H3 semantic decisions.

Explicit no-domain roles are excluded **before** response adjudication:
- channel/platform/deliverable scope;
- product/experience attribute;
- audience/strategy/form context;
- reference/solution reference;
- suggestion/example;
- parameter;
- constraint qualifier.

These rows are not `recommend_reject`; they are not treated as Requirement response questions.

Machine-verified rows with no explicit semantic eligibility fail closed as `semantic_eligibility_unknown`.

### 2. Canonical Obligation

B2.12.2 derives `canonical_obligation_text` only from:
1. `semantic_observation.attributes.source_atom`; or
2. the matching source clause in the current Evidence Unit attached to that semantic observation.

It does **not** concatenate arbitrary description/source_excerpt text.

The display title remains visible for UX and identity, but does not silently truncate the obligation contract.

### 3. Canonical atom recalibration

B2.9 recall candidates are recalibrated using the full canonical obligation before the review queue is rebuilt.

Therefore the B2.12.2 JOVI queue is **not expected to remain 33**. A lower queue count is desirable when pseudo-requirements are removed or canonical qualifiers make unsafe recall candidates fall out.

### 4. Locality-aware core guards

B2.12.2 adds conservative guards for:
- financial/budget obligations;
- travel-themed product activation;
- physical stage + LED/screen;
- platform-format qualifiers including horizontal/vertical.

Locality is explicit: an unrelated token elsewhere in a multi-paragraph candidate window cannot satisfy a compound core obligation.

## Governance freeze

Until a later explicit phase is separately designed and approved:

- do **not** set or activate `domain_primary`;
- do **not** change the governed requirements `read_mode` away from `shadow_compare`;
- do **not** treat PASS or recommendation output as cutover approval;
- do **not** persist machine recommendations as Human Review;
- do **not** synthesize Human Review from algorithmic classes;
- do **not** change active briefing/matrix requirement canaries;
- do **not** relax matcher thresholds merely to increase recall;
- do **not** reprocess Golden masters as part of this phase;
- do **not** auto-merge Requirement identities;
- do **not** run SQL for B2.12.2.

## Golden run required now

Open **Automated Adjudication Recommendations**.

Expected version marker:

`V28.7.3B2.12.2`

Run order:
1. Chambinho;
2. inspect/export JSON;
3. only after Chambinho review, JOVI.

Required package fields include:
- `current_requirement_count_before_semantic_gate`;
- `semantic_eligible_requirement_count`;
- `semantic_excluded_no_domain_count`;
- `semantic_unknown_count`;
- `queue_count`;
- recommendation distribution;
- `semantic_excluded_rows`;
- `recommendation_rows`;
- `projection_rows`.

Any `semantic_unknown_count > 0` yields:

`BLOCKED_SEMANTIC_ELIGIBILITY_UNKNOWN`

and blocks any Truth-effect design.

## Next phase — not yet implemented

No B2.13 is approved.

Only after both B2.12.2 Goldens are accepted should the next read-only Truth-effect projection be designed. That later phase must explicitly preserve the distinction among:
- Requirement semantic eligibility;
- requirement Truth;
- response evidence;
- machine recommendation;
- optional Human Review;
- persisted response Truth.

## Repository files for the current checkpoint

- `project_requirement_semantic_eligibility.py`
- `project_requirement_auto_adjudication_hardening.py`
- `pages/32_Automated_Adjudication_Recommendations.py`
- `tests/test_v28_7_3b2_12_2_semantic_hardening.py`
- `GUIA_NAVE_V28_7_3B2_12_2_SEMANTIC_HARDENING.md`
- `project_requirement_auto_adjudication_recommendation.py` — B2.12.1 base scorer retained
- `project_requirement_semantic_recall_bridge.py`
- `project_requirement_obligation_atom_gate.py`
- `project_requirement_response_contract_canary.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

The existing Home navigation continues to point to page 32; page 32 now exposes B2.12.2.
