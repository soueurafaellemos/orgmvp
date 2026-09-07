# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.2.2 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.3 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.4 Chambinho: GOLDEN APPROVED.

## JOVI B2.12.4 finding

The core projected transaction was correct:
- Current 70 -> 69;
- canonical collisions 1 -> 0;
- one ready plan / zero blockers;
- survivor e6fe10bf-b69e-56f6-a02e-46ff16c74f2f;
- superseded a9536b6a-745f-462c-a78a-637ca59aa216;
- duplicate occurrence correctly detected;
- Legacy alias preserved;
- B2.1 compatibility projected PASS 3/3.

However B2.12.4 is NOT Golden-closed for JOVI because:
1. nine old Domain Evidence links were projected one-for-one to the survivor
   (eight occurrence + one source on the same Evidence Unit);
2. Governance and Knowledge Entity writes were projected without validating the actual
   rows/lifecycle/canonical state that a real transaction would mutate.

## Active checkpoint

**V28.7.3B2.12.4.1 — Transaction Integrity Hardening · DRY RUN**

It remains read-only.

Hardening:
- validate actual Governance + Knowledge Entity rows;
- fail closed on lifecycle/canonical mismatch;
- coalesce historical evidence by Evidence Unit + link role;
- reuse existing survivor evidence where possible;
- preserve all old evidence links historically;
- preserve survivor business metadata;
- recompute occurrence identity;
- preserve/rebind Legacy alias;
- simulate B2.1 after state;
- no writes / Truth / Human Review / cutover.

## Governance freeze

B2.12.5 real write and B2.13 Truth-effect remain blocked until B2.12.4.1 closes Golden on Chambinho and JOVI.
