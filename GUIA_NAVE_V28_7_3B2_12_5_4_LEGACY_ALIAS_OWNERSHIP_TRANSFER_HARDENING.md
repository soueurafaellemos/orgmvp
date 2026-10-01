# NAVE V28.7.3B2.12.5.4 — Legacy Alias Ownership Transfer Hardening

## Root cause proven by B2.12.5.3

The rollback-only probe captured:

- SQLSTATE `23505`
- constraint `project_requirements_legacy_uidx`
- table `public.project_requirements`
- duplicate pair:
  `(memory_briefing_requirements, 8fa8b29c-8f5f-4857-abe3-76c806a6b96c)`

The B2.12.5.1 writer tried to bind the Legacy alias to the survivor while the
superseded Requirement still owned the same unique bridge.

The probe independently verified rollback; the database remained at 70 Current /
1 collision / `shadow_compare`.

## Fix

`set_survivor_legacy_source_id` is now implemented as a guarded atomic ownership transfer:

1. resolve + lock current project-local alias owner;
2. fail closed if ownership is ambiguous or not in the superseded set;
3. clear the old Requirement's Legacy bridge;
4. bind the same source-table/id pair to the survivor;
5. audit the transfer in `intelligence_runs`;
6. preserve transfer provenance in superseded Governance / Knowledge Entity lineage;
7. postcondition proves survivor ownership and old-owner release.

All of this remains inside the existing PostgreSQL transaction. A later failure restores
the old bridge automatically.

Historical provenance remains preserved through immutable occurrences, semantic observations,
Evidence and the explicit transaction/lineage audit. No DELETE is introduced.

## Files

REPLACE:
- `project_requirement_identity_supersession.py`
- `project_requirement_identity_supersession_verify.py`
- `project_requirement_identity_supersession_probe.py`
- `pages/37_Governed_Requirement_Identity_Supersession.py`
- `pages/38_Requirement_Supersession_Post_Transaction_Verifier.py`
- `pages/40_Requirement_Supersession_Transaction_Probe.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

ADD / EXECUTE:
- `NAVE_V28_7_3B2_12_5_4_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql`
- `tests/test_v28_7_3b2_12_5_4_legacy_alias_transfer.py`
- this guide

## SQL
YES. The SQL `CREATE OR REPLACE`s the existing 7-arg writer RPC.
It does not execute a supersession during installation.

## Reboot
YES.

## Mandatory validation order
1. Execute B2.12.5.4 SQL.
2. Deploy files + reboot.
3. Page 37 → JOVI → PRE-FLIGHT only.
4. Download fresh `V28.7.3B2.12.5.4` preflight.
5. Do NOT click WRITE REAL.
6. Page 40 → run B2.12.5.3 rollback-only probe with the 5.4 preflight.
7. Send probe JSON for review.

Desired probe result:
- `WRITER_WOULD_COMPLETE_ROLLED_BACK`
- `rollback_independently_verified=true`
- `state_unchanged=true`

Only then can the real writer be considered again.
