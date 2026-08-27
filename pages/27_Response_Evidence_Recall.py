from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_response_recall_shadow import (
    RESPONSE_RECALL_VERSION,
    run_response_recall_shadow,
)

st.set_page_config(
    page_title="Response Evidence Recall | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Response Evidence Recall",
    "Procura evidências adicionais na apresentação para requirements ainda sem resposta verificada, sem relaxar o contrato de precisão B2.7.1.",
    eyebrow=f"NAVE by VOE · {RESPONSE_RECALL_VERSION} · shadow only",
)

client = get_nave_client()

canaries = (
    client.table("project_domain_consumer_canary")
    .select("*")
    .eq("domain_key", "requirements")
    .eq("consumer_key", "workspace.intelligence.matrix.requirements_readonly")
    .eq("status", "active")
    .execute()
    .data
    or []
)
project_ids = sorted({
    str(row.get("project_id") or "")
    for row in canaries
    if row.get("project_id")
})
if not project_ids:
    st.warning("Nenhum matrix requirements canary ativo encontrado.")
    st.stop()

projects = []
for project_id in project_ids:
    rows = (
        client.table("projects")
        .select("*")
        .eq("id", project_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    row = dict(rows[0]) if rows else {"id": project_id}
    label = (
        row.get("project_name")
        or row.get("event_name")
        or row.get("name")
        or project_id
    )
    projects.append((f"{label} · {project_id}", project_id))

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

if st.button("Executar Response Evidence Recall B2.8", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.8 BLOCKED: requirements não está em shadow_compare.")
            st.stop()

        briefing_canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key="requirements",
            consumer_key="workspace.briefing.requirements_readonly",
        )
        matrix_canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key="requirements",
            consumer_key="workspace.intelligence.matrix.requirements_readonly",
        )
        if not briefing_canary or not matrix_canary:
            st.error(
                "B2.8 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner(
            "Varredura evidence-first da apresentação em busca de recall seguro..."
        ):
            result = run_response_recall_shadow(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_WITH_RECOVERABLE_RECALL":
            st.success(
                "B2.8: PASS_WITH_RECOVERABLE_RECALL · existem requirements sem resposta "
                "verificada para os quais outra Evidence Unit material passa pelos mesmos "
                "gates de precisão."
            )
        elif result.status == "PASS_WITH_RECALL_REVIEW":
            st.warning(
                "B2.8: PASS_WITH_RECALL_REVIEW · não há recuperação automática segura, "
                "mas existem páginas candidatas para revisão."
            )
        else:
            st.info(
                "B2.8: PASS_NO_SAFE_RECALL_FOUND · a varredura não encontrou nova "
                "evidência que possa ser promovida sem relaxar a precisão."
            )

        st.caption(
            "Shadow only. `recoverable` ainda é candidato: nenhum match é persistido, "
            "nenhuma matriz muda e nenhum `no_verified_response` vira automaticamente "
            "`verified_response` nesta página."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": RESPONSE_RECALL_VERSION,
                "status": result.status,
                "current_requirements":
                    result.current_requirement_count,
                "already_verified_response":
                    result.already_verified_response_count,
                "requirements_scanned":
                    result.requirements_scanned_count,
                "recoverable_verified_candidates":
                    result.recoverable_verified_candidate_count,
                "recall_review_candidates":
                    result.review_candidate_count,
                "no_safe_candidate":
                    result.no_candidate_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Recall projetado por requirement")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(1100, 140 + len(detail) * 28),
            )
            st.download_button(
                "Baixar B2.8 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_8_RECALL_{project_id}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"B2.8 BLOCKED: {type(exc).__name__}: {exc}")
