from __future__ import annotations

import json
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_identity_supersession_probe import (
    VERSION,
    run_rollback_only_transaction_probe,
)

st.set_page_config(
    page_title="Supersession Transaction Probe | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Supersession Transaction Probe",
    (
        "B2.12.5.3 executa o caminho exato do writer dentro de uma subtransação "
        "que é obrigatoriamente revertida. Serve apenas para capturar a causa SQL "
        "da falha do B2.12.5.4."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · ROLLBACK-ONLY / INCIDENT PROBE",
)

st.error(
    "NÃO volte para o WRITE REAL. Este probe chama o writer somente dentro de um "
    "rollback obrigatório e depois verifica de forma independente que o banco "
    "continua no estado pre-write."
)

uploaded = st.file_uploader(
    "Anexe o preflight JOVI B2.12.5.4 usado na tentativa mais recente",
    type=["json"],
)

if uploaded is not None:
    try:
        preflight = json.loads(uploaded.getvalue().decode("utf-8"))
    except Exception as exc:
        st.error(f"Preflight JSON inválido: {exc}")
        st.stop()

    st.json({
        "version": preflight.get("version"),
        "project_id": preflight.get("project_id"),
        "status": preflight.get("status"),
        "ready_for_write": preflight.get("ready_for_write"),
        "review_fingerprint": preflight.get("review_fingerprint"),
        "execution_signature": preflight.get("execution_signature"),
    })

    confirm = st.checkbox(
        "Confirmo executar SOMENTE o probe rollback-only. Nenhum write real deve persistir.",
        value=False,
    )

    if st.button(
        "EXECUTAR B2.12.5.3 — PROBE COM ROLLBACK OBRIGATÓRIO",
        type="primary",
        disabled=not confirm,
    ):
        client = get_nave_client()
        with st.spinner(
            "Executando writer em subtransação, capturando SQLSTATE e verificando rollback..."
        ):
            result = run_rollback_only_transaction_probe(
                client,
                preflight=preflight,
            )

        if result.get("rollback_independently_verified"):
            st.success(
                "Rollback verificado independentemente. Nenhuma supersession real persistiu."
            )
        else:
            st.error(
                "O probe retornou, mas o estado pós-probe não foi confirmado como pre-write intacto. "
                "Não execute mais nada."
            )

        rpc = result.get("rpc") or {}
        if rpc.get("status") == "WRITER_FAILED_ROLLED_BACK":
            st.warning(
                "A causa PostgreSQL original foi capturada abaixo. "
                "Não tente o WRITE REAL novamente."
            )
            st.json(rpc.get("error") or {})
        elif rpc.get("status") == "WRITER_WOULD_COMPLETE_ROLLED_BACK":
            st.info(
                "O writer percorreu o caminho completo, mas o probe forçou rollback antes de retornar."
            )

        st.json(result)
        st.download_button(
            "Baixar B2.12.5.3 Transaction Probe JSON",
            data=json.dumps(
                result, ensure_ascii=False, indent=2, default=str
            ).encode("utf-8"),
            file_name=f"NAVE_B2_12_5_3_TRANSACTION_PROBE_{preflight.get('project_id')}.json",
            mime="application/json",
        )
