# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 + H3.1.3P1 Requirement semantics/pipeline.
- B2.12.5.4 Requirement identity supersession JOVI + independent verifier.
- B2.13.1 Response downstream integrity Chambinho/JOVI.
- B2.14 Response Truth Eligibility & Provenance Chambinho/JOVI.
- B2.15P0.3 live Response Truth architecture inventory.
- B2.15.1 Response Truth Ledger Schema Foundation — 15/15 schema verifier PASS.

## B2.15.2 Chambinho runtime finding

First B2.15.2 run correctly BLOCKED on exactly one check:

`current_requirement_count_matches_golden`

Observed:
- B2.14 Current denominator: 13
- Response Truth status view: 13
- raw `project_requirement_truth_status` rows fetched by B2.15.2: 16
- all semantic/provenance/event/evidence checks: PASS
- projected events: 3
- projected evidence links: 3
- ledger remains empty

Root cause:
B2.15.2 incorrectly used the raw cardinality of `project_requirement_truth_status`,
which intentionally includes non-Current/historical Requirement identities. The Current
denominator must be:
- `lifecycle_status = active`
- `truth_state in (verified, human_confirmed)`

This is a projection-denominator bug, not data drift.

## Active checkpoint
**V28.7.3B2.15.2.1 — Current Requirement Truth Denominator Fix**

READ ONLY.

B2.15.2.1:
- preserves raw truth-row count for diagnostics;
- filters the projection input to governed Current Requirement Truth;
- explicitly verifies all rows used by the projection are Current-only;
- keeps the ledger empty requirement;
- changes no event/evidence semantics.

Golden order remains:
1. Chambinho rerun.
2. JOVI only after Chambinho PASS.

No Response Truth write is authorized.
