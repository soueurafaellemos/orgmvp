from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_response_truth_projection_shadow import (
    CHAMBINHO,
    VERSION,
    project_options,
    run_contract_verified_response_truth_projection_shadow,
)

st.set_page_config(
    page_title="Response Truth Ledger Projection | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()

page_header(
    "Contract-Verified Response Truth Projection",
    (
        "B2.15.2 projeta, sem escrever, os Response Truth events que seriam "
        "permitidos pelo contrato B2.7.1 e pelo B2.14. Machine recommendations "
        "e candidatos de confirmação humana permanecem fora do ledger."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · READ ONLY / LEDGER DRY RUN",
)

st.warning(
    "Nenhum Response Truth é persistido nesta página. "
    "O campo `safe_to_write_response_truth` permanece FALSE por design."
)

options = project_options()
label_to_id = {item["label"]: item["project_id"] for item in options}
selected_label = st.selectbox("Projeto", list(label_to_id), index=0)
project_id = label_to_id[selected_label]

if project_id == CHAMBINHO:
    st.caption(
        "Golden order: Chambinho primeiro. Esperado: 3 events / 3 evidence links."
    )
else:
    st.warning(
        "JOVI é controle negativo desta fase. Rode somente depois de Chambinho ser aprovado. "
        "Esperado: 0 contract-verified events; Plenária continua human-confirmation candidate."
    )

if st.button("Executar B2.15.2 — READ ONLY", type="primary"):
    client = get_nave_client()
    with st.spinner(
        "Projetando immutable Response Truth events e validando Evidence/identity..."
    ):
        result = run_contract_verified_response_truth_projection_shadow(
            client,
            project_id=project_id,
        )

    if result.get("all_checks_pass"):
        st.success(
            "PASS — projeção compatível com o ledger, sem persistência."
        )
    else:
        st.error(
            "B2.15.2 bloqueado. Existe drift de identity, Evidence, eligibility "
            "ou estado do ledger."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Requirements", result.get("current_requirement_count", "—"))
    c2.metric("Contract eligible", result.get("contract_eligible_count", "—"))
    c3.metric("Projected events", result.get("projected_event_count", "—"))
    c4.metric(
        "Projected evidence links",
        result.get("projected_evidence_link_count", "—"),
    )

    checks = result.get("checks") or {}
    st.subheader("Checks")
    st.dataframe(
        pd.DataFrame([
            {"check": key, "pass": bool(value)}
            for key, value in checks.items()
        ]),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Projected immutable events")
    events = result.get("event_plans") or []
    if events:
        st.dataframe(
            pd.DataFrame([
                {
                    "requirement_id": row.get("requirement_id"),
                    "requirement_entity_id": row.get("requirement_entity_id"),
                    "truth_state": row.get("truth_state"),
                    "provenance_type": row.get("provenance_type"),
                    "evidence_count": len(row.get("evidence_links") or []),
                    "event_signature": row.get("event_signature"),
                }
                for row in events
            ]),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Nenhum contract-verified event deve ser criado para este projeto.")

    human = result.get("excluded_human_confirmation_candidates") or []
    if human:
        st.subheader("Explicitly excluded human-confirmation candidates")
        st.dataframe(pd.DataFrame(human), hide_index=True, width="stretch")

    diagnostics = result.get("diagnostics") or {}
    if any(diagnostics.values()):
        st.subheader("Diagnostics")
        st.json(diagnostics)

    st.json(result)
    st.download_button(
        "Baixar B2.15.2 Response Truth Projection JSON",
        data=json.dumps(
            result, ensure_ascii=False, indent=2, default=str
        ).encode("utf-8"),
        file_name=f"NAVE_B2_15_2_RESPONSE_TRUTH_PROJECTION_{project_id}.json",
        mime="application/json",
    )
