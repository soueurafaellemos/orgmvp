from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import get_cutover_state
from project_requirement_cross_domain_residual_audit import (
    CROSS_DOMAIN_AUDIT_VERSION,
    run_cross_domain_residual_audit,
)

st.set_page_config(
    page_title="Cross-Domain Residual Placement | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Cross-Domain Residual Placement",
    "Verifica se os resíduos materiais do Unified já vivem em outro domínio Current Domain antes de criar requirements ou aliases.",
    eyebrow=f"NAVE by VOE · {CROSS_DOMAIN_AUDIT_VERSION} · read only",
)

client = get_nave_client()

matrix_canaries = (
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
    for row in matrix_canaries
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

if st.button("Executar Cross-Domain Residual Audit B2.4.6", type="primary"):
    try:
        required_keys = (
            "requirements",
            "context",
            "solutions",
            "strategy",
            "creative",
            "experience",
            "journey",
        )
        bad_modes = []
        for key in required_keys:
            state = get_cutover_state(client, project_id, key)
            if state.get("read_mode") != "shadow_compare":
                bad_modes.append(key)

        if bad_modes:
            st.error(
                "B2.4.6 BLOCKED: domínios fora de shadow_compare: "
                + ", ".join(bad_modes)
            )
            st.stop()

        with st.spinner(
            "Comparando os resíduos materiais com outros Current Domain objects..."
        ):
            result = run_cross_domain_residual_audit(
                client,
                project_id=project_id,
            )

        if result.status == "PASS_NO_RETAINED_RESIDUALS":
            st.success(
                "B2.4.6: PASS_NO_RETAINED_RESIDUALS · não há resíduo material para posicionar."
            )
        elif result.status == "CROSS_DOMAIN_PLACEMENT_CANDIDATES_FOUND":
            st.warning(
                "B2.4.6: CROSS_DOMAIN_PLACEMENT_CANDIDATES_FOUND · existem objetos "
                "em outros domínios semanticamente próximos. Revisão humana é necessária; "
                "nenhum objeto foi movido."
            )
        else:
            st.warning(
                "B2.4.6: NO_STRONG_CROSS_DOMAIN_PLACEMENT · os resíduos não possuem "
                "counterpart forte em outros domínios Current Domain."
            )

        st.caption(
            "Ranking diagnóstico somente. Não cria alias, requirement, relação, Truth "
            "ou mudança de domínio."
        )

        st.dataframe(
            pd.DataFrame([{
                "version": CROSS_DOMAIN_AUDIT_VERSION,
                "status": result.status,
                "retained_residuals": result.retained_residual_count,
                "domains_scanned": ", ".join(result.domain_keys_scanned),
                "candidate_rows": result.candidate_row_count,
                "strong_cross_domain_candidates":
                    result.strong_cross_domain_candidate_count,
            }]),
            hide_index=True,
            width="stretch",
        )

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Top candidates em cada domínio")
            st.dataframe(
                detail,
                hide_index=True,
                width="stretch",
                height=min(950, 130 + len(detail) * 30),
            )
            st.download_button(
                "Baixar B2.4.6 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_4_6_{project_id}.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(f"B2.4.6 BLOCKED: {type(exc).__name__}: {exc}")
