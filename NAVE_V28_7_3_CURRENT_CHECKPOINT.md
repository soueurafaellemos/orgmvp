# NAVE V28.7.3 — Current Governed Checkpoint

## Current recovery phase

Active corrective checkpoint:
**V28.7.2C0.2.4H3.1.1 — Cross-Unit Section Boundary Guard**.

The downstream B2 chain remains preserved through
**V28.7.3B2.12.2.1**, but JOVI remains blocked from B2.13 while Requirement Truth is
revalidated upstream.

## Why H3.1.1 exists

JOVI B2.12.2.1 exposed an upstream H3 false-green: audience/platform/example fragments
such as `Storytelling detalhado.` remained Current Requirements.

H3.1 repaired the cross-Evidence-Unit blind spot and the punctuation-vulnerable Golden
verifier. Its first Chambinho Golden then revealed a second structural edge case:

- run completed;
- semantic gate passed;
- 16 observations;
- 2 no-domain;
- 1 cross-unit override;
- 0 blockers;
- 0 new requirements;
- but `Objetivo principal` was incorrectly classified as `audience_context`.

The source structure is:

`PUBLICO ALVO:` → audience rows → `OBJETIVO E DESAFIO` → `Objetivo principal: ...`

`OBJETIVO E DESAFIO` was extracted without terminal `:`. H3.1's stale-parent brake only
recognized compact headings ending in `:`, so the lookback crossed the new section and
reached the older audience parent.

A technical PASS therefore did not qualify as Golden approval.

## H3.1.1 architecture

`project_requirement_semantic_h31.py` keeps the H3.1 bounded cross-unit lookback but adds
a client-agnostic section-boundary guard:

- reuse H3 heading detection;
- recognize common briefing/document section labels even without terminal punctuation;
- do NOT use all-caps alone as a boundary signal;
- known semantic parents still win;
- explicit requirement parents still win;
- only then does a nearer section boundary stop inheritance from older context;
- human-confirmed Requirement Truth remains protected;
- Evidence-first output remains untouched.

Expected Chambinho semantic roles:

- `Público-alvo` → `audience_context`;
- `Objetivo principal` → `strategy_context`, not `audience_context`.

The total no-domain count may remain 2. The correction is about semantic placement, not
forcing a different count.

## Golden verifier

`NAVE_V28_7_2C0_2_4H3_1_1_VERIFY_GOLDEN_JOVI.sql` remains READ-ONLY and preserves
terminal-punctuation normalization. It must not be run until Chambinho passes H3.1.1 and
JOVI is explicitly released.

## Pipeline isolation

During Golden validation:

- normal `project_intelligence_pipeline.py` remains unchanged;
- H3.1.1 runs only from `pages/33_Requirement_Semantic_Truth_Repair.py`;
- no master reprocessing;
- no Solution Reconciliation A rerun;
- no Core Semantic Domains B rerun;
- no Graph V28.6 rebuild;
- no domain_primary;
- no canary change;
- requirements stay `shadow_compare`.

## Downstream chain preserved

- B2.1 Requirement Identity Compatibility
- B2.2 Relational Consumer Shadow
- B2.3 Matrix requirements canary projection
- B2.4/B2.4.x Unified requirement audits
- B2.4.6 Cross-Domain Residual Placement
- B2.5 Semantic Ownership & Response Evidence Shadow
- B2.6 Response Entailment Shadow
- B2.7.1 Requirement Response Contract
- B2.8 Response Evidence Recall
- B2.9 Semantic Recall Bridge
- B2.10.1 canonical obligation atom calibration
- B2.11 Governed Response Recall Review Projection
- B2.12 Human Response Adjudication Contract
- B2.12.1 Automated Response Adjudication Recommendations
- B2.12.2 Semantic Eligibility & Core Obligation Hardening
- B2.12.2.1 Semantic Precedence Veto + Hard Qualifier Hotfix

No B2.13 / Truth-effect is approved.

## Golden run required now

1. Deploy H3.1.1 files.
2. Reboot.
3. Open Requirement Semantic Truth Repair.
4. Confirm `V28.7.2C0.2.4H3.1.1`.
5. Run Festivalzinho Chambinho once.
6. Export H3.1.1 JSON.
7. Verify semantics before any JOVI run.

Chambinho acceptance is semantic, not numeric:
- gate pass and zero blockers;
- `Público-alvo=audience_context`;
- `Objetivo principal=strategy_context`;
- no stale `cross_unit_parent` override on `Objetivo principal`;
- no unexpected new requirements;
- no A/B/Graph/cutover/canary side effects.

No SQL migration is required.
