from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_auto_adjudication_recommendation import (
    AUTO_ADJUDICATION_VERSION,
    run_automated_adjudication_recommendations,
)

st.set_page_config(
    page_title="Automated Adjudication Recommendations | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Automated Adjudication Recommendations",
    "B2.12.1 elimina a classificação manual linha a linha: a NAVE recomenda automaticamente confirmar, parcial, rejeitar, revisão visual ou adiar. As recomendações continuam machine-only, sem Human Review, sem Truth e sem persistência.",
    eyebrow=f"NAVE by VOE · {AUTO_ADJUDICATION_VERSION} · machine recommendation shadow",
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

st.info(
    "Você não precisa classificar nenhuma linha manualmente. "
    "Esta fase gera recomendações automáticas para toda a fila B2.12 de uma vez."
)

if st.button("Executar recomendações automáticas B2.12.1", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.12.1 BLOCKED: requirements não está em shadow_compare.")
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
                "B2.12.1 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner("Analisando automaticamente toda a fila de review..."):
            result = run_automated_adjudication_recommendations(
                client,
                project_id=project_id,
            )

        st.success(
            "B2.12.1 concluído. Nenhuma intervenção humana linha a linha foi necessária."
        )
        st.caption(
            "Governança: `recommend_confirm` NÃO é `verified_response` e NÃO é Human Review. "
            "Nenhuma recomendação desta página altera Truth, Supabase, read_mode, domain_primary, canaries ou cutover."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": AUTO_ADJUDICATION_VERSION,
                "status": result.status,
                "queue_count": result.queue_count,
                "recommend_confirm": result.recommend_confirm_count,
                "recommend_partial": result.recommend_partial_count,
                "recommend_reject": result.recommend_reject_count,
                "recommend_visual_review": result.recommend_visual_review_count,
                "recommend_defer": result.recommend_defer_count,
                "human_review_created": False,
                "truth_changed": False,
                "persistence_performed": False,
                "cutover_approved": False,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.recommendation_rows))
        if not detail.empty:
            preferred = [
                "machine_recommendation",
                "machine_confidence",
                "requirement_title",
                "projected_response_status",
                "evidence_locator",
                "machine_rationale",
                "machine_rule_id",
                "evidence_text",
                "requirement_atoms",
                "shared_atoms",
                "missing_atoms",
                "missing_hard_atoms",
                "candidate_id",
                "requirement_id",
            ]
            visible = [c for c in preferred if c in detail.columns]
            st.markdown("#### Recomendações automáticas")
            st.dataframe(
                detail[visible],
                hide_index=True,
                width="stretch",
                height=min(1200, 180 + len(detail) * 34),
            )

            st.download_button(
                "Baixar B2.12.1 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_12_1_AUTO_ADJUDICATION_{project_id}.csv",
                mime="text/csv",
            )
            st.download_button(
                "Baixar B2.12.1 completo em JSON",
                data=json.dumps(
                    result.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ).encode("utf-8"),
                file_name=f"NAVE_B2_12_1_AUTO_ADJUDICATION_{project_id}.json",
                mime="application/json",
            )

    except Exception as exc:
        st.error(f"B2.12.1 BLOCKED: {type(exc).__name__}: {exc}")
