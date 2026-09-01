# NAVE V28.7.3 — Current Governed Checkpoint

## Current recovery phase

Active corrective checkpoint:
**V28.7.2C0.2.4H3.1.3 — Structural Refinement Precedence**.

The downstream B2 chain remains preserved through **V28.7.3B2.12.2.1**, but B2.13 / Truth-effect remains blocked while Requirement Truth semantics are revalidated upstream.

## Why H3.1.x was reopened

JOVI B2.12.2.1 exposed pseudo-requirements such as `Storytelling detalhado` and `Performance com muito movimento` in Current Requirement Truth. The old H3 Golden had a verifier false-green because terminal punctuation was not normalized, and the semantic extractor could not see a structural parent across Evidence Unit boundaries.

### H3.1
Added cross-unit structural lookback and normalized Golden verification.

### H3.1.1
Chambinho exposed stale inheritance across an unpunctuated new section (`OBJETIVO E DESAFIO`). Added Section Boundary Guard.

### H3.1.2
JOVI then exposed two false demotions: a real local creative directive inherited old `platform_scope`, and an activation heading already recognized as `solution_reference` was retyped from preceding product context. Added Local Directive Guard and broad base-H3 semantic precedence.

### H3.1.3 finding
The broad H3.1.2 precedence was too conservative. It preserved several **contextual H3 base mistakes**, including:
- `Kit de lentes teleobjetivas destacáveis` as `audience_context` instead of `product_attribute`;
- `Conteúdo de longa duração` / `Reviews técnicos aprofundados` as `audience_context` instead of `platform_scope`;
- `Curadoria visual impecável` / `Conteúdo aspiracional` as `audience_context` instead of `platform_scope`.

These rows were still no-domain, so Truth inclusion was improved, but semantic role integrity was not yet Golden-quality.

## H3.1.3 architecture

`project_requirement_semantic_h31.py` now uses **tiered semantic precedence**:

1. Human-confirmed Requirement Truth remains protected.
2. Local directives (`Direcionamento criativo:`, `Creative Direction:` etc.) remain Requirements and cannot inherit an older semantic parent.
3. Intrinsic/self-contained H3 roles are preserved: `solution_reference`, `reference_signal`, `suggestion_signal`, `example_signal`, `parameter_signal`, `constraint_qualifier`, `form_prompt`.
4. Context-sensitive roles remain structurally refinable: `requirement_candidate`, `constraint_candidate`, `audience_context`, `product_attribute`, `platform_scope`, `strategy_context`, `channel_scope`.
5. If cross-unit context does not yield a known parent, H3 output is preserved.

This keeps the Instagram activation heading as `solution_reference`, keeps the Instagram creative directive as Requirement, and allows nearer `Foco do Produto` / `Adequação à Plataforma` parents to correct contextual H3 mistakes.

## Golden verifier

`NAVE_V28_7_2C0_2_4H3_1_3_VERIFY_GOLDEN_JOVI.sql` is READ-ONLY.

Beyond the previous punctuation-normalized forbidden-title checks, it now verifies semantic **role integrity** for source-bounded siblings:
- YouTube product-focus children → `product_attribute`;
- YouTube platform-fit children → `platform_scope`;
- Instagram platform-fit children → `platform_scope`;
- Instagram local creative directive → Current reconciled Requirement;
- Instagram activation heading → `solution_reference` no-domain.

A Golden cannot pass merely because a pseudo-requirement is no-domain; the no-domain role itself must match the source structure.

## Pipeline isolation

During Golden validation:
- normal `project_intelligence_pipeline.py` remains unchanged;
- H3.1.3 runs only from `pages/33_Requirement_Semantic_Truth_Repair.py`;
- no master reprocessing;
- no Solution Reconciliation A rerun;
- no Core Semantic Domains B rerun;
- no Graph V28.6 rebuild;
- no `domain_primary`;
- no canary change;
- requirements remain `shadow_compare`;
- no auto-merge;
- no Human Review synthesis;
- no B2 Truth-effect.

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

## Golden run required now

1. Deploy H3.1.3 files.
2. Reboot.
3. Open Requirement Semantic Truth Repair.
4. Confirm `V28.7.2C0.2.4H3.1.3`.
5. Run Festivalzinho Chambinho once.
6. Export H3.1.3 JSON and review before JOVI.
7. If Chambinho passes, run JOVI H3.1.3 and export JSON.
8. Only after preliminary JSON approval, run the H3.1.3 JOVI verifier READ-ONLY.

No SQL migration is required.
