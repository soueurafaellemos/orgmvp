from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_semantic_recall_bridge import (
    SEMANTIC_RECALL_BRIDGE_VERSION,
    run_semantic_recall_bridge,
)

st.set_page_config(
    page_title="Semantic Recall Bridge | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Semantic Recall Bridge",
    "Endurece o auto-recall do B2.8 e procura candidatos PT↔EN, paráfrase e contexto adjacente como REVIEW ONLY.",
    eyebrow=f"NAVE by VOE · {SEMANTIC_RECALL_BRIDGE_VERSION} · shadow only",
)

client = get_nave_client()

rows = (
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
    str(r.get("project_id") or "")
    for r in rows
    if r.get("project_id")
})
if not project_ids:
    st.warning("Nenhum matrix requirements canary ativo encontrado.")
    st.stop()

projects = []
for project_id in project_ids:
    result = (
        client.table("projects")
        .select("*")
        .eq("id", project_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    row = dict(result[0]) if result else {"id": project_id}
    label = (
        row.get("project_name")
        or row.get("event_name")
        or row.get("name")
        or project_id
    )
    projects.append((f"{label} · {project_id}", project_id))

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

if st.button("Executar Semantic Recall Bridge B2.9", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.9 BLOCKED: requirements não está em shadow_compare.")
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
                "B2.9 BLOCKED: briefing/matrix canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner("Auditando recall semântico multilíngue..."):
            result = run_semantic_recall_bridge(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_WITH_STRICT_SAFE_RECALL":
            st.success(
                "B2.9: PASS_WITH_STRICT_SAFE_RECALL · há candidatos que continuam "
                "seguros após endurecer a atomicidade."
            )
        elif result.status == "PASS_WITH_SEMANTIC_RECALL_REVIEW":
            st.warning(
                "B2.9: PASS_WITH_SEMANTIC_RECALL_REVIEW · o principal ganho de recall "
                "depende de PT↔EN/paráfrase/janela contextual e permanece review-only."
            )
        else:
            st.info(
                "B2.9: PASS_NO_SAFE_SEMANTIC_RECALL · nenhuma nova evidência segura "
                "ou ponte semântica relevante foi encontrada."
            )

        st.caption(
            "Nenhuma equivalência PT↔EN ou janela adjacente promove resposta. "
            "Esses sinais existem exclusivamente para revisão."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": SEMANTIC_RECALL_BRIDGE_VERSION,
                "status": result.status,
                "current_requirements": result.current_requirement_count,
                "already_verified_response":
                    result.already_verified_response_count,
                "scanned_requirements":
                    result.scanned_requirement_count,
                "b28_old_permissive_auto":
                    result.old_permissive_auto_count,
                "b29_strict_safe_auto":
                    result.strict_safe_auto_count,
                "downgraded_compound_atom":
                    result.downgraded_compound_atom_count,
                "multilingual_review_requirements":
                    result.multilingual_review_requirement_count,
                "context_window_review_requirements":
                    result.context_window_review_requirement_count,
                "remaining_no_candidate":
                    result.remaining_no_candidate_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Recall calibrado")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(1100, 140 + len(detail) * 28),
            )
            st.download_button(
                "Baixar B2.9 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_9_SEMANTIC_RECALL_{project_id}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"B2.9 BLOCKED: {type(exc).__name__}: {exc}")
