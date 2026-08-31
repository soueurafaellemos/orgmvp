# NAVE V28.7.3 — Current Governed Checkpoint

## Current phase

Latest functional checkpoint: **V28.7.3B2.12.2.1 — Semantic Precedence Veto + Hard Qualifier Hotfix**.

B2.12.1 automated the B2.12 review queue without creating Human Review or Truth.
B2.12.2 added semantic eligibility, canonical obligation reconstruction and locality-aware
core-obligation guards. Chambinho passed B2.12.2, but the JOVI Golden exposed a
semantic-precedence defect: a newer eligible-looking observation could mask the H3
`legacy_explanation_*` no-domain decision, allowing pseudo-requirements such as
`Storytelling detalhado` to remain Current and receive a machine recommendation.

B2.12.2.1 fixes that defect without database writes or cutover.

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
- B2.10 — Obligation Atom Gate Golden; superseded for precision by B2.10.1
- B2.10.1 — Canonical requirement-title atom calibration
- B2.11 — Governed Response Recall Review Projection
- B2.12 — Human Response Adjudication Contract
- B2.12.1 — Automated Response Adjudication Recommendations
- B2.12.2 — Semantic Eligibility & Core Obligation Hardening
- **B2.12.2.1 — Semantic Precedence Veto + Hard Qualifier Hotfix**

## Golden findings entering B2.12.2.1

### Chambinho

B2.12.2 passed:
- Current before semantic gate: 13
- Semantic eligible: 13
- Excluded no-domain: 0
- Semantic unknown: 0
- Queue: 3
- 1 confirm / 1 partial / 1 reject
- no Human Review, no Truth, no persistence, no cutover.

The three adjudications remained semantically correct:
- Press kit / Seeding → confirm;
- Promotores e monitores → partial;
- Cobertura de foto e vídeo → reject.

`Restrição de verba e estrutura` remained `false_positive_excluded`.

### JOVI

B2.12.2 is **NOT approved**.

Observed:
- Current before semantic gate: 75
- Semantic eligible: 75
- Excluded no-domain: 0
- Semantic unknown: 0
- Queue: 35
- 3 confirm / 8 partial / 24 reject.

Critical regression:
- `Storytelling detalhado.` remained `requirement_candidate` and received
  `recommend_confirm`.

This violates the previously approved H3 semantic boundary. H3 explicitly treats
platform scope, product/audience context and examples as no-domain and the Cross-Golden
gate forbids Current verified identities such as:
- Frequentadores de festivais de música
- Universo da moda e lifestyle
- Storytelling detalhado
- Mini show ao vivo
- Performance com muito movimento
(and the bare product identity JOVI X300 Ultra).

Other B2.12.2 improvements were validated:
- truncated obligations were reconstructed from source;
- travel press kit ≠ travel product activation;
- food service ≠ budget/cost answer;
- horizontal format qualifier was recovered;
- no Human Review/Truth/persistence/cutover occurred.

Additional hardening in B2.12.2.1:
- persisted H3 no-domain explanation has precedence over newer machine observations;
- plural/hard qualifiers are augmented conservatively;
- physical stage + LED is relational and fail-closed;
- market/challenge copy cannot satisfy an experience-capability obligation;
- specific direct-payment/co-investment/recap-video reasons beat generic financial reasons;
- exact duplicate canonical obligations are surfaced as identity collisions, never auto-merged.

## Semantic precedence contract

For a Current Requirement row:

1. `human_confirmed` may override machine semantic classification.
2. Otherwise, persisted `legacy_explanation_role/status/action` no-domain is a hard veto.
3. Only after that may the selected/current semantic observation establish
   `requirement_candidate` or `constraint_candidate`.
4. Unresolved semantics fail closed as `semantic_eligibility_unknown`.

This prevents a later machine observation from silently resurrecting a pseudo-requirement.

## Governance freeze

Until a later separately designed and approved phase:

- do **not** activate `domain_primary`;
- do **not** move requirements `read_mode` away from `shadow_compare`;
- do **not** treat PASS or recommendation output as cutover approval;
- do **not** persist machine recommendations as Human Review;
- do **not** synthesize Human Review from algorithmic classes;
- do **not** change active briefing/matrix requirement canaries;
- do **not** relax matcher thresholds to increase recall;
- do **not** reprocess Golden masters;
- do **not** auto-merge Requirement identities;
- do **not** proceed to Truth-effect while semantic unknowns or canonical identity collisions remain unresolved.

## Golden run required now

After installing B2.12.2.1:

1. Run **Chambinho first** on `Automated Adjudication Recommendations`.
2. Confirm version `V28.7.3B2.12.2.1`.
3. Export JSON and validate regression.
4. Only after Chambinho passes, run **JOVI**.

JOVI acceptance gates:
- `semantic_unknown_count = 0`;
- H3 no-domain pseudo-requirements must be excluded before adjudication;
- `Storytelling detalhado` must not appear in recommendation queue;
- `Performance com muito movimento` must not appear in recommendation queue;
- known core-obligation controls remain conservative;
- any `canonical_identity_collision_rows` are diagnostic only and block future Truth-effect.

`queue_count` is not frozen: semantic correction may legitimately reduce it.

## Repository files for this checkpoint

- `project_requirement_semantic_eligibility.py`
- `project_requirement_auto_adjudication_hardening.py`
- `pages/32_Automated_Adjudication_Recommendations.py`
- `tests/test_v28_7_3b2_12_2_semantic_hardening.py`
- `GUIA_NAVE_V28_7_3B2_12_2_1_SEMANTIC_PRECEDENCE_HOTFIX.md`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

No SQL is required.
