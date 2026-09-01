from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import get_cutover_state
from project_requirement_identity_collision_shadow import (
    COLLISION_SHADOW_VERSION,
    run_identity_collision_shadow,
)

st.set_page_config(
    page_title="Requirement Identity Collision Shadow | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Canonical Requirement Identity Collision Shadow",
    (
        "B2.12.3 detecta identities Current que representam a mesma obrigação canônica e "
        "produz um plano de survivor/supersession com provenance. Nenhum merge ou write é executado."
    ),
    eyebrow=f"NAVE by VOE · {COLLISION_SHADOW_VERSION} · read-only identity resolution plan",
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
    "Este diagnóstico NÃO faz merge. `ready_for_transactional_resolution` significa apenas "
    "que o plano shadow tem provenance suficiente para desenharmos uma futura transação explícita."
)

if st.button("Executar Identity Collision Shadow B2.12.3", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.12.3 BLOCKED: requirements não está em shadow_compare.")
            st.stop()

        with st.spinner("Auditando collisions canônicas e provenance das identities..."):
            report = run_identity_collision_shadow(
                client,
                project_id=project_id,
            )

        if report.blocked_collision_count:
            st.error("B2.12.3: BLOCKED_COLLISION_INTEGRITY")
        elif report.review_required_count:
            st.warning("B2.12.3: há collision que ainda requer decisão explícita.")
        elif report.collision_count:
            st.success(
                "B2.12.3 shadow concluído: collision possui plano determinístico, "
                "mas nenhuma escrita foi realizada."
            )
        else:
            st.success("B2.12.3: nenhuma canonical identity collision Current encontrada.")

        st.caption(
            "Governança: auto_merge=false · persistence=false · truth_changed=false · "
            "human_review_created=false · cutover=false."
        )

        summary = pd.DataFrame([{
            "version": COLLISION_SHADOW_VERSION,
            "status": report.status,
            "current_requirements": report.current_requirement_count,
            "semantic_eligible": report.semantic_eligible_count,
            "collisions": report.collision_count,
            "ready_for_transactional_resolution": report.ready_collision_count,
            "review_required": report.review_required_count,
            "blocked": report.blocked_collision_count,
            "auto_merge_performed": False,
            "persistence_performed": False,
            "truth_changed": False,
            "cutover_approved": False,
        }])
        st.dataframe(summary, width="stretch", hide_index=True)

        plans = pd.DataFrame([row.to_dict() for row in report.plans])
        if not plans.empty:
            st.markdown("#### Planos de resolução")
            st.dataframe(plans, width="stretch", hide_index=True)

        audit = pd.DataFrame(list(report.identity_audit_rows))
        if not audit.empty:
            st.markdown("#### Identity provenance audit")
            st.dataframe(
                audit,
                width="stretch",
                hide_index=True,
                height=min(1000, 180 + len(audit) * 46),
            )

        st.download_button(
            "Baixar B2.12.3 completo em JSON",
            data=json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
                default=str,
            ).encode("utf-8"),
            file_name=f"NAVE_B2_12_3_IDENTITY_COLLISION_SHADOW_{project_id}.json",
            mime="application/json",
        )

        if not plans.empty:
            st.download_button(
                "Baixar B2.12.3 planos em CSV",
                data=plans.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_12_3_IDENTITY_COLLISION_SHADOW_{project_id}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"B2.12.3 BLOCKED: {type(exc).__name__}: {exc}")
