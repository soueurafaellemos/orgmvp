from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_unified_input_audit import (
    INPUT_SHAPE_AUDIT_VERSION,
    run_unified_input_shape_audit,
)


st.set_page_config(
    page_title="Unified Matcher Input Audit | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Unified Matcher Input-Shape Audit",
    "Testa se requirements semanticamente idênticos por título recebem scores diferentes porque o objeto Domain carrega mais texto no matcher. Diagnóstico apenas.",
    eyebrow=f"NAVE by VOE · {INPUT_SHAPE_AUDIT_VERSION} · read only",
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

if st.button("Executar Unified Matcher Input Audit B2.4.1", type="primary"):
    try:
        readiness = get_cutover_state(client, project_id, "requirements")
        if readiness.get("read_mode") != "shadow_compare":
            st.error("B2.4.1 BLOCKED: requirements não está em shadow_compare.")
            st.stop()

        with st.spinner("Comparando input Legacy e Domain contra a mesma evidência..."):
            result = run_unified_input_shape_audit(
                client,
                project_id=project_id,
            )

        if result.status == "INPUT_SHAPE_CALIBRATION_REQUIRED":
            st.warning(
                "B2.4.1: INPUT_SHAPE_CALIBRATION_REQUIRED · existe counterpart Domain "
                "com título exatamente igual, mas o score cai abaixo do threshold ao "
                "usar o input Domain mais rico."
            )
        elif result.status == "IDENTITY_LINEAGE_REVIEW_REQUIRED":
            st.warning(
                "B2.4.1: IDENTITY_LINEAGE_REVIEW_REQUIRED · existem counterparts por "
                "título exato, mas a divergência não é explicada apenas por score dilution."
            )
        elif result.status == "SEMANTIC_SET_REVIEW_REQUIRED":
            st.warning(
                "B2.4.1: SEMANTIC_SET_REVIEW_REQUIRED · a divergência vem de requirements "
                "sem counterpart exato no outro conjunto."
            )
        else:
            st.success("B2.4.1: PASS")

        st.caption(
            "Título exato aqui é apenas diagnóstico. Nenhum alias é criado e nenhum "
            "matching lexical é usado para alterar runtime, Truth ou consumers."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": INPUT_SHAPE_AUDIT_VERSION,
                "status": result.status,
                "legacy_divergent_matches":
                    result.legacy_divergent_match_count,
                "with_exact_domain_title":
                    result.legacy_divergent_with_exact_domain_title,
                "without_exact_domain_title":
                    result.legacy_divergent_without_exact_domain_title,
                "exact_title_score_dilution":
                    result.exact_title_score_dilution_count,
                "domain_only_matches": result.domain_only_match_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Diagnóstico por requirement")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(850, 120 + len(detail) * 40),
            )
            st.download_button(
                "Baixar B2.4.1 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_4_1_{project_id}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"B2.4.1 BLOCKED: {type(exc).__name__}: {exc}")
