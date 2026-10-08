# NAVE V28.7.3B2.15.2 — Contract-Verified Response Truth Projection Shadow

## What B2.15.1 proved

The ledger schema is installed cleanly:
- 15/15 verifier checks passed;
- tables/views/triggers/RLS exist;
- event/evidence/current-truth stores are empty;
- Goldens are still `shadow_compare`;
- no Human Response Review type was activated.

That closes schema installation, not the write path.

## What B2.15.2 proves

B2.15.2 is the first dry-run against the actual ledger contract.

For every `eligible_contract_verified` Requirement it builds the exact immutable event
that a later writer would insert:

- `event_action = assertion`
- `truth_state = verified_response`
- `provenance_type = governed_response_contract`
- `actor_type = system_contract`
- `source_contract_version = V28.7.3B2.7.1`
- exact Requirement identity + Knowledge Entity identity
- exact supporting Evidence Unit(s)
- frozen Evidence locator/text hash
- deterministic SHA-256 event signature
- deterministic projected event UUID

It does NOT insert anything.

## Frozen Golden provenance

### Chambinho
Only these three Requirements may project Truth:

- Brindes
  - Requirement `cf0516d7-4cf4-49c2-94dd-858dd3ab907c`
  - Evidence `884f4586-c46a-4624-9fa5-c89f63fc1f2e`

- Espaço e ativações Chambinho
  - Requirement `40433db9-3b46-4d68-9add-18eb5d479ef8`
  - Evidence `7bfc9e2f-1bb6-416e-b9a8-f54034964e47`

- Memória afetiva
  - Requirement `be3b3716-95bc-4689-b646-95cfe872988c`
  - Evidence `7bfc9e2f-1bb6-416e-b9a8-f54034964e47`

Press kit / Seeding remains excluded because it is `eligible_human_confirmation_only`.

Expected:
- 13 Current Requirements
- 3 contract-eligible
- 1 human-confirmation candidate
- 3 projected events
- 3 projected event→Evidence links
- 0 persisted ledger rows before and after

### JOVI
Expected:
- 69 Current Requirements
- 0 contract-eligible
- 1 human-confirmation candidate (Plenária)
- 0 projected events
- 0 projected event→Evidence links

## SQL
NO.

## Deploy / reboot
YES / YES.

## Run order
1. Deploy patch + reboot.
2. Open `🧱 Response Truth Ledger Projection`.
3. Run Chambinho first.
4. Download/send JSON.
5. Only after Chambinho Golden, run JOVI control.
6. No write follows automatically.

## Important
`safe_to_write_response_truth` is deliberately `false` even on PASS.
A later phase must separately design a transactional writer and a rollback-only probe.
