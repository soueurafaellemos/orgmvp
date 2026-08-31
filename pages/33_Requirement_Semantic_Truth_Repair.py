from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import get_cutover_state
from project_requirement_reconciliation_h31 import reconcile_project_requirements
from project_requirement_semantic_h31 import H31_VERSION

st.set_page_config(
    page_title="Requirement Semantic Truth Repair | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Semantic Truth Repair",
    (
        "H3.1 corrige a leitura estrutural de bullets cujo parent semântico está em "
        "Evidence Units anteriores. A ação reconcilia somente Requirement Truth e "
        "preserva masters, A/B, canaries, legacy_shadow e Graph V28.6."
    ),
    eyebrow=f"NAVE by VOE · {H31_VERSION} · governed upstream repair",
)

client = get_nave_client()

rows = (
    client.table("projects")
    .select("id,project_name,client_brand,event_name,updated_at")
    .order("updated_at", desc=True)
    .limit(500)
    .execute()
    .data
    or []
)
projects: list[tuple[str, str]] = []
for row in rows:
    project_id = str(row.get("id") or "")
    if not project_id:
        continue
    name = str(row.get("project_name") or row.get("event_name") or "Projeto sem nome")
    brand = str(row.get("client_brand") or "").strip()
    label = f"{name} · {brand} · {project_id}" if brand else f"{name} · {project_id}"
    projects.append((label, project_id))

if not projects:
    st.warning("Nenhum projeto disponível para reconciliação H3.1.")
    st.stop()

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

st.warning(
    "Esta é uma ação governada de reconciliação semântica upstream. Ela PODE alterar "
    "Requirement Truth quando a evidência atual provar que uma identidade legacy é "
    "scope/attribute/context/example em vez de Requirement. Não altera os arquivos "
    "originais e não cria Human Review."
)

st.markdown(
    """
**H3.1 nesta etapa não faz:**
- não reprocessa PDF/DOCX/XLSM/PPTX;
- não reroda Solution Reconciliation A;
- não reroda Core Semantic Domains B;
- não reconstrói Graph V28.6;
- não ativa `domain_primary`;
- não altera canaries;
- não auto-mergeia Requirement identities;
- não persiste adjudicações B2.12.x.

**Importante:** o pipeline normal continua em H3 durante a prova Golden. H3.1 só roda por esta tela.
"""
)

confirm = st.checkbox(
    "Confirmo executar somente a reconciliação governada H3.1 sobre o projeto selecionado.",
    value=False,
)

if st.button(
    f"Executar Requirement Truth Repair · {H31_VERSION}",
    type="primary",
    width="stretch",
    disabled=not confirm,
):
    state = get_cutover_state(client, project_id, "requirements")
    if str(state.get("read_mode") or "") != "shadow_compare":
        st.error(
            f"H3.1 BLOCKED: requirements read_mode={state.get('read_mode')!r}. "
            "A correção só pode rodar em shadow_compare."
        )
        st.stop()

    with st.spinner("Executando somente Requirement Semantic Reconciliation H3.1..."):
        result = reconcile_project_requirements(client, project_id)

    actions = result.get("actions") or {}
    gate = result.get("semantic_gate") or {}
    summary = result.get("extraction_summary") or {}

    if str(result.get("status") or "") == "completed":
        st.success(f"{H31_VERSION} concluído sem promover cutover e sem rerodar A/B/Graph.")
    else:
        st.error(
            "H3.1 não concluiu todos os gates. O estado anterior válido deve ser tratado "
            "como baseline até revisão do diagnóstico abaixo."
        )

    st.markdown("#### Requirement H3.1")
    metrics = st.columns(6)
    metrics[0].metric("Observations", int(actions.get("observations") or 0))
    metrics[1].metric("No-domain", int(actions.get("no_domain_object") or 0))
    metrics[2].metric("Cross-unit overrides", int(actions.get("h31_cross_unit_structural_overrides") or 0))
    metrics[3].metric("Review required", int(actions.get("review_required") or 0))
    metrics[4].metric("Gate blockers", int(actions.get("semantic_gate_blockers") or 0))
    metrics[5].metric("New requirements", int(actions.get("new_requirements") or 0))

    st.caption(
        f"Pipeline Requirement: {result.get('version') or '—'} · "
        f"semantic_gate_pass={bool(gate.get('pass'))} · "
        f"legacy observations={int(summary.get('legacy_observations') or 0)} · "
        f"evidence-first={int(summary.get('evidence_first_observations') or 0)}."
    )

    classified = []
    for key in ("contexts", "scopes", "attributes", "examples", "suggestions"):
        for value in actions.get(key) or []:
            classified.append({"Classe": key, "Observação": value})
    if classified:
        with st.expander("Classificações semânticas H3.1", expanded=True):
            st.dataframe(pd.DataFrame(classified), hide_index=True, width="stretch")

    diagnostics = result.get("diagnostics") or []
    if diagnostics:
        with st.expander("Diagnóstico Requirement", expanded=False):
            st.dataframe(pd.DataFrame(diagnostics), hide_index=True, width="stretch")

    warnings = [str(x) for x in (result.get("warnings") or []) if str(x).strip()]
    if warnings:
        with st.expander("Avisos", expanded=True):
            for warning in warnings:
                st.caption("• " + warning)

    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    st.download_button(
        "Baixar auditoria H3.1 JSON",
        payload.encode("utf-8"),
        file_name=f"NAVE_H3_1_REQUIREMENT_TRUTH_REPAIR_{project_id}.json",
        mime="application/json",
    )

    st.info(
        "No Golden Chambinho, baixe o JSON e envie para revisão antes de qualquer outro run. "
        "No Golden de controle com verifier específico, depois da liberação, rode também o verifier H3.1 read-only no Supabase. "
        "NÃO avance para B2.13 e NÃO trate o status da página isoladamente como Golden aprovado."
    )
