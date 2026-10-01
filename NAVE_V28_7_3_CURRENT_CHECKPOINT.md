# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI.
- B2.12.2.2 Chambinho/JOVI.
- B2.12.3 Chambinho/JOVI.
- B2.12.4.1 Chambinho/JOVI.
- H3.1.3P1 normal pipeline promotion Chambinho/JOVI.
- B2.12.5.1 preflight Chambinho/JOVI: semantic plan Golden.
- B2.12.5.2 failure-state diagnostic: both real-write failures independently confirmed full rollback.
- B2.12.5.3 rollback-only transaction probe: ROOT_CAUSE_CAPTURED_ROLLBACK_VERIFIED.

## Captured root cause
PostgreSQL SQLSTATE `23505` on `project_requirements_legacy_uidx`.

The writer attempted to assign Legacy alias
`8fa8b29c-8f5f-4857-abe3-76c806a6b96c`
to the survivor while the superseded Requirement still owned:
`(legacy_source_table, legacy_source_id) =
(memory_briefing_requirements, 8fa8b29c-8f5f-4857-abe3-76c806a6b96c)`.

This is an alias-ownership sequencing defect, not a semantic-plan defect,
permission defect or partial-write incident.

## Active checkpoint
**V28.7.3B2.12.5.4 — Legacy Alias Ownership Transfer Hardening**

The writer now:
1. resolves and locks the current project-local owner of each Legacy alias;
2. fails closed if ownership is ambiguous or outside the superseded set;
3. releases the unique Legacy bridge from the old Requirement inside the transaction;
4. binds the exact bridge to the canonical survivor;
5. records the transfer in `intelligence_runs`, Governance and Knowledge Entity lineage;
6. verifies survivor ownership and old-owner release as postconditions.

Any later failure still rolls the whole transaction back, including alias ownership.

## Required validation order
1. Install B2.12.5.4 SQL + code and reboot.
2. Generate fresh JOVI B2.12.5.4 PRE-FLIGHT only.
3. Run existing B2.12.5.3 rollback-only probe using that fresh preflight.
4. Require:
   - `WRITER_WOULD_COMPLETE_ROLLED_BACK`,
   - `rollback_independently_verified=true`,
   - `state_unchanged=true`.
5. Only after independent review may one real write be authorized.

## Governance freeze
- DO NOT run B2.12.5.4 real writer yet.
- DO NOT run H3 repair, A/B/Graph, or B2.13.
- Keep requirements `shadow_compare`.
