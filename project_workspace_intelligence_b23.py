from __future__ import annotations

"""NAVE V28.7.3B2.3 — matrix-only workspace rendering overlay.

The current Legacy intelligence is built AND persisted first. Only afterwards,
an in-memory canary may replace the requirement identity used by the matrix.
Unified, gaps, findings, recommendations and persisted snapshots stay Legacy.
"""

from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client

import project_workspace_intelligence as _intel
from project_requirement_matrix_consumer import route_matrix_requirement_consumer


def render_project_intelligence_b23(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    st.markdown(_intel.DIAGNOSTIC_CSS, unsafe_allow_html=True)

    with st.spinner("Cruzando briefing, apresentação, custos e resultados..."):
        new_cost_links = _intel.ensure_automatic_cost_links(
            client, project_id=project_id, snapshot=snapshot
        )
        new_brief_links = _intel.ensure_automatic_briefing_links(
            client, project_id=project_id, snapshot=snapshot
        )

        # Production intelligence remains entirely Legacy and is persisted first.
        legacy_intelligence = _intel.build_project_intelligence(snapshot)
        _intel.persist_project_intelligence(
            client,
            project_id=project_id,
            intelligence=legacy_intelligence,
        )

        # B2.3 changes only the in-memory matrix relationship identity.
        matrix_route = route_matrix_requirement_consumer(
            client,
            project_id=project_id,
            snapshot=snapshot,
            legacy_intelligence=legacy_intelligence,
        )
        intelligence = matrix_route.intelligence

    st.subheader("Diagnóstico e recomendações")
    st.caption(
        "Leitura executiva do projeto: aderência, riscos, oportunidades e decisões. "
        "Resultados pós-evento e aprendizados permanecem em uma área própria do workspace."
    )

    metrics = intelligence["metrics"]
    semantic = (
        metrics.get("semantic_synthesis")
        if isinstance(metrics.get("semantic_synthesis"), dict)
        else {}
    )
    if semantic.get("executive_summary"):
        st.markdown("#### Leitura executiva")
        st.info(str(semantic.get("executive_summary")))

    if metrics.get("stage") in {"proposal", "no_return", "won"}:
        metric_rows = [
            ("Situação", metrics.get("stage_label") or "Em proposta"),
            ("Demandas do briefing", metrics.get("briefing_requirements", 0)),
            ("Entregas apresentadas", metrics.get("presentation_items", 0)),
            ("Entregas com custo direto", metrics.get("items_with_cost", 0)),
            ("Custos sem correspondência", metrics.get("cost_only_items", 0)),
            ("Demandas sem evidência", metrics.get("briefing_gaps", 0)),
        ]
    else:
        metric_rows = [
            ("Demandas do briefing", metrics.get("briefing_requirements", 0)),
            ("Entregas apresentadas", metrics.get("presentation_items", 0)),
            ("Entregas com custo direto", metrics.get("items_with_cost", 0)),
            ("Executadas com evidência", metrics.get("executed_with_evidence", 0)),
            (
                "Ainda sem evidência de execução",
                metrics.get("without_execution_evidence", 0),
            ),
            ("Custos sem correspondência", metrics.get("cost_only_items", 0)),
        ]

    cards = "".join(
        f'<div class="nave-exec-metric"><div class="nave-exec-metric-label">{str(label)}</div>'
        f'<div class="nave-exec-metric-value">{str(value)}</div></div>'
        for label, value in metric_rows
    )
    st.markdown(
        """
        <style>
        .nave-exec-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:.55rem 0 1rem}
        .nave-exec-metric{background:#F7F9FC;border:1px solid #E1E6EF;border-radius:14px;padding:14px 15px;min-width:0}
        .nave-exec-metric-label{font-size:.78rem;line-height:1.25;color:#58647B;font-weight:700;white-space:normal;overflow-wrap:anywhere;min-height:2.0em}
        .nave-exec-metric-value{font-size:1.75rem;line-height:1.1;color:#121B42;font-weight:850;margin-top:.35rem;overflow-wrap:anywhere}
        @media(max-width:900px){.nave-exec-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
        </style>
        <div class="nave-exec-metrics">"""
        + cards
        + "</div>",
        unsafe_allow_html=True,
    )

    # All of this remains the Legacy Unified intelligence built before B2.3.
    unified = intelligence.get("unified") or {}
    decision = unified.get("decision_intelligence") or {}
    diagnostics = [
        row
        for row in decision.get("diagnostic") or []
        if str(row.get("text") or "").strip()
    ]
    recommendations = [
        row
        for row in decision.get("recommendations") or []
        if str(row.get("text") or "").strip()
    ]
    connections = [
        row
        for row in decision.get("connections") or []
        if str(row.get("text") or "").strip()
    ]

    if diagnostics or recommendations or connections:
        st.markdown("#### Inteligência de decisão")
        tabs = st.tabs(["Diagnóstico", "Recomendações", "Conexões descobertas"])
        with tabs[0]:
            if diagnostics:
                for row in diagnostics[:8]:
                    title = str(row.get("title") or "Leitura NAVE")
                    text = str(row.get("text") or "")
                    if str(row.get("kind") or "") in {"contradiction", "risk"}:
                        st.warning(f"**{title}**\n\n{text}")
                    else:
                        st.info(f"**{title}**\n\n{text}")
            else:
                st.caption(
                    "Nenhum diagnóstico adicional consolidado com as fontes atuais."
                )
        with tabs[1]:
            if recommendations:
                for index, row in enumerate(recommendations[:8], start=1):
                    title = str(row.get("title") or f"Recomendação {index}")
                    st.success(f"**{title}**\n\n{str(row.get('text') or '')}")
            else:
                for index, value in enumerate(
                    (intelligence.get("recommendations") or [])[:8],
                    start=1,
                ):
                    st.markdown(f"**{index}.** {value}")
        with tabs[2]:
            if connections:
                for row in connections[:8]:
                    st.info(
                        f"**{row.get('title') or 'Conexão'}**\n\n"
                        f"{row.get('text') or ''}"
                    )
            else:
                st.caption("Nenhuma conexão adicional consolidada com segurança.")

    advanced = intelligence.get("advanced_insights") or {}
    business_findings = [
        row
        for row in (advanced.get("findings") or [])
        if str(row.get("title") or "") not in {"Custo por participante"}
    ]
    if business_findings:
        st.markdown("#### Leituras objetivas")
        for row in business_findings[:5]:
            if row.get("level") == "warning":
                st.warning(f"**{row.get('title')}**\n\n{row.get('text')}")
            else:
                st.info(f"**{row.get('title')}**\n\n{row.get('text')}")

    with st.expander("Detalhes e auditoria do projeto", expanded=False):
        st.markdown("**Cobertura das fontes**")
        coverage = intelligence["coverage"]
        columns = st.columns(5)
        for column, key in zip(
            columns,
            ("briefing", "presentation", "cost", "report", "feedback"),
        ):
            with column:
                st.markdown(
                    _intel._render_source_card(coverage[key]),
                    unsafe_allow_html=True,
                )

        if new_cost_links or new_brief_links:
            st.caption(
                f"Nesta leitura, a NAVE criou {new_cost_links} nova(s) sugestão(ões) "
                f"de custo e {new_brief_links} nova(s) sugestão(ões) de aderência."
            )

        matrix = pd.DataFrame(intelligence["matrix"])
        st.markdown("**Matriz integrada do projeto**")

        if matrix_route.served_source == "domain":
            st.caption(
                "Canary B2.3 · a identidade requirement ↔ item da matriz está sendo "
                "resolvida pela Current Domain Truth. Unified, gaps e snapshot "
                "persistido continuam Legacy."
            )
        elif matrix_route.fallback_used:
            st.warning(
                "Canary B2.3 voltou automaticamente para a matriz Legacy. "
                f"{matrix_route.failure_code or 'Falha de contrato'}."
            )

        if matrix.empty:
            st.caption(
                "Ainda não há entregas estruturadas suficientes para montar a matriz."
            )
        else:
            display = matrix.drop(
                columns=["item_id", "section_key"],
                errors="ignore",
            )
            display = _intel._dataframe_money(display, ["Custo direto"])
            st.dataframe(
                display,
                hide_index=True,
                width="stretch",
                height=min(680, 95 + len(display) * 38),
            )

        # These discrepancy tabs remain Legacy by design in B2.3.
        discrepancies = intelligence["discrepancies"]
        proposal_view = metrics.get("stage") in {"proposal", "no_return", "won"}
        tabs = st.tabs([
            "Proposta × custos" if proposal_view else "Proposta × execução",
            "Custos sem correspondência",
            "Entregas adicionais",
            "Briefing ainda sem evidência",
        ])

        with tabs[0]:
            if matrix.empty:
                st.caption("Nenhuma entrega estruturada.")
            elif proposal_view:
                proposal_df = matrix[
                    [
                        "Item apresentado",
                        "Área",
                        "Situação na apresentação",
                        "Briefing",
                        "Custo direto",
                        "Correlação do custo",
                    ]
                ]
                proposal_df = _intel._dataframe_money(
                    proposal_df,
                    ["Custo direto"],
                )
                st.dataframe(
                    proposal_df,
                    hide_index=True,
                    width="stretch",
                )
            else:
                execution_view = matrix[
                    [
                        "Item apresentado",
                        "Área",
                        "Execução",
                        "Evidência / resultado",
                    ]
                ]
                st.dataframe(
                    execution_view,
                    hide_index=True,
                    width="stretch",
                )

        with tabs[1]:
            rows = discrepancies["cost_only"]
            if rows:
                st.dataframe(
                    _intel._dataframe_money(
                        pd.DataFrame(rows),
                        ["Valor"],
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.caption(
                    "Todas as linhas possuem alguma correspondência sugerida ou confirmada."
                )

        with tabs[2]:
            rows = discrepancies["report_only"]
            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.caption(
                    "Nenhuma entrega adicional foi identificada no relatório atual."
                )

        with tabs[3]:
            evidence_rows = (
                discrepancies.get("briefing_evidence_unconsolidated") or []
            )
            gap_rows = discrepancies["briefing_gaps"]
            if evidence_rows:
                st.markdown(
                    "**Demandas com resposta identificada, ainda aguardando "
                    "confirmação de vínculo**"
                )
                st.dataframe(
                    pd.DataFrame(evidence_rows),
                    hide_index=True,
                    width="stretch",
                )
            if gap_rows:
                st.markdown("**Demandas ainda sem evidência identificada**")
                st.dataframe(
                    pd.DataFrame(gap_rows),
                    hide_index=True,
                    width="stretch",
                )
            if not evidence_rows and not gap_rows:
                st.caption("Não foram identificadas demandas sem evidência.")

    technical_health = intelligence.get("technical_health") or []
    if technical_health:
        with st.expander("Saúde da leitura NAVE", expanded=False):
            st.caption(
                "Diagnóstico técnico do processamento; não faz parte da análise de negócio."
            )
            for row in technical_health[:20]:
                severity = str(
                    row.get("severity") or row.get("level") or "warning"
                )
                message = (
                    f"**{row.get('title') or 'Aviso técnico'}** — "
                    f"{row.get('text') or ''}"
                )
                if severity in {"critical", "high", "error"}:
                    st.error(message)
                else:
                    st.warning(message)

    history = snapshot.get("recommendation_queries", [])
    if history:
        with st.expander("Histórico de análises anteriores", expanded=False):
            for index, row in enumerate(history, start=1):
                title = (
                    row.get("query_label")
                    or row.get("project_name")
                    or f"Análise {index}"
                )
                st.markdown(f"**{title}**")
                if row.get("objective"):
                    st.caption(str(row.get("objective")))

    st.caption(
        "A análise é atualizada quando novas fontes entram no projeto. "
        "Ausência de evidência não é tratada como prova de ausência."
    )
