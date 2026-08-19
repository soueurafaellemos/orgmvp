from __future__ import annotations

"""NAVE V28.7.3A2 — Runtime Shadow Canary.

Página temporária de diagnóstico. Ela NÃO muda read_mode e NÃO serve Domain
para nenhuma tela de produção. O objetivo é provar que o runtime implantado
consegue atravessar o Domain Reader nos oito domínios, inclusive domínios
legitimamente vazios, sem fallback e sem exception.

Em shadow_compare o reader continua servindo Legacy. Para este probe técnico,
o legacy_loader é deliberadamente vazio: NÃO é um comparador semântico.
O dado avaliado aqui é exclusivamente ``domain_candidate``.
"""

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_reader import (
    READ_PATH_VERSION,
    SUPPORTED_DOMAIN_KEYS,
    get_cutover_state,
    probe_domain_read_schema,
    read_domain,
)

CANARY_SCOPE = "v28.7.3a2_runtime_shadow_probe"

st.set_page_config(
    page_title="Domain Read Canary | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)

enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Domain Read Canary",
    "Probe técnico temporário do read-path V28.7.3A2. Não altera Truth, readiness nem read_mode.",
    eyebrow="NAVE by VOE · V28.7.3A2 · shadow only",
)

client = get_nave_client()


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _project_label(row: Mapping[str, Any]) -> str:
    name = (
        row.get("name")
        or row.get("project_name")
        or row.get("title")
        or row.get("client_name")
        or "Projeto"
    )
    return f"{name} · {row.get('id')}"


schema = probe_domain_read_schema(client)
if not schema.get("available"):
    st.error("Domain Read schema indisponível no runtime.")
    st.json(schema)
    st.stop()

try:
    projects = _rows(client.table("projects").select("*").limit(500).execute())
except Exception as exc:
    st.error(f"Não foi possível listar projects: {exc}")
    st.stop()

if not projects:
    st.warning("Nenhum projeto encontrado.")
    st.stop()

projects = sorted(projects, key=lambda row: _project_label(row).lower())
labels = [_project_label(row) for row in projects]
selected_label = st.selectbox("Projeto", labels)
project = projects[labels.index(selected_label)]
project_id = str(project["id"])

states: list[dict[str, Any]] = []
for domain_key in SUPPORTED_DOMAIN_KEYS:
    state = get_cutover_state(client, project_id, domain_key)
    states.append({
        "domain_key": domain_key,
        "read_mode": state.get("read_mode"),
        "readiness_state": state.get("readiness_state"),
        "expected_domain_rows": int(state.get("domain_row_count") or 0),
        "semantic_gate_ok": bool(state.get("semantic_gate_ok")),
        "current_evidence_ok": bool(state.get("current_evidence_ok")),
        "findings": len(state.get("governed_findings") or []),
    })

st.caption(
    "Pré-condição do canary: todos os domínios deste projeto devem continuar em "
    "shadow_compare e estar ready/ready_with_findings."
)
st.dataframe(pd.DataFrame(states), use_container_width=True, hide_index=True)

if st.button("Executar Runtime Shadow Canary", type="primary"):
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for domain_key in SUPPORTED_DOMAIN_KEYS:
        try:
            state = get_cutover_state(client, project_id, domain_key)
            result = read_domain(
                client,
                project_id,
                domain_key,
                # Probe técnico: não é semantic comparator. Em shadow_compare o
                # reader exige um adapter legacy explícito; aqui ele é vazio para
                # testar somente a capacidade de materializar domain_candidate.
                legacy_loader=lambda: [],
                audit=True,
                audit_scope=CANARY_SCOPE,
                audit_metadata={
                    "canary_probe": True,
                    "legacy_adapter": "diagnostic_empty_not_semantic_comparator",
                    "domain_candidate_is_test_subject": True,
                },
            )
            expected = int(state.get("domain_row_count") or 0)
            actual = len(result.domain_candidate)
            ok = (
                result.read_mode == "shadow_compare"
                and result.readiness_state in {"ready", "ready_with_findings"}
                and result.served_source == "legacy"
                and result.fallback_used is False
                and actual == expected
            )
            results.append({
                "domain_key": domain_key,
                "PASS": ok,
                "read_mode": result.read_mode,
                "readiness_state": result.readiness_state,
                "served_source": result.served_source,
                "fallback_used": result.fallback_used,
                "domain_rows": actual,
                "expected_rows": expected,
                "empty_domain_valid": actual == 0,
                "findings": len(result.governed_findings),
            })
            if not ok:
                errors.append(f"{domain_key}: runtime invariant falhou")
        except Exception as exc:
            errors.append(f"{domain_key}: {type(exc).__name__}: {exc}")
            results.append({
                "domain_key": domain_key,
                "PASS": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    frame = pd.DataFrame(results)
    if errors:
        st.error("Runtime Shadow Canary: BLOCKED")
        for error in errors:
            st.caption("• " + error)
    else:
        st.success(
            f"Runtime Shadow Canary: PASS · {len(results)}/{len(SUPPORTED_DOMAIN_KEYS)} "
            f"domínios · reader {READ_PATH_VERSION}"
        )
        st.caption(
            "Este PASS prova o runtime Domain Candidate em shadow. Ele NÃO promove "
            "domain_primary e NÃO afirma paridade semântica com o legado."
        )

    st.dataframe(frame, use_container_width=True, hide_index=True)
