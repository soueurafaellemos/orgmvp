from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import get_cutover_state
from project_requirement_auto_adjudication_hardening import (
    SEMANTIC_HARDENING_VERSION,
    run_semantic_hardened_adjudication,
)

st.set_page_config(
    page_title="Automated Adjudication Recommendations | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Automated Adjudication Recommendations",
    (
        "B2.12.2.1 corrige a precedência semântica antes da adjudicação, reconstrói a "
        "obrigação canônica a partir da fonte e endurece qualificadores compostos. "
        "Continua machine-only, read-only e sem efeito em Truth."
    ),
    eyebrow=f"NAVE by VOE · {SEMANTIC_HARDENING_VERSION} · semantic hardening shadow",
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

st.info(
    "B2.12.2.1 não usa a fila antiga como verdade. Primeiro remove sinais que a "
    "reconciliação semântica já classificou como scope/attribute/context/example, "
    "depois recalibra os atoms com a obrigação canônica completa e só então recomenda."
)

if st.button("Executar hardening automático B2.12.2.1", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.12.2.1 BLOCKED: requirements não está em shadow_compare.")
            st.stop()

        with st.spinner("Aplicando semantic eligibility + canonical obligation hardening..."):
            result = run_semantic_hardened_adjudication(
                client,
                project_id=project_id,
            )

        if result.status == "BLOCKED_SEMANTIC_ELIGIBILITY_UNKNOWN":
            st.error(
                "B2.12.2.1 bloqueou avanço: existem Requirements Current sem uma "
                "classificação semântica explícita suficiente. O relatório pode ser "
                "exportado para diagnóstico, mas NÃO deve alimentar Truth."
            )
        else:
            st.success(
                "B2.12.2.1 concluído. A fila foi semanticamente filtrada e recalibrada "
                "sem intervenção humana linha a linha."
            )

        st.caption(
            "Governança: nenhuma recomendação desta página cria Human Review, altera "
            "Requirement Truth, persiste resposta, muda read_mode/domain_primary/canaries "
            "ou aprova cutover."
        )

        st.markdown("#### Gate semântico e distribuição")
        st.dataframe(
            pd.DataFrame([{
                "version": SEMANTIC_HARDENING_VERSION,
                "status": result.status,
                "current_before_gate": result.current_requirement_count_before_semantic_gate,
                "semantic_eligible": result.semantic_eligible_requirement_count,
                "excluded_no_domain": result.semantic_excluded_no_domain_count,
                "semantic_unknown": result.semantic_unknown_count,
                "identity_collisions": result.canonical_identity_collision_count,
                "queue_count": result.queue_count,
                "recommend_confirm": result.recommend_confirm_count,
                "recommend_partial": result.recommend_partial_count,
                "recommend_reject": result.recommend_reject_count,
                "recommend_visual_review": result.recommend_visual_review_count,
                "recommend_defer": result.recommend_defer_count,
                "human_review_created": False,
                "truth_changed": False,
                "persistence_performed": False,
                "cutover_approved": False,
            }]),
            hide_index=True,
            width="stretch",
        )

        excluded = pd.DataFrame(list(result.semantic_excluded_rows))
        if not excluded.empty:
            st.markdown("#### Excluídos antes da adjudicação")
            st.caption(
                "Estas linhas não são respostas rejeitadas: elas foram removidas da fila "
                "porque não são Requirements semanticamente elegíveis ou ainda não têm "
                "elegibilidade resolvida."
            )
            preferred_excluded = [
                "semantic_eligibility_reason",
                "semantic_role_current",
                "requirement_title",
                "canonical_obligation_text",
                "truth_state",
                "requirement_id",
                "semantic_observation_id",
            ]
            visible = [c for c in preferred_excluded if c in excluded.columns]
            st.dataframe(
                excluded[visible],
                hide_index=True,
                width="stretch",
                height=min(900, 180 + len(excluded) * 34),
            )

        collisions = pd.DataFrame(list(result.canonical_identity_collision_rows))
        if not collisions.empty:
            st.markdown("#### Colisões de identidade canônica")
            st.warning(
                "A mesma obrigação canônica está representada por mais de uma identidade Current. "
                "O B2.12.2.1 NÃO faz auto-merge. As recomendações podem ser auditadas, mas qualquer "
                "Truth-effect futuro permanece bloqueado até uma fase explícita de identidade."
            )
            st.dataframe(
                collisions,
                hide_index=True,
                width="stretch",
                height=min(700, 180 + len(collisions) * 46),
            )

        detail = pd.DataFrame(list(result.recommendation_rows))
        if not detail.empty:
            st.markdown("#### Recomendações automáticas semanticamente endurecidas")
            preferred = [
                "machine_recommendation",
                "machine_confidence",
                "requirement_title",
                "canonical_obligation_text",
                "semantic_role_current",
                "projected_response_status",
                "evidence_locator",
                "machine_rationale",
                "machine_rule_id",
                "evidence_text",
                "requirement_atoms",
                "shared_atoms",
                "missing_atoms",
                "missing_hard_atoms",
                "candidate_id",
                "requirement_id",
            ]
            visible = [c for c in preferred if c in detail.columns]
            st.dataframe(
                detail[visible],
                hide_index=True,
                width="stretch",
                height=min(1400, 180 + len(detail) * 34),
            )

            st.download_button(
                "Baixar B2.12.2.1 em CSV",
                data=detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_12_2_1_SEMANTIC_HARDENING_{project_id}.csv",
                mime="text/csv",
            )

        st.download_button(
            "Baixar B2.12.2.1 completo em JSON",
            data=json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=2,
                default=str,
            ).encode("utf-8"),
            file_name=f"NAVE_B2_12_2_1_SEMANTIC_HARDENING_{project_id}.json",
            mime="application/json",
        )

    except Exception as exc:
        st.error(f"B2.12.2.1 BLOCKED: {type(exc).__name__}: {exc}")
