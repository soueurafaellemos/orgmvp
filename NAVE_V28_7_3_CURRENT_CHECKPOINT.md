# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 + H3.1.3P1 Requirement semantics/pipeline.
- B2.12.5.4 Requirement identity supersession JOVI + independent verifier.
- B2.13.1 Response downstream integrity Chambinho/JOVI.
- B2.14 Response Truth Eligibility & Provenance Chambinho/JOVI.
- B2.15P0.3 live Response Truth architecture inventory.
- B2.15.1 Response Truth Ledger Schema Foundation.

## B2.15.1 verifier
`V28.7.3B2.15.1V1`
- PASS_RESPONSE_TRUTH_LEDGER_SCHEMA
- 15 / 15 checks passed
- zero failed checks
- event/evidence/current-truth stores empty
- append-only triggers installed
- insert validation trigger installed
- RLS enabled
- both Goldens remain shadow_compare
- no domain_primary promotion
- Requirement Response Human Review type still not activated

B2.15.1 is schema-installation Golden only.
The event INSERT path has intentionally not been runtime-tested yet.

## Active checkpoint
**V28.7.3B2.15.2 — Contract-Verified Response Truth Projection Shadow**

READ ONLY.

Purpose:
- project the already-governed B2.7.1 `verified_response` rows into exact immutable
  B2.15.1 event/evidence payloads;
- prove Requirement identity/entity mapping;
- prove Evidence Unit existence;
- freeze deterministic event signatures;
- explicitly exclude machine/human-confirmation candidates;
- require the ledger to remain empty.

Golden order:
1. Chambinho: expected 3 events / 3 evidence links.
2. JOVI: expected 0 events; Plenária remains excluded human-confirmation candidate.

## Governance freeze
- no Response Truth insert;
- no Human Review creation;
- no machine recommendation promotion;
- no Requirement writer rerun;
- no read_mode/domain_primary/cutover change;
- no A/B/Graph rerun.

No real Response Truth write is authorized by B2.15.2.
