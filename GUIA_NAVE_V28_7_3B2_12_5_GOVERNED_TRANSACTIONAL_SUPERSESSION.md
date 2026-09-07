# NAVE V28.7.3B2.12.5 — Governed Transactional Requirement Identity Supersession

## This is a real write
B2.12.5 is the first persistence step after the H3.1.3 / B2.12.x shadow Goldens.

The write is intentionally small: resolve one canonical Requirement identity collision
without changing the survivor's business meaning.

## SQL
YES.

Run:
`NAVE_V28_7_3B2_12_5_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql`

The SQL only installs/replaces the RPC. It does NOT execute a supersession by itself.

## Reboot
YES after deploying the code files.

## Files

ADD:
- `project_requirement_identity_supersession.py`
- `project_requirement_identity_supersession_verify.py`
- `pages/37_Governed_Requirement_Identity_Supersession.py`
- `pages/38_Requirement_Supersession_Post_Transaction_Verifier.py`
- `tests/test_v28_7_3b2_12_5_transactional_supersession.py`
- `NAVE_V28_7_3B2_12_5_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql`
- `GUIA_NAVE_V28_7_3B2_12_5_GOVERNED_TRANSACTIONAL_SUPERSESSION.md`

REPLACE:
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## Safety architecture
- database transaction + project advisory lock;
- confirmation token `SUPERSEDE:<project_id>`;
- fresh B2.12.4.1 generated again immediately before RPC;
- identity/entity/current-count/lifecycle preconditions;
- exact occurrence action validation;
- no hash recomputation in SQL: target hashes are the Golden-proven Python hashes from the fresh dry-run;
- no DELETE;
- no business metadata merge;
- historical Evidence/Semantic records preserved;
- alias uniqueness postcondition;
- Current count postcondition;
- any failed postcondition raises and rolls back the entire function call.

## Golden order
Do not write JOVI immediately.

1. Install SQL + deploy + reboot.
2. Open Governed Requirement Identity Supersession.
3. Select Festivalzinho Chambinho.
4. Click `Preparar preflight B2.12.5 — SEM WRITE`.
5. Expected: `NO_TRANSACTION_REQUIRED`, `ready_for_write=false`, no write button.
6. Download and send the preflight JSON.
7. Only after approval select JOVI.
8. Prepare preflight and review it.
9. Type the exact confirmation token and execute ONCE.
10. Download transaction result.
11. Open the separate Post-Transaction Verifier.
12. Run JOVI verifier and send JSON.
13. Do not advance to B2.13 until the independent verifier is Golden.
