from __future__ import annotations

import json
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_response_truth_projection_shadow import project_options
from project_requirement_response_truth_transaction import (
    build_response_truth_transaction_preflight,
)
from project_requirement_response_truth_transaction_probe import (
    VERSION,
    run_response_truth_transaction_probe,
)

st.set_page_config(
    page_title="Response Truth Transaction Probe | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()

page_header(
    "Response Truth Transaction Probe",
    (
        "B2.15.3P1 executa o writer inteiro dentro de uma subtransação "
        "obrigatoriamente revertida e reconstrói o preflight depois."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · ROLLBACK ONLY",
)

st.error("Este probe NÃO autoriza write real.")

options = project_options()
label_to_id = {item["label"]: item["project_id"] for item in options}
selected_label = st.selectbox("Projeto", list(label_to_id), index=0)
project_id = label_to_id[selected_label]

client = get_nave_client()
preview = build_response_truth_transaction_preflight(client, project_id=project_id)

st.json({
    "preflight_status": preview.get("status"),
    "projected_event_count": preview.get("projected_event_count"),
    "projected_evidence_link_count": preview.get("projected_evidence_link_count"),
    "review_fingerprint": preview.get("review_fingerprint"),
    "ready_for_probe": preview.get("ready_for_probe"),
    "ready_for_real_write": preview.get("ready_for_real_write"),
})

if preview.get("status") == "NO_TRANSACTION_REQUIRED":
    st.success("Controle negativo: nenhum transaction probe é necessário.")
elif preview.get("status") != "READY_FOR_ROLLBACK_ONLY_PROBE":
    st.error("O preflight atual não permite probe.")
else:
    confirm = st.checkbox("Confirmo executar somente o rollback-only probe.", value=False)
    if st.button(
        "EXECUTAR B2.15.3P1 — ROLLBACK-ONLY PROBE",
        type="primary",
        disabled=not confirm,
    ):
        with st.spinner("Executando writer em subtransação e verificando rollback..."):
            result = run_response_truth_transaction_probe(
                client,
                project_id=project_id,
            )

        if result.get("rollback_independently_verified"):
            st.success("Rollback independentemente verificado.")
        else:
            st.error("Rollback não foi independentemente verificado. Pare aqui.")

        st.json(result)
        st.download_button(
            "Baixar B2.15.3P1 Transaction Probe JSON",
            data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            file_name=f"NAVE_B2_15_3P1_TRANSACTION_PROBE_{project_id}.json",
            mime="application/json",
        )
