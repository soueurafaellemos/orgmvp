from __future__ import annotations

"""NAVE V28.7.3B2.2 — Requirements Relational Consumer Shadow."""

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_relational_shadow import (
    RELATIONAL_SHADOW_VERSION,
    run_relational_consumer_shadow,
)


st.set_page_config(
    page_title="Relational Consumer Shadow | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirements Relational Consumer Shadow",
    "Compara matriz/unified Legacy com uma cópia paralela usando Current Domain requirement IDs. O resultado servido ao usuário continua Legacy.",
    eyebrow=f"NAVE by VOE · {RELATIONAL_SHADOW_VERSION} · shadow only",
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
    st.error(f"Não foi possível ler os canaries aprovados: {exc}")
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

if st.button("Executar Relational Consumer Shadow B2.2", type="primary"):
    try:
        readiness = get_cutover_state(client, project_id, "requirements")
        canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key="requirements",
            consumer_key="workspace.briefing.requirements_readonly",
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
        if not canary:
            governance_blockers.append("REQUIREMENTS_CANARY_NOT_ACTIVE")

        if governance_blockers:
            st.error(
                "B2.2 BLOCKED antes da comparação: "
                + ", ".join(governance_blockers)
            )
            st.stop()

        with st.spinner("Calculando Legacy + Domain shadow em paralelo..."):
            result, legacy_intelligence, domain_intelligence = (
                run_relational_consumer_shadow(
                    client,
                    project_id=project_id,
                )
            )

        if result.status == "PASS":
            st.success(
                "Relational Consumer Shadow B2.2: PASS · "
                "relações da matriz preservadas com identidade Current Domain."
            )
        elif result.status == "PASS_WITH_OBSERVATION":
            st.warning(
                "Relational Consumer Shadow B2.2: PASS_WITH_OBSERVATION · "
                "nenhuma relação ativa foi perdida; diferenças do Unified/da cardinalidade "
                "foram mantidas como observação."
            )
        else:
            st.error(
                "Relational Consumer Shadow B2.2: BLOCKED · "
                + ", ".join(result.hard_blockers)
            )

        st.caption(
            "Shadow only: a UI de negócio continua servindo o fluxo atual. "
            "Nenhum write, Truth, readiness, read_mode ou domain_primary foi alterado."
        )

        summary = result.to_dict()
        st.dataframe(
            pd.DataFrame([{
                "version": RELATIONAL_SHADOW_VERSION,
                "status": result.status,
                "read_mode": readiness.get("read_mode"),
                "canary_active": bool(canary),
                "legacy_requirements": result.legacy_requirement_count,
                "domain_requirements": result.domain_requirement_count,
                "legacy_active_links": result.legacy_active_link_count,
                "domain_active_links": result.domain_active_link_count,
                "matrix_rows_legacy": result.matrix_row_count_legacy,
                "matrix_rows_domain": result.matrix_row_count_domain,
                "matrix_briefing_drifts": result.matrix_briefing_drift_count,
                "orphan_domain_links": result.orphan_domain_link_count,
                "legacy_unified_matches": result.legacy_unified_match_count,
                "domain_unified_matches": result.domain_unified_match_count,
            }]),
            width="stretch",
            hide_index=True,
        )

        if result.hard_blockers:
            st.markdown("#### Hard blockers")
            st.json(list(result.hard_blockers))

        if result.observations:
            st.markdown("#### Diferenças explicadas / observações")
            st.json({
                "observations": list(result.observations),
                "mapped_legacy_matches_missing_in_domain":
                    list(result.mapped_legacy_matches_missing_in_domain),
                "domain_unified_additions":
                    list(result.domain_unified_additions),
                "legacy_unmapped_unified_matches":
                    list(result.legacy_unmapped_unified_matches),
                "legacy_briefing_gaps": result.legacy_gap_count,
                "domain_briefing_gaps": result.domain_gap_count,
                "legacy_unconsolidated": result.legacy_unconsolidated_count,
                "domain_unconsolidated": result.domain_unconsolidated_count,
            })

        if result.matrix_drift_detail:
            st.markdown("#### Drift de relação na matriz")
            st.dataframe(
                pd.DataFrame(list(result.matrix_drift_detail)),
                width="stretch",
                hide_index=True,
            )

        st.markdown("#### Comparação de briefing no Unified")
        st.dataframe(
            pd.DataFrame([{
                "Legacy matches": result.legacy_unified_match_count,
                "Legacy matches com alias Domain":
                    result.mapped_legacy_unified_match_count,
                "Domain matches": result.domain_unified_match_count,
                "Mapped Legacy ausentes no Domain":
                    len(result.mapped_legacy_matches_missing_in_domain),
                "Adições Domain":
                    len(result.domain_unified_additions),
                "Legacy matches sem alias":
                    len(result.legacy_unmapped_unified_matches),
            }]),
            width="stretch",
            hide_index=True,
        )

    except Exception as exc:
        st.error(f"B2.2 BLOCKED: {type(exc).__name__}: {exc}")
