from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_identity_supersession import (
    VERSION,
    build_supersession_preflight,
    execute_governed_supersession,
)

st.set_page_config(
    page_title="Governed Requirement Supersession | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Governed Requirement Identity Supersession",
    (
        "B2.12.5.1 é a primeira escrita real desta sequência. A execução só é habilitada "
        "após um B2.12.4.1 fresco, H3.1.3P1 ativo e confirmação explícita."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · TRANSACTIONAL WRITE / FAIL CLOSED",
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

if not projects:
    st.warning("Nenhum requirements canary ativo.")
    st.stop()

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

st.error(
    "WRITE REAL. Não use esta tela para diagnóstico casual. Uma execução concluída "
    "transforma a Requirement identity superseded em histórica. Ela NÃO altera "
    "Response Truth, Human Review, canary ou read_mode."
)

if st.button("Preparar preflight B2.12.5 — SEM WRITE", type="primary"):
    with st.spinner("Recriando B2.12.4.1 e validando H3.1.3P1..."):
        preflight = build_supersession_preflight(
            client,
            project_id=project_id,
        )
    st.session_state["b2125_preflight"] = preflight

preflight = st.session_state.get("b2125_preflight")
if preflight and str(preflight.get("project_id")) == project_id:
    st.markdown("### Preflight")
    st.json({
        "version": preflight.get("version"),
        "status": preflight.get("status"),
        "ready_for_write": preflight.get("ready_for_write"),
        "blockers": preflight.get("blockers"),
        "execution_signature": preflight.get("execution_signature"),
        "review_fingerprint": preflight.get("review_fingerprint"),
    })

    dry = preflight.get("dry_run_report") or {}
    st.dataframe(pd.DataFrame([{
        "current_before": dry.get("current_requirement_count_before"),
        "collisions_before": dry.get("collision_count_before"),
        "plans": dry.get("transaction_plan_count"),
        "ready": dry.get("ready_transaction_plan_count"),
        "blocked": dry.get("blocked_transaction_plan_count"),
        "projected_current_after": dry.get("projected_current_requirement_count_after"),
        "projected_collisions_after": dry.get("projected_collision_count_after"),
    }]), hide_index=True, width="stretch")

    st.download_button(
        "Baixar preflight B2.12.5 JSON",
        data=json.dumps(preflight, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        file_name=f"NAVE_B2_12_5_PREFLIGHT_{project_id}.json",
        mime="application/json",
    )

    if not preflight.get("ready_for_write"):
        st.info(
            "Nenhum botão de write é disponibilizado para este estado. "
            "NO_TRANSACTION_REQUIRED é o comportamento esperado do Golden de controle."
        )
    else:
        plan = preflight.get("execution_plan") or {}
        st.markdown("### Transação que será executada")
        st.json({
            "survivor_requirement_id": plan.get("survivor_requirement_id"),
            "superseded_requirement_ids": plan.get("superseded_requirement_ids"),
            "metadata_conflicts": plan.get("metadata_conflicts"),
            "occurrence_actions": plan.get("occurrence_actions"),
            "alias_actions": plan.get("alias_actions"),
            "evidence_actions": plan.get("evidence_actions"),
            "projected_current_after": plan.get("projected_current_after"),
            "projected_collisions_after": plan.get("projected_collisions_after"),
        })

        expected_token = str(preflight.get("confirmation_token") or "")
        reviewed_fingerprint = str(preflight.get("review_fingerprint") or "")
        st.warning(
            "Para executar, copie exatamente o token abaixo. Ele está vinculado ao "
            "fingerprint do plano que você acabou de revisar. No clique, o sistema refaz "
            "o preflight e bloqueia o write se o plano tiver mudado."
        )
        st.code(expected_token)
        st.caption(f"review_fingerprint={reviewed_fingerprint}")

        confirm = st.checkbox(
            "Confirmo executar a supersession transacional exatamente para o projeto e identities exibidos acima.",
            value=False,
        )
        token = st.text_input(
            "Token de confirmação",
            value="",
            placeholder=expected_token,
        )

        if st.button(
            "EXECUTAR B2.12.5 — WRITE REAL",
            type="primary",
            disabled=(not confirm or token != expected_token),
        ):
            with st.spinner("Executando transação fail-closed..."):
                result = execute_governed_supersession(
                    client,
                    project_id=project_id,
                    confirmation_token=token,
                    reviewed_fingerprint=reviewed_fingerprint,
                )

            st.success(
                "B2.12.5.1 concluiu a transação. NÃO execute novamente. "
                "Agora use exclusivamente o Post-Transaction Verifier."
            )
            st.json(result)
            st.download_button(
                "Baixar resultado B2.12.5 JSON",
                data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                file_name=f"NAVE_B2_12_5_TRANSACTION_RESULT_{project_id}.json",
                mime="application/json",
            )
