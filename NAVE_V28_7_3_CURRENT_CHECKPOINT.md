# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed

Upstream:
- V28.7.2C0.2.4H3.1.3 — Festivalzinho Chambinho: GOLDEN APPROVED.
- V28.7.2C0.2.4H3.1.3 — JOVI: GOLDEN APPROVED.

Response adjudication shadow:
- V28.7.3B2.12.2.2 — Festivalzinho Chambinho: GOLDEN APPROVED.
- V28.7.3B2.12.2.2 — JOVI: GOLDEN APPROVED.

JOVI B2.12.2.2 baseline:
- 70 Current / 70 semantic eligible;
- 0 semantic excluded / 0 unknown;
- queue 33;
- 1 confirm / 6 partial / 26 reject;
- 1 completeness downgrade;
- 1 canonical identity collision;
- no Human Review, Truth, persistence or cutover effect.

## Active checkpoint

**V28.7.3B2.12.3 — Canonical Requirement Identity Collision Resolution Shadow**

B2.13 / any response Truth-effect remains blocked.

## Why B2.12.3 exists

JOVI contains one exact canonical obligation represented by two Current Requirement identities:
co-investment / sponsorship / shared budget + organic/paid KOL content during launch.

The identities have different historical provenance and metadata.
The existing reconciliation policy intentionally never auto-merges two existing identities.
That invariant remains correct.

B2.12.3 therefore does NOT resolve the database state. It produces a governed shadow plan.

## B2.12.3 contract

- source-bounded canonical obligation only;
- exact normalized canonical equality required;
- semantic eligibility required;
- provenance-aware survivor ranking;
- human_confirmed wins;
- evidence-led identity outranks legacy mirror when provenance is materially stronger;
- full title outranks a truncated title;
- metadata conflicts are exposed, never silently reconciled;
- active occurrence and legacy alias rebind counts are projected;
- no auto-merge;
- no persistence;
- no Truth change;
- no Human Review synthesis;
- no cutover.

A plan may be labeled `ready_for_transactional_resolution`, but this means only that a
future explicit B2.12.4 transaction can be designed and Golden-tested.

## Golden order

1. Deploy B2.12.3.
2. Reboot.
3. Run Festivalzinho Chambinho.
4. Expected: zero canonical collisions.
5. Approve regression.
6. Run JOVI.
7. Expected: exactly one canonical collision.
8. Audit proposed survivor, superseded identity, metadata conflicts, occurrences and aliases.
9. Only after approval design B2.12.4 transactional supersession.

## Governance freeze

Still frozen:
- requirements read_mode = shadow_compare;
- no domain_primary;
- no canary change;
- no Human Review synthesis;
- no response persistence;
- no Requirement identity mutation;
- no auto-merge;
- no B2.13 / Truth effect;
- no master reprocessing.
