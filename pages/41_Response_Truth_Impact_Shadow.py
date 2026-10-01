from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_requirement_response_truth_impact_shadow import (
    BASELINE_VERSION,
    VERSION,
    run_response_truth_impact_shadow,
)

st.set_page_config(
    page_title="Response Truth Impact Shadow | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()

page_header(
    "Response Truth Impact Shadow",
    (
        "B2.13 compara um Golden B2.12.2.2 pré-supersession com uma projeção "
        "B2.12.2.2 fresca sobre o estado Current. O objetivo é provar que a "
        "supersession alterou identidade/lineage sem alterar a semântica downstream."
    ),
    eyebrow=f"NAVE by VOE · {VERSION} · READ ONLY / POST-SUPERSESSION SHADOW",
)

st.info(
    "Use o JSON B2.12.2.2 GOLDEN original do projeto. Esta página não grava dados, "
    "não cria Human Review e não altera Response Truth, Requirement Truth, read_mode ou cutover."
)

uploaded = st.file_uploader(
    f"Baseline pré-supersession ({BASELINE_VERSION})",
    type=["json"],
)

if uploaded is not None:
    try:
        baseline = json.loads(uploaded.getvalue().decode("utf-8"))
    except Exception as exc:
        st.error(f"Baseline JSON inválido: {exc}")
        st.stop()

    project_id = str(baseline.get("project_id") or "")
    st.json({
        "baseline_version": baseline.get("version"),
        "project_id": project_id,
        "baseline_status": baseline.get("status"),
        "baseline_current_requirements": baseline.get(
            "current_requirement_count_before_semantic_gate"
        ),
        "baseline_queue": baseline.get("queue_count"),
        "baseline_collisions": baseline.get("canonical_identity_collision_count"),
    })

    if str(baseline.get("version") or "") != BASELINE_VERSION:
        st.error(
            f"Baseline incorreto. Esperado {BASELINE_VERSION}; recebido "
            f"{baseline.get('version') or '—'}."
        )
        st.stop()

    if st.button("Executar B2.13 — READ ONLY", type="primary"):
        client = get_nave_client()
        with st.spinner(
            "Recalculando a cadeia de Response shadow e comparando identidade/semântica..."
        ):
            result = run_response_truth_impact_shadow(
                client,
                baseline=baseline,
            )

        if result.get("all_checks_pass"):
            if result.get("mode") == "CONTROL_NO_SUPERSESSION":
                st.success("PASS CONTROL — nenhum downstream drift detectado.")
            else:
                st.success(
                    "PASS POST-SUPERSESSION — identidade consolidada sem drift "
                    "semântico downstream."
                )
        else:
            st.error(
                "B2.13 bloqueado. Existe pelo menos uma diferença que não é "
                "explicada pela supersession governada."
            )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mode", result.get("mode") or "—")
        c2.metric(
            "Current",
            (result.get("current") or {}).get("current_requirement_count", "—"),
        )
        c3.metric(
            "Queue",
            (result.get("current") or {}).get("queue_count", "—"),
        )
        c4.metric(
            "Collisions",
            (result.get("current") or {}).get("collision_count", "—"),
        )

        checks = result.get("checks") or {}
        if checks:
            st.dataframe(
                pd.DataFrame([
                    {"check": key, "pass": bool(value)}
                    for key, value in checks.items()
                ]),
                hide_index=True,
                width="stretch",
            )

        mismatch = result.get("mismatch_rows") or []
        if mismatch:
            st.subheader("Diferenças não explicadas")
            st.dataframe(pd.DataFrame(mismatch), hide_index=True, width="stretch")

        st.json(result)
        st.download_button(
            "Baixar B2.13 Response Truth Impact Shadow JSON",
            data=json.dumps(
                result, ensure_ascii=False, indent=2, default=str
            ).encode("utf-8"),
            file_name=f"NAVE_B2_13_RESPONSE_TRUTH_IMPACT_{project_id}.json",
            mime="application/json",
        )
