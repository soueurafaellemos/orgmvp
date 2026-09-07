# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho: GOLDEN APPROVED.
- H3.1.3 JOVI: GOLDEN APPROVED.
- B2.12.2.2 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.3 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.4.1 Chambinho: GOLDEN APPROVED.
- B2.12.4.1 JOVI: GOLDEN APPROVED.
  - Current 70 -> projected 69.
  - collision 1 -> projected 0.
  - Governance / Knowledge Entity integrity PASS.
  - raw historical Evidence 9 -> 2 coalesced actions.
  - B2.1 projected PASS 3/3.
  - no writes.

## Newly discovered promotion blocker

After downstream + transaction dry-run Goldens, code review proved the normal
`project_intelligence_pipeline.py` still selected the base H3 entrypoint
`project_requirement_reconciliation.reconcile_project_requirements`.

The explicit repair page already selected:
`project_requirement_reconciliation_h31.reconcile_project_requirements`.

A real B2.12.5 supersession must not be executed while this page/pipeline divergence exists,
because a future normal project-intelligence run could reintroduce pre-H3.1.3 Requirement Truth.

## Active checkpoint

**V28.7.2C0.2.4H3.1.3P1 — Governed Normal Pipeline Promotion**

This is wiring-only promotion.

It:
- changes the normal Requirement reconciliation entrypoint to H3.1.3;
- preserves ordering A -> audits -> Requirement -> B;
- does not execute the pipeline at deploy/import time;
- does not rerun A/B/Graph;
- does not change masters;
- preserves legacy_shadow / requirements shadow_compare;
- does not change canaries or domain_primary;
- does not auto-merge Requirement identities;
- does not create Human Review.

## Verification order

1. Deploy P1 and reboot.
2. Open `Requirement Pipeline Promotion Verifier`.
3. Run Festivalzinho Chambinho — READ ONLY.
4. Expected: all checks pass; read_mode shadow_compare; no writes.
5. Send JSON.
6. After approval run JOVI — READ ONLY.
7. Expected: same wiring contract and shadow_compare.
8. Only after both pass may B2.12.5 real transactional supersession be installed/executed.

## Governance freeze

B2.12.5 real write and B2.13 response Truth-effect remain blocked until P1 wiring closes
Golden on both control projects.
