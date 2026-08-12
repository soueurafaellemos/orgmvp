from __future__ import annotations

from datetime import date
from html import escape
import re
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from supabase import Client

from project_workspace_db import (
    FILE_ROLE_LABELS,
    archive_project_file,
    create_project_file_signed_url,
    create_storage_signed_url,
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
from project_workspace_intelligence import (
    build_project_intelligence,
    cost_document_kind,
    project_stage,
    proposal_cost_items,
    render_project_intelligence,
)
from project_intelligence_unified import build_unified_project_snapshot
from project_intelligence_report import build_project_intelligence_pdf



_INTERNAL_NOTE_RE = re.compile(r"\[NAVE-V[^\]]+\]\s*[^\n:]+:\s*(?:documento anexado)?", re.IGNORECASE)

def _clean_user_note(value: Any) -> str:
    """Remove marcadores internos de provenance de campos editáveis do usuário."""
    text = str(value or "")
    text = _INTERNAL_NOTE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

def _trusted_outcome_default(outcome: dict[str, Any], field: str, allowed: set[str], fallback: str) -> str:
    value = str(outcome.get(field) or "")
    confidence = str(outcome.get("confidence_level") or "")
    source = str(outcome.get("information_source") or "")
    # Resultado comercial/proposta só deve aparecer pré-confirmado quando há uma
    # fonte decisória confiável. Um relatório anexado ou estado legado não basta.
    trusted = confidence in {"client_confirmed", "voe_confirmed"} or source in {"client_feedback", "email", "meeting"}
    return value if trusted and value in allowed else fallback

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

BUSINESS_STATE_OPTIONS = [
    "proposal",
    "won",
    "lost",
    "no_return",
    "production",
    "executed",
    "cancelled",
]
BUSINESS_STATE_LABELS = {
    "proposal": "Em proposta / concorrência",
    "won": "Ganhou / aprovada",
    "lost": "Perdeu / proposta não aprovada",
    "no_return": "Sem resposta",
    "production": "Em produção",
    "executed": "Executada",
    "cancelled": "Cancelada",
}
PROCESS_TYPE_OPTIONS = ["competition", "direct", "proactive", "renewal"]
PROCESS_TYPE_LABELS = {
    "competition": "Concorrência",
    "direct": "Projeto direto",
    "proactive": "Proativo",
    "renewal": "Renovação",
}
BUSINESS_TO_PROJECT_STATUS = {
    "proposal": "apresentado",
    "won": "aprovado_ganho",
    "lost": "perdido",
    "no_return": "apresentado",
    "production": "em_producao",
    "executed": "executado",
    "cancelled": "cancelado",
}

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


def _optional_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _business_state(project: dict[str, Any], outcome: dict[str, Any]) -> str:
    execution = str(outcome.get("execution_result") or "")
    commercial = str(outcome.get("commercial_result") or "")
    status = str(project.get("status") or "")
    client_decision = (
        str(outcome.get("information_source") or "") == "client_feedback"
        and str(outcome.get("confidence_level") or "") == "client_confirmed"
    )
    if client_decision and commercial == "lost":
        return "lost"
    if client_decision and commercial == "cancelled":
        return "cancelled"
    if execution in {"executed", "partially_executed"} or status == "executado":
        return "executed"
    if execution == "in_progress" or status == "em_producao":
        return "production"
    if commercial == "lost" or status == "perdido":
        return "lost"
    if commercial == "cancelled" or status == "cancelado":
        return "cancelled"
    if commercial == "no_return":
        return "no_return"
    if commercial == "won" or status == "aprovado_ganho":
        return "won"
    return "proposal"


def _project_header(
    project: dict[str, Any],
    outcome: dict[str, Any] | None = None,
    unified: dict[str, Any] | None = None,
) -> None:
    title = project.get("project_name") or "Projeto sem nome"
    client = project.get("client_brand") or "Cliente não informado"
    event = project.get("event_name") or "Evento não informado"
    business_state = _business_state(project, outcome or {})
    status = BUSINESS_STATE_LABELS.get(business_state, "Não informado")
    truth = (unified or {}).get("project_truth") if isinstance(unified, dict) else {}
    if isinstance(truth, dict) and truth.get("stage_label"):
        status = str(truth.get("stage_label"))
    process_type = str((outcome or {}).get("process_type") or "")
    if business_state == "lost" and process_type == "competition":
        status = "Concorrência perdida / proposta não aprovada"
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
    outcome: dict[str, Any] | None = None,
) -> None:
    outcome = outcome or {}
    current_state = _business_state(project, outcome)
    process_type = str(outcome.get("process_type") or "competition")
    if process_type not in PROCESS_TYPE_OPTIONS:
        process_type = "competition"

    with st.form(f"business_state_{project_id}"):
        columns = st.columns([1.15, 1, 0.55], vertical_alignment="bottom")
        with columns[0]:
            selected_state = st.selectbox(
                "Situação do projeto",
                BUSINESS_STATE_OPTIONS,
                index=BUSINESS_STATE_OPTIONS.index(current_state),
                format_func=lambda value: BUSINESS_STATE_LABELS[value],
            )
        with columns[1]:
            selected_process = st.selectbox(
                "Tipo de processo",
                PROCESS_TYPE_OPTIONS,
                index=PROCESS_TYPE_OPTIONS.index(process_type),
                format_func=lambda value: PROCESS_TYPE_LABELS[value],
            )
        with columns[2]:
            submitted = st.form_submit_button("Atualizar", width="stretch")

    if submitted:
        mappings = {
            "proposal": ("in_evaluation", outcome.get("proposal_result") or "not_informed", "not_informed"),
            "won": ("won", "fully_approved", outcome.get("execution_result") or "not_informed"),
            "lost": ("lost", "not_approved", "not_applicable"),
            "no_return": ("no_return", "no_feedback", "not_applicable"),
            "production": ("won", "fully_approved", "in_progress"),
            "executed": ("won", "fully_approved", "executed"),
            "cancelled": ("cancelled", outcome.get("proposal_result") or "not_informed", "not_applicable"),
        }
        commercial_result, proposal_result, execution_result = mappings[selected_state]
        try:
            save_project_outcome(
                client,
                project_id=project_id,
                process_type=selected_process,
                commercial_result=str(commercial_result),
                proposal_result=str(proposal_result),
                execution_result=str(execution_result),
                result_date=_optional_date(outcome.get("result_date")),
                execution_date=_optional_date(outcome.get("execution_date")),
                contracting_client=outcome.get("contracting_client"),
                partners_involved=outcome.get("partners_involved"),
                result_reasons=list(outcome.get("result_reasons") or []),
                result_context=outcome.get("result_context"),
                execution_notes=outcome.get("execution_notes"),
                budget_amount=(float(outcome.get("budget_amount")) if outcome.get("budget_amount") not in (None, "") else None),
                confidence_level="voe_confirmed",
                information_source="voe_team",
            )
            update_project_workspace_data(
                client,
                project_id=project_id,
                status=BUSINESS_TO_PROJECT_STATUS[selected_state],
            )
        except Exception as exc:
            st.error(f"Não foi possível atualizar a situação do projeto: {exc}")
        else:
            st.success("Situação do projeto atualizada.")
            st.rerun()

    workspace = _workspace_raw(project)
    with st.expander("Próxima ação e observações"):
        with st.form(f"workspace_meta_{project_id}"):
            next_action = st.text_input(
                "Próxima ação",
                value=str(workspace.get("next_action") or ""),
                placeholder="Ex.: aguardar retorno do cliente sobre a proposta",
            )
            notes = st.text_area(
                "Observações operacionais",
                value=str(workspace.get("notes") or ""),
                height=90,
            )
            meta_submitted = st.form_submit_button("Salvar observações", width="stretch")
        if meta_submitted:
            update_project_workspace_data(
                client,
                project_id=project_id,
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


def _semantic_document_role(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return str(metadata.get("document_role") or "")


def _presentation_file_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in snapshot.get("project_files", []):
        if row.get("is_archived"):
            continue
        file_role = str(row.get("file_role") or "")
        semantic_role = _semantic_document_role(row)
        if file_role == "final_presentation" or semantic_role in {"proposal_presentation", "final_presentation"}:
            rows.append(row)
    return rows


def _count_structured_or_files(structured_rows: list[Any], file_rows: list[Any]) -> int:
    """Evita contar o mesmo original duas vezes após a materialização."""
    return max(len(structured_rows), len(file_rows))


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
            storage_bucket=row.get("storage_bucket"),
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
        pending.append("Adicionar a apresentação / proposta.")

    status = str(project.get("status") or "")
    outcome = snapshot.get("outcome") or {}
    business_state = _business_state(project, outcome)

    if business_state in {"won", "lost", "production", "executed"} and not has_feedback:
        pending.append("Registrar feedback ou decisão do cliente.")

    if business_state == "lost" and not _has_role(
        snapshot,
        "closure_report",
    ):
        pending.append("Adicionar o relatório de encerramento da concorrência.")

    if business_state == "executed" and not _has_role(
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
        "Situação comercial, leitura do material recebido, aderência financeira e próximos passos.",
    )

    metrics = st.columns(5)
    metrics[0].metric(
        "Briefings",
        _count_structured_or_files(
            list(snapshot.get("briefing_documents", [])),
            _role_rows(snapshot, "briefing_original"),
        ),
    )
    metrics[1].metric(
        "Apresentações",
        _count_structured_or_files(
            list(snapshot.get("memory_documents", [])),
            _presentation_file_rows(snapshot),
        ),
    )
    metrics[2].metric(
        "Conteúdos",
        len(snapshot.get("memory_items", [])),
    )
    feedback_files = _role_rows(snapshot, "feedback") + _role_rows(snapshot, "approval")
    metrics[3].metric(
        "Feedbacks",
        len(feedback_files) if feedback_files else len(snapshot.get("feedback_entries", [])),
        help="Conta fontes de feedback. Uma única fonte pode gerar vários claims estruturados sem ser contada várias vezes.",
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

    intelligence = build_project_intelligence(snapshot)
    intel_metrics = intelligence.get("metrics") or {}
    unified_financial = ((intelligence.get("unified") or {}).get("financial_context") or {})
    overview_direct_payment = bool(unified_financial.get("direct_payment_signal"))
    st.markdown("#### Leitura atual do projeto")
    stage_label = intel_metrics.get("stage_label") or "Em proposta / concorrência"
    st.info(
        f"**{stage_label}.** A leitura atual considera briefing, proposta e custos. "
        + (
            "Ainda não é esperado haver evidência de execução neste momento."
            if intel_metrics.get("stage") in {"proposal", "no_return", "won"}
            else "Resultados de execução entram somente quando houver fonte que os comprove."
        )
    )

    budget_amount = intel_metrics.get("budget_amount")
    cost_total = intel_metrics.get("cost_total")
    budget_delta = intel_metrics.get("budget_delta")
    usage = intel_metrics.get("budget_usage_pct")
    if budget_delta is not None:
        delta_number = float(budget_delta)
        if delta_number < 0 and overview_direct_payment:
            delta_title = "Diferença bruta a reconciliar"
        else:
            delta_title = "Folga no budget" if delta_number >= 0 else "Acima do teto"
        delta_value = _format_money(abs(delta_number))
        delta_detail = (
            ("Responsabilidades de pagamento pendentes" if delta_number < 0 and overview_direct_payment else f"{abs(delta_number) / float(budget_amount):.2%} do budget")
            if budget_amount not in (None, 0, "") else ""
        )
    else:
        delta_title, delta_value, delta_detail = "Diferença", "—", "Sem base comparável"
    st.markdown(
        f"""
        <style>
        .nave-overview-fin {{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:.45rem 0 1rem;}}
        .nave-overview-fin-card {{background:#F7F9FC;border:1px solid #E1E6EF;border-radius:14px;padding:14px 15px;min-width:0;}}
        .nave-overview-fin-label {{font-size:.72rem;color:#667188;font-weight:700;margin-bottom:5px;}}
        .nave-overview-fin-value {{font-size:1.24rem;line-height:1.18;color:#121B42;font-weight:850;overflow-wrap:anywhere;}}
        .nave-overview-fin-detail {{font-size:.72rem;color:#778198;margin-top:5px;}}
        @media (max-width:900px) {{.nave-overview-fin {{grid-template-columns:repeat(2,minmax(0,1fr));}}}}
        </style>
        <div class="nave-overview-fin">
          <div class="nave-overview-fin-card"><div class="nave-overview-fin-label">Budget do briefing</div><div class="nave-overview-fin-value">{escape(_format_money(budget_amount) if budget_amount is not None else '—')}</div><div class="nave-overview-fin-detail">Teto / referência comprovada</div></div>
          <div class="nave-overview-fin-card"><div class="nave-overview-fin-label">Total da proposta</div><div class="nave-overview-fin-value">{escape(_format_money(cost_total) if cost_total is not None else '—')}</div><div class="nave-overview-fin-detail">Valor orçado, não gasto real</div></div>
          <div class="nave-overview-fin-card"><div class="nave-overview-fin-label">{escape(delta_title)}</div><div class="nave-overview-fin-value">{escape(delta_value)}</div><div class="nave-overview-fin-detail">{escape(delta_detail)}</div></div>
          <div class="nave-overview-fin-card"><div class="nave-overview-fin-label">Uso do budget</div><div class="nave-overview-fin-value">{escape(f'{usage:.1%}' if usage is not None else '—')}</div><div class="nave-overview-fin-detail">Proposta ÷ budget</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    semantic = intel_metrics.get("semantic_synthesis") if isinstance(intel_metrics.get("semantic_synthesis"), dict) else None
    if semantic:
        st.markdown("#### O que a NAVE entendeu")
        st.info(str(semantic.get("executive_summary") or ""))
        connections = [
            row for row in (semantic.get("strongest_connections") or [])
            if isinstance(row, dict) and row.get("analysis")
        ]
        gaps = [
            row for row in (semantic.get("contradictions_or_gaps") or [])
            if isinstance(row, dict) and row.get("analysis")
        ]
        if connections or gaps:
            cols = st.columns(2, gap="large")
            with cols[0]:
                st.markdown("**Conexões mais relevantes**")
                for row in connections[:3]:
                    st.success(f"**{row.get('title') or 'Conexão'}**\n\n{row.get('analysis')}")
            with cols[1]:
                st.markdown("**Riscos / contradições**")
                for row in gaps[:3]:
                    st.warning(f"**{row.get('title') or 'Ponto de atenção'}**\n\n{row.get('analysis')}")

    context_notes: list[str] = []
    observations: list[str] = []
    if snapshot.get("cost_documents") and intel_metrics.get("cost_total") is None:
        observations.append("A planilha de custos está anexada, mas ainda não há total financeiro utilizável na leitura estruturada.")
    preliminary_total = intel_metrics.get("preliminary_budget_total")
    if preliminary_total is not None:
        context_notes.append(
            f"Estudo preliminar de verba: {_format_money(preliminary_total)}. É referência de alocação e não é somado novamente à proposta detalhada."
        )
    additional_cost_sheets = intel_metrics.get("additional_cost_sheets") or []
    if additional_cost_sheets:
        readable = ", ".join(
            f"{row.get('sheet_name') or 'Aba adicional'} ({_format_money(row.get('client_total'))})"
            for row in additional_cost_sheets[:3]
        )
        context_notes.append(
            f"Escopo(s) financeiro(s) apartado(s) do total principal: {readable}."
        )
    if intel_metrics.get("budget_delta") is not None and float(intel_metrics.get("budget_delta")) < 0:
        if overview_direct_payment:
            observations.append(
                f"O total bruto supera o budget nominal em {_format_money(abs(float(intel_metrics.get('budget_delta'))))}, mas há indicação de pagamento direto pelo cliente; a diferença precisa ser reconciliada antes de classificar aderência financeira."
            )
        else:
            observations.append(
                f"A proposta detalhada excede o budget em {_format_money(abs(float(intel_metrics.get('budget_delta'))))}."
            )
    if intel_metrics.get("presentation_items", 0) == 0 and snapshot.get("memory_documents"):
        observations.append("A apresentação está preservada, mas a decupagem semântica ainda não gerou entregas confiáveis.")
    if intel_metrics.get("briefing_gaps", 0):
        observations.append(f"Há {intel_metrics.get('briefing_gaps')} demanda(s) do briefing ainda sem correspondência consolidada na proposta.")
    if intel_metrics.get("cost_only_items", 0):
        observations.append(f"Há {intel_metrics.get('cost_only_items')} linha(s) de custo ainda sem correspondência direta com uma entrega apresentada.")
    for note in context_notes[:2]:
        st.info(note)
    if observations:
        for observation in observations[:4]:
            st.warning(observation)

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

    business_state = _business_state(project, snapshot.get("outcome") or {})
    report_role = (
        "post_execution_report"
        if business_state == "executed"
        else "closure_report"
        if business_state == "lost"
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
            "Apresentação / proposta",
            "Versão apresentada ao cliente e suas evoluções.",
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
    ]
    if report_role:
        cards.append((
            "Fechamento",
            report_title,
            "Documento de encerramento, resultado ou pós-execução.",
            _has_role(snapshot, report_role),
        ))

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

    if len(cards) > 3:
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

    st.markdown("#### Arquivos principais")

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
                "jpg",
                "jpeg",
                "png",
                "webp",
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
    if generic:
        _render_file_list(
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
        view = pd.DataFrame()
        if "title" in structured_df.columns:
            view["Briefing"] = structured_df["title"].fillna(structured_df.get("file_name"))
        elif "file_name" in structured_df.columns:
            view["Briefing"] = structured_df["file_name"]
        if "requirements_count" in structured_df.columns:
            view["Demandas"] = structured_df["requirements_count"]
        if "budget_amount" in structured_df.columns:
            view["Budget"] = pd.to_numeric(structured_df["budget_amount"], errors="coerce")
        st.dataframe(
            view,
            hide_index=True,
            width="stretch",
            column_config={
                "Budget": st.column_config.NumberColumn("Budget", format="R$ %.2f"),
            },
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
        type_labels = {
            "objective": "Objetivo", "deliverable": "Entregável", "mandatory": "Obrigatoriedade",
            "restriction": "Restrição", "audience": "Público", "logistics": "Logística",
            "budget": "Budget", "kpi": "KPI", "operation": "Operação",
            "communication": "Comunicação", "desirable": "Desejável", "context": "Contexto",
        }
        priority_labels = {
            "critical": "Crítica", "high": "Alta", "medium": "Média", "low": "Baixa", "not_informed": "",
        }
        adherence_labels = {
            "not_assessed": "Não avaliada", "fulfilled": "Cumprida", "partially_fulfilled": "Parcial",
            "not_fulfilled": "Não cumprida", "exceeded": "Superada", "changed_justified": "Alterada",
            "removed_budget": "Retirada por budget", "removed_timeline": "Retirada por prazo",
            "not_applicable": "Não aplicável", "unproven": "Não comprovada",
        }
        view = pd.DataFrame({
            "Tipo": req_df.get("requirement_type", pd.Series(dtype=str)).map(type_labels).fillna(req_df.get("requirement_type", "")),
            "Demanda": req_df.get("title", ""),
            "Prioridade": req_df.get("priority", pd.Series(dtype=str)).map(priority_labels).fillna(""),
            "Obrigatória": req_df.get("mandatory", False),
            "Aderência": req_df.get("adherence_status", pd.Series(dtype=str)).map(adherence_labels).fillna(""),
        })
        st.dataframe(view, hide_index=True, width="stretch")
    else:
        st.caption(
            "As demandas aparecerão aqui após a análise estruturada do briefing."
        )


def _render_recommendations(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    render_project_intelligence(
        client,
        project_id=project_id,
        snapshot=snapshot,
    )


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


def _evidence_page_visual(snapshot: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    source_name = str(row.get("source_name") or "").strip().casefold()
    locator = str(row.get("locator_text") or "").strip().casefold()
    match = re.search(r"(?:page|slide|pagina|página)\s*(\d+)", locator)
    if not match:
        return None
    page_number = int(match.group(1))
    docs = snapshot.get("memory_documents") or []
    doc_ids: set[str] = set()
    for doc in docs:
        names = {
            str(doc.get("file_name") or "").strip().casefold(),
            str(doc.get("title") or "").strip().casefold(),
            str(doc.get("source_file") or "").strip().casefold(),
        }
        names.discard("")
        if not source_name or any(name == source_name or name in source_name or source_name in name for name in names):
            if doc.get("id"):
                doc_ids.add(str(doc.get("id")))
    for page in snapshot.get("memory_pages") or []:
        if int(page.get("page_number") or 0) != page_number:
            continue
        if doc_ids and str(page.get("document_id") or "") not in doc_ids:
            continue
        if page.get("storage_path"):
            return dict(page)
    return None


def _render_unified_evidence_cards(
    client: Client,
    snapshot: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    intro: str,
    limit: int = 10,
) -> None:
    """Projeta evidência ainda não consolidada sem expor provenance como produto final.

    Quando uma página visual já está preservada, a interface mostra a imagem e usa
    arquivo/página apenas como fonte discreta. Sem visual disponível, mantém um
    expander textual auditável.
    """
    if not rows:
        return
    st.info(intro)
    for row in rows[:limit]:
        source = str(row.get("source_name") or "Fonte")
        locator = str(row.get("locator_text") or "").strip()
        visual = _evidence_page_visual(snapshot, row)
        text = str(row.get("text") or "Evidência sem texto extraído.")
        if visual:
            with st.container(border=True):
                image_url = create_storage_signed_url(
                    client,
                    bucket_name=visual.get("storage_bucket"),
                    storage_path=visual.get("storage_path"),
                )
                if image_url:
                    image_col, text_col = st.columns([0.42, 0.58], gap="large", vertical_alignment="center")
                    with image_col:
                        st.image(image_url, width="stretch")
                    with text_col:
                        st.markdown(f"**{str(visual.get('slide_title') or row.get('domain') or 'Evidência visual').strip()}**")
                        st.write(text)
                        st.caption(source + (f" · {locator}" if locator else ""))
                else:
                    st.write(text)
                    st.caption(source + (f" · {locator}" if locator else ""))
        else:
            title = source + (f" · {locator}" if locator else "")
            with st.expander(title, expanded=False):
                st.write(text)
                confidence = row.get("confidence")
                if confidence not in (None, ""):
                    try:
                        st.caption(f"Confiança de extração: {float(confidence):.0%}")
                    except Exception:
                        pass


def _render_strategy(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Estratégia e conceito",
        "Direcionais estratégicos, conceitos criativos e racional do projeto.",
    )
    strategy_rows = [
        row for row in snapshot.get("memory_items", [])
        if str(row.get("section_key") or "") == "strategy"
    ]
    unified = snapshot.get("unified_intelligence") or build_unified_project_snapshot(snapshot)
    evidence = (unified.get("domain_evidence") or {}).get("strategy") or []
    semantic_snapshots = snapshot.get("intelligence_snapshots") or []
    semantic = None
    for stored in semantic_snapshots:
        metrics = stored.get("metrics") if isinstance(stored.get("metrics"), dict) else {}
        candidate = metrics.get("semantic_synthesis")
        if isinstance(candidate, dict) and (candidate.get("strategic_reading") or candidate.get("strategy_framework")):
            semantic = candidate
            break

    framework = (semantic or {}).get("strategy_framework") if isinstance((semantic or {}).get("strategy_framework"), dict) else {}
    if semantic and (semantic.get("strategic_reading") or framework):
        st.markdown("#### Leitura estratégica consolidada")
        if semantic.get("strategic_reading"):
            st.info(str(semantic.get("strategic_reading")))
        if framework:
            fields = [
                ("Território", framework.get("territory")),
                ("Tensão", framework.get("tension")),
                ("Direção estratégica", framework.get("strategic_direction")),
                ("Conceito / POV", framework.get("concept")),
                ("Papel da experiência", framework.get("experience_role")),
                ("Aderência ao briefing", framework.get("briefing_adherence")),
            ]
            for label, value in fields:
                if value:
                    st.markdown(f"**{label}**  \n{value}")
            pillars = [str(v).strip() for v in framework.get("pillars") or [] if str(v).strip()]
            if pillars:
                st.markdown("**Pilares**  \n" + " · ".join(pillars))

    if strategy_rows:
        with st.expander("Evidências e conteúdos estratégicos da apresentação", expanded=not bool(semantic)):
            _render_memory_cards(
                client,
                project_id=project_id,
                section_keys=["strategy"],
                empty_message="",
            )
    elif evidence:
        st.markdown("#### Evidências estratégicas encontradas nas fontes")
        _render_unified_evidence_cards(
            client, snapshot, evidence,
            intro=(
                "A NAVE encontrou evidências estratégicas no Intelligence Graph. "
                "Elas ficam visíveis como fonte enquanto as fichas canônicas são consolidadas."
            ),
            limit=12,
        )
    elif not semantic:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma evidência de estratégia ou conceito foi encontrada nas fontes atuais.</div>',
            unsafe_allow_html=True,
        )


def _render_scenography(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    _section_title(
        "Cenografia e ativações",
        "Ambientes, ativações, experiências, conteúdo artístico, comunicação, jornada e operação.",
    )

    st.markdown("#### Cenografia e ambientes")
    scenography_rows = [
        row for row in snapshot.get("memory_items", [])
        if str(row.get("section_key") or "") == "scenography"
    ]
    unified = snapshot.get("unified_intelligence") or build_unified_project_snapshot(snapshot)
    scenography_evidence = (unified.get("domain_evidence") or {}).get("scenography") or []
    if scenography_rows:
        render_visual_section(
            client,
            project_id=project_id,
            snapshot=snapshot,
            section_keys=["scenography"],
            empty_message="Nenhum ambiente ou solução cenográfica foi identificado.",
        )
    elif scenography_evidence:
        _render_unified_evidence_cards(
            client, snapshot, scenography_evidence,
            intro=(
                "A NAVE encontrou evidências de cenografia/ambientes nas fontes, embora ainda não existam fichas legadas consolidadas. "
                "O conteúdo abaixo impede um falso vazio enquanto a materialização é aprimorada."
            ),
            limit=10,
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma evidência de ambiente ou solução cenográfica foi encontrada.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("#### Ativações e experiências")
    activation_rows = [
        row for row in snapshot.get("memory_items", [])
        if str(row.get("section_key") or "") == "activations"
    ]
    activation_evidence = (unified.get("domain_evidence") or {}).get("activations") or []
    if activation_rows:
        render_visual_section(
            client,
            project_id=project_id,
            snapshot=snapshot,
            section_keys=["activations"],
            empty_message="",
        )
        # Quando a extração legada condensou várias mecânicas em uma única ficha,
        # mantemos as páginas visuais complementares disponíveis. Isso evita que
        # uma apresentação rica vire um card textual genérico.
        if len(activation_evidence) > max(2, len(activation_rows) * 2):
            with st.expander("Outras evidências visuais de ativações", expanded=False):
                _render_unified_evidence_cards(
                    client, snapshot, activation_evidence,
                    intro=(
                        "A apresentação contém outras evidências relacionadas a ativações que ainda não foram separadas em fichas canônicas."
                    ),
                    limit=12,
                )
    elif activation_evidence:
        _render_unified_evidence_cards(
            client, snapshot, activation_evidence,
            intro=(
                "A NAVE encontrou ativações/experiências nas fontes. As evidências visuais ficam disponíveis enquanto as fichas canônicas são consolidadas."
            ),
            limit=12,
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma evidência de ativação ou experiência foi encontrada nas fontes atuais.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("#### Conteúdo, artístico e programação")
    _render_memory_cards(
        client,
        project_id=project_id,
        section_keys=["content_agenda"],
        empty_message="Nenhum conteúdo artístico, palestrante ou programação foi estruturado.",
    )

    st.markdown("#### Comunicação e materiais")
    communication_rows = [
        row for row in snapshot.get("memory_items", [])
        if str(row.get("section_key") or "") == "communication"
    ]
    communication_evidence = (unified.get("domain_evidence") or {}).get("communication") or []
    if communication_rows:
        _render_memory_cards(
            client, project_id=project_id, section_keys=["communication"], empty_message=""
        )
    elif communication_evidence:
        _render_unified_evidence_cards(
            client, snapshot, communication_evidence,
            intro="A NAVE encontrou evidências de comunicação e materiais nas fontes atuais.",
            limit=8,
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma evidência de comunicação ou material foi encontrada nas fontes atuais.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("#### Jornada e operação")
    journey_rows = [
        row for row in snapshot.get("memory_items", [])
        if str(row.get("section_key") or "") == "journey_operation"
    ]
    journey_evidence = (unified.get("domain_evidence") or {}).get("journey_operation") or []
    if journey_rows:
        _render_memory_cards(
            client, project_id=project_id, section_keys=["journey_operation"], empty_message=""
        )
    elif journey_evidence:
        _render_unified_evidence_cards(
            client, snapshot, journey_evidence,
            intro="A NAVE encontrou evidências de jornada/operação nas fontes atuais.",
            limit=8,
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma evidência de jornada ou operação foi encontrada nas fontes atuais.</div>',
            unsafe_allow_html=True,
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

    gift_rows = [
        row for row in snapshot.get("memory_items", [])
        if str(row.get("section_key") or "") == "gifts"
    ]
    unified = snapshot.get("unified_intelligence") or build_unified_project_snapshot(snapshot)
    gift_evidence = (unified.get("domain_evidence") or {}).get("gifts") or []
    if gift_rows:
        render_visual_section(
            client,
            project_id=project_id,
            snapshot=snapshot,
            section_keys=["gifts"],
            empty_message="Nenhum brinde, press kit ou material visual foi identificado.",
        )
        if len(gift_evidence) > max(2, len(gift_rows) * 2):
            with st.expander("Outras evidências visuais de brindes e press kits", expanded=False):
                _render_unified_evidence_cards(
                    client, snapshot, gift_evidence,
                    intro="Há outras evidências visuais de brindes/press kits ainda não consolidadas em fichas canônicas.",
                    limit=10,
                )
    elif gift_evidence:
        _render_unified_evidence_cards(
            client, snapshot, gift_evidence,
            intro=(
                "A NAVE encontrou evidências visuais de brindes/press kits, mas as fichas canônicas ainda não foram consolidadas. "
                "As fontes abaixo permanecem visíveis para evitar falso vazio."
            ),
            limit=12,
        )
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma evidência de brinde, press kit ou material visual foi encontrada nas fontes atuais.</div>',
            unsafe_allow_html=True,
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
        "Budget do briefing, estudo preliminar de verba, proposta detalhada e leitura financeira sem duplicar fontes.",
    )

    intelligence = build_project_intelligence(snapshot)
    financial = intelligence.get("metrics") or {}
    budget_amount = financial.get("budget_amount")
    proposal_total = financial.get("cost_total")
    preliminary_total = financial.get("preliminary_budget_total")
    delta = financial.get("budget_delta")
    usage = financial.get("budget_usage_pct")
    additional_cost_sheets = financial.get("additional_cost_sheets") or []

    advanced = intelligence.get("advanced_insights") or {}
    cost_per_attendee = advanced.get("cost_per_attendee")
    audience_quantity = advanced.get("audience_quantity")
    audience_scope = advanced.get("audience_scope")
    graph_units = ((snapshot.get("intelligence_graph") or {}).get("evidence_units") or []) if isinstance(snapshot.get("intelligence_graph"), dict) else []
    direct_payment_signal = any(
        "pagamento direto" in str(row.get("content_text") or "").casefold()
        or "forma direta" in str(row.get("content_text") or "").casefold()
        for row in graph_units
    )
    overage = (-float(delta)) if delta is not None and float(delta) < 0 else None
    headroom = float(delta) if delta is not None and float(delta) >= 0 else None
    if overage is not None and direct_payment_signal:
        delta_label = "Diferença bruta a reconciliar"
    else:
        delta_label = "Acima do teto" if overage is not None else "Folga no budget" if headroom is not None else "Diferença"
    delta_value = _format_money(overage if overage is not None else headroom) if delta is not None else "—"
    delta_detail = (
        f"+{(overage / float(budget_amount)):.2%}"
        if overage is not None and budget_amount
        else f"{(headroom / float(budget_amount)):.2%} disponível"
        if headroom is not None and budget_amount
        else "Sem base comparável"
    )
    budget_value = _format_money(budget_amount) if budget_amount is not None else "—"
    proposal_value = _format_money(proposal_total) if proposal_total is not None else "—"
    usage_value = f"{usage:.1%}" if usage is not None else "—"
    attendee_value = _format_money(cost_per_attendee) if cost_per_attendee is not None else "—"
    if audience_scope == "festival_event" and audience_quantity:
        attendee_detail = f"{int(audience_quantity)} = público do evento; não usar como visitantes da ativação"
    elif audience_quantity:
        attendee_detail = f"Base comprovada: {int(audience_quantity)} pessoas"
    else:
        attendee_detail = "Não calculável com as fontes atuais"

    st.markdown(
        f"""
        <style>
        .nave-fin-grid {{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:.5rem 0 1rem 0;}}
        .nave-fin-card {{background:#F7F9FC;border:1px solid #E1E6EF;border-radius:14px;padding:14px 15px;min-width:0;}}
        .nave-fin-label {{font-size:.72rem;color:#667188;font-weight:700;margin-bottom:6px;}}
        .nave-fin-value {{font-size:1.30rem;line-height:1.18;color:#121B42;font-weight:850;overflow-wrap:anywhere;}}
        .nave-fin-detail {{font-size:.68rem;color:#7C879D;margin-top:5px;line-height:1.25;}}
        @media (max-width: 1100px) {{.nave-fin-grid {{grid-template-columns:repeat(2,minmax(0,1fr));}}}}
        </style>
        <div class="nave-fin-grid">
          <div class="nave-fin-card"><div class="nave-fin-label">Budget do briefing</div><div class="nave-fin-value">{budget_value}</div><div class="nave-fin-detail">Teto comprovado na fonte</div></div>
          <div class="nave-fin-card"><div class="nave-fin-label">Total da proposta</div><div class="nave-fin-value">{proposal_value}</div><div class="nave-fin-detail">Total final estruturado</div></div>
          <div class="nave-fin-card"><div class="nave-fin-label">{delta_label}</div><div class="nave-fin-value">{delta_value}</div><div class="nave-fin-detail">{delta_detail}</div></div>
          <div class="nave-fin-card"><div class="nave-fin-label">Uso do budget</div><div class="nave-fin-value">{usage_value}</div><div class="nave-fin-detail">Proposta ÷ budget</div></div>
          <div class="nave-fin-card"><div class="nave-fin-label">Custo por participante</div><div class="nave-fin-value">{attendee_value}</div><div class="nave-fin-detail">{attendee_detail}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if preliminary_total is not None:
        if budget_amount is not None and abs(float(preliminary_total) - float(budget_amount)) <= 0.01:
            st.info(
                f"**Estudo de verba:** {_format_money(preliminary_total)} · reconciliado com o budget do briefing. "
                "Ele é referência de alocação e não é somado novamente à proposta detalhada."
            )
        else:
            st.info(
                f"**Estudo de verba:** {_format_money(preliminary_total)} · tratado separadamente como referência de alocação, "
                "sem ser somado novamente à proposta detalhada."
            )

    if budget_amount is not None and proposal_total is not None:
        if delta is not None and delta >= 0:
            st.success(
                f"A proposta detalhada está {_format_money(delta)} abaixo do budget registrado no briefing."
            )
        else:
            over_pct = (abs(float(delta)) / float(budget_amount)) if delta is not None and budget_amount else None
            suffix = f" ({over_pct:.1%} na comparação bruta)" if over_pct is not None else ""
            if direct_payment_signal:
                st.warning(
                    f"O total bruto da planilha supera o budget nominal em {_format_money(abs(float(delta or 0)))}{suffix}, "
                    "mas o briefing contém indicação de pagamento direto pelo cliente. A NAVE não classifica esse valor como estouro definitivo até reconciliar responsabilidades financeiras."
                )
            else:
                st.warning(
                    f"A proposta detalhada está {_format_money(abs(float(delta or 0)))} acima do budget registrado no briefing{suffix}."
                )
    elif budget_amount is not None and snapshot.get("cost_documents"):
        st.warning(
            "O budget foi identificado, mas a proposta detalhada ainda não possui um total financeiro comprovado. "
            "A aderência não será inventada até a leitura conseguir provar os valores."
        )

    top_categories = advanced.get("top_categories") or []
    top_items = advanced.get("top_items") or []
    if top_categories or top_items:
        st.markdown("#### Leitura NAVE do orçamento")
        left_analysis, right_analysis = st.columns(2, gap="large")
        with left_analysis:
            st.markdown("**Onde o budget está concentrado**")
            if top_categories:
                category_rows = []
                for row in top_categories[:6]:
                    category_rows.append({
                        "Categoria": row.get("category") or "Sem categoria",
                        "Valor": float(row.get("value") or 0),
                        "% da proposta": float(row.get("share") or 0) if row.get("share") is not None else None,
                    })
                st.dataframe(
                    pd.DataFrame(category_rows), hide_index=True, width="stretch",
                    column_config={
                        "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
                        "% da proposta": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
                concentration = advanced.get("top4_category_share")
                if concentration is not None:
                    st.caption(f"As 4 maiores categorias concentram {float(concentration):.1%} do total.")
        with right_analysis:
            st.markdown("**Maiores itens individuais**")
            if top_items:
                top_rows = []
                for row in top_items[:6]:
                    share = (float(row.get("value") or 0) / float(proposal_total)) if proposal_total else None
                    top_rows.append({
                        "Item": row.get("name") or "Item",
                        "Categoria": row.get("category") or "Sem categoria",
                        "Valor": float(row.get("value") or 0),
                        "%": share,
                    })
                st.dataframe(
                    pd.DataFrame(top_rows), hide_index=True, width="stretch",
                    column_config={
                        "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
                        "%": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )

    if additional_cost_sheets:
        st.markdown("#### Escopos financeiros apartados")
        for row in additional_cost_sheets:
            label = row.get("sheet_name") or "Aba adicional"
            value = row.get("client_total")
            st.info(
                f"**{label}: {_format_money(value)}.** Este valor permanece fora do total principal até que o escopo seja confirmado como parte da proposta."
            )

    files = _role_rows(snapshot, "cost_sheet")
    cost_documents = snapshot.get("cost_documents", [])
    if files:
        _render_file_list(client, rows=files, empty_message="", allow_archive=True)
    elif cost_documents:
        st.caption("As planilhas foram incorporadas pela importação inteligente e estão preservadas no projeto.")
    else:
        st.markdown(
            '<div class="nave-workspace-empty">Nenhuma planilha foi anexada.</div>',
            unsafe_allow_html=True,
        )

    _upload_box(
        client,
        project_id=project_id,
        role="cost_sheet",
        title="Planilha de custos",
        accepted_types=["xlsx", "xlsm", "xls", "csv"],
        key_suffix="budget",
    )

    st.markdown("#### Planilhas já estruturadas pela NAVE")
    if cost_documents:
        structured_rows: list[dict[str, Any]] = []
        for document in cost_documents:
            kind = cost_document_kind(document)
            metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
            total = document.get("client_total")
            if total in (None, ""):
                total = document.get("budget_amount")
            structured_rows.append({
                "Arquivo": document.get("file_name") or document.get("title") or "Planilha",
                "Leitura": "Proposta detalhada" if kind == "detailed_costs" else "Estudo de verba",
                "Aba principal": document.get("sheet_name") or metadata.get("sheet_name") or "—",
                "Itens": document.get("items_count") if document.get("items_count") is not None else "—",
                "Total identificado": _format_money(total) if total not in (None, "") else "Não identificado",
                "Estruturada em": document.get("created_at") or "—",
            })
        st.dataframe(pd.DataFrame(structured_rows), hide_index=True, width="stretch")
    else:
        st.caption("Nenhuma planilha estruturada foi encontrada.")

    proposal_items = proposal_cost_items(snapshot)
    st.markdown("#### Proposta detalhada — linhas de custo")
    if proposal_items:
        df = pd.DataFrame(proposal_items)
        status_labels = {
            "included": "Incluído", "optional": "Opcional", "reserve": "Reserva",
            "pending": "Pendente", "no_value": "Sem valor", "client_responsibility": "Responsabilidade do cliente",
        }
        estimate_labels = {
            "quoted": "Cotado", "estimated": "Estimado", "reserve": "Reserva",
            "waiting_supplier": "Aguardando fornecedor", "no_value": "Sem valor",
        }
        vendors = []
        for raw in df.get("raw_data", pd.Series([{}] * len(df))):
            vendors.append(raw.get("vendor") if isinstance(raw, dict) else None)
        final_values = pd.to_numeric(df.get("client_total"), errors="coerce")
        view = pd.DataFrame({
            "Categoria": df.get("category", ""),
            "Item": df.get("item_name", ""),
            "Descrição / escopo": df.get("description", ""),
            "Fornecedor": vendors,
            "Qtd.": df.get("quantity"),
            "Unitário": pd.to_numeric(df.get("unit_value"), errors="coerce"),
            "Custo base": pd.to_numeric(df.get("base_value"), errors="coerce"),
            "Markup": pd.to_numeric(df.get("fees_value"), errors="coerce"),
            "Impostos": pd.to_numeric(df.get("charges_value"), errors="coerce"),
            "Total final": final_values,
            "% proposta": (final_values / float(proposal_total)) if proposal_total else None,
            "Situação": df.get("item_status", pd.Series(dtype=str)).map(status_labels).fillna(""),
        })
        st.dataframe(
            view,
            hide_index=True,
            width="stretch",
            column_config={
                "Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo base": st.column_config.NumberColumn(format="R$ %.2f"),
                "Markup": st.column_config.NumberColumn(format="R$ %.2f"),
                "Impostos": st.column_config.NumberColumn(format="R$ %.2f"),
                "Total final": st.column_config.NumberColumn(format="R$ %.2f"),
                "% proposta": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
        if proposal_total is not None:
            st.metric("Total reconciliado da proposta", _format_money(proposal_total))
    else:
        if any(cost_document_kind(row) == "detailed_costs" for row in cost_documents):
            st.warning(
                "A proposta detalhada está preservada, mas nenhuma linha de custo útil foi materializada. "
                "O total permanece não identificado até uma leitura confiável."
            )
        else:
            st.caption("Nenhuma proposta detalhada de custos foi estruturada.")

    category_breakdown = financial.get("cost_category_breakdown") or []
    if category_breakdown and proposal_total:
        st.markdown("#### Distribuição da proposta por categoria")
        category_rows = []
        for row in category_breakdown:
            value = float(row.get("total") or 0)
            category_rows.append({
                "Categoria": row.get("category") or "Sem categoria",
                "Valor": value,
                "% da proposta": f"{(value / float(proposal_total)):.1%}",
            })
        st.dataframe(
            pd.DataFrame(category_rows),
            hide_index=True,
            width="stretch",
            column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")},
        )

    preliminary_documents = {
        str(document.get("id")): document
        for document in cost_documents
        if document.get("id") and cost_document_kind(document) == "preliminary_budget"
    }
    preliminary_items = [
        item for item in snapshot.get("cost_items", [])
        if str(item.get("cost_document_id") or "") in preliminary_documents
    ]
    if preliminary_items:
        st.markdown("#### Estudo de verba — alocação preliminar")
        allocation_rows = []
        for item in preliminary_items:
            raw = item.get("raw_data") if isinstance(item.get("raw_data"), dict) else {}
            pct = raw.get("allocation_pct")
            try:
                pct_text = f"{float(pct):.1%}" if pct not in (None, "") else "—"
            except (TypeError, ValueError):
                pct_text = "—"
            allocation_rows.append({
                "Categoria": item.get("item_name") or item.get("category") or "Sem categoria",
                "Alocação": float(item.get("client_total") or 0),
                "% do estudo": pct_text,
            })
        st.dataframe(
            pd.DataFrame(allocation_rows),
            hide_index=True,
            width="stretch",
            column_config={"Alocação": st.column_config.NumberColumn(format="R$ %.2f")},
        )


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
    outcome = snapshot.get("outcome") or {}
    if str(outcome.get("information_source") or "") == "client_feedback":
        st.markdown("#### Leitura NAVE da decisão")
        commercial_labels = {
            "won": "Ganho", "lost": "Perdido", "cancelled": "Cancelado",
            "suspended": "Suspenso", "no_return": "Sem retorno", "in_evaluation": "Em avaliação",
        }
        proposal_labels = {
            "fully_approved": "Aprovada integralmente", "partially_approved": "Aprovada parcialmente",
            "not_approved": "Não aprovada", "in_revision": "Em revisão", "no_feedback": "Sem feedback",
        }
        cols = st.columns(3)
        cols[0].metric("Resultado comercial", commercial_labels.get(str(outcome.get("commercial_result") or ""), "Não informado"))
        cols[1].metric("Proposta", proposal_labels.get(str(outcome.get("proposal_result") or ""), "Não informada"))
        cols[2].metric("Confiança", "Confirmado pelo cliente" if outcome.get("confidence_level") == "client_confirmed" else str(outcome.get("confidence_level") or "Não informada"))
        if outcome.get("result_context"):
            st.info(str(outcome.get("result_context")))

    st.markdown("#### Histórico de feedbacks")

    if entries:
        for row in entries:
            interpretation = str(row.get("internal_interpretation") or "")
            is_transcription = "transcrição da fonte" in interpretation
            sentiment_label = {
                "positive": "Positivo", "negative": "Negativo", "neutral": "Neutro", "mixed": "Misto",
            }.get(str(row.get("sentiment") or ""), "")
            theme_label = str(row.get("theme") or "outro").replace("_", " ").title()
            title = (
                f"{_format_date(row.get('feedback_date'))} · Transcrição do arquivo"
                if is_transcription
                else f"{_format_date(row.get('feedback_date'))} · {theme_label}" + (f" · {sentiment_label}" if sentiment_label else "")
            )
            with st.expander(title, expanded=is_transcription):
                if is_transcription:
                    st.markdown("**Texto transcrito da fonte**")
                else:
                    st.markdown("**Evidência / trecho do cliente**")
                st.write(row.get("original_feedback"))
                if interpretation:
                    clean_interpretation = interpretation.split(" · claim ", 1)[-1] if " · claim " in interpretation else interpretation
                    st.markdown(f"**Leitura NAVE:** {clean_interpretation}")
                if row.get("action_taken"):
                    st.markdown(f"**Aprendizado recomendado:** {row.get('action_taken')}")
    else:
        report_feedback = []
        for analysis in snapshot.get("report_analyses", []) or []:
            for item in analysis.get("client_feedback") or []:
                if isinstance(item, dict):
                    text = str(item.get("text") or item.get("feedback") or "").strip()
                else:
                    text = str(item or "").strip()
                if text:
                    report_feedback.append(text)
        if report_feedback:
            st.markdown("**Feedback explícito identificado em relatório**")
            for text in report_feedback[:12]:
                st.markdown(f"- {text}")
        else:
            st.caption("Nenhum feedback explícito do cliente foi identificado nas fontes atuais.")

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
                "jpg",
                "jpeg",
                "png",
                "webp",
            ],
            key_suffix="feedback",
        )
    with columns[1]:
        _upload_box(
            client,
            project_id=project_id,
            role="approval",
            title="Arquivo de aprovação",
            accepted_types=["pdf", "docx", "pptx", "txt", "md", "eml", "jpg", "jpeg", "png", "webp"],
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
    unified = snapshot.get("unified_intelligence") or build_unified_project_snapshot(snapshot)
    truth = unified.get("project_truth") or {}
    business_state = str(truth.get("stage") or "") or _business_state(project, outcome)

    if business_state in {"proposal", "no_return"}:
        _section_title(
            "Situação comercial",
            "O projeto ainda está em proposta. Resultado de execução e aprendizados pós-evento só passam a fazer sentido depois da decisão do cliente.",
        )
        st.info(
            f"Situação atual: **{BUSINESS_STATE_LABELS[business_state]}** · "
            f"Processo: **{PROCESS_TYPE_LABELS.get(str(outcome.get('process_type') or 'competition'), 'Concorrência')}**. "
            "Use o controle no topo do projeto para marcar ganho, perda, ausência de resposta, produção ou execução quando isso acontecer."
        )
        if outcome.get("result_context"):
            st.markdown("#### Observações já registradas")
            st.write(_clean_user_note(outcome.get("result_context")))
        return

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
    unified_results = unified.get("results") or {}
    if not snapshot.get("report_analyses") and (
        unified_results.get("activation_results") or unified_results.get("participants_count") is not None
    ):
        st.markdown("#### Leitura consolidada a partir das evidências pós-evento")
        if unified_results.get("participants_count") is not None:
            scope_note = (
                "Público do evento/festival — não equivale automaticamente a visitantes da ativação."
                if unified_results.get("participants_scope") == "festival_event"
                else "Escopo conforme o relatório."
            )
            st.metric("Público registrado", int(float(unified_results.get("participants_count"))))
            st.caption(scope_note)
        if unified_results.get("activation_results"):
            st.dataframe(
                pd.DataFrame(unified_results.get("activation_results")),
                hide_index=True,
                width="stretch",
            )
        for value in unified_results.get("pending") or []:
            st.warning(value)
        for value in unified_results.get("data_quality") or []:
            st.warning(f"Qualidade de dado: {value}")

    # Resultados e aprendizados são uma experiência de fechamento própria. Eles
    # compartilham a Unified Truth com o Diagnóstico, mas não ficam escondidos
    # dentro da mesma seção de decisão.
    decision = unified.get("decision_intelligence") or {}
    result_findings = decision.get("results") or []
    learning_findings = decision.get("learnings") or []
    if result_findings:
        st.markdown("#### O que a NAVE comprovou")
        for row in result_findings[:12]:
            st.info(f"**{row.get('title') or 'Resultado'}**\n\n{row.get('text') or ''}")
    if learning_findings:
        st.markdown("#### Aprendizados consolidados")
        for row in learning_findings[:12]:
            st.success(f"**{row.get('title') or 'Aprendizado'}**\n\n{row.get('text') or ''}")

    semantic = None
    for stored in snapshot.get("intelligence_snapshots") or []:
        metrics = stored.get("metrics") if isinstance(stored.get("metrics"), dict) else {}
        candidate = metrics.get("semantic_synthesis")
        if isinstance(candidate, dict):
            semantic = candidate
            break
    if semantic:
        validated = [str(v).strip() for v in semantic.get("validated_learnings") or [] if str(v).strip()]
        challenged = [str(v).strip() for v in semantic.get("challenged_learnings") or [] if str(v).strip()]
        if validated or challenged:
            st.markdown("#### Memória que este projeto deixa para a VOE")
            columns = st.columns(2, gap="large")
            with columns[0]:
                st.markdown("**O que merece ser preservado**")
                for value in validated[:8]:
                    st.success(value)
            with columns[1]:
                st.markdown("**O que deve mudar em projetos futuros**")
                for value in challenged[:8]:
                    st.warning(value)

    commercial_default = _trusted_outcome_default(
        outcome, "commercial_result",
        {"in_evaluation", "won", "lost", "cancelled", "suspended", "no_return", "not_applicable", "not_informed"},
        "not_informed",
    )
    proposal_default = _trusted_outcome_default(
        outcome, "proposal_result",
        {"fully_approved", "partially_approved", "not_approved", "in_revision", "no_feedback", "not_informed"},
        "not_informed",
    )
    execution_default = (
        str(outcome.get("execution_result"))
        if str(outcome.get("execution_result") or "") in {"executed", "partially_executed", "not_executed", "in_progress", "not_applicable", "not_informed"}
        and str(outcome.get("confidence_level") or "") in {"client_confirmed", "voe_confirmed"}
        else ("executed" if business_state == "executed" else "not_informed")
    )

    with st.expander("Ajustar informações manualmente", expanded=False):
        st.caption("Campos não comprovados permanecem como 'Não informado'. A evidência de execução não implica aprovação integral da proposta nem resultado comercial ganho.")
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
                    ].index(commercial_default)
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
                    ].index(proposal_default)
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
                    ].index(execution_default)
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
                value=_clean_user_note(outcome.get("result_context")),
                height=130,
            )
            execution_notes = st.text_area(
                "Observações de execução",
                value=_clean_user_note(outcome.get("execution_notes")),
                height=110,
            )
            budget_amount = st.number_input(
                "Budget registrado",
                min_value=0.0,
                value=float(outcome.get("budget_amount") or truth.get("budget_amount") or 0),
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

    unified = build_unified_project_snapshot(snapshot)
    snapshot["unified_intelligence"] = unified
    _project_header(project, snapshot.get("outcome") or {}, unified)

    # O Dossiê é uma projeção do MESMO cérebro consumido pelo workspace — nunca
    # uma impressão das abas. Assim PDF e interface não podem chegar a verdades
    # diferentes sobre o projeto.
    try:
        dossier_intelligence = build_project_intelligence(snapshot)
        dossier_bytes = build_project_intelligence_pdf(
            snapshot=snapshot,
            intelligence=dossier_intelligence,
        )
        file_stub = re.sub(r"[^A-Za-z0-9_-]+", "_", str(project.get("project_name") or "projeto")).strip("_") or "projeto"
        st.download_button(
            "↓ Baixar Dossiê Inteligente — PDF",
            data=dossier_bytes,
            file_name=f"NAVE_Dossie_Inteligente_{file_stub}_{str(dossier_intelligence.get('source_signature') or '')[:8]}.pdf",
            mime="application/pdf",
            width="stretch",
            key=f"download_intelligence_dossier_{project_id}",
        )
    except Exception as exc:
        st.caption(f"Dossiê Inteligente temporariamente indisponível: {exc}")

    _status_selector(
        client,
        project=project,
        project_id=project_id,
        outcome=snapshot.get("outcome") or {},
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
            _render_recommendations(
                client,
                project_id=project_id,
                snapshot=snapshot,
            )
        elif selected_section == "Estratégia e conceito":
            _render_strategy(
                client,
                project_id=project_id,
                snapshot=snapshot,
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
    # O UUID acompanha a tabela, mas fica oculto pelo guard transversal em
    # branding.py. Sem ele a exclusão segura nunca consegue identificar o
    # projeto real por trás da posição visual da linha.
    table_columns = ["project_id", *display_columns]

    return st.dataframe(
        dataframe[table_columns],
        hide_index=True,
        width="stretch",
        height=min(620, 95 + max(len(dataframe), 1) * 38),
        on_select="rerun",
        selection_mode="single-row",
        key="nave_projects_workspace_table",
        column_config={"project_id": None},
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
        valid_rows = [
            int(position)
            for position in selected_rows
            if isinstance(position, int)
            and 0 <= int(position) < len(filtered)
        ]
        if len(valid_rows) == 1:
            selected_row = filtered.reset_index(drop=True).iloc[valid_rows[0]]
            action_col, hint_col = st.columns([1.2, 3.8])
            with action_col:
                if st.button(
                    "Abrir projeto selecionado",
                    width="stretch",
                    key="open_selected_workspace_project",
                ):
                    st.session_state["nave_workspace_project_id"] = str(
                        selected_row["project_id"]
                    )
                    st.rerun()
            with hint_col:
                st.caption(
                    "A seleção permanece ativa para permitir excluir um projeto "
                    "incorreto com confirmação antes de abri-lo."
                )
        elif len(valid_rows) > 1:
            st.caption(
                f"{len(valid_rows)} projetos selecionados. Use a ação de exclusão "
                "acima somente se esses registros realmente entraram duplicados ou errados."
            )
