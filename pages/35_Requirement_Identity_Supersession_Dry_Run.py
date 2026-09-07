from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import get_cutover_state
from project_requirement_identity_supersession_dry_run import VERSION, run_dry_run

st.set_page_config(page_title="Requirement Supersession Dry Run | NAVE by VOE", page_icon=NAVE_APP_ICON, layout="wide")
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Identity Supersession Dry Run",
    "B2.12.4 simula a transação de supersession/rebind sem alterar nenhum dado.",
    eyebrow=f"NAVE by VOE · {VERSION} · DRY RUN / NO WRITES",
)

client = get_nave_client()

canaries = (
    client.table("project_domain_consumer_canary").select("*")
    .eq("domain_key", "requirements")
    .eq("consumer_key", "workspace.intelligence.matrix.requirements_readonly")
    .eq("status", "active").execute().data or []
)
project_ids = sorted({str(x.get("project_id")) for x in canaries if x.get("project_id")})
projects = []
for pid in project_ids:
    rows = client.table("projects").select("*").eq("id", pid).limit(1).execute().data or []
    row = dict(rows[0]) if rows else {"id": pid}
    label = row.get("project_name") or row.get("event_name") or row.get("name") or pid
    projects.append((f"{label} · {pid}", pid))

if not projects:
    st.warning("Nenhum requirements canary ativo.")
    st.stop()

selected = st.selectbox("Projeto", [x[0] for x in projects])
project_id = dict(projects)[selected]

st.info("READ ONLY: nenhum UPDATE/INSERT/DELETE, Human Review, Truth effect, read_mode ou cutover.")

if st.button("Executar Supersession Dry Run B2.12.4", type="primary"):
    state = get_cutover_state(client, project_id, "requirements")
    if state.get("read_mode") != "shadow_compare":
        st.error("B2.12.4 BLOCKED: requirements não está em shadow_compare.")
        st.stop()

    try:
        with st.spinner("Simulando lifecycle, occurrences, aliases, evidence e B2.1 compatibility..."):
            report = run_dry_run(client, project_id=project_id)

        if report.blocked_count:
            st.error("B2.12.4 DRY RUN BLOCKED.")
        elif report.plans:
            st.success("B2.12.4 DRY RUN PASS. Nenhum write foi realizado.")
        else:
            st.success("B2.12.4 PASS: nenhuma transação necessária.")

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

        for i, plan in enumerate(report.plans, 1):
            st.markdown(f"### Plano {i}")
            st.json(plan.to_dict())

        st.download_button(
            "Baixar B2.12.4 DRY RUN em JSON",
            data=json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            file_name=f"NAVE_B2_12_4_SUPERSESSION_DRY_RUN_{project_id}.json",
            mime="application/json",
        )

        if report.plans:
            df = pd.DataFrame([{
                "canonical_obligation_text": p.canonical_obligation_text,
                "survivor_requirement_id": p.survivor_requirement_id,
                "superseded_requirement_ids": " | ".join(p.superseded_requirement_ids),
                "metadata_conflicts": " | ".join(p.metadata_conflicts),
                "occurrence_actions": len(p.occurrence_actions),
                "alias_actions": len(p.alias_actions),
                "evidence_actions": len(p.evidence_actions),
                "compatibility_after": p.compatibility_status_after,
                "projected_current_after": p.projected_current_after,
                "projected_collisions_after": p.projected_collisions_after,
                "blockers": " | ".join(p.blockers),
            } for p in report.plans])
            st.download_button(
                "Baixar B2.12.4 planos em CSV",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"NAVE_B2_12_4_SUPERSESSION_DRY_RUN_{project_id}.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(f"B2.12.4 BLOCKED: {type(exc).__name__}: {exc}")
