from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_response_contract_canary import (
    RESPONSE_CONTRACT_VERSION,
    run_response_contract_canary,
)

st.set_page_config(
    page_title="Requirement Response Contract | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Response Contract",
    "Projeta o contrato client-facing de resposta ao briefing sem alterar a matriz atual: resposta verificada, revisão de evidência, falso positivo excluído ou sem resposta verificada.",
    eyebrow=f"NAVE by VOE · {RESPONSE_CONTRACT_VERSION} · canary projection",
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

if st.button("Executar Requirement Response Contract B2.7.1", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.7.1 BLOCKED: requirements não está em shadow_compare.")
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
                "B2.7.1 BLOCKED: briefing/matrix canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner("Projetando contrato de resposta..."):
            result = run_response_contract_canary(
                client,
                project_id=project_id,
            )

        if result.status == "BLOCKED_CURRENT_RESPONSE_FALSE_POSITIVE":
            st.error(
                "B2.7.1: BLOCKED_CURRENT_RESPONSE_FALSE_POSITIVE · a leitura atual "
                "ainda contém pelo menos uma resposta governada sustentada por "
                "evidência semanticamente incompatível."
            )
        elif result.status == "PASS_WITH_RESPONSE_REVIEW":
            st.warning(
                "B2.7.1: PASS_WITH_RESPONSE_REVIEW · não há falso positivo material "
                "confirmado, mas existe evidência/ownership que ainda exige revisão."
            )
        else:
            st.success(
                "B2.7.1: PASS_RESPONSE_PRECISION · as respostas atualmente afirmadas "
                "passam pelo contrato de precisão."
            )

        st.caption(
            "IMPORTANTE: `no_verified_response` NÃO significa automaticamente que a "
            "proposta não respondeu. Pode significar que o retrieval ainda não encontrou "
            "evidência suficiente. B2.7.1 mede precisão das afirmações atuais, não recall completo."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": RESPONSE_CONTRACT_VERSION,
                "status": result.status,
                "requirements_total": result.total_requirements,
                "verified_response": result.verified_response_count,
                "response_review": result.response_review_count,
                "false_positive_excluded":
                    result.false_positive_excluded_count,
                "no_verified_response":
                    result.no_verified_response_count,
                "cross_domain_supported":
                    result.cross_domain_supported_count,
                "semantic_component_review":
                    result.component_review_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        req_df = pd.DataFrame(list(result.requirement_rows))
        if not req_df.empty:
            # Keep export scalar-friendly.
            export_df = req_df.copy()
            export_df["response_evidence"] = export_df["response_evidence"].apply(
                lambda value: json.dumps(value, ensure_ascii=False)
            )

            st.markdown("#### Requirements · contrato projetado")
            st.dataframe(
                req_df.drop(columns=["response_evidence"]),
                hide_index=True,
                width="stretch",
                height=min(1000, 130 + len(req_df) * 34),
            )
            st.download_button(
                "Baixar requirements B2.7 em CSV",
                data=export_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_7_REQUIREMENTS_{project_id}.csv",
                mime="text/csv",
            )

        semantic_df = pd.DataFrame(list(result.semantic_response_rows))
        if not semantic_df.empty:
            st.markdown("#### Respostas semânticas fora de requirements")
            st.dataframe(
                semantic_df,
                hide_index=True,
                width="stretch",
            )
            st.download_button(
                "Baixar semantic responses B2.7 em CSV",
                data=semantic_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_7_SEMANTIC_{project_id}.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(f"B2.7.1 BLOCKED: {type(exc).__name__}: {exc}")
