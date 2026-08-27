from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_unified_residual_coverage import (
    RESIDUAL_COVERAGE_VERSION,
    run_residual_evidence_coverage_audit,
)

st.set_page_config(
    page_title="Unified Residual Evidence Coverage | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Unified Residual Evidence Coverage",
    "Testa se a mesma evidência material que sobrevive ao Evidence Role Gate também suporta algum Current Domain requirement. Nenhum alias é criado.",
    eyebrow=f"NAVE by VOE · {RESIDUAL_COVERAGE_VERSION} · read only",
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

if st.button("Executar Residual Evidence Coverage B2.4.5", type="primary"):
    try:
        readiness = get_cutover_state(client, project_id, "requirements")
        if readiness.get("read_mode") != "shadow_compare":
            st.error("B2.4.5 BLOCKED: requirements não está em shadow_compare.")
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
                "B2.4.5 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner(
            "Testando a evidência residual contra Current Domain requirements..."
        ):
            result = run_residual_evidence_coverage_audit(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_NO_RETAINED_RESIDUALS":
            st.success(
                "B2.4.5: PASS_NO_RETAINED_RESIDUALS · após o Evidence Role Gate "
                "não resta match Legacy material sem alias."
            )
        else:
            st.warning(
                f"B2.4.5: {result.status} · a evidência residual foi auditada contra "
                "todo o set Current Domain; nenhum alias foi criado."
            )

        st.caption(
            "O ranking usa a MESMA evidência da proposta e a fórmula atual do Unified. "
            "Title-only score é apenas hipótese diagnóstica; não altera runtime."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": RESIDUAL_COVERAGE_VERSION,
                "status": result.status,
                "retained_legacy_residuals":
                    result.retained_legacy_residual_count,
                "domain_full_support":
                    result.residual_with_domain_full_match_count,
                "title_only_support":
                    result.residual_with_title_only_match_count,
                "near_threshold":
                    result.residual_near_threshold_count,
                "no_domain_coverage":
                    result.residual_without_domain_coverage_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Top Current Domain candidates por evidência residual")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(900, 130 + len(detail) * 34),
            )
            st.download_button(
                "Baixar B2.4.5 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_4_5_{project_id}.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(f"B2.4.5 BLOCKED: {type(exc).__name__}: {exc}")
