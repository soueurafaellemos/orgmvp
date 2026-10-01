# NAVE V28.7.3B2.12.5.3 — Rollback-Only Transaction Probe

## Why
The second B2.12.5.1 real-write attempt failed at the RPC boundary even after Supabase
was active. B2.12.5.2 then proved the database remained exactly in the pre-write state.

The original PostgreSQL error is still redacted by Streamlit. This probe obtains it without
allowing any supersession mutation to persist.

## Safety model
The SQL diagnostic function wraps the existing B2.12.5.1 writer in a PL/pgSQL
`BEGIN ... EXCEPTION` subtransaction.

- If the writer fails: PostgreSQL rolls back the inner subtransaction, and the probe captures
  `SQLSTATE`, message, detail, hint, context, schema/table/column/constraint.
- If the writer succeeds: the probe deliberately raises
  `NAVE_B21253_FORCED_ROLLBACK_AFTER_WRITER_SUCCESS`, which rolls back the successful
  inner writer path before the outer diagnostic function returns.
- The Python layer independently runs B2.12.5.2 before and after the probe and refuses to
  call the probe unless the initial state is `CONFIRMED_PREWRITE_STATE_INTACT`.

The probe never authorizes a real write.

## Files
ADD:
- `NAVE_V28_7_3B2_12_5_3_ROLLBACK_ONLY_TRANSACTION_PROBE.sql`
- `project_requirement_identity_supersession_probe.py`
- `pages/40_Requirement_Supersession_Transaction_Probe.py`
- `tests/test_v28_7_3b2_12_5_3_rollback_only_probe.py`
- `GUIA_NAVE_V28_7_3B2_12_5_3_ROLLBACK_ONLY_TRANSACTION_PROBE.md`

REPLACE:
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL
YES. Install the supplied SQL. It creates only the diagnostic RPC.
It does not execute the writer during installation.

## Reboot
YES.

## Run
1. Install the B2.12.5.3 SQL in Supabase.
2. Deploy the code files and reboot.
3. Open `🧯 Supersession Transaction Probe`.
4. Upload the latest JOVI B2.12.5.1 preflight JSON.
5. Tick the rollback-only confirmation.
6. Execute the probe exactly once.
7. Download the Transaction Probe JSON and send it for review.
8. Do NOT return to the real writer.
