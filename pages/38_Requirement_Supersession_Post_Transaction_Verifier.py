from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_identity_supersession_verify import (
    VERSION,
    verify_supersession,
)

st.set_page_config(
    page_title="Requirement Supersession Verifier | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Supersession Post-Transaction Verifier",
    (
        "Verificação independente e read-only do estado persistido após B2.12.5.4."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · READ ONLY",
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
projects = []
for row in rows:
    project_id = str(row.get("id") or "")
    if not project_id:
        continue
    name = str(row.get("project_name") or row.get("event_name") or "Projeto sem nome")
    brand = str(row.get("client_brand") or "").strip()
    label = f"{name} · {brand} · {project_id}" if brand else f"{name} · {project_id}"
    projects.append((label, project_id))

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

st.info(
    "READ ONLY. Este verifier não chama o writer, não executa H3.1.3, não roda A/B/Graph "
    "e não altera Requirement/Response Truth."
)

if st.button("Verificar estado pós-B2.12.5", type="primary"):
    with st.spinner("Verificando Truth, lineage, aliases, Evidence, B2.1 e collisions..."):
        result = verify_supersession(
            client,
            project_id=project_id,
        )

    if result.get("all_checks_pass"):
        st.success("PASS_POST_TRANSACTION_VERIFICATION")
    else:
        st.error(
            str(result.get("status") or "BLOCKED")
            + " · "
            + ", ".join(result.get("failed_checks") or [])
        )

    checks = result.get("checks") or {}
    if checks:
        st.dataframe(
            pd.DataFrame([
                {"check": key, "pass": value}
                for key, value in checks.items()
            ]),
            hide_index=True,
            width="stretch",
        )

    st.json(result)
    st.download_button(
        "Baixar verifier pós-transação JSON",
        data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        file_name=f"NAVE_B2_12_5_POST_TRANSACTION_VERIFY_{project_id}.json",
        mime="application/json",
    )
