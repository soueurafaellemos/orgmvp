from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_response_truth_projection_shadow import project_options
from project_requirement_response_truth_transaction import (
    VERSION,
    build_response_truth_transaction_preflight,
)

st.set_page_config(
    page_title="Response Truth Transaction Preflight | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()

page_header(
    "Response Truth Transaction Preflight",
    (
        "B2.15.3.1 usa o Golden B2.15.2.1 congelado por SHA-256 e valida apenas guards live. "
        "Esta página NÃO possui botão de write real."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · PRE-FLIGHT ONLY",
)

st.error(
    "WRITE REAL NÃO ESTÁ AUTORIZADO NESTA FASE. "
    "O próximo gate é o rollback-only probe."
)

options = project_options()
label_to_id = {item["label"]: item["project_id"] for item in options}
selected_label = st.selectbox("Projeto", list(label_to_id), index=1)
project_id = label_to_id[selected_label]

if st.button("Preparar B2.15.3.1 — SEM WRITE", type="primary"):
    client = get_nave_client()
    with st.spinner("Validando Golden congelado + guards live..."):
        result = build_response_truth_transaction_preflight(
            client,
            project_id=project_id,
        )

    if result.get("status") == "NO_TRANSACTION_REQUIRED":
        st.success("NO_TRANSACTION_REQUIRED — zero contract-verified events.")
    elif result.get("status") == "READY_FOR_ROLLBACK_ONLY_PROBE":
        st.warning("Pronto apenas para rollback-only probe. NÃO autoriza write real.")
    else:
        st.error("Preflight bloqueado.")

    st.json(result)

    events = ((result.get("execution_bundle") or {}).get("events") or [])
    if events:
        st.dataframe(
            pd.DataFrame([
                {
                    "requirement_id": row.get("requirement_id"),
                    "requirement_entity_id": row.get("requirement_entity_id"),
                    "event_signature": row.get("event_signature"),
                    "evidence_links": len(row.get("evidence_links") or []),
                }
                for row in events
            ]),
            hide_index=True,
            width="stretch",
        )

    st.download_button(
        "Baixar B2.15.3 Transaction Preflight JSON",
        data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        file_name=f"NAVE_B2_15_3_1_TRANSACTION_PREFLIGHT_{project_id}.json",
        mime="application/json",
    )
