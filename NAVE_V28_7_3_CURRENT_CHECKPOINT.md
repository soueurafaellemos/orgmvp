# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI.
- B2.12.2.2 Chambinho/JOVI.
- B2.12.3 identity collision shadow Chambinho/JOVI.
- B2.12.4.1 transaction integrity Chambinho/JOVI.
- H3.1.3P1 normal-pipeline promotion Chambinho/JOVI.
- B2.12.5.4 transactional Requirement identity supersession JOVI + independent verifier.
- B2.13.1 post-supersession Response integrity Chambinho/JOVI.

## B2.13.1 closed result
Chambinho:
- PASS_CONTROL_NO_DOWNSTREAM_DRIFT;
- 13 Current / queue 3 / collision 0 unchanged;
- exact projection and recommendation hashes unchanged.

JOVI:
- PASS_POST_SUPERSESSION_RESPONSE_INTEGRITY;
- 70 → 69 Current exactly;
- queue 33 → 32 exactly;
- collisions 1 → 0;
- recommendation distribution changed only by removal of the superseded duplicate:
  reject 26 → 25;
- all surviving projection rows unchanged;
- all surviving recommendation rows unchanged;
- no mismatch rows;
- Response Truth unchanged.

## Active checkpoint
**V28.7.3B2.14 — Response Truth Eligibility & Provenance Shadow**

B2.14 remains read-only and establishes the provenance boundary for a later Response Truth ledger.

- `eligible_contract_verified`: already `verified_response` under governed B2.7.1
  with explicit supporting Evidence.
- `eligible_human_confirmation_only`: machine `recommend_confirm`, explicit evidence,
  high-confidence projection; machine remains non-Truth and requires future explicit
  human decision for any `human_confirmed_response`.
- partial/reject/visual/defer/no-safe/false-positive: not eligible.
- any unknown state: fail closed as `blocked_unclassified`.

## Governance freeze
- do not persist Response Truth;
- do not auto-promote machine recommendations;
- do not synthesize Human Review;
- do not rerun Requirement writer;
- no A/B/Graph rerun;
- no cutover/domain_primary;
- requirements remain `shadow_compare`.

Golden order: Chambinho first, then JOVI.
