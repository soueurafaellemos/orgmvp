from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_unified_evidence_role_shadow import (
    EVIDENCE_ROLE_SHADOW_VERSION,
    run_evidence_role_shadow,
)

st.set_page_config(
    page_title="Unified Evidence Role Shadow | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Unified Evidence Role Shadow",
    "Projeta, sem alterar runtime, a diferença entre citar/repetir o briefing e apresentar evidência real de resposta na proposta.",
    eyebrow=f"NAVE by VOE · {EVIDENCE_ROLE_SHADOW_VERSION} · shadow only",
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

if st.button("Executar Evidence Role Shadow B2.4.4", type="primary"):
    try:
        readiness = get_cutover_state(
            client,
            project_id,
            "requirements",
        )
        if readiness.get("read_mode") != "shadow_compare":
            st.error(
                "B2.4.4 BLOCKED: requirements não está em shadow_compare."
            )
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
                "B2.4.4 BLOCKED: briefing/matrix canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner(
            "Classificando papel da evidência e projetando o gate em memória..."
        ):
            result = run_evidence_role_shadow(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_PROJECTED_PARITY":
            st.success(
                "B2.4.4: PASS_PROJECTED_PARITY · ao remover apenas evidências que "
                "são recap/capa/menção ambígua, os sets reconciliam."
            )
        elif result.status == "BLOCKED_PROJECTED_MAPPED_LOSS":
            st.error(
                "B2.4.4: BLOCKED_PROJECTED_MAPPED_LOSS · o gate projetado criaria "
                "perda assimétrica em uma identidade já governada."
            )
        else:
            st.warning(
                f"B2.4.4: {result.status} · o gate remove falsos sinais, mas ainda "
                "resta divergência sem alias que precisa de modelagem semântica."
            )

        st.caption(
            "Shadow only: nenhuma evidência é removida do Unified servido. "
            "Nenhum alias, Truth, read_mode, canary ou snapshot persistido é alterado."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": EVIDENCE_ROLE_SHADOW_VERSION,
                "status": result.status,
                "raw_legacy_matches": result.raw_legacy_match_count,
                "raw_domain_matches": result.raw_domain_match_count,
                "projected_legacy_matches":
                    result.projected_legacy_match_count,
                "projected_domain_matches":
                    result.projected_domain_match_count,
                "excluded_legacy": result.excluded_legacy_count,
                "excluded_domain": result.excluded_domain_count,
                "projected_mapped_missing":
                    result.projected_mapped_missing_count,
                "projected_legacy_without_domain_alias":
                    result.projected_legacy_without_domain_alias_count,
                "projected_domain_without_legacy_alias":
                    result.projected_domain_without_legacy_alias_count,
                "projected_mapped_both":
                    result.projected_mapped_both_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Papel projetado de cada match atual")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(900, 130 + len(detail) * 38),
            )
            st.download_button(
                "Baixar B2.4.4 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_4_4_{project_id}.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(
            f"B2.4.4 BLOCKED: {type(exc).__name__}: {exc}"
        )
