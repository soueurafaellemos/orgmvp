# NAVE V28.7.3B2.15.2.1 — Current Requirement Truth Denominator Fix

## Captured runtime result

The first Chambinho B2.15.2 run returned:

- `BLOCKED_CONTRACT_VERIFIED_RESPONSE_TRUTH_PROJECTION`
- one failed check only: `current_requirement_count_matches_golden`
- `current_requirement_count = 16`
- `truth_status_row_count = 13`
- 3 contract-eligible rows
- 3 projected immutable events
- 3 projected Evidence links
- zero missing/invalid/mismatched Evidence or identity diagnostics
- ledger remained empty

Every semantic/provenance check passed.

## Root cause

`project_requirement_truth_status` is a historical/current truth view, not a Current-only
view. The B2.15.2 runtime fetched all project rows and incorrectly used the raw row count
as the Current denominator.

The governed Current Requirement denominator is the same contract used throughout the
Requirement reader:

- `lifecycle_status = active`
- `truth_state in ('verified','human_confirmed')`

For Chambinho this is 13, while the raw truth view currently contains 16 rows.

## Fix

B2.15.2.1 now:

1. fetches the raw truth view for diagnostics;
2. filters to governed Current rows before projection;
3. records:
   - raw Requirement Truth row count;
   - Current Requirement Truth row count;
   - non-Current/historical row count;
4. adds an explicit `requirement_truth_rows_are_current_only` check.

No semantic eligibility, Evidence identity, event payload, signature rule or ledger guard
was loosened.

## SQL
NO.

## Deploy / reboot
YES / YES.

## Run order
1. Deploy patch + reboot.
2. Open `Response Truth Ledger Projection`.
3. Select Festivalzinho Chambinho.
4. Run `Executar B2.15.2.1 — READ ONLY`.
5. Download/send JSON.
6. Do not run JOVI until Chambinho is approved.

Expected Chambinho:
- Current = 13
- raw truth rows = 16
- non-Current/historical truth rows = 3
- contract eligible = 3
- projected events = 3
- projected Evidence links = 3
- ledger events/evidence/current truth = 0
- PASS

No Response Truth write is authorized.
