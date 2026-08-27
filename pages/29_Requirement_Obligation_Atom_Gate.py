from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_obligation_atom_gate import (
    OBLIGATION_ATOM_VERSION,
    run_obligation_atom_gate,
)

st.set_page_config(
    page_title="Requirement Obligation Atom Gate | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Obligation Atom Gate",
    "Reduz o ruído dos reviews B2.9 verificando cobertura da obrigação completa — combinações, quantidades e qualificadores — sem promover nenhuma resposta.",
    eyebrow=f"NAVE by VOE · {OBLIGATION_ATOM_VERSION} · review precision shadow",
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

if st.button("Executar Obligation Atom Gate B2.10", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.10 BLOCKED: requirements não está em shadow_compare.")
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
                "B2.10 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner(
            "Decompondo requirements e medindo cobertura das obrigações..."
        ):
            result = run_obligation_atom_gate(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_WITH_STRICT_SAFE_RECALL":
            st.success(
                "B2.10: PASS_WITH_STRICT_SAFE_RECALL · existe recall estrito preservado. "
                "Ainda assim, esta página não promove nenhuma resposta."
            )
        elif result.status == "PASS_WITH_HIGH_CONFIDENCE_REVIEWS":
            st.success(
                "B2.10: PASS_WITH_HIGH_CONFIDENCE_REVIEWS · o ruído B2.9 foi reduzido "
                "e há um conjunto pequeno de candidatos de revisão com cobertura forte "
                "da obrigação completa."
            )
        elif result.status == "PASS_WITH_PARTIAL_REVIEWS":
            st.warning(
                "B2.10: PASS_WITH_PARTIAL_REVIEWS · há apenas cobertura parcial; "
                "nenhuma resposta deve ser promovida."
            )
        else:
            st.info(
                "B2.10: PASS_NO_ACTIONABLE_RECALL · nenhum candidato sobreviveu "
                "ao gate de obrigação completa."
            )

        st.caption(
            "HIGH_CONFIDENCE continua sendo REVIEW. Quantidade, negação, qualificadores "
            "e conjunções ausentes impedem promoção. Nenhum write é executado."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": OBLIGATION_ATOM_VERSION,
                "status": result.status,
                "requirements_scanned": result.scanned_requirement_count,
                "strict_safe_auto_preserved": result.strict_safe_auto_preserved_count,
                "high_confidence_review": result.high_confidence_review_count,
                "partial_obligation_coverage": result.partial_obligation_coverage_count,
                "generic_overlap_rejected": result.generic_overlap_rejected_count,
                "no_candidate": result.no_candidate_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Review precision por requirement")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(1100, 140 + len(detail) * 30),
            )
            st.download_button(
                "Baixar B2.10 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_10_OBLIGATION_ATOMS_{project_id}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"B2.10 BLOCKED: {type(exc).__name__}: {exc}")
