# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI.
- B2.12.2.2 Chambinho/JOVI.
- B2.12.3 Chambinho/JOVI.
- B2.12.4.1 Chambinho/JOVI.
- H3.1.3P1 normal pipeline promotion Chambinho/JOVI.
- B2.12.5 preflight Chambinho control: GOLDEN APPROVED.
- B2.12.5 preflight JOVI: semantic transaction plan PASS, but real write NOT YET APPROVED.

## Active checkpoint
**V28.7.3B2.12.5.1 — Confirmation Binding + RPC Permission Hardening**

Two last writer-governance gaps were found before the first write:
1. user confirmation must be cryptographically bound to the exact reviewed plan;
2. the RPC must explicitly revoke EXECUTE from PUBLIC in addition to anon/authenticated.

No real supersession write has been executed.

B2.12.5.1 requires fresh preflight after deploy. JOVI write remains blocked until the
fingerprint-bound preflight is reviewed and explicitly approved.

B2.13 remains blocked.
