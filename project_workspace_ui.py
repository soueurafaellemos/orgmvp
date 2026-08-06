from __future__ import annotations

from datetime import date
from html import escape
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from supabase import Client

from project_workspace_db import (
    FILE_ROLE_LABELS,
    STATUS_LABELS,
    archive_project_file,
    create_project_file_signed_url,
    fetch_memory_items_by_sections,
    fetch_project_files,
    fetch_project_linked_suppliers,
    fetch_project_workspace_snapshot,
    fetch_projects_workspace,
    save_project_feedback,
    save_project_file,
    save_project_outcome,
    save_project_report_analysis,
    update_project_workspace_data,
)
from project_report_extractor import analyze_project_report
from project_workspace_reports import (
    render_pending_report_actions,
    render_report_analyses,
)
from project_workspace_visuals import render_visual_section


PROJECT_SECTIONS = [
    "Visão geral",
    "Briefing original",
    "Diagnóstico e recomendações",
    "Estratégia e conceito",
    "Cenografia e ativações",
    "Brindes e press kits",
    "Orçamento e aderência",
    "Fornecedores e referências",
    "Apresentações finais",
    "Feedbacks e aprovações",
    "Resultados e aprendizados",
    "Documentos",
]

STATUS_OPTIONS = list(STATUS_LABELS.keys())
STATUS_BY_LABEL = {label: key for key, label in STATUS_LABELS.items()}

WORKSPACE_CSS = """
<style>
.nave-workspace-header {
    background:
        linear-gradient(
            135deg,
            rgba(18, 27, 66, 1) 0%,
            rgba(25, 43, 92, 1) 72%,
            rgba(24, 205, 234, 0.96) 140%
        );
    border-radius: 18px;
    color: #FFFFFF;
    margin-bottom: 1rem;
    padding: 1.25rem 1.35rem;
}

.nave-workspace-eyebrow {
    color: #18CDEA;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.13em;
    text-transform: uppercase;
}

.nave-workspace-title {
    color: #FFFFFF !important;
    font-size: clamp(1.5rem, 3vw, 2.25rem);
    letter-spacing: -0.035em;
    line-height: 1.08;
    margin: 0.38rem 0 0;
}

.nave-workspace-meta {
    color: rgba(255, 255, 255, 0.76);
    font-size: 0.84rem;
    line-height: 1.5;
    margin-top: 0.6rem;
}

.nave-workspace-card {
    background: #FFFFFF;
    border: 1px solid #E1E6EF;
    border-radius: 14px;
    min-height: 128px;
    padding: 0.95rem 1rem;
}

.nave-workspace-card-label {
    color: #18AFC9;
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.09em;
    text-transform: uppercase;
}

.nave-workspace-card-title {
    color: #121B42;
    font-size: 0.98rem;
    font-weight: 750;
    margin-top: 0.38rem;
}

.nave-workspace-card-copy {
    color: #687188;
    font-size: 0.8rem;
    line-height: 1.45;
    margin-top: 0.34rem;
}

.nave-workspace-status-ok {
    color: #17845B;
    font-weight: 700;
}

.nave-workspace-status-pending {
    color: #A96E00;
    font-weight: 700;
}

.nave-workspace-nav-title {
    color: #18AFC9;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    margin: 0 0 0.35rem;
    text-transform: uppercase;
}

.nave-workspace-section-intro {
    color: #687188;
    font-size: 0.88rem;
    line-height: 1.55;
    margin: -0.25rem 0 1rem;
}

.nave-workspace-empty {
    background: #F4F6F9;
    border: 1px dashed #C9D1E2;
    border-radius: 13px;
    color: #687188;
    padding: 1rem;
}

.nave-workspace-item {
    background: #FFFFFF;
    border: 1px solid #E1E6EF;
    border-radius: 13px;
    margin-bottom: 0.7rem;
    padding: 0.9rem 1rem;
}

.nave-workspace-item-title {
    color: #121B42;
    font-size: 0.95rem;
    font-weight: 750;
}

.nave-workspace-item-meta {
    color: #7D869C;
    font-size: 0.72rem;
    margin-top: 0.2rem;
}

.nave-workspace-item-copy {
    color: #4F5971;
    font-size: 0.82rem;
    line-height: 1.48;
    margin-top: 0.45rem;
}

div[data-testid="stRadio"] > label {
    color: #18AFC9 !important;
    font-size: 0.68rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

div[data-testid="stRadio"] div[role="radiogroup"] {
    background: #F4F6F9;
    border: 1px solid #E1E6EF;
    border-radius: 14px;
    padding: 0.45rem;
}

div[data-testid="stRadio"] div[role="radiogroup"] label {
    background: transparent;
    border-radius: 9px;
    margin: 0.06rem 0;
    padding: 0.24rem 0.35rem;
}

div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
    background: rgba(24, 205, 234, 0.1);
}
</style>
"""


def _inject_workspace_css() -> None:
    st.markdown(WORKSPACE_CSS, unsafe_allow_html=True)


def _format_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Não informada"
    try:
        parsed = pd.to_datetime(text)
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return text


