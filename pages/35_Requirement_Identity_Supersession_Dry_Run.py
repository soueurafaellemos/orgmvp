from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import get_cutover_state
from project_requirement_identity_supersession_dry_run import (
    VERSION,
    run_hardened_dry_run,
)

st.set_page_config(
    page_title="Requirement Supersession Dry Run | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Identity Supersession Dry Run",
    (
        "B2.12.4.1 valida Governance/Knowledge Entity reais e coalescence de Evidence "
        "antes de qualquer write de supersession."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · HARDENED DRY RUN / NO WRITES",
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

st.info(
    "READ ONLY. Esta versão bloqueia o plano se Governance/Knowledge Entity não baterem "
    "com as identities e coalesce Evidence histórica antes de projetar qualquer link no survivor."
)

if st.button("Executar Supersession Hardened Dry Run B2.12.4.1", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.12.4.1 BLOCKED: requirements não está em shadow_compare.")
            st.stop()

        with st.spinner("Validando transaction integrity, evidence coalescence e B2.1..."):
            report = run_hardened_dry_run(client, project_id=project_id)

        if report.blocked_count:
            st.error("B2.12.4.1 BLOCKED_TRANSACTION_INTEGRITY")
        elif report.plans:
            st.success("B2.12.4.1 HARDENED DRY RUN PASS. Nenhum write foi realizado.")
        else:
            st.success("B2.12.4.1 PASS: nenhuma transação necessária.")

        st.dataframe(pd.DataFrame([{
            "version": VERSION,
            "status": report.status,
            "current_before": report.current_before,
            "collisions_before": report.collisions_before,
            "plans": len(report.plans),
            "ready_plans": report.ready_count,
            "blocked_plans": report.blocked_count,
            "projected_current_after": report.projected_current_after,
            "projected_collisions_after": report.projected_collisions_after,
            "write_performed": False,
            "truth_changed": False,
        }]), hide_index=True, width="stretch")

        for index, plan in enumerate(report.plans, start=1):
            st.markdown(f"### Plano {index}")
            st.json(plan.to_dict())

        st.download_button(
            "Baixar B2.12.4.1 completo em JSON",
            data=json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
                default=str,
            ).encode("utf-8"),
            file_name=f"NAVE_B2_12_4_1_TRANSACTION_INTEGRITY_{project_id}.json",
            mime="application/json",
        )

        if report.plans:
            flat = pd.DataFrame([{
                "canonical_obligation_text": plan.canonical_obligation_text,
                "survivor_requirement_id": plan.survivor_requirement_id,
                "superseded_requirement_ids": " | ".join(plan.superseded_requirement_ids),
                "metadata_conflicts": " | ".join(plan.metadata_conflicts),
                "raw_historical_evidence_links": plan.raw_historical_evidence_link_count,
                "coalesced_evidence_actions": plan.coalesced_evidence_action_count,
                "compatibility_after": plan.compatibility_status_after,
                "projected_current_after": plan.projected_current_after,
                "projected_collisions_after": plan.projected_collisions_after,
                "blockers": " | ".join(plan.blockers),
            } for plan in report.plans])
            st.download_button(
                "Baixar B2.12.4.1 planos em CSV",
                data=flat.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_12_4_1_TRANSACTION_INTEGRITY_{project_id}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"B2.12.4.1 BLOCKED: {type(exc).__name__}: {exc}")
