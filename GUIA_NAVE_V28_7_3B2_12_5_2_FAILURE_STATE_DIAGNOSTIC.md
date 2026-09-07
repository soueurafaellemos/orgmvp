# NAVE V28.7.3B2.12.5.2 — Failed Supersession State Diagnostic

## Purpose
A B2.12.5.1 write attempt returned `postgrest.exceptions.APIError` with the database
message redacted by Streamlit. Do not retry the writer.

This patch adds a read-only incident diagnostic. It requires the exact JOVI preflight JSON
that was reviewed before the failed click and compares the live database with both expected
states.

## Classifications
- `CONFIRMED_PREWRITE_STATE_INTACT`: all pre-write invariants still hold; write did not persist.
- `CONFIRMED_TRANSACTION_COMPLETED_STATE`: persisted state matches full post-transaction contract.
- `PARTIAL_OR_UNEXPECTED_STATE`: neither safe model fully matches; freeze all writes.

The diagnostic checks Current count, canonical collision count, survivor/old Truth and
status, Governance lineage, Knowledge Entity lineage, occurrence lifecycle, Legacy alias
resolution, historical Evidence counts, semantic observations, writer-created Evidence,
matching intelligence_runs, B2.1 compatibility and requirements read_mode.

## Files
ADD:
- `project_requirement_supersession_failure_diagnostic.py`
- `pages/39_Requirement_Supersession_Failure_State_Diagnostic.py`
- `tests/test_v28_7_3b2_12_5_2_failure_state_diagnostic.py`
- `GUIA_NAVE_V28_7_3B2_12_5_2_FAILURE_STATE_DIAGNOSTIC.md`

REPLACE:
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL
NO.

## Reboot
YES.

## Run
1. Deploy + reboot.
2. Open `Supersession Failure State Diagnostic`.
3. Upload the exact `NAVE_B2_12_5_PREFLIGHT_<JOVI>.json` used before the failed write.
4. Run the read-only diagnostic.
5. Download JSON and send it back.
6. Do not run the writer again regardless of classification until root cause review.
