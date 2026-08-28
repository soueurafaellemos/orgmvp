# NAVE V28.7.3B2.12 — Human Response Adjudication Contract

## Purpose

B2.12 converts the governed B2.11 review projection into an explicit human
adjudication queue while preserving provenance.

It is intentionally **not** a Truth write phase.

## Golden basis accepted before B2.12

### JOVI

B2.11:
- 75 Current Domain requirements;
- 0 `verified_response`;
- 3 `response_review_high_confidence`;
- 30 `response_review_partial`;
- 42 `no_safely_verified_response`;
- 8 source-role rejections and 8 generic-overlap rejections in the underlying
  recall gate;
- `cutover_approved=false`;
- `persistence_performed=false`.

B2.12 expected editable queue: **33 rows**.

### Chambinho

B2.11:
- 13 Current Domain requirements;
- 3 `verified_response`;
- 1 `response_review_high_confidence`;
- 2 `response_review_partial`;
- 1 `false_positive_excluded`;
- 6 `no_safely_verified_response`;
- `cutover_approved=false`;
- `persistence_performed=false`.

B2.12 expected editable queue: **3 rows**.

## Human decisions

A reviewer must explicitly choose one of:

- `confirm_response` — Confirmar resposta;
- `partial_response` — Resposta parcial;
- `reject_match` — Rejeitar correspondência;
- `visual_structured_review` — Requer revisão visual/estruturada;
- `defer` — Adiar decisão.

The initial UI value `— Selecione —` is **not** a decision.

`confirm_response`, `partial_response` and `reject_match` require a human
rationale. Any explicit decision requires a reviewer identity typed into the UI.

## Provenance preserved

Each candidate receives a stable `candidate_id` derived from:
- project;
- requirement;
- evidence identity;
- projected review status;
- B2.11 projection version;
- B2.10.1 obligation gate version;
- B2.7.1 response-contract version.

The exported decision snapshot preserves:
- project and requirement identity;
- canonical requirement title;
- requirement type, mandatory flag, priority and Truth state at review time;
- B2.11 projected status and reason;
- current response evidence snapshot;
- recall evidence id/source/page/text;
- obligation atoms, shared atoms and missing atoms;
- algorithm versions;
- human decision;
- human rationale;
- reviewer;
- adjudication timestamp;
- explicit `truth_effect_applied=false`;
- explicit `persistence_performed=false`.

## Package states

- `EMPTY_DRAFT` — no explicit decision;
- `PARTIAL_DRAFT` — some candidates decided;
- `INVALID_DRAFT` — reviewer/rationale/decision validation failed;
- `COMPLETE_REVIEW_PACKAGE` — every queue row has an explicit valid human
  decision, including `defer` where appropriate.

A complete package is still **not Truth**.

## Governance

B2.12 does not:
- INSERT or UPDATE Supabase;
- create persistent Human Review;
- alter `project_requirement_truth_status`;
- change `read_mode`;
- set or activate `domain_primary`;
- alter briefing/matrix canaries;
- change matcher thresholds;
- change Unified served consumers;
- approve cutover.

## Next phase

Only after Golden adjudication packages are produced and manually reviewed
should a separate B2.13 Truth-effect projection be designed.

B2.13 must treat the B2.12 package as an explicit human-provenance input and
must still begin as read-only. Persistence requires a later, separately
approved write path.
