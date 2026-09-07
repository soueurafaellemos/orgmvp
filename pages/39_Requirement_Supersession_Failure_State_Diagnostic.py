from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_supersession_failure_diagnostic import VERSION, diagnose_failed_supersession

st.set_page_config(
    page_title="Supersession Failure Diagnostic | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Supersession Failure State Diagnostic",
    (
        "B2.12.5.2 prova o estado persistido depois de um erro de RPC sem chamar o writer. "
        "Classifica o banco como pre-write intacto, transaction completed ou estado inesperado."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · READ ONLY / INCIDENT DIAGNOSTIC",
)

st.error(
    "NÃO execute novamente o B2.12.5.x enquanto este diagnóstico não estiver fechado. "
    "Esta página é somente leitura e não possui botão de write."
)

uploaded = st.file_uploader(
    "Anexe o MESMO preflight JOVI B2.12.5.1 que foi revisado antes do erro",
    type=["json"],
)

if uploaded is not None:
    try:
        preflight = json.loads(uploaded.getvalue().decode("utf-8"))
    except Exception as exc:
        st.error(f"Preflight JSON inválido: {exc}")
        st.stop()

    st.caption(
        f"project_id={preflight.get('project_id')} · "
        f"review_fingerprint={preflight.get('review_fingerprint') or '—'}"
    )

    if st.button("Executar diagnóstico read-only pós-falha", type="primary"):
        client = get_nave_client()
        with st.spinner("Comparando estado persistido com pre-write e post-write esperados..."):
            result = diagnose_failed_supersession(client, preflight=preflight)

        classification = result.get("classification")
        if classification == "CONFIRMED_PREWRITE_STATE_INTACT":
            st.success(
                "CONFIRMED_PREWRITE_STATE_INTACT — o banco continua exatamente no estado "
                "anterior à supersession. Isto prova que o write não persistiu."
            )
        elif classification == "CONFIRMED_TRANSACTION_COMPLETED_STATE":
            st.warning(
                "CONFIRMED_TRANSACTION_COMPLETED_STATE — a transação persistiu apesar do erro "
                "HTTP/UI. NÃO execute o writer novamente."
            )
        else:
            st.error(
                f"{classification} — estado não corresponde integralmente a nenhum modelo seguro. "
                "Nenhuma nova tentativa é permitida."
            )

        st.dataframe(pd.DataFrame([
            {"model": "prewrite", **result.get("prewrite_model", {}).get("checks", {})},
            {"model": "postwrite", **result.get("postwrite_model", {}).get("checks", {})},
        ]), hide_index=True, width="stretch")

        st.json(result)
        st.download_button(
            "Baixar B2.12.5.2 Failure State Diagnostic JSON",
            data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            file_name=f"NAVE_B2_12_5_2_FAILURE_STATE_{preflight.get('project_id')}.json",
            mime="application/json",
        )
