from __future__ import annotations

"""NAVE V28.7.3B2.4 — Unified Requirements Reconciliation."""

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_unified_reconciliation import (
    UNIFIED_RECONCILIATION_VERSION,
    run_unified_requirement_reconciliation,
)


st.set_page_config(
    page_title="Unified Requirements Reconciliation | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Unified Requirements Reconciliation",
    "Explica exatamente por que os briefing_matches do Unified diferem entre Legacy e Current Domain. Nenhum matcher ou consumer é alterado.",
    eyebrow=f"NAVE by VOE · {UNIFIED_RECONCILIATION_VERSION} · diagnostic only",
)

client = get_nave_client()

try:
    canaries = (
        client.table("project_domain_consumer_canary")
        .select("*")
        .eq("domain_key", "requirements")
        .eq("consumer_key", "workspace.briefing.requirements_readonly")
        .eq("status", "active")
        .execute()
        .data
        or []
    )
except Exception as exc:
    st.error(f"Não foi possível ler os requirements canaries: {exc}")
    st.stop()

project_ids = sorted({
    str(row.get("project_id") or "")
    for row in canaries
    if row.get("project_id")
})
if not project_ids:
    st.warning("Nenhum requirements canary ativo encontrado.")
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

if st.button("Executar Unified Requirement Reconciliation B2.4", type="primary"):
    try:
        readiness = get_cutover_state(client, project_id, "requirements")
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

        governance_blockers = []
        if readiness.get("read_mode") != "shadow_compare":
            governance_blockers.append("READ_MODE_NOT_SHADOW_COMPARE")
        if readiness.get("readiness_state") not in {"ready", "ready_with_findings"}:
            governance_blockers.append("READINESS_NOT_READY")
        if not bool(readiness.get("semantic_gate_ok")):
            governance_blockers.append("SEMANTIC_GATE_NOT_OK")
        if not bool(readiness.get("current_evidence_ok")):
            governance_blockers.append("CURRENT_EVIDENCE_NOT_OK")
        if not briefing_canary:
            governance_blockers.append("BRIEFING_REQUIREMENTS_CANARY_NOT_ACTIVE")
        if not matrix_canary:
            governance_blockers.append("MATRIX_REQUIREMENTS_CANARY_NOT_ACTIVE")

        if governance_blockers:
            st.error(
                "B2.4 BLOCKED antes da análise: "
                + ", ".join(governance_blockers)
            )
            st.stop()

        with st.spinner("Recalculando Unified Legacy + Domain em memória..."):
            result = run_unified_requirement_reconciliation(
                client,
                project_id=project_id,
            )

        if result.status == "PASS":
            st.success(
                "Unified Requirement Reconciliation B2.4: PASS · "
                "o conjunto de briefing_matches é reconciliado pela ponte atual."
            )
        elif result.status == "PASS_WITH_OBSERVATION":
            st.warning(
                "Unified Requirement Reconciliation B2.4: PASS_WITH_OBSERVATION · "
                "os aliases mapeados são preservados, mas a evidência selecionada difere."
            )
        elif result.status == "RECONCILIATION_REQUIRED":
            st.warning(
                "Unified Requirement Reconciliation B2.4: RECONCILIATION_REQUIRED · "
                "não há perda de match com alias Domain; a divergência vem de requirements "
                "que existem apenas em um dos conjuntos."
            )
        else:
            st.error(
                "Unified Requirement Reconciliation B2.4: BLOCKED_CALIBRATION · "
                + ", ".join(result.hard_blockers)
            )

        st.caption(
            "Diagnostic only: nenhum mapping lexical é criado; nenhum matcher, Truth, "
            "readiness, read_mode, canary, Unified servido ou snapshot persistido é alterado."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": UNIFIED_RECONCILIATION_VERSION,
                "status": result.status,
                "read_mode": readiness.get("read_mode"),
                "briefing_canary": bool(briefing_canary),
                "matrix_canary": bool(matrix_canary),
                "legacy_requirements": result.legacy_requirement_count,
                "domain_requirements": result.domain_requirement_count,
                "legacy_unified_matches": result.legacy_unified_match_count,
                "domain_unified_matches": result.domain_unified_match_count,
                "mapped_legacy_matches": result.mapped_legacy_match_count,
                "mapped_missing_in_domain":
                    result.mapped_legacy_missing_in_domain_count,
                "legacy_matches_without_domain_alias":
                    result.legacy_match_without_domain_alias_count,
                "domain_matches_without_legacy_alias":
                    result.domain_match_without_legacy_alias_count,
                "mapped_both_match": result.mapped_both_match_count,
                "mapped_different_evidence":
                    result.mapped_different_evidence_count,
            }]),
            width="stretch",
            hide_index=True,
        )

        if result.hard_blockers:
            st.markdown("#### Hard blockers")
            st.json(list(result.hard_blockers))

        if result.observations:
            st.markdown("#### Classificações encontradas")
            st.json(list(result.observations))

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Itens que explicam a divergência")
            st.caption(
                "Priorize as linhas legacy_match_without_current_domain_alias e "
                "domain_match_without_legacy_alias. Elas explicam o gap sem inventar identidade."
            )
            st.dataframe(
                detail,
                width="stretch",
                hide_index=True,
                height=min(800, 110 + len(detail) * 38),
            )
            st.download_button(
                "Baixar reconciliação B2.4 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_4_{project_id}.csv",
                mime="text/csv",
            )
        else:
            st.caption("Nenhuma divergência de requirement set foi encontrada.")

    except Exception as exc:
        st.error(f"B2.4 BLOCKED: {type(exc).__name__}: {exc}")
