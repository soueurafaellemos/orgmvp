# NAVE V28.7.3B2.15.3.1 — Frozen Golden Preflight Hotfix

## Captured problem

B2.15.3 preflight was functionally correct but operationally wrong: every click rebuilt the entire B2.12.2.2 → B2.14 → B2.15.2.1 chain live. On JOVI that means reprocessing the large Response projection only to rediscover an already-reviewed Golden result.

This is why the UI could sit for a long time on “Reconstruindo projection e transaction fingerprint...”.

## Fix

B2.15.3.1 packages the two approved B2.15.2.1 Golden JSONs and locks them with SHA-256:

- Chambinho: `424a9c0a7992c99a7a37117784d7304ecb86033431e40d8687171a20286264d2`
- JOVI: `e1c5b18c9faecbf15e63d34fc5c482a5927130b5fb18f1f07d4c8f60778ade44`

The preflight no longer reruns B2.12/B2.14/B2.15.2.1. Instead it performs only lightweight live guards:

- Current Response Truth status cardinality still equals the Golden;
- all Current rows still have `no_persisted_response_truth`;
- event/evidence/current-truth ledgers are still empty;
- requirements remain `shadow_compare`;
- every target Requirement identity/entity is still Current;
- every target Evidence Unit still exists.

No governance condition is removed. The heavy historical computation becomes immutable input; mutable database state is still checked live.

## SQL

NO new SQL. Do not reinstall B2.15.3 SQL merely for this hotfix.

## Deploy / reboot

YES / YES.

## Run order

1. Stop the currently hanging Streamlit run. It is preflight/read-only.
2. Deploy B2.15.3.1 and reboot.
3. Open Response Truth Transaction Preflight.
4. JOVI first.
5. Click `Preparar B2.15.3.1 — SEM WRITE`.
6. Download/send JSON.

Expected JOVI: `NO_TRANSACTION_REQUIRED`, 0 events, probe false, real-write false.
