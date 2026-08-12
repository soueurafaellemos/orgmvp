from __future__ import annotations

import re
from html import escape
from typing import Any

import streamlit as st

from nave_storage import get_bytes as storage_get_bytes


def _money(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "Não informado"
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _clean_result_text(value: Any) -> str:
    """Protege a projeção contra linguagem de performance sem prova explícita.

    O relatório pode comprovar execução sem comprovar sucesso/performance. Este
    filtro não inventa uma conclusão nova; apenas neutraliza qualificadores que
    ultrapassam a evidência operacional disponível.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    text = re.sub(r"\brealizad[ao]\s+com\s+sucesso\b", "executada", text, flags=re.I)
    text = re.sub(r"\bexecutad[ao]\s+com\s+sucesso\b", "executada", text, flags=re.I)
    return text


def _safe_objectives_text(latest: dict[str, Any]) -> str:
    text = _clean_result_text(latest.get("objectives_result"))
    if not text:
        return ""
    norm = text.casefold()
    participants = latest.get("participants_count")
    # Extratores antigos podiam transformar público total do evento em sucesso da
    # ativação. Quando o próprio texto combina "atingiu público-alvo" com o total
    # do evento, reconstruímos uma leitura conservadora e explicitamos o limite.
    conflates_event_audience = (
        participants not in (None, "")
        and any(term in norm for term in ("atingindo o público-alvo", "atingiu o público-alvo", "atingindo o publico-alvo", "atingiu o publico-alvo"))
        and any(term in norm for term in ("presentes no evento", "pessoas no evento", "festival"))
    )
    if conflates_event_audience:
        return (
            "O relatório comprova a execução da ativação e registra brincadeiras, presença de mascote e distribuição de produtos. "
            f"O evento recebeu {int(float(participants)):,} pessoas; as fontes atuais não informam quantas delas participaram especificamente da ativação."
        ).replace(",", ".")
    return text


def _status_label(value: Any) -> str:
    return {
        "executed": "Executada",
        "partially_executed": "Executada parcialmente",
        "pending": "Pendente",
        "not_executed": "Não executada",
        "achieved": "Atingido",
        "exceeded": "Superado",
        "not_achieved": "Não atingido",
    }.get(str(value or "").casefold(), str(value or "Não informado").replace("_", " ").title())


def _metric_cards(values: list[tuple[str, str, str]]) -> None:
    if not values:
        return
    cards = "".join(
        f'<div class="nave-report-metric"><div class="nave-report-metric-label">{escape(label)}</div>'
        f'<div class="nave-report-metric-value">{escape(value)}</div>'
        f'<div class="nave-report-metric-detail">{escape(detail)}</div></div>'
        for label, value, detail in values
    )
    st.markdown(
        """
        <style>
        .nave-report-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:.4rem 0 1rem}
        .nave-report-metric{background:#F7F9FC;border:1px solid #E1E6EF;border-radius:14px;padding:14px 15px;min-width:0}
        .nave-report-metric-label{font-size:.78rem;font-weight:700;color:#58647B;line-height:1.25;white-space:normal;overflow-wrap:anywhere}
        .nave-report-metric-value{font-size:1.75rem;font-weight:850;color:#121B42;line-height:1.1;margin-top:.35rem;overflow-wrap:anywhere}
        .nave-report-metric-detail{font-size:.70rem;color:#7C879D;line-height:1.3;margin-top:.35rem}
        @media(max-width:850px){.nave-report-metrics{grid-template-columns:1fr}}
        </style>
        <div class="nave-report-metrics">""" + cards + "</div>",
        unsafe_allow_html=True,
    )


def _render_activation_results(values: list[dict[str, Any]]) -> None:
    if not values:
        return
    st.markdown("#### Resultados por ativação ou entrega")
    cols = st.columns(2, gap="large")
    for index, item in enumerate(values):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{item.get('name') or item.get('item_name') or 'Entrega'}**")
                status = _status_label(item.get("status") or item.get("outcome_status"))
                st.caption(status)
                result = _clean_result_text(item.get("result") or item.get("feedback"))
                if result:
                    st.write(result)
                participants = item.get("participants")
                if participants not in (None, ""):
                    st.caption(f"Participação específica registrada: {participants}")
                evidence = item.get("evidence")
                if evidence:
                    with st.expander("Ver fonte", expanded=False):
                        st.write(evidence)


def _render_kpis(values: list[dict[str, Any]]) -> None:
    if not values:
        return
    st.markdown("#### Indicadores comprovados")
    for item in values[:12]:
        name = str(item.get("name") or "Indicador")
        # Público total do evento não pode parecer participação da ativação.
        if any(token in name.casefold() for token in ("público", "publico", "presentes")):
            name = "Público do evento"
        actual = item.get("actual")
        target = item.get("target")
        unit = str(item.get("unit") or "").strip()
        left, right = st.columns([0.7, 0.3])
        with left:
            st.markdown(f"**{name}**")
            actual_text = f"{actual} {unit}".strip() if actual not in (None, "") else "Não informado"
            st.write(actual_text)
            if target not in (None, ""):
                st.caption(f"Referência/meta informada: {target}")
        with right:
            st.caption(_status_label(item.get("status")))
        if item.get("evidence"):
            with st.expander("Fonte do indicador", expanded=False):
                st.write(item.get("evidence"))


def render_report_analyses(snapshot: dict[str, Any]) -> None:
    analyses = snapshot.get("report_analyses", [])
    if not analyses:
        return
    latest = analyses[0]
    st.markdown("#### Leitura estruturada do relatório")

    cards: list[tuple[str, str, str]] = []
    participants = latest.get("participants_count")
    if participants not in (None, ""):
        cards.append((
            "Público registrado no evento",
            f"{int(float(participants)):,}".replace(",", "."),
            "Não equivale automaticamente a visitantes da ativação.",
        ))
    if latest.get("planned_cost") not in (None, ""):
        cards.append(("Custo previsto no relatório", _money(latest.get("planned_cost")), "Somente quando explicitamente informado."))
    if latest.get("actual_cost") not in (None, ""):
        cards.append(("Custo realizado no relatório", _money(latest.get("actual_cost")), "Somente quando explicitamente informado."))
    _metric_cards(cards)

    if latest.get("executive_summary"):
        st.info(_clean_result_text(latest.get("executive_summary")))

    objectives = _safe_objectives_text(latest)
    if objectives:
        st.markdown("#### O que o relatório permite afirmar")
        st.write(objectives)

    highlights = [_clean_result_text(value) for value in latest.get("highlights") or [] if _clean_result_text(value)]
    issues = [_clean_result_text(value) for value in latest.get("issues") or [] if _clean_result_text(value)]
    if highlights or issues:
        cols = st.columns(2, gap="large")
        with cols[0]:
            st.markdown("**Destaques documentados**")
            if highlights:
                for value in highlights[:10]:
                    st.markdown(f"- {value}")
            else:
                st.caption("Nenhum destaque explícito identificado.")
        with cols[1]:
            st.markdown("**Ocorrências e pontos de atenção**")
            if issues:
                for value in issues[:10]:
                    st.markdown(f"- {value}")
            else:
                st.caption("Nenhuma ocorrência explícita identificada.")

    _render_kpis(latest.get("kpis") or [])
    _render_activation_results(latest.get("activation_results") or [])

    explicit_learnings = [_clean_result_text(value) for value in latest.get("learnings") or [] if _clean_result_text(value)]
    explicit_recommendations = [_clean_result_text(value) for value in latest.get("recommendations") or [] if _clean_result_text(value)]
    if explicit_learnings or explicit_recommendations:
        st.markdown("#### Aprendizados e recomendações explicitamente registrados no relatório")
        cols = st.columns(2, gap="large")
        with cols[0]:
            st.markdown("**Aprendizados da fonte**")
            if explicit_learnings:
                for value in explicit_learnings[:8]:
                    st.markdown(f"- {value}")
            else:
                st.caption("Nenhum aprendizado foi escrito explicitamente no relatório.")
        with cols[1]:
            st.markdown("**Recomendações da fonte**")
            if explicit_recommendations:
                for value in explicit_recommendations[:8]:
                    st.markdown(f"- {value}")
            else:
                st.caption("Nenhuma recomendação futura foi escrita explicitamente no relatório.")

    supplier_evaluations = latest.get("supplier_evaluations") or []
    if supplier_evaluations:
        with st.expander("Avaliação de fornecedores registrada no relatório", expanded=False):
            st.dataframe(supplier_evaluations, hide_index=True, width="stretch")
    media_results = latest.get("media_results") or []
    if media_results:
        with st.expander("Resultados de mídia e conteúdo", expanded=False):
            st.dataframe(media_results, hide_index=True, width="stretch")
    feedbacks = latest.get("client_feedback") or []
    if feedbacks:
        st.markdown("#### Feedback explícito identificado no relatório")
        for feedback in feedbacks:
            if isinstance(feedback, dict):
                text = feedback.get("text") or feedback.get("feedback") or feedback
            else:
                text = feedback
            st.markdown(f"- {text}")


def render_pending_report_actions(
    client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
    report_role: str,
) -> None:
    from project_report_extractor import analyze_project_report
    from project_workspace_db import save_project_report_analysis

    analysed_ids = {
        str(row.get("report_file_id"))
        for row in snapshot.get("report_analyses", [])
        if row.get("report_file_id")
    }
    pending = [
        row
        for row in snapshot.get("project_files", [])
        if row.get("file_role") == report_role
        and not row.get("is_archived")
        and str(row.get("id")) not in analysed_ids
    ]
    if not pending:
        return

    st.warning(
        "Há relatório anexado sem leitura estruturada. "
        "Analise-o para preencher resultados, indicadores, feedbacks e aprendizados."
    )

    for row in pending:
        file_id = str(row.get("id"))
        file_name = str(row.get("file_name") or row.get("title") or "Relatório")
        if st.button(
            f"Analisar arquivo já anexado — {file_name}",
            key=f"analyse_existing_report_{file_id}",
            width="stretch",
        ):
            try:
                bucket = str(row.get("storage_bucket") or "nave-project-files")
                path = str(row.get("storage_path") or "")
                if not path:
                    raise RuntimeError("O caminho do arquivo não foi encontrado.")
                file_bytes = storage_get_bytes(client, bucket_name=bucket, path=path)
                if not file_bytes:
                    raise RuntimeError("O arquivo não pôde ser baixado do armazenamento privado.")
                api_key = (
                    st.secrets.get("GEMINI_API_KEY")
                    or st.secrets.get("GOOGLE_API_KEY")
                )
                model = st.secrets.get("GEMINI_MODEL")
                report_type = "closure" if report_role == "closure_report" else "post_execution"
                with st.spinner(
                    "Lendo o relatório e aplicando os dados ao projeto..."
                ):
                    analysis = analyze_project_report(
                        file_name=file_name,
                        mime_type=row.get("mime_type"),
                        file_bytes=file_bytes,
                        report_type=report_type,
                        api_key=str(api_key or ""),
                        model=str(model or "") or None,
                    )
                    save_project_report_analysis(
                        client,
                        project_id=project_id,
                        report_file_id=file_id,
                        report_type=report_type,
                        analysis=analysis,
                    )
            except Exception as exc:
                st.error(f"Não foi possível analisar o relatório: {exc}")
            else:
                st.success(
                    "Relatório analisado e aplicado ao projeto."
                )
                st.rerun()
