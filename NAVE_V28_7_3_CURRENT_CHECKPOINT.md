# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- B2.12.5.4 Requirement identity supersession + independent verifier.
- B2.13.1 Response downstream integrity Chambinho/JOVI.
- B2.14 Response Truth Eligibility & Provenance Chambinho/JOVI.
- B2.15P0.3 Response Truth architecture inventory.
- B2.15.1 Response Truth Ledger Schema Foundation.
- B2.15.2.1 Contract-Verified Response Truth Projection:
  - Chambinho GOLDEN: 13 Current, 3 contract eligible, 3 events, 3 Evidence links.
  - JOVI GOLDEN control: 69 Current, 0 contract eligible, 1 human candidate, 0 events.

JOVI raw truth-view rows = 114; governed Current = 69; non-Current/historical = 45.
Raw view cardinality is diagnostic history, not the Current denominator.

## Active
V28.7.3B2.15.3 — Transaction Preflight + Rollback-Only Probe

No real Response Truth write is authorized.

UI exposes only:
1. preflight;
2. rollback-only probe.

Writer accepts only governed B2.7.1 verified_response event plans from B2.15.2.1.
It rejects machine/human-confirmation paths and requires the bootstrap ledger to be empty.

Validation order:
1. install SQL + deploy/reboot;
2. JOVI preflight first -> NO_TRANSACTION_REQUIRED;
3. review JOVI JSON;
4. Chambinho preflight -> READY_FOR_ROLLBACK_ONLY_PROBE;
5. review Chambinho JSON;
6. only then run Chambinho rollback-only probe;
7. no real write until a later explicit checkpoint.
