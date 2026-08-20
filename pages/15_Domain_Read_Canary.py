from __future__ import annotations

"""NAVE V28.7.3A3.1.1 — Runtime + Subject-aware Semantic Shadow Canary.

Temporary diagnostic page. It never changes read_mode/readiness/Truth and never
serves Domain to a production consumer.

A2 proves runtime materialization of Domain candidates.
A3.1.1 compares real legacy semantic adapters against real Domain candidates after
binding outcome subject/lifecycle scope, and persists only observability/audit rows
in project_domain_read_audit.
"""

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_legacy_adapters import (
    LEGACY_ADAPTER_VERSION,
    build_legacy_domain_snapshot,
    legacy_rows_for_domain,
)
from project_domain_reader import (
    READ_PATH_VERSION,
    SUPPORTED_DOMAIN_KEYS,
    get_cutover_state,
    probe_domain_read_schema,
    read_domain,
)
from project_domain_semantic_scope import (
    SCOPE_BINDING_VERSION,
    bind_semantic_subjects,
    build_semantic_scope_snapshot,
)
from project_domain_semantic_comparator import (
    COMPARATOR_VERSION,
    COMPARISON_SCOPE,
    compare_domain_candidates,
    persist_semantic_comparison_audit,
)

A2_SCOPE = "v28.7.3a2_runtime_shadow_probe"

