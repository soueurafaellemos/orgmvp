from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_pipeline_promotion import (
    verify_requirement_pipeline_promotion,
)
from project_intelligence_pipeline import (
    REQUIREMENT_PIPELINE_PROMOTION_VERSION,
)

st.set_page_config(
    page_title="Requirement Pipeline Promotion Verifier | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Requirement Pipeline Promotion Verifier",
    (
        "Verifica, sem executar o pipeline, que o entrypoint normal de Requirement "
        "agora é exatamente o H3.1.3 Golden."
    ),
    eyebrow=(
        f"NAVE by VOE · {REQUIREMENT_PIPELINE_PROMOTION_VERSION} · "
        "READ ONLY / NO PIPELINE RUN"
    ),
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

if not projects:
    st.warning("Nenhum projeto disponível.")
    st.stop()

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

st.info(
    "Este verifier NÃO chama finalize_project_intelligence, NÃO reconcilia Requirement, "
    "NÃO roda A/B/Graph e NÃO escreve no banco. Ele verifica apenas wiring + read_mode."
)

if st.button("Verificar promoção H3.1.3 no pipeline normal", type="primary"):
    result = verify_requirement_pipeline_promotion(
        client,
        project_id=project_id,
    )
    if result["all_checks_pass"]:
        st.success("PASS: pipeline normal está wired em H3.1.3 e continua shadow_compare.")
    else:
        st.error(
            "BLOCKED: " + ", ".join(result.get("failed_checks") or [])
        )

    st.dataframe(
        pd.DataFrame([
            {"check": key, "pass": value}
            for key, value in result["checks"].items()
        ]),
        hide_index=True,
        width="stretch",
    )
    st.json(result["contract"])

    payload = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8")
    st.download_button(
        "Baixar verifier de promoção em JSON",
        data=payload,
        file_name=f"NAVE_H3_1_3P1_PIPELINE_PROMOTION_{project_id}.json",
        mime="application/json",
    )
