from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_unified_semantic_audit import (
    SEMANTIC_AUDIT_VERSION,
    run_unified_semantic_audit,
)

st.set_page_config(
    page_title="Unified Semantic Counterpart Audit | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Unified Semantic Counterpart Audit",
    "Ranqueia possíveis counterparts sem criar aliases e destaca sinais de evidência fraca nos matches atuais do Unified.",
    eyebrow=f"NAVE by VOE · {SEMANTIC_AUDIT_VERSION} · read only",
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
project_ids = sorted({str(row.get("project_id") or "") for row in canaries if row.get("project_id")})
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
    label = row.get("project_name") or row.get("event_name") or row.get("name") or project_id
    projects.append((f"{label} · {project_id}", project_id))

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

if st.button("Executar Semantic Counterpart Audit B2.4.3", type="primary"):
    try:
        readiness = get_cutover_state(client, project_id, "requirements")
        if readiness.get("read_mode") != "shadow_compare":
            st.error("B2.4.3 BLOCKED: requirements não está em shadow_compare.")
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
            st.error("B2.4.3 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos.")
            st.stop()

        with st.spinner("Ranqueando counterparts e auditando evidências atuais..."):
            result = run_unified_semantic_audit(client, project_id=project_id)

        if result.status == "PASS":
            st.success("B2.4.3: PASS")
        elif result.status == "BLOCKED_SCORE_PARITY_DRIFT":
            st.error("B2.4.3: BLOCKED_SCORE_PARITY_DRIFT")
        else:
            st.warning(
                f"B2.4.3: {result.status} · diagnóstico material para revisão; nenhum alias ou filtro foi aplicado."
            )

        st.caption(
            "Candidate score é somente ranking diagnóstico. Nunca vira alias, Truth ou regra de runtime. "
            "Evidence quality flags também são sinais de revisão, não decisões automáticas."
        )

        st.dataframe(pd.DataFrame([{
            "version": SEMANTIC_AUDIT_VERSION,
            "status": result.status,
            "legacy_divergent_matches": result.legacy_divergent_match_count,
            "domain_only_matches": result.domain_only_match_count,
            "high_review_risk_matches": result.high_review_risk_match_count,
            "restatement_review_matches": result.restatement_review_match_count,
            "candidate_rows": result.counterpart_candidate_row_count,
            "exact_score_parity": result.exact_score_parity,
        }]), hide_index=True, width="stretch")

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Counterparts candidatos + qualidade da evidência atual")
            st.dataframe(detail, hide_index=True, width="stretch", height=min(900, 130 + len(detail) * 35))
            st.download_button(
                "Baixar B2.4.3 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_4_3_{project_id}.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(f"B2.4.3 BLOCKED: {type(exc).__name__}: {exc}")