st.set_page_config(
    page_title="Domain Read Canary | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)

enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Domain Read Canary",
    "Runtime A2 + comparação semântica A3.1.1 subject-aware. Nenhuma ação desta página promove Domain Primary.",
    eyebrow="NAVE by VOE · V28.7.3A3.1.1 · shadow only",
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


def _a2_proof(project_id: str) -> dict[str, Any]:
    try:
        audits = _rows(
            client.table("project_domain_read_audit")
            .select("*")
            .eq("project_id", project_id)
            .eq("request_scope", A2_SCOPE)
            .order("read_at", desc=True)
            .limit(100)
            .execute()
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "domains": []}

    latest: dict[str, dict[str, Any]] = {}
    for row in audits:
        key = str(row.get("domain_key") or "")
        if key in SUPPORTED_DOMAIN_KEYS and key not in latest:
            latest[key] = row

    valid = []
    for domain_key in SUPPORTED_DOMAIN_KEYS:
        row = latest.get(domain_key) or {}
        ok = bool(row) and (
            row.get("read_mode") == "shadow_compare"
            and row.get("served_source") == "legacy"
            and row.get("fallback_used") is False
            and int(row.get("domain_row_count") or 0)
            == int(get_cutover_state(client, project_id, domain_key).get("domain_row_count") or 0)
        )
        valid.append({"domain_key": domain_key, "PASS": ok})
    return {"ok": all(row["PASS"] for row in valid), "domains": valid}


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
    states.append(
        {
            "domain_key": domain_key,
            "read_mode": state.get("read_mode"),
            "readiness_state": state.get("readiness_state"),
            "expected_domain_rows": int(state.get("domain_row_count") or 0),
            "semantic_gate_ok": bool(state.get("semantic_gate_ok")),
            "current_evidence_ok": bool(state.get("current_evidence_ok")),
            "findings": len(state.get("governed_findings") or []),
        }
    )

st.caption(
    "Pré-condição: todos os domínios permanecem em shadow_compare e ready/ready_with_findings."
)
st.dataframe(pd.DataFrame(states), width="stretch", hide_index=True)

st.subheader("A2 · Runtime Shadow Canary")
if st.button("Executar Runtime Shadow Canary A2"):
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for domain_key in SUPPORTED_DOMAIN_KEYS:
        try:
            state = get_cutover_state(client, project_id, domain_key)
            result = read_domain(
                client,
                project_id,
                domain_key,
                # A2 remains a technical probe only.
                legacy_loader=lambda: [],
                audit=True,
                audit_scope=A2_SCOPE,
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
            results.append(
                {
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
                }
            )
            if not ok:
                errors.append(f"{domain_key}: runtime invariant falhou")
        except Exception as exc:
            errors.append(f"{domain_key}: {type(exc).__name__}: {exc}")
            results.append(
                {"domain_key": domain_key, "PASS": False, "error": f"{type(exc).__name__}: {exc}"}
            )

    frame = pd.DataFrame(results)
    if errors:
        st.error("Runtime Shadow Canary A2: BLOCKED")
        for error in errors:
            st.caption("• " + error)
    else:
        st.success(
            f"Runtime Shadow Canary A2: PASS · {len(results)}/{len(SUPPORTED_DOMAIN_KEYS)} "
            f"domínios · reader {READ_PATH_VERSION}"
        )
        st.caption(
            "A2 prova somente materialização runtime do Domain Candidate. Não é comparação semântica."
        )
    st.dataframe(frame, width="stretch", hide_index=True)

st.divider()
st.subheader("A3.1.1 · Semantic Shadow Comparator")
a2 = _a2_proof(project_id)
if a2.get("ok"):
    st.success("Pré-condição A2: PASS · 8/8 domínios com prova runtime persistida.")
else:
    st.warning(
        "Pré-condição A2 ainda não foi provada para este projeto neste runtime. "
        "Execute o A2 antes do A3."
    )

st.caption(
    "A3.1.1 usa Legacy real + Domain real e só compara outcomes categóricos quando o sujeito semântico coincide. "
    "Diferença de cardinalidade não é falha por si só. O comparador também distingue correção de Truth "
    "evidence-backed, transição de lifecycle, feedback que exige reconciliação e conflito realmente autoritativo."
)

if st.button("Executar Semantic Shadow Comparator A3.1.1", type="primary", disabled=not bool(a2.get("ok"))):
    summary_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        legacy_snapshot = build_legacy_domain_snapshot(client, project_id)
        semantic_scope_snapshot = build_semantic_scope_snapshot(client, project_id)
    except Exception as exc:
        st.error(f"A3.1.1 BLOCKED: leitura de escopo/Legacy falhou antes da comparação: {type(exc).__name__}: {exc}")
        st.stop()

    for domain_key in SUPPORTED_DOMAIN_KEYS:
        try:
            state = get_cutover_state(client, project_id, domain_key)
            precondition_ok = (
                state.get("read_mode") == "shadow_compare"
                and state.get("readiness_state") in {"ready", "ready_with_findings"}
                and bool(state.get("semantic_gate_ok"))
                and bool(state.get("current_evidence_ok"))
            )
            if not precondition_ok:
                raise RuntimeError(
                    "A3.1.1 precondition failed: domain must remain shadow_compare, ready, semantic_gate_ok and current_evidence_ok"
                )

            legacy_rows = legacy_rows_for_domain(legacy_snapshot, project_id, domain_key)
            result = read_domain(
                client,
                project_id,
                domain_key,
                legacy_loader=lambda rows=legacy_rows: rows,
                audit=False,
            )
            scoped_domain_rows, scoped_legacy_rows = bind_semantic_subjects(
                domain_key,
                result.domain_candidate,
                legacy_rows,
                project_id=project_id,
                scope_snapshot=semantic_scope_snapshot,
            )
            comparison = compare_domain_candidates(
                domain_key,
                scoped_domain_rows,
                scoped_legacy_rows,
                domain_evidence_ready=bool(state.get("current_evidence_ok")),
            )

            # A3.1.1 proof must be persisted. Audit persistence failure blocks A3.1.1;
            # it is not silently ignored like non-gating runtime telemetry.
            persist_semantic_comparison_audit(
                client,
                project_id=project_id,
                domain_key=domain_key,
                read_mode=result.read_mode,
                readiness_state=result.readiness_state,
                served_source=result.served_source,
                domain_row_count=len(result.domain_candidate),
                legacy_row_count=len(legacy_rows),
                fallback_used=result.fallback_used,
                reader_version=READ_PATH_VERSION,
                comparison=comparison,
                legacy_adapter_version=LEGACY_ADAPTER_VERSION,
                semantic_scope_version=SCOPE_BINDING_VERSION,
            )

            counts = comparison.classification_counts
            summary_rows.append(
                {
                    "domain_key": domain_key,
                    "semantic_status": comparison.semantic_status,
                    "domain_rows": comparison.domain_row_count,
                    "legacy_rows": comparison.legacy_row_count,
                    "same_semantics": int(counts.get("same_semantics", 0)),
                    "domain_more_precise": int(counts.get("domain_more_precise", 0)),
                    "structural_difference": int(counts.get("expected_structural_difference", 0)),
                    "legacy_only_unverified": int(counts.get("legacy_only_unverified", 0)),
                    "domain_only_evidence_led": int(counts.get("domain_only_evidence_led", 0)),
                    "expected_truth_correction": int(counts.get("expected_truth_correction", 0)),
                    "review_required": comparison.review_required,
                    "semantic_conflict": comparison.semantic_conflicts,
                }
            )

            for item in comparison.items:
                if item.classification == "same_semantics":
                    continue
                detail_rows.append(
                    {
                        "domain_key": domain_key,
                        "classification": item.classification,
                        "score": item.score,
                        "domain": item.domain_text,
                        "legacy": item.legacy_text,
                        "legacy_source": item.legacy_source,
                        "domain_subject": item.domain_subject,
                        "legacy_subject": item.legacy_subject,
                        "domain_phase": item.domain_phase,
                        "legacy_phase": item.legacy_phase,
                        "reason": item.reason,
                    }
                )
        except Exception as exc:
            errors.append(f"{domain_key}: {type(exc).__name__}: {exc}")
            summary_rows.append(
                {
                    "domain_key": domain_key,
                    "semantic_status": "technical_blocker",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    summary = pd.DataFrame(summary_rows)
    conflicts = int(summary.get("semantic_conflict", pd.Series(dtype=int)).fillna(0).sum()) if not summary.empty else 0
    reviews = int(summary.get("review_required", pd.Series(dtype=int)).fillna(0).sum()) if not summary.empty else 0

    if errors or conflicts:
        st.error(
            f"Semantic Shadow Comparator A3.1.1: BLOCKED · conflicts={conflicts} · technical_errors={len(errors)}"
        )
    elif reviews:
        st.warning(f"Semantic Shadow Comparator A3.1.1: PASS WITH REVIEW · review_required={reviews}")
    else:
        st.success(
            f"Semantic Shadow Comparator A3.1.1: PASS · 8/8 domínios · comparator {COMPARATOR_VERSION}"
        )

    if errors:
        for error in errors:
            st.caption("• " + error)

    st.caption(
        f"Audit scope: {COMPARISON_SCOPE} · Legacy adapter {LEGACY_ADAPTER_VERSION} · "
        f"scope binder {SCOPE_BINDING_VERSION}. A3.1.1 escreve somente auditoria de observabilidade; "
        "não altera Truth, readiness ou read_mode."
    )
    st.dataframe(summary, width="stretch", hide_index=True)

    if detail_rows:
        st.markdown("#### Diferenças explicadas / itens para revisão")
        st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)
