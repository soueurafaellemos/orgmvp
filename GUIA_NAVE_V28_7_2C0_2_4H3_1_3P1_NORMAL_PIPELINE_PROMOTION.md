# NAVE H3.1.3P1 — Governed Normal Pipeline Promotion

## Why this step exists

H3.1.3 closed Golden upstream on Chambinho and JOVI, and downstream B2.12.2.2 /
B2.12.3 / B2.12.4.1 also closed.

Before the first real identity supersession write, repository review showed one
remaining architecture gap:

- explicit repair page -> `project_requirement_reconciliation_h31`
- normal project pipeline -> old `project_requirement_reconciliation`

Executing B2.12.5 before fixing this would leave a future normal run capable of
reintroducing old Requirement semantics.

## What P1 changes

Only normal-pipeline wiring:
- Requirement entrypoint becomes `project_requirement_reconciliation_h31.reconcile_project_requirements`.
- A / audits / B ordering is unchanged.
- H3.1.3 SQL contract remains the already-installed C0/H1 RPC.
- no migration.
- no data run on deployment.

The explicit repair page is retained, but its copy now correctly says H3.1.3 is also
the normal-pipeline entrypoint.

## Files

ADD:
- `project_requirement_pipeline_promotion.py`
- `pages/36_Requirement_Pipeline_Promotion_Verifier.py`
- `tests/test_v28_7_2c0_2_4h3_1_3p1_pipeline_promotion.py`
- `GUIA_NAVE_V28_7_2C0_2_4H3_1_3P1_NORMAL_PIPELINE_PROMOTION.md`

REPLACE:
- `project_intelligence_pipeline.py`
- `pages/33_Requirement_Semantic_Truth_Repair.py`
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL
NO.

## Reboot
YES.

## Golden order
1. Deploy + reboot.
2. Do NOT run Requirement Semantic Truth Repair.
3. Open Requirement Pipeline Promotion Verifier.
4. Run Chambinho and send JSON.
5. After approval, run JOVI and send JSON.
6. Only then move to B2.12.5 real write.
