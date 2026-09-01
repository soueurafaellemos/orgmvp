# NAVE V28.7.3 — Current Governed Checkpoint

## H3.1.2 Golden finding

JOVI H3.1.1 fixed the target pseudo-requirements but exposed one false demotion: a local creative directive was incorrectly inherited as `platform_scope`, and an activation heading was retyped despite base H3 already recognizing its no-domain semantics. H3.1.2 therefore adds Base H3 semantic precedence plus a Local Directive Guard. Chambinho must be rerun before JOVI.


## Current recovery phase

Active corrective checkpoint:
**V28.7.2C0.2.4H3.1.2 — Local Directive & Base Semantic Precedence Guard**.

The downstream B2 chain remains preserved through **V28.7.3B2.12.2.1**, but JOVI
remains blocked from B2.13 while Requirement Truth is revalidated upstream.

## Why H3.1.2 exists

H3.1 fixed the cross-Evidence-Unit blind spot that allowed audience/platform/example
fragments to remain Current Requirements. H3.1.1 then added a Section Boundary Guard
after Chambinho proved that an unpunctuated new section (`OBJETIVO E DESAFIO`) could be
skipped by the wider lookback. Chambinho H3.1.1 subsequently passed.

The first JOVI H3.1.1 run fixed the original targets — audience fragments, platform
characteristics, examples and the bare product model — but exposed two precedence
problems:

- `Direcionamento criativo: Construir um espaço altamente instagramável...` is a real
  local client directive, yet inherited the older Instagram `platform_scope` and was
  incorrectly demoted from Current Requirement Truth;
- `Ativação Instagram: Aesthetics & Lifestyle Gallery` had already been recognized by
  base H3 as a solution/reference heading, but H3.1.1 unnecessarily retyped it from the
  preceding product context.

Technical PASS therefore did not qualify as Golden approval.

## H3.1.2 architecture

`project_requirement_semantic_h31.py` preserves the H3.1/H3.1.1 structural repairs and
adds two conservative precedence guards:

1. **Base H3 semantic precedence** — cross-unit repair may only demote rows that base H3
   still considered `requirement_candidate` or `constraint_candidate`. Existing
   no-domain classifications are preserved rather than retyped.
2. **Local Directive Guard** — a fresh local directive such as `Direcionamento criativo:`
   / `Creative Direction:` cannot inherit an older audience/platform/product/example
   parent.

The rules are client-agnostic. Project-specific strings exist only in regression tests
and the Golden verifier. Human-confirmed Requirement Truth remains protected and
Evidence-first output remains untouched.

## Golden verifier

`NAVE_V28_7_2C0_2_4H3_1_2_VERIFY_GOLDEN_JOVI.sql` is READ-ONLY. In addition to the
existing punctuation-normalized forbidden-title checks, it now verifies that the
Instagram creative directive remains a reconciled Current Requirement and that the
activation heading retains `solution_reference` no-domain semantics.

Do not run the verifier until Chambinho passes H3.1.2 and JOVI is explicitly released.

## Pipeline isolation

During Golden validation:

- normal `project_intelligence_pipeline.py` remains unchanged;
- H3.1.2 runs only from `pages/33_Requirement_Semantic_Truth_Repair.py`;
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

1. Deploy H3.1.2 files.
2. Reboot.
3. Open Requirement Semantic Truth Repair.
4. Confirm `V28.7.2C0.2.4H3.1.2`.
5. Run Festivalzinho Chambinho once.
6. Export H3.1.2 JSON and review before any JOVI run.
7. If Chambinho passes, run JOVI H3.1.2 and export JSON.
8. Only after preliminary JSON approval, run the H3.1.2 JOVI verifier READ-ONLY.

Chambinho acceptance remains semantic, not merely numeric. JOVI additionally requires:
- `Storytelling detalhado` no-domain as `platform_scope`;
- audience fragments no-domain as `audience_context`;
- `Mini show ao vivo` / `Performance com muito movimento` no-domain as examples;
- bare product model no-domain as `product_attribute`;
- Instagram local creative directive preserved as `requirement_candidate`;
- Instagram activation heading preserved as `solution_reference`;
- no A/B/Graph/cutover/canary side effects.

No SQL migration is required.
