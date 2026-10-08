# NAVE V28.7.3B2.15.3 — Transaction Preflight + Rollback-Only Probe

B2.15.2.1 closed the projection layer:
- Chambinho: 3 contract-verified events + 3 Evidence links.
- JOVI: 0 events; Plenária remains human-confirmation-only.

B2.15.3 installs the real bootstrap writer path but does NOT expose a real-write button.

## SQL
Install:
`NAVE_V28_7_3B2_15_3_CONTRACT_VERIFIED_RESPONSE_TRUTH_TRANSACTION.sql`

It creates:
- `apply_contract_verified_response_truth_b2153(...)`
- `diagnose_contract_verified_response_truth_b2153(...)`

Installing it writes no Truth data.

## Writer guards
- empty bootstrap ledger;
- requirements `shadow_compare`;
- exact B2.15.2.1 projection version;
- exact event-signature transaction fingerprint;
- Current Requirement identity/entity;
- verified/human-confirmed Requirement Truth;
- `verified_response`;
- `governed_response_contract`;
- `system_contract`;
- explicit supported Evidence Units;
- no Human Review;
- no machine recommendation path.

Inside the transaction it also proves:
- Current Response Truth view sees every inserted event;
- Response Truth status view sees every inserted event;
- Requirement Truth count unchanged;
- intelligence_reviews count unchanged;
- Requirement domain Evidence unchanged;
- read_mode remains shadow_compare.

## Rollback-only probe
If the writer succeeds, the probe deliberately throws
`NAVE_B2153_FORCED_ROLLBACK_AFTER_WRITER_SUCCESS`.

If it fails, original PostgreSQL diagnostics are returned.

After either path, Python rebuilds the fresh preflight to prove the ledger returned to
exactly the same pre-write state.

## UI
Page 44: PRE-FLIGHT ONLY. No real-write button.
Page 45: ROLLBACK-ONLY PROBE.

## SQL / deploy / reboot
YES / YES / YES.

## Mandatory order
1. Install SQL.
2. Deploy patch and reboot.
3. Page 44 -> JOVI -> `Preparar B2.15.3 — SEM WRITE`.
4. Download/send JOVI JSON.
5. Do NOT run Chambinho probe yet.

After JOVI negative control is reviewed:
6. prepare Chambinho preflight;
7. review it;
8. only then run Chambinho rollback-only probe.

No real Response Truth write is authorized by B2.15.3.
