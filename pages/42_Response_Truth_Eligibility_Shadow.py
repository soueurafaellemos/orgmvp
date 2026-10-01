from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_response_truth_eligibility_shadow import (
    VERSION,
    project_options,
    run_response_truth_eligibility_shadow,
)

st.set_page_config(
    page_title="Response Truth Eligibility Shadow | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()

page_header(
    "Response Truth Eligibility & Provenance Shadow",
    (
        "B2.14 define, sem persistência, quais respostas já possuem provenance de "
        "contrato suficiente para um futuro Truth ledger e quais podem apenas ser "
        "encaminhadas para confirmação humana explícita."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · READ ONLY / TRUTH ELIGIBILITY",
)

st.warning(
    "Machine recommendation NÃO é Response Truth. `recommend_confirm` cria apenas "
    "um candidato para confirmação humana explícita. Esta página não escreve Truth, "
    "não cria Human Review e não persiste decisões."
)

options = project_options()
label_to_id = {item["label"]: item["project_id"] for item in options}
selected_label = st.selectbox("Projeto", list(label_to_id), index=0)
project_id = label_to_id[selected_label]

if project_id == "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136":
    st.caption("Golden order: Chambinho primeiro.")
else:
    st.caption("JOVI deve ser executado somente após Chambinho ser revisado.")

if st.button("Executar B2.14 — READ ONLY", type="primary"):
    client = get_nave_client()
    with st.spinner("Classificando Response Truth eligibility e provenance..."):
        result = run_response_truth_eligibility_shadow(client, project_id=project_id)

    if result.get("all_checks_pass"):
        st.success(
            "PASS — todas as Current Requirements receberam uma classe de eligibility "
            "sem criar Truth ou Human Review."
        )
    else:
        st.error(
            "B2.14 bloqueado. Existe estado de Response/Provenance não classificado "
            "ou algum invariant de governança falhou."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Requirements", result.get("current_requirement_count", "—"))
    c2.metric("Contract verified", result.get("contract_verified_count", "—"))
    c3.metric(
        "Human confirmation candidates",
        result.get("human_confirmation_candidate_count", "—"),
    )
    c4.metric("Blocked", result.get("blocked_count", "—"))

    st.subheader("Eligibility distribution")
    dist = result.get("eligibility_counts") or {}
    st.dataframe(
        pd.DataFrame([
            {"eligibility_class": key, "count": value}
            for key, value in dist.items()
        ]),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Checks")
    checks = result.get("checks") or {}
    st.dataframe(
        pd.DataFrame([
            {"check": key, "pass": bool(value)}
            for key, value in checks.items()
        ]),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Requirement eligibility")
    st.dataframe(
        pd.DataFrame(result.get("eligibility_rows") or []),
        hide_index=True,
        width="stretch",
    )

    st.json(result)
    st.download_button(
        "Baixar B2.14 Response Truth Eligibility JSON",
        data=json.dumps(
            result, ensure_ascii=False, indent=2, default=str
        ).encode("utf-8"),
        file_name=f"NAVE_B2_14_RESPONSE_TRUTH_ELIGIBILITY_{project_id}.json",
        mime="application/json",
    )
