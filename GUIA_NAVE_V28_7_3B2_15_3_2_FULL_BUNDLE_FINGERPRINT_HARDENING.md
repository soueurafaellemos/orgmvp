# NAVE V28.7.3B2.15.3.2 — Full-Bundle Fingerprint Hardening

The Chambinho B2.15.3.1 preflight is semantically correct and all live guards passed.
However, its transaction fingerprint covered only the sorted event_signature list.

That left nested fields that would be persisted—reason, provenance_snapshot and
evidence_snapshot—outside the reviewed transaction fingerprint.

B2.15.3.2 closes that gap.

## What changes
The database itself computes SHA-256 over the entire JSONB execution bundle. The exact
same helper is used by the preflight inspection RPC and by the writer immediately before
its first mutation.

The writer is also narrowed to the reviewed first-write canary:
- Chambinho only;
- baseline SHA `424a9c0a7992c99a7a37117784d7304ecb86033431e40d8687171a20286264d2`;
- exact 3 reviewed event signatures;
- exactly 3 events and 3 Evidence links;
- exactly 13 Current Requirements;
- shadow_compare;
- empty ledger.

The old weaker B2.15.3 writer/probe RPCs are dropped.

## SQL
YES.

Run:
`NAVE_V28_7_3B2_15_3_2_FULL_BUNDLE_FINGERPRINT_HARDENING.sql`

Installing it writes no Response Truth.

## Deploy / reboot
YES / YES.

## Next action
Do NOT run the rollback probe yet.

After SQL + deploy + reboot:
1. Open Response Truth Transaction Preflight.
2. Select Festivalzinho Chambinho.
3. Run `Preparar B2.15.3.2 — SEM WRITE`.
4. Download/send the JSON.

Expected:
- READY_FOR_ROLLBACK_ONLY_PROBE
- 3 events
- 3 Evidence links
- fingerprint_scope = entire_jsonb_execution_bundle
- all live guards PASS
- ledger remains 0/0/0
- ready_for_real_write = false

JOVI does not need another negative-control rerun because this hotfix changes only the
non-empty transaction fingerprint/writer path.
