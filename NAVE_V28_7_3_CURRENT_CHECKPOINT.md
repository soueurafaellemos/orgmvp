# NAVE V28.7.3 — Current Governed Checkpoint

## Current recovery phase

Active corrective checkpoint: **V28.7.2C0.2.4H3.1 — Cross-Unit Structural Context & Golden Verifier Repair**.

The downstream B2 chain remains preserved through **V28.7.3B2.12.2.1**, but JOVI is
blocked from B2.13 because B2.12.2.1 exposed an upstream Requirement Truth regression.

## Why H3.1 reopened the upstream layer

JOVI B2.12.2.1 returned:

- Current Requirements before semantic gate: 75
- Semantic eligible: 75
- Semantic no-domain excluded: 0
- Semantic unknown: 0
- canonical identity collisions: 1
- recommendation queue: 35
- 3 confirm / 5 partial / 27 reject

`Storytelling detalhado.` remained a Current `requirement_candidate` and received
`recommend_confirm`. `Performance com muito movimento;`, `Mini show ao vivo;`,
`Frequentadores de festivais de música;` and `Universo da moda e lifestyle.` also
remained Current Requirement identities.

The response adjudicator was no longer the root cause.

### Root cause 1 — cross-Evidence-Unit structural blind spot

H3 legacy recall found a nominal bullet inside the current Evidence Unit and therefore
never considered the immediately preceding Evidence Units that carried its semantic
parent. This allowed audience/platform/example children to fall through to legacy
Requirement fallbacks.

### Root cause 2 — false-green Golden verifier

The H3 verifier compared `lower(trim(title))` with punctuation-free regression strings.
Terminal `.` / `;` therefore allowed forbidden Current Requirements to escape the gate.

H3.1 repairs both at the upstream Requirement reconciliation boundary.

## H3.1 architecture

- `project_requirement_semantic_h31.py`
  - reuses H3 collection;
  - repairs only legacy-recall cross-unit structural parent semantics;
  - does not reclassify Evidence-first output;
  - explicit obligations are not demoted;
  - human-confirmed Requirement Truth is preserved;
  - failure to inspect human-confirmed Truth blocks the run.

- `project_requirement_reconciliation_h31.py`
  - reuses H3 planner + installed C0.2.4 RPC;
  - stamps H3.1 provenance on the bundle/run/materialized new objects;
  - no auto-merge of existing Requirement identities.

- normal `project_intelligence_pipeline.py` remains unchanged during Golden validation;
  H3.1 is invoked only from the explicit governed repair page.

- `pages/33_Requirement_Semantic_Truth_Repair.py`
  - explicit governed UI for the H3.1 repair;
  - requires requirements `shadow_compare`;
  - no master reprocessing.

- `NAVE_V28_7_2C0_2_4H3_1_VERIFY_GOLDEN_JOVI.sql`
  - read-only;
  - terminal-punctuation normalization;
  - positive role proofs for the known cross-unit regression controls.

## Downstream B2 chain preserved

Completed/implemented shadow chain remains:

- B2.1 — Requirement Identity Compatibility
- B2.2 — Relational Consumer Shadow
- B2.3 — Matrix requirements canary projection
- B2.4 / B2.4.x — Unified requirement reconciliation/input/semantic/evidence-role/residual audits
- B2.4.6 — Cross-Domain Residual Placement
- B2.5 — Semantic Ownership & Response Evidence Shadow
- B2.6 — Response Entailment Shadow
- B2.7.1 — Requirement Response Contract denominator correction
- B2.8 — Response Evidence Recall Shadow
- B2.9 — Multilingual Semantic Recall Bridge Shadow
- B2.10 / B2.10.1 — Obligation Atom Gate calibration
- B2.11 — Governed Response Recall Review Projection
- B2.12 — Human Response Adjudication Contract
- B2.12.1 — Automated Response Adjudication Recommendations
- B2.12.2 — Semantic Eligibility & Core Obligation Hardening
- B2.12.2.1 — Semantic Precedence Veto + Hard Qualifier Hotfix

B2.12.2.1 itself remains useful and its core guards were validated. It is **not** being
rolled back. It will be rerun only after H3.1 repairs Requirement Truth.

## B2.12.2.1 findings that remain valid

JOVI confirmed correct downstream hardening for:

- travel press kit ≠ travel product activation;
- food service ≠ financial/budget response;
- direct payment qualifier;
- bilingual promoters;
- co-investment;
- recap video + horizontal/vertical formats;
- source-bounded complete canonical obligation text;
- market/challenge copy ≠ experience implementation evidence;
- physical stage + LED as a relational obligation;
- platform-format qualifier;
- canonical co-investment identity collision surfaced without auto-merge.

The co-investment collision remains a blocker for any future Truth-effect phase and must
not be auto-merged.

## Governance freeze

Until H3.1 + downstream rerun are separately approved:

- do **not** activate `domain_primary`;
- keep requirements `read_mode = shadow_compare`;
- do **not** alter active briefing/matrix canaries;
- do **not** persist machine recommendations as Human Review;
- do **not** synthesize Human Review from machine classes;
- do **not** reprocess Golden masters;
- do **not** reconstruct Graph V28.6;
- do **not** auto-merge Requirement identities;
- do **not** advance to B2.13;
- do **not** treat PASS status alone as Golden approval.

## Required validation sequence

1. Deploy H3.1 code + reboot. Normal imports/pipeline remain H3 during this validation phase.
2. Run **Chambinho H3.1 first** from `Requirement Semantic Truth Repair` (the only H3.1 caller).
3. Export/send H3.1 JSON and verify no regression.
4. Only after approval, run **JOVI H3.1**.
5. Run the new JOVI H3.1 read-only verifier and send JSON + CSV.
6. If H3.1 passes both Goldens, rerun B2.12.2.1 on Chambinho then JOVI.
7. Only then redesign/consider B2.13.

## H3.1 JOVI acceptance intent

The verifier must prove, rather than infer from aggregate counts, that:

- `Frequentadores de festivais de música` → audience context / no-domain;
- `Universo da moda e lifestyle` → audience context / no-domain;
- `Storytelling detalhado` → platform scope / no-domain;
- `Mini show ao vivo` → example / no-domain;
- `Performance com muito movimento` → example / no-domain;
- none of these survives as Current verified/human-confirmed Requirement Truth in the Golden;
- bare model guard and H3 identity isolation remain intact;
- semantic gate remains fail-closed with zero blockers;
- A/B regressions remain intact;
- Graph V28.6 remains frozen;
- no existing-existing auto-merge occurs.

Current Requirement cardinality is **not frozen**. Correct semantic exclusions may
legitimately reduce the JOVI Current denominator.

## Patch files

Add:
- `project_requirement_semantic_h31.py`
- `project_requirement_reconciliation_h31.py`
- `pages/33_Requirement_Semantic_Truth_Repair.py`
- `tests/test_v28_7_2c0_2_4h3_1_cross_unit_context.py`
- `NAVE_V28_7_2C0_2_4H3_1_VERIFY_GOLDEN_JOVI.sql`
- `GUIA_NAVE_V28_7_2C0_2_4H3_1_CROSS_UNIT_STRUCTURAL_CONTEXT.md`

Replace:
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

Migration SQL: **NO**.
Verifier SQL: **READ ONLY**.
Reboot: **YES**.
