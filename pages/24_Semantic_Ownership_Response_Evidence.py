from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_unified_semantic_ownership_shadow import (
    SEMANTIC_OWNERSHIP_VERSION,
    run_semantic_ownership_shadow,
)

st.set_page_config(page_title="Semantic Ownership & Response Evidence | NAVE by VOE", page_icon=NAVE_APP_ICON, layout="wide")
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Semantic Ownership & Response Evidence",
    "Projeta um contrato evidence-first: separa restatement de resposta, preserva requirements governados e reconhece ownership fora de requirements somente por proveniência explícita.",
    eyebrow=f"NAVE by VOE · {SEMANTIC_OWNERSHIP_VERSION} · shadow only",
)

client = get_nave_client()
canaries = (
    client.table("project_domain_consumer_canary").select("*")
    .eq("domain_key", "requirements")
    .eq("consumer_key", "workspace.intelligence.matrix.requirements_readonly")
    .eq("status", "active").execute().data or []
)
project_ids = sorted({str(r.get("project_id") or "") for r in canaries if r.get("project_id")})
if not project_ids:
    st.warning("Nenhum matrix requirements canary ativo encontrado.")
    st.stop()

projects = []
for project_id in project_ids:
    rows = client.table("projects").select("*").eq("id", project_id).limit(1).execute().data or []
    row = dict(rows[0]) if rows else {"id": project_id}
    label = row.get("project_name") or row.get("event_name") or row.get("name") or project_id
    projects.append((f"{label} · {project_id}", project_id))

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

if st.button("Executar Semantic Ownership Shadow B2.5", type="primary"):
    try:
        required_keys = ("requirements", "context", "solutions", "strategy", "creative", "experience", "journey")
        bad_modes = []
        for key in required_keys:
            state = get_cutover_state(client, project_id, key)
            if state.get("read_mode") != "shadow_compare":
                bad_modes.append(key)
        if bad_modes:
            st.error("B2.5 BLOCKED: domínios fora de shadow_compare: " + ", ".join(bad_modes))
            st.stop()

        briefing_canary = fetch_active_canary(client, project_id=project_id, domain_key="requirements", consumer_key="workspace.briefing.requirements_readonly")
        matrix_canary = fetch_active_canary(client, project_id=project_id, domain_key="requirements", consumer_key="workspace.intelligence.matrix.requirements_readonly")
        if not briefing_canary or not matrix_canary:
            st.error("B2.5 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos.")
            st.stop()

        with st.spinner("Projetando ownership semântico e papel da evidência..."):
            result = run_semantic_ownership_shadow(client, project_id=project_id)

        if result.status == "PASS_PROJECTED_SEMANTIC_OWNERSHIP":
            st.success("B2.5: PASS_PROJECTED_SEMANTIC_OWNERSHIP · todo response candidate possui ownership governado por requirement ou por proveniência Current Domain.")
        elif result.status == "BLOCKED_MAPPED_RESPONSE_ASYMMETRY":
            st.error("B2.5: BLOCKED_MAPPED_RESPONSE_ASYMMETRY · uma identity requirement já governada ficaria assimétrica após o Response Evidence Gate.")
        else:
            st.warning("B2.5: PASS_WITH_OWNERSHIP_REVIEW · o contrato projetado é coerente, mas ainda existe material response sem ownership Current Domain explícito.")

        st.caption("Shadow only: score semântico nunca cria ownership. Ownership automático fora de requirements exige o MESMO source evidence ID. Nenhum Unified servido, alias, Truth, read_mode, domain_primary ou canary é alterado.")

        st.dataframe(pd.DataFrame([{
            "version": SEMANTIC_OWNERSHIP_VERSION,
            "status": result.status,
            "raw_legacy_matches": result.raw_legacy_match_count,
            "raw_domain_matches": result.raw_domain_match_count,
            "legacy_non_response_excluded": result.excluded_non_response_legacy_count,
            "domain_non_response_excluded": result.excluded_non_response_domain_count,
            "requirement_owned_responses": result.requirement_owned_response_count,
            "cross_domain_same_evidence_owned": result.cross_domain_owned_same_evidence_count,
            "cross_domain_candidate_reviews": result.cross_domain_candidate_review_count,
            "material_components_unowned": result.material_response_component_unowned_count,
            "material_responses_unowned": result.material_response_unowned_count,
            "mapped_response_asymmetry": result.mapped_response_asymmetry_count,
            "unresolved_ownership": result.unresolved_ownership_count,
        }]), hide_index=True, width="stretch")

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown("#### Contrato projetado por match")
            st.dataframe(detail, hide_index=True, width="stretch", height=min(1000, 130 + len(detail) * 36))
            st.download_button("Baixar B2.5 em CSV", data=detail.to_csv(index=False).encode("utf-8-sig"), file_name=f"NAVE_B2_5_{project_id}.csv", mime="text/csv")
    except Exception as exc:
        st.error(f"B2.5 BLOCKED: {type(exc).__name__}: {exc}")