def _format_datetime(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Não informada"
    try:
        parsed = pd.to_datetime(text)
        return parsed.strftime("%d/%m/%Y · %H:%M")
    except Exception:
        return text


def _format_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Não informado"
    formatted = f"{number:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _project_header(project: dict[str, Any]) -> None:
    title = project.get("project_name") or "Projeto sem nome"
    client = project.get("client_brand") or "Cliente não informado"
    event = project.get("event_name") or "Evento não informado"
    status = STATUS_LABELS.get(
        str(project.get("status") or ""),
        str(project.get("status") or "Não informado"),
    )
    date_text = _format_date(project.get("event_date"))

    st.markdown(
        f"""
        <section class="nave-workspace-header">
            <div class="nave-workspace-eyebrow">Workspace do projeto</div>
            <h1 class="nave-workspace-title">{escape(str(title))}</h1>
            <div class="nave-workspace-meta">
                {escape(str(client))} · {escape(str(event))}<br>
                Status: {escape(status)} · Data do evento: {escape(date_text)}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _workspace_raw(project: dict[str, Any]) -> dict[str, Any]:
    raw_data = project.get("raw_data")
    if not isinstance(raw_data, dict):
        return {}
    workspace = raw_data.get("workspace")
    return workspace if isinstance(workspace, dict) else {}


def _status_selector(
    client: Client,
    *,
    project: dict[str, Any],
    project_id: str,
) -> None:
    current_status = str(project.get("status") or "rascunho")
    if current_status not in STATUS_OPTIONS:
        STATUS_OPTIONS_WITH_CURRENT = [current_status, *STATUS_OPTIONS]
    else:
        STATUS_OPTIONS_WITH_CURRENT = STATUS_OPTIONS

    status_index = STATUS_OPTIONS_WITH_CURRENT.index(current_status)
    workspace = _workspace_raw(project)

    with st.expander("Editar status e próxima ação"):
        with st.form(f"workspace_meta_{project_id}"):
            selected_status = st.selectbox(
                "Status do projeto",
                options=STATUS_OPTIONS_WITH_CURRENT,
                index=status_index,
                format_func=lambda value: STATUS_LABELS.get(
                    value,
                    value.replace("_", " ").title(),
                ),
            )
            next_action = st.text_input(
                "Próxima ação",
                value=str(workspace.get("next_action") or ""),
                placeholder="Ex.: revisar orçamento antes do envio ao cliente",
            )
            notes = st.text_area(
                "Observações operacionais",
                value=str(workspace.get("notes") or ""),
                height=90,
            )

            submitted = st.form_submit_button(
                "Salvar informações",
                width="stretch",
            )

        if submitted:
            update_project_workspace_data(
                client,
                project_id=project_id,
                status=selected_status,
                next_action=next_action,
                workspace_notes=notes,
            )
            st.success("Informações do projeto atualizadas.")
            st.rerun()


def _html_file_card(
    *,
    label: str,
    title: str,
    copy: str,
    ready: bool,
) -> str:
    status_class = (
        "nave-workspace-status-ok"
        if ready
        else "nave-workspace-status-pending"
    )
    status_text = "Disponível" if ready else "Pendente"

    return f"""
    <article class="nave-workspace-card">
        <div class="nave-workspace-card-label">{escape(label)}</div>
        <div class="nave-workspace-card-title">{escape(title)}</div>
        <div class="nave-workspace-card-copy">{escape(copy)}</div>
        <div class="{status_class}" style="margin-top:0.55rem;font-size:0.78rem;">
            {status_text}
        </div>
    </article>
    """


def _role_rows(
    snapshot: dict[str, Any],
    role: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in snapshot.get("project_files", [])
        if row.get("file_role") == role
        and not row.get("is_archived")
    ]


def _has_role(
    snapshot: dict[str, Any],
    role: str,
) -> bool:
    return bool(_role_rows(snapshot, role))


def _upload_box(
    client: Client,
    *,
    project_id: str,
    role: str,
    title: str,
    accepted_types: list[str],
    key_suffix: str,
    notes_label: str = "Observação opcional",
) -> None:
    with st.expander(f"Adicionar ou atualizar — {title}"):
        uploaded = st.file_uploader(
            title,
            type=accepted_types,
            key=f"upload_{project_id}_{role}_{key_suffix}",
        )
        notes = st.text_input(
            notes_label,
            key=f"notes_{project_id}_{role}_{key_suffix}",
        )

        if st.button(
            "Salvar no projeto",
            key=f"save_{project_id}_{role}_{key_suffix}",
            width="stretch",
            disabled=uploaded is None,
        ):
            if uploaded is None:
                st.warning("Selecione um arquivo.")
                return

            try:
                file_bytes = uploaded.getvalue()
                if role in {"closure_report", "post_execution_report"}:
                    report_type = (
                        "closure"
                        if role == "closure_report"
                        else "post_execution"
                    )
                    api_key = (
                        st.secrets.get("GEMINI_API_KEY")
                        or st.secrets.get("GOOGLE_API_KEY")
                    )
                    model = st.secrets.get("GEMINI_MODEL")
                    with st.spinner(
                        "Analisando o relatório e preenchendo resultados, "
                        "indicadores e aprendizados..."
                    ):
                        analysis = analyze_project_report(
                            file_name=uploaded.name,
                            mime_type=uploaded.type,
                            file_bytes=file_bytes,
                            report_type=report_type,
                            api_key=str(api_key or ""),
                            model=str(model or "") or None,
                        )
                        saved_file = save_project_file(
                            client,
                            project_id=project_id,
                            file_role=role,
                            title=title,
                            file_name=uploaded.name,
                            file_bytes=file_bytes,
                            mime_type=uploaded.type,
                            notes=notes,
                            metadata={"report_analysis": "processed"},
                        )
                        save_project_report_analysis(
                            client,
                            project_id=project_id,
                            report_file_id=str(saved_file.get("id")),
                            report_type=report_type,
                            analysis=analysis,
                        )
                else:
                    save_project_file(
                        client,
                        project_id=project_id,
                        file_role=role,
                        title=title,
                        file_name=uploaded.name,
                        file_bytes=file_bytes,
                        mime_type=uploaded.type,
                        notes=notes,
                    )
            except Exception as exc:
                st.error(f"Não foi possível processar o arquivo: {exc}")
            else:
                if role in {"closure_report", "post_execution_report"}:
                    st.success(
                        "Relatório analisado. Resultados, indicadores, "
                        "feedbacks e aprendizados foram aplicados ao projeto."
                    )
                else:
                    st.success("Arquivo salvo no projeto.")
                st.rerun()


def _render_file_list(
    client: Client,
    *,
    rows: list[dict[str, Any]],
    empty_message: str,
    allow_archive: bool = False,
) -> None:
    if not rows:
        st.markdown(
            f'<div class="nave-workspace-empty">{escape(empty_message)}</div>',
            unsafe_allow_html=True,
        )
        return

    for row in rows:
        columns = st.columns([4.7, 1.4, 1.2])
        with columns[0]:
            role_label = FILE_ROLE_LABELS.get(
                str(row.get("file_role") or ""),
                str(row.get("file_role") or "Arquivo"),
            )
            st.markdown(
                f"""
                <div class="nave-workspace-item">
                    <div class="nave-workspace-item-title">
                        {escape(str(row.get("title") or row.get("file_name") or "Arquivo"))}
                    </div>
                    <div class="nave-workspace-item-meta">
                        {escape(role_label)} · versão {int(row.get("version_number") or 1)}
                        · {_format_datetime(row.get("created_at"))}
                    </div>
                    <div class="nave-workspace-item-copy">
                        {escape(str(row.get("file_name") or ""))}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        signed_url = create_project_file_signed_url(
            client,
            row.get("storage_path"),
            download=True,
        )

        with columns[1]:
            if signed_url:
                st.link_button(
                    "Baixar",
                    signed_url,
                    width="stretch",
                )
            else:
                st.button(
                    "Indisponível",
                    key=f"unavailable_{row.get('id')}",
                    disabled=True,
                    width="stretch",
                )

        with columns[2]:
            if allow_archive:
                if st.button(
                    "Arquivar",
                    key=f"archive_{row.get('id')}",
                    width="stretch",
                ):
                    archive_project_file(
                        client,
                        file_id=str(row.get("id")),
                    )
                    st.rerun()


def _section_title(title: str, intro: str) -> None:
    st.subheader(title)
    st.markdown(
        f'<div class="nave-workspace-section-intro">{escape(intro)}</div>',
        unsafe_allow_html=True,
    )


def _derive_pending_items(
    snapshot: dict[str, Any],
    project: dict[str, Any],
) -> list[str]:
    pending = []

    has_briefing = bool(snapshot.get("briefing_documents")) or _has_role(
        snapshot,
        "briefing_original",
    )
    has_cost = bool(snapshot.get("cost_documents")) or _has_role(
        snapshot,
        "cost_sheet",
    )
    has_presentation = bool(snapshot.get("memory_documents")) or _has_role(
        snapshot,
        "final_presentation",
    )
    has_feedback = bool(snapshot.get("feedback_entries")) or _has_role(
        snapshot,
        "feedback",
    ) or _has_role(snapshot, "approval")

    if not has_briefing:
        pending.append("Anexar o briefing original.")
    if not has_cost:
        pending.append("Anexar a planilha de custos.")
    if not has_presentation:
        pending.append("Adicionar a apresentação final.")

    status = str(project.get("status") or "")

    if status in {
        "apresentado",
        "em_revisao",
        "em_negociacao",
        "aprovado_ganho",
        "perdido",
        "em_producao",
        "executado",
    } and not has_feedback:
        pending.append("Registrar feedback ou aprovação do cliente.")

    if status == "perdido" and not _has_role(
        snapshot,
        "closure_report",
    ):
        pending.append("Adicionar o relatório de encerramento da concorrência.")

    if status == "executado" and not _has_role(
        snapshot,
        "post_execution_report",
    ):
        pending.append("Adicionar o relatório pós-execução.")

    return pending


def _render_overview(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    project = snapshot["project"]
    _section_title(
        "Visão geral",
        "Status, pendências, arquivos principais e próximos passos do projeto.",
    )

    metrics = st.columns(5)
    metrics[0].metric(
        "Briefings",
        len(snapshot.get("briefing_documents", []))
        + len(_role_rows(snapshot, "briefing_original")),
    )
    metrics[1].metric(
        "Apresentações",
        len(snapshot.get("memory_documents", []))
        + len(_role_rows(snapshot, "final_presentation")),
    )
    metrics[2].metric(
        "Conteúdos",
        len(snapshot.get("memory_items", [])),
    )
    metrics[3].metric(
        "Feedbacks",
        len(snapshot.get("feedback_entries", []))
        + len(_role_rows(snapshot, "feedback"))
        + len(_role_rows(snapshot, "approval")),
    )
    metrics[4].metric(
        "Arquivos",
        len(
            [
                row
                for row in snapshot.get("project_files", [])
                if not row.get("is_archived")
            ]
        ),
    )

    pending = _derive_pending_items(snapshot, project)
    workspace = _workspace_raw(project)

    st.markdown("#### Pendências e próxima ação")
    left, right = st.columns([1.25, 1])

    with left:
        if pending:
            for item in pending:
                st.warning(item)
        else:
            st.success("Nenhuma pendência automática identificada.")

    with right:
        next_action = workspace.get("next_action") or "Não informada"
        st.info(f"**Próxima ação:** {next_action}")

    st.markdown("#### Arquivos principais")

    status = str(project.get("status") or "")
    report_role = (
        "post_execution_report"
        if status == "executado"
        else "closure_report"
        if status == "perdido"
        else None
    )
    report_title = (
        "Relatório pós-execução"
        if report_role == "post_execution_report"
        else "Relatório de encerramento"
        if report_role == "closure_report"
        else "Relatório de fechamento"
    )

    cards = [
        (
            "Entrada",
            "Briefing original",
            "Arquivo-base recebido para iniciar o projeto.",
            bool(snapshot.get("briefing_documents"))
            or _has_role(snapshot, "briefing_original"),
        ),
        (
            "Viabilidade",
            "Planilha de custos",
            "Orçamento previsto, revisado ou aprovado.",
            bool(snapshot.get("cost_documents"))
            or _has_role(snapshot, "cost_sheet"),
        ),
        (
            "Entrega",
            "Apresentações finais",
            "Versões apresentadas, aprovadas ou executadas.",
            bool(snapshot.get("memory_documents"))
            or _has_role(snapshot, "final_presentation"),
        ),
        (
            "Decisão",
            "Feedbacks e aprovações",
            "Retornos, pedidos de ajuste e decisões do cliente.",
            bool(snapshot.get("feedback_entries"))
            or _has_role(snapshot, "feedback")
            or _has_role(snapshot, "approval"),
        ),
        (
            "Fechamento",
            report_title,
            "Documento de encerramento, resultado ou pós-execução.",
            bool(report_role and _has_role(snapshot, report_role)),
        ),
    ]

    first_row = st.columns(3)
    for column, card in zip(first_row, cards[:3]):
        with column:
            st.markdown(
                _html_file_card(
                    label=card[0],
                    title=card[1],
                    copy=card[2],
                    ready=card[3],
                ),
                unsafe_allow_html=True,
            )

    second_row = st.columns(3)
    for column, card in zip(second_row, cards[3:]):
        with column:
            st.markdown(
                _html_file_card(
                    label=card[0],
                    title=card[1],
                    copy=card[2],
                    ready=card[3],
                ),
                unsafe_allow_html=True,
            )

    st.markdown("#### Adicionar arquivos sem sair da Visão geral")

    upload_columns = st.columns(2)
    with upload_columns[0]:
        _upload_box(
            client,
            project_id=project_id,
            role="briefing_original",
            title="Briefing original",
            accepted_types=["pdf", "docx", "pptx", "txt", "md"],
            key_suffix="overview",
        )
        _upload_box(
            client,
            project_id=project_id,
            role="final_presentation",
            title="Apresentação final",
            accepted_types=["pdf", "pptx"],
            key_suffix="overview",
        )

    with upload_columns[1]:
        _upload_box(
            client,
            project_id=project_id,
            role="cost_sheet",
            title="Planilha de custos",
            accepted_types=["xlsx", "xlsm", "xls", "csv"],
            key_suffix="overview",
        )
        _upload_box(
            client,
            project_id=project_id,
            role="feedback",
            title="Feedback ou aprovação",
            accepted_types=[
                "pdf",
                "docx",
                "pptx",
                "txt",
                "md",
                "eml",
                "msg",
            ],
            key_suffix="overview",
        )

    if report_role:
        _upload_box(
            client,
            project_id=project_id,
            role=report_role,
            title=report_title,
            accepted_types=["pdf", "docx", "pptx", "xlsx", "txt", "md"],
            key_suffix="overview",
        )


def _render_briefing(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Briefing original",
        "Arquivo recebido, versões e demandas estruturadas do briefing.",
    )

    structured = snapshot.get("briefing_documents", [])
    generic = _role_rows(snapshot, "briefing_original")

    st.markdown("#### Arquivo original")
    _render_file_list(
        client,
        rows=generic,
        empty_message="Nenhum briefing original foi anexado por esta central.",
        allow_archive=True,
    )

    _upload_box(
        client,
        project_id=project_id,
        role="briefing_original",
        title="Briefing original",
        accepted_types=["pdf", "docx", "pptx", "txt", "md"],
        key_suffix="briefing",
    )

    st.markdown("#### Briefings já estruturados pela NAVE")

    if structured:
        structured_df = pd.DataFrame(structured)
        display_columns = [
            column
            for column in (
                "title",
                "file_name",
                "requirements_count",
                "budget_amount",
                "created_at",
            )
            if column in structured_df.columns
        ]
        st.dataframe(
            structured_df[display_columns],
            hide_index=True,
            width="stretch",
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">'
            "Ainda não há briefing estruturado na matriz de aderência."
            "</div>",
            unsafe_allow_html=True,
        )

    requirements = snapshot.get("briefing_requirements", [])
    st.markdown("#### Demandas e obrigatoriedades")

    if requirements:
        req_df = pd.DataFrame(requirements)
        wanted = [
            column
            for column in (
                "requirement_type",
                "title",
                "priority",
                "mandatory",
                "adherence_status",
            )
            if column in req_df.columns
        ]
        st.dataframe(
            req_df[wanted],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption(
            "As demandas aparecerão aqui após a análise estruturada do briefing."
        )


def _render_recommendations(
    *,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Diagnóstico e recomendações",
        "Histórico de diagnósticos, versões e recomendações geradas para o projeto.",
    )

    rows = snapshot.get("recommendation_queries", [])

    if not rows:
        st.markdown(
            '<div class="nave-workspace-empty">'
            "Nenhum diagnóstico ou recomendação foi encontrado para este projeto."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    for index, row in enumerate(rows, start=1):
        title = (
            row.get("query_label")
            or row.get("project_name")
            or f"Análise {index}"
        )
        objective = row.get("objective") or "Objetivo não informado"
        created = _format_datetime(row.get("created_at"))

        with st.expander(f"{title} · {created}", expanded=index == 1):
            st.markdown(f"**Objetivo:** {objective}")
            if row.get("briefing_text"):
                st.markdown("**Briefing analisado**")
                st.write(row.get("briefing_text"))
            if isinstance(row.get("parsed_brief"), dict):
                st.markdown("**Leitura estruturada**")
                st.json(row.get("parsed_brief"))


def _render_memory_cards(
    client: Client,
    *,
    project_id: str,
    section_keys: Iterable[str],
    empty_message: str,
) -> None:
    dataframe = fetch_memory_items_by_sections(
        client,
        project_id=project_id,
        section_keys=section_keys,
    )

    if dataframe.empty:
        st.markdown(
            f'<div class="nave-workspace-empty">{escape(empty_message)}</div>',
            unsafe_allow_html=True,
        )
        return

    for _, row in dataframe.iterrows():
        title = row.get("title") or "Conteúdo sem título"
        summary = (
            row.get("summary")
            or row.get("description")
            or "Sem resumo disponível."
        )
        item_type = row.get("item_type") or "Conteúdo"
        status = row.get("item_status") or "Não informado"
        st.markdown(
            f"""
            <article class="nave-workspace-item">
                <div class="nave-workspace-item-title">{escape(str(title))}</div>
                <div class="nave-workspace-item-meta">
                    {escape(str(item_type))} · {escape(str(status))}
                </div>
                <div class="nave-workspace-item-copy">
                    {escape(str(summary))}
                </div>
            </article>
            """,
            unsafe_allow_html=True,
        )


def _render_strategy(
    client: Client,
    *,
    project_id: str,
) -> None:
    _section_title(
        "Estratégia e conceito",
        "Direcionais estratégicos, conceitos criativos e racional do projeto.",
    )
    _render_memory_cards(
        client,
        project_id=project_id,
        section_keys=["strategy"],
        empty_message=(
            "Nenhum conteúdo de estratégia ou conceito foi estruturado."
        ),
    )



def _render_scenography(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Cenografia e ativações",
        "Ambientes, ativações, experiências, jornada e operação.",
    )

    st.markdown("#### Cenografia e ambientes")
    render_visual_section(
        client,
        project_id=project_id,
        snapshot=snapshot,
        section_keys=["scenography"],
        empty_message="Nenhum ambiente ou solução cenográfica foi identificado.",
    )

    st.markdown("#### Ativações e experiências")
    render_visual_section(
        client,
        project_id=project_id,
        snapshot=snapshot,
        section_keys=["activations"],
        empty_message="Nenhuma ativação ou experiência foi identificada.",
    )

    st.markdown("#### Jornada e operação")
    _render_memory_cards(
        client,
        project_id=project_id,
        section_keys=["journey_operation"],
        empty_message="Nenhum conteúdo de jornada ou operação foi estruturado.",
    )


def _render_gifts(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Brindes e press kits",
        "Conceitos, itens, composições, mockups, custos e referências.",
    )

    render_visual_section(
        client,
        project_id=project_id,
        snapshot=snapshot,
        section_keys=["gifts"],
        empty_message="Nenhum brinde, press kit ou material visual foi identificado.",
    )

    st.markdown("#### Referências e arquivos")
    rows = _role_rows(snapshot, "gift_presskit_reference")
    _render_file_list(
        client,
        rows=rows,
        empty_message="Nenhuma referência adicional foi anexada.",
        allow_archive=True,
    )

    _upload_box(
        client,
        project_id=project_id,
        role="gift_presskit_reference",
        title="Referência de brinde ou press kit",
        accepted_types=[
            "pdf",
            "pptx",
            "docx",
            "xlsx",
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key_suffix="gifts",
    )


def _render_budget(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Orçamento e aderência",
        "Planilhas, linhas de custo e conexão entre briefing, proposta e orçamento.",
    )

    files = _role_rows(snapshot, "cost_sheet")
    _render_file_list(
        client,
        rows=files,
        empty_message="Nenhuma planilha foi anexada por esta central.",
        allow_archive=True,
    )

    _upload_box(
        client,
        project_id=project_id,
        role="cost_sheet",
        title="Planilha de custos",
        accepted_types=["xlsx", "xlsm", "xls", "csv"],
        key_suffix="budget",
    )

    cost_documents = snapshot.get("cost_documents", [])
    cost_items = snapshot.get("cost_items", [])

    st.markdown("#### Planilhas já estruturadas pela NAVE")

    if cost_documents:
        df = pd.DataFrame(cost_documents)
        wanted = [
            column
            for column in (
                "file_name",
                "items_count",
                "budget_amount",
                "created_at",
            )
            if column in df.columns
        ]
        st.dataframe(
            df[wanted],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Nenhuma planilha estruturada foi encontrada.")

    st.markdown("#### Linhas de custo")

    if cost_items:
        df = pd.DataFrame(cost_items)
        wanted = [
            column
            for column in (
                "category",
                "item_name",
                "quantity",
                "unit_value",
                "client_total",
                "item_status",
                "estimate_type",
            )
            if column in df.columns
        ]
        st.dataframe(
            df[wanted],
            hide_index=True,
            width="stretch",
        )

        if "client_total" in df.columns:
            total = pd.to_numeric(
                df["client_total"],
                errors="coerce",
            ).fillna(0).sum()
            st.metric("Total identificado", _format_money(total))
    else:
        st.caption("As linhas aparecerão após a estruturação da planilha.")


def _render_suppliers(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Fornecedores e referências",
        "Parceiros vinculados ao projeto, soluções relacionadas e materiais de apoio.",
    )

    dataframe = fetch_project_linked_suppliers(
        client,
        project_id=project_id,
    )

    if dataframe.empty:
        st.markdown(
            '<div class="nave-workspace-empty">'
            "Nenhum fornecedor foi vinculado diretamente aos itens do projeto."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.dataframe(
            dataframe,
            hide_index=True,
            width="stretch",
        )

    st.markdown("#### Arquivos e referências")
    rows = _role_rows(snapshot, "supplier_reference")
    _render_file_list(
        client,
        rows=rows,
        empty_message="Nenhum material de fornecedor foi anexado.",
        allow_archive=True,
    )

    _upload_box(
        client,
        project_id=project_id,
        role="supplier_reference",
        title="Fornecedor ou referência",
        accepted_types=[
            "pdf",
            "pptx",
            "docx",
            "xlsx",
            "xlsm",
            "csv",
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key_suffix="suppliers",
    )


def _render_presentations(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Apresentações finais",
        "Versões apresentadas ao cliente, aprovadas, executadas ou preservadas como histórico.",
    )

    generic = _role_rows(snapshot, "final_presentation")
    _render_file_list(
        client,
        rows=generic,
        empty_message="Nenhuma apresentação foi anexada por esta central.",
        allow_archive=True,
    )

    _upload_box(
        client,
        project_id=project_id,
        role="final_presentation",
        title="Apresentação final",
        accepted_types=["pdf", "pptx"],
        key_suffix="presentations",
    )

    st.markdown("#### Apresentações analisadas pela NAVE")
    documents = snapshot.get("memory_documents", [])

    if documents:
        df = pd.DataFrame(documents)
        wanted = [
            column
            for column in (
                "title",
                "file_name",
                "version_label",
                "document_status",
                "page_count",
                "items_count",
                "created_at",
            )
            if column in df.columns
        ]
        st.dataframe(
            df[wanted],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Nenhuma apresentação analisada foi encontrada.")


def _render_feedbacks(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Feedbacks e aprovações",
        "Retornos do cliente, pedidos de alteração, aprovações e decisões registradas.",
    )

    with st.expander("Registrar feedback em texto", expanded=False):
        with st.form(f"feedback_form_{project_id}"):
            feedback_date = st.date_input(
                "Data do feedback",
                value=date.today(),
            )
            source_type = st.selectbox(
                "Origem",
                [
                    "client",
                    "procurement",
                    "marketing",
                    "branding",
                    "partner_agency",
                    "production",
                    "public",
                    "internal_team",
                    "not_informed",
                ],
                format_func=lambda value: {
                    "client": "Cliente",
                    "procurement": "Compras",
                    "marketing": "Marketing",
                    "branding": "Branding",
                    "partner_agency": "Agência parceira",
                    "production": "Produção",
                    "public": "Público",
                    "internal_team": "Equipe interna",
                    "not_informed": "Não informado",
                }[value],
            )
            process_stage = st.selectbox(
                "Etapa",
                [
                    "presentation",
                    "revision",
                    "commercial_decision",
                    "production",
                    "post_event",
                    "not_informed",
                ],
                format_func=lambda value: {
                    "presentation": "Apresentação",
                    "revision": "Revisão",
                    "commercial_decision": "Decisão comercial",
                    "production": "Produção",
                    "post_event": "Pós-evento",
                    "not_informed": "Não informada",
                }[value],
            )
            theme = st.selectbox(
                "Tema",
                [
                    "strategy",
                    "creative_concept",
                    "kv",
                    "scenography",
                    "activation",
                    "gift",
                    "journey",
                    "operation",
                    "technology",
                    "budget",
                    "timeline",
                    "presentation",
                    "other",
                ],
                format_func=lambda value: value.replace("_", " ").title(),
            )
            sentiment = st.selectbox(
                "Leitura",
                ["positive", "negative", "neutral", "mixed"],
                format_func=lambda value: {
                    "positive": "Positivo",
                    "negative": "Negativo",
                    "neutral": "Neutro",
                    "mixed": "Misto",
                }[value],
            )
            original_feedback = st.text_area(
                "Feedback recebido",
                height=120,
            )
            internal_interpretation = st.text_area(
                "Interpretação interna",
                height=90,
            )
            action_taken = st.text_area(
                "Ação decorrente",
                height=90,
            )
            submitted = st.form_submit_button(
                "Salvar feedback",
                width="stretch",
            )

        if submitted:
            try:
                save_project_feedback(
                    client,
                    project_id=project_id,
                    feedback_date=feedback_date,
                    source_type=source_type,
                    process_stage=process_stage,
                    theme=theme,
                    sentiment=sentiment,
                    original_feedback=original_feedback,
                    internal_interpretation=internal_interpretation,
                    action_taken=action_taken,
                )
            except Exception as exc:
                st.error(f"Não foi possível salvar o feedback: {exc}")
            else:
                st.success("Feedback registrado.")
                st.rerun()

    entries = snapshot.get("feedback_entries", [])
    st.markdown("#### Histórico de feedbacks")

    if entries:
        for row in entries:
            title = (
                f"{_format_date(row.get('feedback_date'))} · "
                f"{str(row.get('theme') or 'outro').replace('_', ' ').title()}"
            )
            with st.expander(title):
                st.write(row.get("original_feedback"))
                if row.get("internal_interpretation"):
                    st.markdown(
                        f"**Interpretação interna:** "
                        f"{row.get('internal_interpretation')}"
                    )
                if row.get("action_taken"):
                    st.markdown(
                        f"**Ação decorrente:** {row.get('action_taken')}"
                    )
    else:
        st.caption("Nenhum feedback em texto foi registrado.")

    st.markdown("#### Arquivos de feedback e aprovação")
    files = [
        *_role_rows(snapshot, "feedback"),
        *_role_rows(snapshot, "approval"),
    ]
    _render_file_list(
        client,
        rows=files,
        empty_message="Nenhum arquivo de feedback ou aprovação foi anexado.",
        allow_archive=True,
    )

    columns = st.columns(2)
    with columns[0]:
        _upload_box(
            client,
            project_id=project_id,
            role="feedback",
            title="Arquivo de feedback",
            accepted_types=[
                "pdf",
                "docx",
                "pptx",
                "txt",
                "md",
                "eml",
                "msg",
            ],
            key_suffix="feedback",
        )
    with columns[1]:
        _upload_box(
            client,
            project_id=project_id,
            role="approval",
            title="Arquivo de aprovação",
            accepted_types=["pdf", "docx", "pptx", "txt", "md", "eml"],
            key_suffix="approval",
        )


def _render_results(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    project = snapshot["project"]
    status = str(project.get("status") or "")
    outcome = snapshot.get("outcome") or {}

    title = (
        "Encerramento e aprendizados"
        if status == "perdido"
        else "Resultados e aprendizados"
    )
    intro = (
        "Motivos da perda, feedback final e aprendizados para próximas concorrências."
        if status == "perdido"
        else "Resultado comercial, execução, contexto e aprendizados do projeto."
    )
    _section_title(title, intro)
    render_report_analyses(snapshot)

    with st.expander("Ajustar informações manualmente", expanded=not bool(snapshot.get("report_analyses"))):
        with st.form(f"outcome_form_{project_id}"):
            process_type = st.selectbox(
                "Tipo de processo",
                [
                    "competition",
                    "direct",
                    "proactive",
                    "renewal",
                    "not_informed",
                ],
                index=max(
                    0,
                    [
                        "competition",
                        "direct",
                        "proactive",
                        "renewal",
                        "not_informed",
                    ].index(outcome.get("process_type"))
                    if outcome.get("process_type")
                    in {
                        "competition",
                        "direct",
                        "proactive",
                        "renewal",
                        "not_informed",
                    }
                    else 4,
                ),
                format_func=lambda value: {
                    "competition": "Concorrência",
                    "direct": "Projeto direto",
                    "proactive": "Proativo",
                    "renewal": "Renovação",
                    "not_informed": "Não informado",
                }[value],
            )

            commercial_result = st.selectbox(
                "Resultado comercial",
                [
                    "in_evaluation",
                    "won",
                    "lost",
                    "cancelled",
                    "suspended",
                    "no_return",
                    "not_applicable",
                    "not_informed",
                ],
                index=(
                    [
                        "in_evaluation",
                        "won",
                        "lost",
                        "cancelled",
                        "suspended",
                        "no_return",
                        "not_applicable",
                        "not_informed",
                    ].index(outcome.get("commercial_result"))
                    if outcome.get("commercial_result")
                    in {
                        "in_evaluation",
                        "won",
                        "lost",
                        "cancelled",
                        "suspended",
                        "no_return",
                        "not_applicable",
                        "not_informed",
                    }
                    else 0
                ),
                format_func=lambda value: {
                    "in_evaluation": "Em avaliação",
                    "won": "Ganho",
                    "lost": "Perdido",
                    "cancelled": "Cancelado",
                    "suspended": "Suspenso",
                    "no_return": "Sem retorno",
                    "not_applicable": "Não aplicável",
                    "not_informed": "Não informado",
                }[value],
            )

            proposal_result = st.selectbox(
                "Resultado da proposta",
                [
                    "fully_approved",
                    "partially_approved",
                    "not_approved",
                    "in_revision",
                    "no_feedback",
                    "not_informed",
                ],
                index=(
                    [
                        "fully_approved",
                        "partially_approved",
                        "not_approved",
                        "in_revision",
                        "no_feedback",
                        "not_informed",
                    ].index(outcome.get("proposal_result"))
                    if outcome.get("proposal_result")
                    in {
                        "fully_approved",
                        "partially_approved",
                        "not_approved",
                        "in_revision",
                        "no_feedback",
                        "not_informed",
                    }
                    else 5
                ),
                format_func=lambda value: {
                    "fully_approved": "Integralmente aprovada",
                    "partially_approved": "Parcialmente aprovada",
                    "not_approved": "Não aprovada",
                    "in_revision": "Em revisão",
                    "no_feedback": "Sem feedback",
                    "not_informed": "Não informado",
                }[value],
            )

            execution_result = st.selectbox(
                "Execução",
                [
                    "executed",
                    "partially_executed",
                    "not_executed",
                    "in_progress",
                    "not_applicable",
                    "not_informed",
                ],
                index=(
                    [
                        "executed",
                        "partially_executed",
                        "not_executed",
                        "in_progress",
                        "not_applicable",
                        "not_informed",
                    ].index(outcome.get("execution_result"))
                    if outcome.get("execution_result")
                    in {
                        "executed",
                        "partially_executed",
                        "not_executed",
                        "in_progress",
                        "not_applicable",
                        "not_informed",
                    }
                    else 5
                ),
                format_func=lambda value: {
                    "executed": "Executado",
                    "partially_executed": "Parcialmente executado",
                    "not_executed": "Não executado",
                    "in_progress": "Em andamento",
                    "not_applicable": "Não aplicável",
                    "not_informed": "Não informado",
                }[value],
            )

            date_columns = st.columns(2)
            with date_columns[0]:
                result_date = st.date_input(
                    "Data do resultado",
                    value=None,
                )
            with date_columns[1]:
                execution_date = st.date_input(
                    "Data da execução",
                    value=None,
                )

            contracting_client = st.text_input(
                "Cliente contratante",
                value=str(outcome.get("contracting_client") or ""),
            )
            partners_involved = st.text_input(
                "Parceiros envolvidos",
                value=str(outcome.get("partners_involved") or ""),
            )
            reasons_text = st.text_area(
                "Motivos e fatores do resultado",
                value="\n".join(outcome.get("result_reasons") or []),
                help="Use uma linha para cada motivo.",
                height=100,
            )
            result_context = st.text_area(
                "Contexto e aprendizados",
                value=str(outcome.get("result_context") or ""),
                height=130,
            )
            execution_notes = st.text_area(
                "Observações de execução",
                value=str(outcome.get("execution_notes") or ""),
                height=110,
            )
            budget_amount = st.number_input(
                "Budget registrado",
                min_value=0.0,
                value=float(outcome.get("budget_amount") or 0),
                step=1000.0,
            )
            confidence_level = st.selectbox(
                "Confiança da informação",
                [
                    "client_confirmed",
                    "voe_confirmed",
                    "inferred",
                    "incomplete",
                ],
                index=(
                    [
                        "client_confirmed",
                        "voe_confirmed",
                        "inferred",
                        "incomplete",
                    ].index(outcome.get("confidence_level"))
                    if outcome.get("confidence_level")
                    in {
                        "client_confirmed",
                        "voe_confirmed",
                        "inferred",
                        "incomplete",
                    }
                    else 3
                ),
                format_func=lambda value: {
                    "client_confirmed": "Confirmado pelo cliente",
                    "voe_confirmed": "Confirmado pela VOE",
                    "inferred": "Inferido",
                    "incomplete": "Incompleto",
                }[value],
            )
            information_source = st.selectbox(
                "Fonte",
                [
                    "client_feedback",
                    "voe_team",
                    "email",
                    "meeting",
                    "document",
                    "other",
                    "not_informed",
                ],
                index=(
                    [
                        "client_feedback",
                        "voe_team",
                        "email",
                        "meeting",
                        "document",
                        "other",
                        "not_informed",
                    ].index(outcome.get("information_source"))
                    if outcome.get("information_source")
                    in {
                        "client_feedback",
                        "voe_team",
                        "email",
                        "meeting",
                        "document",
                        "other",
                        "not_informed",
                    }
                    else 6
                ),
                format_func=lambda value: value.replace("_", " ").title(),
            )

            submitted = st.form_submit_button(
                "Salvar resultado",
                width="stretch",
            )
    if submitted:
        try:
            save_project_outcome(
                client,
                project_id=project_id,
                process_type=process_type,
                commercial_result=commercial_result,
                proposal_result=proposal_result,
                execution_result=execution_result,
                result_date=result_date,
                execution_date=execution_date,
                contracting_client=contracting_client,
                partners_involved=partners_involved,
                result_reasons=reasons_text.splitlines(),
                result_context=result_context,
                execution_notes=execution_notes,
                budget_amount=budget_amount or None,
                confidence_level=confidence_level,
                information_source=information_source,
            )
        except Exception as exc:
            st.error(f"Não foi possível salvar o resultado: {exc}")
        else:
            st.success("Resultado atualizado.")
            st.rerun()

    if status == "perdido":
        report_role = "closure_report"
        report_title = "Relatório de encerramento da concorrência"
    elif status == "executado":
        report_role = "post_execution_report"
        report_title = "Relatório pós-execução"
    else:
        report_role = "project_document"
        report_title = "Documento de fechamento"

    st.markdown(f"#### {report_title}")
    _render_file_list(
        client,
        rows=_role_rows(snapshot, report_role),
        empty_message=f"Nenhum {report_title.lower()} foi anexado.",
        allow_archive=True,
    )
    render_pending_report_actions(
        client,
        project_id=project_id,
        snapshot=snapshot,
        report_role=report_role,
    )

    _upload_box(
        client,
        project_id=project_id,
        role=report_role,
        title=report_title,
        accepted_types=[
            "pdf",
            "docx",
            "pptx",
            "xlsx",
            "xlsm",
            "xls",
            "csv",
            "txt",
            "md",
        ],
        key_suffix="results",
    )


def _render_documents(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Documentos",
        "Central de arquivos do projeto, independentemente da etapa ou do desfecho.",
    )

    current_files = [
        row
        for row in snapshot.get("project_files", [])
        if not row.get("is_archived")
    ]

    _render_file_list(
        client,
        rows=current_files,
        empty_message="Nenhum arquivo foi anexado à central do projeto.",
        allow_archive=True,
    )

    _upload_box(
        client,
        project_id=project_id,
        role="project_document",
        title="Documento do projeto",
        accepted_types=[
            "pdf",
            "docx",
            "pptx",
            "xlsx",
            "xlsm",
            "xls",
            "csv",
            "txt",
            "md",
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key_suffix="documents",
    )

    st.markdown("#### Registros estruturados existentes")

    structured_rows = []

    for row in snapshot.get("briefing_documents", []):
        structured_rows.append(
            {
                "Tipo": "Briefing estruturado",
                "Título": row.get("title") or row.get("file_name"),
                "Arquivo": row.get("file_name"),
                "Data": _format_datetime(row.get("created_at")),
            }
        )

    for row in snapshot.get("memory_documents", []):
        structured_rows.append(
            {
                "Tipo": "Apresentação analisada",
                "Título": row.get("title") or row.get("file_name"),
                "Arquivo": row.get("file_name"),
                "Data": _format_datetime(row.get("created_at")),
            }
        )

    for row in snapshot.get("cost_documents", []):
        structured_rows.append(
            {
                "Tipo": "Planilha estruturada",
                "Título": row.get("title") or row.get("file_name"),
                "Arquivo": row.get("file_name"),
                "Data": _format_datetime(row.get("created_at")),
            }
        )

    if structured_rows:
        st.dataframe(
            pd.DataFrame(structured_rows),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Nenhum registro estruturado foi encontrado.")


def render_project_workspace(
    client: Client,
    *,
    project_id: str,
) -> None:
    _inject_workspace_css()
    snapshot = fetch_project_workspace_snapshot(
        client,
        project_id=project_id,
    )
    project = snapshot.get("project") or {}

    if not project:
        st.error("O projeto selecionado não foi encontrado.")
        return

    _project_header(project)
    _status_selector(
        client,
        project=project,
        project_id=project_id,
    )

    nav_column, content_column = st.columns([0.24, 0.76], gap="large")

    with nav_column:
        st.markdown(
            '<div class="nave-workspace-nav-title">Navegação do projeto</div>',
            unsafe_allow_html=True,
        )
        selected_section = st.radio(
            "Navegação do projeto",
            PROJECT_SECTIONS,
            label_visibility="collapsed",
            key=f"project_section_{project_id}",
        )

    with content_column:
        if selected_section == "Visão geral":
            _render_overview(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Briefing original":
            _render_briefing(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Diagnóstico e recomendações":
            _render_recommendations(snapshot=snapshot)
        elif selected_section == "Estratégia e conceito":
            _render_strategy(
                client,
                project_id=project_id,
            )
        elif selected_section == "Cenografia e ativações":
            _render_scenography(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Brindes e press kits":
            _render_gifts(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Orçamento e aderência":
            _render_budget(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Fornecedores e referências":
            _render_suppliers(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Apresentações finais":
            _render_presentations(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Feedbacks e aprovações":
            _render_feedbacks(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Resultados e aprendizados":
            _render_results(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Documentos":
            _render_documents(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )


def _project_list_table(dataframe: pd.DataFrame):
    display_columns = [
        column
        for column in (
            "Projeto",
            "Cliente",
            "Evento",
            "Status",
            "Briefings",
            "Recomendações",
            "Apresentações",
            "Conteúdos",
            "Arquivos",
            "Próxima ação",
            "Última atualização",
        )
        if column in dataframe.columns
    ]

    return st.dataframe(
        dataframe[display_columns],
        hide_index=True,
        width="stretch",
        height=min(620, 95 + max(len(dataframe), 1) * 38),
        on_select="rerun",
        selection_mode="single-row",
        key="nave_projects_workspace_table",
    )


def render_projects_page(client: Client) -> None:
    _inject_workspace_css()

    selected_project_id = st.session_state.get(
        "nave_workspace_project_id"
    )

    if selected_project_id:
        if st.button(
            "← Voltar para todos os projetos",
            key="back_to_projects_workspace",
        ):
            st.session_state.pop("nave_workspace_project_id", None)
            st.rerun()

        render_project_workspace(
            client,
            project_id=str(selected_project_id),
        )
        return

    st.subheader("Projetos")
    st.caption(
        "Selecione um projeto para abrir seu workspace completo. "
        "Não é necessário entrar novamente em Memória, orçamento "
        "ou apresentação."
    )

    dataframe = fetch_projects_workspace(client)

    if dataframe.empty:
        st.info("Nenhum projeto foi encontrado.")
        return

    filters = st.columns([1.5, 1])
    with filters[0]:
        search = st.text_input(
            "Buscar projeto",
            placeholder="Projeto, cliente ou evento",
        )
    with filters[1]:
        status_values = sorted(
            value
            for value in dataframe["Status"].dropna().unique().tolist()
        )
        status_filter = st.selectbox(
            "Status",
            ["Todos", *status_values],
        )

    filtered = dataframe.copy()

    if search.strip():
        term = search.casefold().strip()
        mask = (
            filtered["Projeto"].astype(str).str.casefold().str.contains(
                term,
                regex=False,
            )
            | filtered["Cliente"].astype(str).str.casefold().str.contains(
                term,
                regex=False,
            )
            | filtered["Evento"].astype(str).str.casefold().str.contains(
                term,
                regex=False,
            )
        )
        filtered = filtered[mask]

    if status_filter != "Todos":
        filtered = filtered[filtered["Status"] == status_filter]

    if filtered.empty:
        st.warning("Nenhum projeto corresponde aos filtros.")
        return

    event = _project_list_table(filtered.reset_index(drop=True))

    selected_rows = []
    try:
        selected_rows = list(event.selection.rows)
    except Exception:
        selected_rows = []

    if selected_rows:
        selected_index = int(selected_rows[0])
        selected_row = filtered.reset_index(drop=True).iloc[selected_index]
        st.session_state["nave_workspace_project_id"] = str(
            selected_row["project_id"]
        )
        st.rerun()
