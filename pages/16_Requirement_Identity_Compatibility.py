from __future__ import annotations

"""NAVE V28.7.3B2.1 — Requirement Identity Compatibility Shadow.

Diagnostic only. No writes and no consumer cutover.
"""

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_compatibility import (
    COMPATIBILITY_VERSION,
    load_requirement_compatibility,
)


st.set_page_config(
    page_title="Requirement Compatibility | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Identity Compatibility",
    "Shadow da ponte Legacy requirement ID → Current Domain requirement ID. Nenhum consumer é alterado.",
    eyebrow=f"NAVE by VOE · {COMPATIBILITY_VERSION} · shadow only",
)

client = get_nave_client()

try:
    canaries = (
        client.table("project_domain_consumer_canary")
        .select("*")
        .eq("domain_key", "requirements")
        .eq("consumer_key", "workspace.briefing.requirements_readonly")
        .eq("status", "active")
        .execute()
        .data
        or []
    )
except Exception as exc:
    st.error(f"Não foi possível ler os canaries aprovados: {exc}")
    st.stop()

if not canaries:
    st.warning("Nenhum requirements canary ativo encontrado.")
    st.stop()

project_ids = sorted({str(row.get("project_id") or "") for row in canaries if row.get("project_id")})
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

if st.button("Executar Compatibility Shadow B2.1", type="primary"):
    try:
        report = load_requirement_compatibility(client, project_id=project_id)
        readiness = get_cutover_state(client, project_id, "requirements")
        canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key="requirements",
            consumer_key="workspace.briefing.requirements_readonly",
        )

        registry_ok = (
            readiness.get("read_mode") == "shadow_compare"
            and readiness.get("readiness_state") in {"ready", "ready_with_findings"}
            and bool(readiness.get("semantic_gate_ok"))
            and bool(readiness.get("current_evidence_ok"))
        )
        canary_ok = bool(canary)

        if report.pass_data_bridge and registry_ok and canary_ok:
            st.success(
                "Requirement Compatibility B2.1: PASS · "
                f"{report.resolved_active_link_count}/{report.active_link_count} active links "
                "resolvidos para Current Domain."
            )
        else:
            st.error("Requirement Compatibility B2.1: BLOCKED")

        st.caption(
            "Shadow only: nenhum ID Legacy foi substituído nos consumers; "
            "nenhum write, Truth, readiness ou read_mode foi alterado."
        )

        summary = pd.DataFrame([{
            "compatibility_version": COMPATIBILITY_VERSION,
            "read_mode": readiness.get("read_mode"),
            "readiness_state": readiness.get("readiness_state"),
            "canary_active": canary_ok,
            "domain_requirements": report.current_domain_count,
            "legacy_requirements": report.legacy_requirement_count,
            "active_links": report.active_link_count,
            "resolved_links": report.resolved_active_link_count,
            "unmapped_links": report.active_links_unmapped,
            "ambiguous_links": report.active_links_ambiguous,
            "domain_without_legacy_alias": report.domain_without_legacy_alias_count,
        }])
        st.dataframe(summary, width="stretch", hide_index=True)

        if report.links:
            st.markdown("#### Active links traduzidos")
            st.dataframe(
                pd.DataFrame([row.to_dict() for row in report.links]),
                width="stretch",
                hide_index=True,
            )

        if report.legacy_unmapped_ids:
            st.markdown("#### Legacy requirements sem alias Domain")
            st.caption(
                "Não bloqueiam B2.1 quando não possuem active link. "
                "Não serão inventados mappings lexicais."
            )
            st.dataframe(
                pd.DataFrame({"legacy_requirement_id": list(report.legacy_unmapped_ids)}),
                width="stretch",
                hide_index=True,
            )

    except Exception as exc:
        st.error(f"B2.1 BLOCKED: {type(exc).__name__}: {exc}")
