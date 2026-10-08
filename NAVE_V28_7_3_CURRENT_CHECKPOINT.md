# NAVE V28.7.3 — Current Governed Checkpoint

## Closed Goldens
- B2.15.1 Response Truth Ledger Schema Foundation.
- B2.15.2.1 Response Truth Projection:
  - Chambinho: 13 Current / 3 contract events / 3 Evidence links.
  - JOVI: 69 Current / 0 contract events / 1 human-only candidate.
- B2.15.3.1 JOVI negative transaction preflight: NO_TRANSACTION_REQUIRED.

## B2.15.3.1 Chambinho review
Chambinho passed every semantic/live guard and produced the expected 3-event / 3-Evidence
bundle. Independent review also recomputed its old fingerprint successfully.

Before the rollback probe, one integrity gap was found:
the B2.15.3.1 fingerprint covered only the three event_signature values, while the writer
would also persist nested reason/provenance/evidence snapshot payloads.

## Active
V28.7.3B2.15.3.2 — Full-Bundle Fingerprint Hardening

The database now computes SHA-256 over the entire JSONB execution bundle and the writer
recomputes that exact fingerprint before any mutation.

The first-write writer is intentionally restricted to:
- Chambinho only;
- locked Chambinho B2.15.2.1 SHA;
- exact 3 Golden event signatures;
- exactly 3 events / 3 Evidence links;
- 13 Current Requirements;
- shadow_compare;
- empty Response Truth ledger.

Old B2.15.3 writer/probe RPCs are removed by the migration.

No real Response Truth write is authorized.
