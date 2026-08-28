from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_response_recall_review_projection import (
    RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
    run_response_recall_review_projection,
)

st.set_page_config(
    page_title="Governed Response Recall Review Projection | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Governed Response Recall Review Projection",
    "B2.11 combina o contrato atual B2.7.1 com o recall calibrado B2.10.1 e projeta uma fila de revisão sem criar Truth, sem persistir Human Review e sem alterar consumidores.",
    eyebrow=f"NAVE by VOE · {RESPONSE_RECALL_REVIEW_PROJECTION_VERSION} · read-only projection",
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

if st.button("Executar Governed Response Recall Review Projection B2.11", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.11 BLOCKED: requirements não está em shadow_compare.")
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
                "B2.11 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner("Projetando contrato governado de resposta + recall..."):
            result = run_response_recall_review_projection(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_READ_ONLY_PROJECTION_WITH_REVIEW_AND_EXCLUSIONS":
            st.warning(
                "B2.11: projeção read-only concluída com fila de revisão e falsos positivos já excluídos do contrato projetado."
            )
        elif result.status == "PASS_READ_ONLY_PROJECTION_WITH_REVIEW":
            st.success(
                "B2.11: projeção read-only concluída com fila de revisão governada."
            )
        elif result.status == "PASS_READ_ONLY_PROJECTION_WITH_EXCLUSIONS":
            st.warning(
                "B2.11: projeção read-only concluída com exclusões, sem novos candidatos de revisão."
            )
        else:
            st.success(
                "B2.11: projeção read-only concluída sem fila adicional de revisão."
            )

        st.caption(
            "Somente respostas já verificadas pelo B2.7.1 permanecem `verified_response`. "
            "Todo recall B2.10.1 — inclusive STRICT_SAFE_AUTO_PRESERVED — continua REVIEW ONLY. "
            "Nenhum write, Human Review, Truth, read_mode, domain_primary ou canary é alterado."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
                "status": result.status,
                "total_requirements": result.total_requirements,
                "verified_response": result.verified_response_count,
                "review_high_confidence": result.high_confidence_review_count,
                "review_visual_or_structured": result.visual_or_structured_review_count,
                "review_partial": result.partial_review_count,
                "review_existing_evidence": result.existing_review_count,
                "false_positive_excluded": result.false_positive_excluded_count,
                "no_safely_verified_response": result.no_safely_verified_response_count,
                "source_role_rejected": result.source_role_rejected_count,
                "generic_overlap_rejected": result.generic_overlap_rejected_count,
                "strict_safe_recall_candidates_review_only": result.strict_safe_recall_candidate_count,
                "cutover_approved": False,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.requirement_rows))
        if not detail.empty:
            high = detail[
                detail["projected_response_status"] == "response_review_high_confidence"
            ]
            if not high.empty:
                st.markdown("#### Fila prioritária · High-confidence review")
                st.dataframe(
                    high,
                    hide_index=True,
                    width="stretch",
                    height=min(700, 140 + len(high) * 34),
                )

            st.markdown("#### Contrato projetado por requirement")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(1200, 160 + len(detail) * 30),
            )
            st.download_button(
                "Baixar B2.11 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_11_RESPONSE_RECALL_REVIEW_{project_id}.csv",
                mime="text/csv",
            )
            st.download_button(
                "Baixar B2.11 completo em JSON",
                data=json.dumps(
                    result.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ).encode("utf-8"),
                file_name=f"NAVE_B2_11_RESPONSE_RECALL_REVIEW_{project_id}.json",
                mime="application/json",
            )

        semantic = pd.DataFrame(list(result.semantic_response_rows))
        if not semantic.empty:
            st.markdown("#### Respostas semânticas cross-domain preservadas separadamente")
            st.caption(
                "Estas linhas continuam sendo conhecimento semântico do projeto e não são convertidas em compliance de requirement."
            )
            st.dataframe(
                semantic,
                hide_index=True,
                width="stretch",
                height=min(700, 140 + len(semantic) * 34),
            )

    except Exception as exc:
        st.error(f"B2.11 BLOCKED: {type(exc).__name__}: {exc}")
