# NAVE V28.7.3B2.14 — Response Truth Eligibility & Provenance Shadow

B2.13 proved that Requirement identity consolidation created no downstream Response drift.
B2.14 now defines which provenance classes could support a later Response Truth ledger,
without writing that ledger.

## Eligibility
- `eligible_contract_verified`: governed B2.7.1 verified response + explicit supported Evidence.
- `eligible_human_confirmation_only`: machine `recommend_confirm`, high-confidence projection,
  explicit Evidence and no completeness downgrade. This is still NON-TRUTH until a future
  explicit human decision.
- all other machine/no-safe/false-positive states are not eligible.
- unknown state blocks the phase.

## Safety
No SQL. No writes. No Human Review creation. No Response Truth persistence. No cutover.

## Reboot
YES.

## Golden order
1. Chambinho.
2. JOVI.

Expected broad shape:
- Chambinho: 3 contract-verified rows + 1 human-confirmation candidate.
- JOVI: 0 contract-verified rows + 1 human-confirmation candidate.
These are expectations for review, not hard-coded pass criteria.
