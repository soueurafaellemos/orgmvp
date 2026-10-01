# NAVE V28.7.3B2.13 — Post-Supersession Response Projection Integrity Shadow

## Why this phase exists

B2.12.5.4 proved that Requirement identity supersession can be executed transactionally.
B2.13 asks the downstream question:

> Does the Current response layer remain semantically identical after identity consolidation,
> except for the intentional removal of the duplicate Requirement identity?

This is deliberately read-only. It does not design or apply Response Truth.

## Baseline contract

The page requires the original approved `V28.7.3B2.12.2.2` JSON for the same project.
That artifact is the pre-supersession semantic baseline.

The baseline is not silently reconstructed from today's database because doing so would
erase the historical comparison we need to prove.

## JOVI checks

B2.13:
- reruns B2.12.2.2 live over the post-supersession Current reader;
- loads the completed B2.12.5.4 transaction lineage;
- reruns the independent post-transaction verifier;
- requires Current IDs = baseline IDs minus superseded IDs;
- requires survivor present / old identities absent from Current-facing response outputs;
- compares all surviving projection and recommendation rows exactly;
- separately proves the duplicate pre-supersession rows had the same response-semantic
  signature despite legitimate identity/business-metadata differences;
- derives the expected queue/recommendation distribution delta from the exact old row(s);
- requires zero canonical collisions;
- requires historical Evidence/Semantic Observation/lineage preservation;
- requires Response Truth unchanged.

## Chambinho control

With no completed supersession, B2.13 becomes a strict control:
- same Current identity set;
- same projection rows;
- same recommendation rows;
- same counts/distribution/collision count.

Any difference blocks the phase.

## Files

ADD:
- `project_requirement_response_truth_impact_shadow.py`
- `pages/41_Response_Truth_Impact_Shadow.py`
- `tests/test_v28_7_3b2_13_response_truth_impact_shadow.py`
- `GUIA_NAVE_V28_7_3B2_13_RESPONSE_TRUTH_IMPACT_SHADOW.md`

REPLACE:
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL
NO.

## Reboot
YES.

## Golden order

1. Deploy + reboot.
2. Open `🪞 Response Truth Impact Shadow`.
3. Run **Chambinho first** with its original B2.12.2.2 JSON.
4. Download/send B2.13 JSON.
5. Only after Chambinho control passes, run JOVI with its original pre-supersession
   B2.12.2.2 JSON.
6. Download/send B2.13 JSON.
7. No Truth effect or persistence follows automatically from PASS.
