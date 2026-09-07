# NAVE V28.7.3B2.12.5.1 — Confirmation Binding + RPC Permission Hardening

## Why this hotfix exists

JOVI B2.12.5 preflight is semantically correct and projects the already Golden-approved
supersession. Before the first real write, two writer-governance gaps were found:

1. the UI confirmation token was bound only to `project_id`. The executor correctly rebuilt
   a fresh preflight before RPC, but it did not prove that the fresh plan was identical to
   the plan the user had just reviewed;
2. PostgreSQL functions may inherit EXECUTE for `PUBLIC` by default. Revoking only
   `anon, authenticated` is not a sufficiently explicit least-privilege contract.

No B2.12.5 write has been executed yet.

## Hardening

- deterministic `review_fingerprint` excludes timestamp noise and binds the exact
  transaction-critical execution plan;
- confirmation token is now
  `SUPERSEDE:<project_id>:<fingerprint-prefix>`;
- clicking WRITE rebuilds the fresh preflight;
- if fresh fingerprint != reviewed fingerprint, no RPC is called;
- SQL verifies token + full fingerprint + bundle fingerprint;
- old 6-arg RPC is dropped;
- new 7-arg RPC is explicitly revoked from `PUBLIC`, `anon`, `authenticated`;
- execute remains granted only to `service_role`;
- writer version becomes `V28.7.3B2.12.5.1`;
- post-transaction verifier expects the hardened writer version.

## SQL
YES. Re-run the supplied SQL after deploying this hotfix.

## Reboot
YES.

## Golden order
1. Install B2.12.5.1 SQL.
2. Deploy code + reboot.
3. Re-run Chambinho PRE-FLIGHT only: NO_TRANSACTION_REQUIRED, no write button.
4. Send JSON.
5. Re-run JOVI PRE-FLIGHT only.
6. Confirm new `review_fingerprint` and fingerprint-bound token.
7. Send JSON.
8. Only after explicit approval execute JOVI WRITE once.
