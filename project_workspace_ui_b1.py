from __future__ import annotations

"""Thin B1 overlay for the existing project workspace UI.

Only the read-only requirements block in Briefing original is changed. The
legacy workspace module remains the implementation for every other consumer.
"""

from html import escape
from typing import Any

import streamlit as st
from supabase import Client

import project_workspace_ui as _legacy
from project_domain_requirement_consumer import read_requirement_consumer

_ORIGINAL_RENDER_BRIEFING = _legacy._render_briefing


def _render_domain_requirement_cards(rows: list[dict[str, Any]]) -> None:
    type_labels = {
        "objective": "Objetivo",
        "deliverable": "Entregável",
        "mandatory": "Obrigatoriedade",
        "restriction": "Restrição",
        "audience": "Público",
        "logistics": "Logística",
        "budget": "Budget",
        "kpi": "KPI",
        "operation": "Operação",
        "communication": "Comunicação",
        "desirable": "Desejável",
        "context": "Contexto",
        "other": "Outro requisito",
        "deadline": "Prazo",
    }
    priority_labels = {
        "critical": "Crítica",
        "high": "Alta",
        "medium": "Média",
        "low": "Baixa",
        "not_informed": "",
        None: "",
    }
    cards: list[str] = []
    for row in rows:
        req_type_raw = str(row.get("requirement_type") or "")
        req_type = type_labels.get(req_type_raw, req_type_raw.replace("_", " ").title())
        priority = priority_labels.get(row.get("priority"), "")
        mandatory = row.get("mandatory") is True
        title = str(row.get("title") or row.get("description") or "Demanda sem título").strip()
        truth_status = str(row.get("truth_status") or "")
        status = "Confirmada" if truth_status == "human_confirmed" else "Verificada"
        meta_parts = [part for part in (req_type, priority, "Obrigatória" if mandatory else "") if part]
        cards.append(
            '<article class="nave-requirement-card">'
            f'<div class="nave-requirement-meta">{escape(" · ".join(meta_parts) or "Demanda")}</div>'
            f'<div class="nave-requirement-title">{escape(title)}</div>'
            f'<div class="nave-requirement-status ok">{escape(status)}</div>'
            '</article>'
        )

    st.caption("Canary B1 · demandas servidas pela Truth governada do Domain · somente leitura")
    st.markdown(
        """
        <style>
        .nave-requirement-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:.35rem 0 1rem}
        .nave-requirement-card{border:1px solid #E1E6EF;border-radius:13px;background:#fff;padding:13px 14px;min-width:0}
        .nave-requirement-meta{font-size:.69rem;text-transform:uppercase;letter-spacing:.035em;color:#748096;font-weight:750;line-height:1.3}
        .nave-requirement-title{color:#121B42;font-weight:760;line-height:1.42;margin:.35rem 0 .55rem;overflow-wrap:anywhere}
        .nave-requirement-status{display:inline-block;border-radius:999px;padding:4px 8px;font-size:.70rem;font-weight:760;line-height:1.2}
        .nave-requirement-status.ok{background:#EAF8EF;color:#176A3A}
        @media(max-width:850px){.nave-requirement-grid{grid-template-columns:1fr}}
        </style>
        <div class="nave-requirement-grid">"""
        + "".join(cards)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_briefing_b1(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    legacy_rows = snapshot.get("briefing_requirements", []) or []
    consumer_read = read_requirement_consumer(
        client,
        project_id=project_id,
        legacy_rows=legacy_rows,
    )

    # Controls and fallbacks render the untouched production UI.
    if consumer_read.served_source != "domain":
        if consumer_read.fallback_used:
            st.warning(
                "Canary B1 voltou automaticamente para a leitura Legacy. "
                "Nenhum dado de Truth foi alterado."
            )
        return _ORIGINAL_RENDER_BRIEFING(
            client,
            project_id=project_id,
            snapshot=snapshot,
        )

    # Domain path: keep the full original Briefing rendering and replace only the
    # requirements block. The original snapshot is still used for unified
    # intelligence/matches, so Legacy IDs do not leak into the Domain contract.
    _legacy._section_title(
        "Briefing original",
        "Arquivo recebido, versões e demandas estruturadas do briefing.",
    )

    structured = snapshot.get("briefing_documents", [])
    generic = _legacy._role_rows(snapshot, "briefing_original")
    unified = snapshot.get("unified_intelligence") or _legacy.build_unified_project_snapshot(snapshot)
    unified_budget = ((unified.get("project_truth") or {}).get("budget_amount"))

    st.markdown("#### Arquivo original")
    if generic:
        _legacy._render_file_list(
            client,
            rows=generic,
            empty_message="",
            allow_archive=True,
        )
    elif structured:
        st.caption(
            "O briefing original foi incorporado pela importação inteligente e está preservado no projeto."
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhum briefing original foi anexado.</div>',
            unsafe_allow_html=True,
        )

    _legacy._upload_box(
        client,
        project_id=project_id,
        role="briefing_original",
        title="Briefing original",
        accepted_types=["pdf", "docx", "pptx", "txt", "md"],
        key_suffix="briefing",
    )

    st.markdown("#### Briefings já estruturados pela NAVE")
    if structured:
        cards = []
        for row in structured:
            title = str(row.get("title") or row.get("file_name") or "Briefing").strip()
            count = row.get("requirements_count")
            budget_value = row.get("budget_amount")
            if budget_value in (None, ""):
                budget_value = unified_budget
            count_text = (
                f"{int(count)} demandas"
                if count not in (None, "")
                else "Demandas ainda não contabilizadas"
            )
            budget_text = (
                _legacy._format_money(budget_value)
                if budget_value not in (None, "")
                else "Budget não informado"
            )
            cards.append(
                '<article class="nave-briefing-summary-card">'
                f'<div class="nave-briefing-summary-title">{escape(title)}</div>'
                f'<div class="nave-briefing-summary-meta">{escape(count_text)} · {escape(budget_text)}</div>'
                '</article>'
            )
        st.markdown(
            """
            <style>
            .nave-briefing-summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:.35rem 0 1rem}
            .nave-briefing-summary-card{border:1px solid #E1E6EF;border-radius:13px;background:#F8FAFC;padding:14px 15px;min-width:0}
            .nave-briefing-summary-title{font-weight:800;color:#121B42;line-height:1.35;overflow-wrap:anywhere}
            .nave-briefing-summary-meta{font-size:.78rem;color:#69758B;margin-top:6px;line-height:1.4}
            @media(max-width:850px){.nave-briefing-summary-grid{grid-template-columns:1fr}}
            </style>
            <div class="nave-briefing-summary-grid">"""
            + "".join(cards)
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">'
            "Ainda não há briefing estruturado na matriz de aderência."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("#### Demandas e obrigatoriedades")
    if consumer_read.rows:
        _render_domain_requirement_cards(consumer_read.rows)
    else:
        st.caption("Nenhuma demanda Domain current foi materializada.")


# Patch only the function referenced by the existing render_projects_page flow.
_legacy._render_briefing = _render_briefing_b1
render_projects_page = _legacy.render_projects_page
render_project_workspace = _legacy.render_project_workspace
