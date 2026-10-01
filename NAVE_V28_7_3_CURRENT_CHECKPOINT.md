# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI.
- B2.12.2.2 Chambinho/JOVI.
- B2.12.3 Chambinho/JOVI.
- B2.12.4.1 Chambinho/JOVI.
- H3.1.3P1 normal pipeline promotion Chambinho/JOVI.
- B2.12.5.1 preflight Chambinho: GOLDEN APPROVED.
- B2.12.5.1 preflight JOVI: GOLDEN APPROVED.

## Incident state
Two authorized JOVI B2.12.5.1 writer attempts returned PostgREST APIError.
The second attempt occurred with Supabase active.

B2.12.5.2 independently confirmed after the second failure:
- CONFIRMED_PREWRITE_STATE_INTACT;
- 70 Current Requirements;
- 1 canonical collision;
- old Requirement/Governance/Knowledge Entity/occurrence still active;
- 9 historical Evidence links unchanged;
- 2 Semantic Observations unchanged;
- no writer-created Evidence;
- no completed matching writer run;
- requirements read_mode remains shadow_compare.

Therefore both failed attempts left no persisted supersession effect.

## Active checkpoint
**V28.7.3B2.12.5.3 — Rollback-Only Transaction Probe**

The probe executes the exact B2.12.5.1 RPC inside a PostgreSQL subtransaction and:
1. captures SQLSTATE/message/detail/hint/context on failure;
2. forces an exception after writer success so success also rolls back;
3. independently reruns B2.12.5.2 before/after to prove state remained pre-write.

## Governance freeze
- DO NOT retry B2.12.5.1 real writer.
- DO NOT run H3 repair, A/B/Graph, or B2.13.
- Keep requirements shadow_compare.
- Root cause must be captured and fixed before any new real-write authorization.
