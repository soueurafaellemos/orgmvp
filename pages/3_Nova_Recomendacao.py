from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from adaptive_briefing import (
    DELIVERABLE_COLUMNS,
    EXECUTION_COLUMNS,
    METRIC_COLUMNS,
    PRODUCT_COLUMNS,
    PROFILE_OPTIONS,
    REFERENCE_COLUMNS,
    comma_list,
    dataframe_records,
    lines_to_list,
    list_to_comma,
    list_to_lines,
    records_dataframe,
)
from briefing_diagnostic import (
    build_diagnostic,
    generate_service_agenda,
)
from document_io import prepare_documents
from exporters import format_pt_br_number
from gemini_extractor import (
    parse_recommendation_brief,
    parse_recommendation_sources,
)
from recommendation_engine import score_candidates
from supabase_db import (
    fetch_recommendation_candidates,
    get_supabase_client,
    save_recommendation,
)


st.set_page_config(
    page_title="Nova recomendação",
    page_icon="✨",
    layout="wide",
)

st.title("Nova recomendação")
st.caption(
    "O formulário se adapta a uma entrega simples, a um projeto único "
    "estruturado ou a um programa com várias execuções."
)

try:
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    supabase_url = st.secrets.get("SUPABASE_URL", "")
    supabase_key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )
except Exception:
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

if not gemini_key or not supabase_url or not supabase_key:
    st.error("Configure Gemini e Supabase nos Secrets.")
    st.stop()

client = get_supabase_client(supabase_url, supabase_key)

with st.sidebar:
    model = st.selectbox(
        "Modelo Gemini",
        [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ],
    )
    st.info(
        "A IA escolhe o nível de estrutura. Você pode alterar o perfil "
        "antes de revisar ou recomendar."
    )

type_labels = {
    "product": "Brindes / produtos / press kits",
    "activation": "Soluções / ativações / serviços",
    "venue": "Locais / espaços",
}

campaign_options = [
    "Evento",
    "Promoção",
    "Ativação",
    "Incentivo",
    "Stand / feira",
    "Campanha 360º",
    "Digital",
    "Endomarketing",
]

service_options = [
    "Criação",
    "Arte-final",
    "Planejamento",
    "3D",
    "Produção",
    "Pré-produção",
]

production_options = [
    "VOE",
    "Cliente",
    "Fornecedor",
]

currency_options = [
    "BRL",
    "USD",
    "EUR",
    "Outro",
    "Não informado",
]

budget_status_options = [
    "Confirmado",
    "Estimado",
    "Parcial / saldo restante",
    "Não necessário",
    "Não informado",
]

competition_options = [
    "Sim",
    "Não",
    "Não informado",
]


def _set_default_state() -> None:
    defaults = {
        "rec_profile": "Entrega simples",
        "rec_profile_reason": "",
        "rec_project_name": "",
        "rec_client_brand": "",
        "rec_event_name": "",
        "rec_objective": "",
        "rec_audience_profile": "",
        "rec_quantity": 0,
        "rec_budget_total": 0.0,
        "rec_city": "",
        "rec_state": "",
        "rec_event_date": None,
        "rec_delivery_date": None,
        "rec_available_days": 0,
        "rec_desired_types": ["product"],
        "rec_desired_attributes": "",
        "rec_restrictions": "",
        "rec_key_message": "",
        "rec_expected_result": "",
        "rec_event_format": "",
        "rec_briefing_paste": "",
        "rec_job_code": "",
        "rec_job_folder": "",
        "rec_account_manager": "",
        "rec_client_contacts": "",
        "rec_competition_status": "Não informado",
        "rec_competitors": "",
        "rec_campaign_types": [],
        "rec_agency_services": [],
        "rec_production_responsibility": [],
        "rec_budget_currency": "BRL",
        "rec_budget_status": "Não informado",
        "rec_budget_scope": "",
        "rec_remaining_budget": 0.0,
        "rec_payment_terms": "",
        "rec_direct_payment": False,
        "rec_advance_payment": False,
        "rec_financial_notes": "",
        "rec_agenda_items": "",
        "rec_operational_requirements": "",
        "rec_mandatory_requirements": "",
        "rec_decisions": "",
        "rec_contradictions": "",
        "rec_products_records": [],
        "rec_deliverables_records": [],
        "rec_metrics_records": [],
        "rec_executions_records": [],
        "rec_references_records": [],
        "rec_editor_revision": 0,
        "recommendation_diagnostic": None,
        "recommendation_service_agenda": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _to_date(value: Any):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _safe_index(value: str, options: list[str], fallback: str):
    return value if value in options else fallback


def _apply_parsed_brief(parsed: dict) -> None:
    agency = parsed.get("agency_context") or {}
    financial = parsed.get("financial_context") or {}

    st.session_state["rec_profile"] = _safe_index(
        parsed.get("briefing_profile"),
        PROFILE_OPTIONS,
        "Entrega simples",
    )
    st.session_state["rec_profile_reason"] = (
        parsed.get("profile_reason") or ""
    )
    st.session_state["rec_project_name"] = (
        parsed.get("project_name") or ""
    )
    st.session_state["rec_client_brand"] = (
        parsed.get("client_brand") or ""
    )
    st.session_state["rec_event_name"] = (
        parsed.get("event_name") or ""
    )
    st.session_state["rec_objective"] = (
        parsed.get("objective") or ""
    )
    st.session_state["rec_audience_profile"] = (
        parsed.get("audience_profile") or ""
    )
    st.session_state["rec_quantity"] = int(
        parsed.get("audience_quantity") or 0
    )
    st.session_state["rec_budget_total"] = float(
        parsed.get("budget_total_brl") or 0
    )
    st.session_state["rec_city"] = (
        parsed.get("location_city") or ""
    )
    st.session_state["rec_state"] = (
        parsed.get("location_state") or ""
    )
    st.session_state["rec_event_date"] = _to_date(
        parsed.get("event_date")
    )
    st.session_state["rec_delivery_date"] = _to_date(
        parsed.get("desired_delivery_date")
    )
    st.session_state["rec_available_days"] = int(
        parsed.get("available_days") or 0
    )
    st.session_state["rec_desired_types"] = (
        parsed.get("desired_types") or ["product"]
    )
    st.session_state["rec_desired_attributes"] = list_to_comma(
        parsed.get("desired_attributes")
    )
    st.session_state["rec_restrictions"] = list_to_comma(
        parsed.get("restrictions")
    )
    st.session_state["rec_key_message"] = (
        parsed.get("key_message") or ""
    )
    st.session_state["rec_expected_result"] = (
        parsed.get("expected_result") or ""
    )
    st.session_state["rec_event_format"] = (
        parsed.get("event_format") or ""
    )

    st.session_state["rec_job_code"] = (
        agency.get("job_code") or ""
    )
    st.session_state["rec_job_folder"] = (
        agency.get("job_folder") or ""
    )
    st.session_state["rec_account_manager"] = (
        agency.get("account_manager") or ""
    )
    st.session_state["rec_client_contacts"] = list_to_comma(
        agency.get("client_contacts")
    )
    st.session_state["rec_competition_status"] = _safe_index(
        agency.get("competition_status"),
        competition_options,
        "Não informado",
    )
    st.session_state["rec_competitors"] = list_to_comma(
        agency.get("competitors")
    )
    st.session_state["rec_campaign_types"] = [
        value
        for value in (agency.get("campaign_types") or [])
        if value in campaign_options
    ]
    st.session_state["rec_agency_services"] = [
        value
        for value in (agency.get("agency_services") or [])
        if value in service_options
    ]
    st.session_state["rec_production_responsibility"] = [
        value
        for value in (
            agency.get("production_responsibility") or []
        )
        if value in production_options
    ]

    st.session_state["rec_budget_currency"] = _safe_index(
        financial.get("currency"),
        currency_options,
        "Não informado",
    )
    st.session_state["rec_budget_status"] = _safe_index(
        financial.get("budget_status"),
        budget_status_options,
        "Não informado",
    )
    st.session_state["rec_budget_scope"] = (
        financial.get("budget_scope") or ""
    )
    st.session_state["rec_remaining_budget"] = float(
        financial.get("remaining_budget") or 0
    )
    st.session_state["rec_payment_terms"] = (
        financial.get("payment_terms") or ""
    )
    st.session_state["rec_direct_payment"] = bool(
        financial.get("direct_payment_required") or False
    )
    st.session_state["rec_advance_payment"] = bool(
        financial.get("advance_payment_required") or False
    )
    st.session_state["rec_financial_notes"] = (
        financial.get("notes") or ""
    )

    st.session_state["rec_agenda_items"] = list_to_lines(
        parsed.get("agenda_items")
    )
    st.session_state["rec_operational_requirements"] = (
        list_to_lines(parsed.get("operational_requirements"))
    )
    st.session_state["rec_mandatory_requirements"] = (
        list_to_lines(parsed.get("mandatory_requirements"))
    )
    st.session_state["rec_decisions"] = list_to_lines(
        parsed.get("decisions_already_made")
    )
    st.session_state["rec_contradictions"] = list_to_lines(
        parsed.get("contradictions")
    )

    st.session_state["rec_products_records"] = (
        parsed.get("products_or_brands") or []
    )
    st.session_state["rec_deliverables_records"] = (
        parsed.get("deliverables") or []
    )
    st.session_state["rec_metrics_records"] = (
        parsed.get("success_metrics") or []
    )
    st.session_state["rec_executions_records"] = (
        parsed.get("executions") or []
    )
    st.session_state["rec_references_records"] = (
        parsed.get("related_references") or []
    )
    st.session_state["rec_editor_revision"] += 1


def _source_text_for_history(parsed: dict) -> str:
    pasted = st.session_state.get("rec_briefing_paste", "").strip()
    files = parsed.get("source_files") or []
    parts = []
    if files:
        parts.append("Arquivos: " + ", ".join(files))
    if pasted:
        parts.append(pasted)
    if not pasted:
        parts.append(parsed.get("source_summary") or "")
    return "\n\n".join(part for part in parts if part)


def _render_issues(items, empty_message):
    if not items:
        st.success(empty_message)
        return

    for item in items:
        blocking = (
            " · Bloqueia recomendação segura"
            if item.get("blocks_recommendation")
            else ""
        )
        st.markdown(
            f"**{item.get('title')}**  \n"
            f"`{item.get('category')}` · "
            f"Responsável: **{item.get('responsible')}** · "
            f"Impacto: **{item.get('impact')}**{blocking}"
        )
        st.write(item.get("finding") or "")
        st.info(item.get("question") or "")
        if item.get("source_support"):
            st.caption(
                "Apoio da fonte: "
                + str(item.get("source_support"))
            )
        st.divider()


_set_default_state()

# ================================================================
# 1. SOURCE
# ================================================================
st.subheader("1. Envie o briefing")

uploaded_briefings = st.file_uploader(
    "Arquivos do atendimento",
    type=[
        "pdf",
        "txt",
        "md",
        "json",
        "html",
        "xml",
        "doc",
        "docx",
        "rtf",
        "odt",
        "ppt",
        "pptx",
        "csv",
        "tsv",
        "xls",
        "xlsx",
        "eml",
    ],
    accept_multiple_files=True,
    help=(
        "Você pode enviar briefing, e-mail, apresentação, planilha, "
        "PDF ou documento."
    ),
    key="recommendation_brief_files",
)

st.text_area(
    "Texto do briefing ou e-mail",
    height=150,
    placeholder=(
        "Cole aqui um briefing simples ou complemente os arquivos."
    ),
    key="rec_briefing_paste",
)

read_briefing = st.button(
    "Ler briefing e preencher campos",
    type="primary",
    use_container_width=True,
)

if read_briefing:
    if not uploaded_briefings and not st.session_state[
        "rec_briefing_paste"
    ].strip():
        st.error("Envie um arquivo ou cole o briefing.")
    else:
        raw_files = [
            (file.name, file.getvalue(), file.type or None)
            for file in uploaded_briefings
        ]

        try:
            docs = prepare_documents(raw_files)

            with st.spinner(
                "Lendo o briefing e escolhendo o nível de estrutura..."
            ):
                parsed_model = parse_recommendation_sources(
                    docs,
                    pasted_text=st.session_state[
                        "rec_briefing_paste"
                    ],
                    api_key=gemini_key,
                    model=model,
                )
                parsed = parsed_model.model_dump()

            _apply_parsed_brief(parsed)
            diagnostic = build_diagnostic(parsed)
            agenda = generate_service_agenda(parsed, diagnostic)

            st.session_state["recommendation_prefill"] = parsed
            st.session_state["recommendation_diagnostic"] = diagnostic
            st.session_state["recommendation_service_agenda"] = agenda
            st.session_state["recommendation_source_text"] = (
                _source_text_for_history(parsed)
            )

            st.success(
                "Briefing lido. O perfil foi detectado e os campos "
                "correspondentes foram preenchidos."
            )

        except Exception as exc:
            st.exception(exc)

# ================================================================
# 2. PROFILE AND DIAGNOSTIC
# ================================================================
prefill = st.session_state.get("recommendation_prefill")
diagnostic = st.session_state.get("recommendation_diagnostic")

st.divider()
st.subheader("2. Nível de estrutura")

profile = st.selectbox(
    "Perfil do briefing",
    options=PROFILE_OPTIONS,
    key="rec_profile",
    help=(
        "Entrega simples mantém o formulário enxuto. Projetos únicos "
        "estruturados liberam operação e métricas. Programas liberam "
        "praças, ondas ou unidades."
    ),
)

if st.session_state.get("rec_profile_reason"):
    st.caption(
        "Motivo identificado pela IA: "
        + st.session_state["rec_profile_reason"]
    )

profile_explanations = {
    "Entrega simples": (
        "Uma entrega pontual, como press kit, brinde, peça física ou "
        "cotação isolada."
    ),
    "Projeto único estruturado": (
        "Um evento ou ativação central com várias frentes operacionais."
    ),
    "Programa multi-execução": (
        "Um projeto-mãe com várias cidades, datas, instituições, ondas "
        "ou produtos."
    ),
}
st.info(profile_explanations[profile])

if prefill and diagnostic:
    status = diagnostic.get("readiness_status")
    score = int(diagnostic.get("completeness_score") or 0)
    issues = diagnostic.get("issues") or []
    critical = [
        item for item in issues
        if item.get("severity") == "Crítica"
    ]
    important = [
        item for item in issues
        if item.get("severity") == "Importante"
    ]
    enrichment = [
        item for item in issues
        if item.get("severity") == "Enriquecimento"
    ]

    st.markdown("### Diagnóstico")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Completude", f"{score}%")
    c2.metric("Status", status)
    c3.metric("Pendências críticas", len(critical))
    c4.metric(
        "Confiança da leitura",
        f"{float(prefill.get('confidence') or 0) * 100:.0f}%",
    )

    st.progress(score / 100)
    st.write(diagnostic.get("diagnostic_summary") or "")

    tab_critical, tab_important, tab_enrichment = st.tabs(
        [
            f"Críticas ({len(critical)})",
            f"Importantes ({len(important)})",
            f"Enriquecimento ({len(enrichment)})",
        ]
    )

    with tab_critical:
        _render_issues(
            critical,
            "Nenhuma pendência crítica identificada.",
        )

    with tab_important:
        _render_issues(
            important,
            "Nenhuma pendência importante identificada.",
        )

    with tab_enrichment:
        _render_issues(
            enrichment,
            "Nenhuma provocação adicional identificada.",
        )

    agenda = st.session_state.get(
        "recommendation_service_agenda",
        "",
    )

    st.download_button(
        "Baixar pauta para atendimento",
        data=agenda.encode("utf-8"),
        file_name="pauta_complementacao_briefing.txt",
        mime="text/plain",
        use_container_width=True,
    )

# ================================================================
# 3. ADAPTIVE FORM
# ================================================================
st.divider()
st.subheader("3. Revise e complete")

revision = st.session_state["rec_editor_revision"]

with st.form("adaptive_recommendation_form"):
    st.markdown("### Informações centrais")

    row1, row2, row3 = st.columns(3)
    with row1:
        project_name = st.text_input(
            "Nome do projeto",
            key="rec_project_name",
        )
    with row2:
        client_brand = st.text_input(
            "Cliente / marca",
            key="rec_client_brand",
        )
    with row3:
        event_name = st.text_input(
            "Evento ou iniciativa",
            key="rec_event_name",
        )

    context1, context2 = st.columns(2)
    with context1:
        objective = st.text_area(
            "Objetivo principal",
            height=115,
            key="rec_objective",
        )
    with context2:
        audience_profile = st.text_area(
            "Perfil do público",
            height=115,
            key="rec_audience_profile",
        )

    quantity_col, budget_col, currency_col, status_col = st.columns(
        [1, 1.3, 0.8, 1.2]
    )
    with quantity_col:
        quantity = st.number_input(
            "Quantidade / público",
            min_value=0,
            step=1,
            key="rec_quantity",
        )
    with budget_col:
        budget_total = st.number_input(
            "Budget total",
            min_value=0.0,
            step=1000.0,
            key="rec_budget_total",
        )
    with currency_col:
        budget_currency = st.selectbox(
            "Moeda",
            currency_options,
            key="rec_budget_currency",
        )
    with status_col:
        budget_status = st.selectbox(
            "Status do budget",
            budget_status_options,
            key="rec_budget_status",
        )

    date1, date2, days = st.columns(3)
    with date1:
        event_date_value = st.date_input(
            "Data do evento",
            key="rec_event_date",
        )
    with date2:
        delivery_date_value = st.date_input(
            "Data desejada de entrega",
            key="rec_delivery_date",
        )
    with days:
        available_days = st.number_input(
            "Janela operacional em dias",
            min_value=0,
            step=1,
            key="rec_available_days",
            help=(
                "Não confundir com condição de pagamento."
            ),
        )

    location1, location2 = st.columns(2)
    with location1:
        city = st.text_input(
            "Cidade principal",
            key="rec_city",
        )
    with location2:
        state = st.text_input(
            "Estado principal",
            key="rec_state",
        )

    desired_types = st.multiselect(
        "O que pode entrar na recomendação?",
        options=list(type_labels.keys()),
        format_func=lambda value: type_labels[value],
        key="rec_desired_types",
    )

    message1, message2 = st.columns(2)
    with message1:
        key_message = st.text_area(
            "Mensagem principal",
            height=95,
            key="rec_key_message",
        )
    with message2:
        expected_result = st.text_area(
            "Resultado esperado",
            height=95,
            key="rec_expected_result",
        )

    attributes1, attributes2 = st.columns(2)
    with attributes1:
        desired_attributes_text = st.text_input(
            "Atributos desejados",
            key="rec_desired_attributes",
            placeholder=(
                "Ex.: tecnológico, sustentável, colecionável"
            ),
        )
    with attributes2:
        restrictions_text = st.text_input(
            "Restrições",
            key="rec_restrictions",
            placeholder=(
                "Ex.: produção nacional, sem opcional, uso de KV atual"
            ),
        )

    if budget_total and quantity:
        st.caption(
            "Budget bruto por pessoa/unidade: "
            + format_pt_br_number(
                budget_total / quantity,
                prefix=(
                    "R$ "
                    if budget_currency == "BRL"
                    else ""
                ),
            )
        )

    with st.expander(
        "Identificação da agência e escopo contratado",
        expanded=False,
    ):
        agency1, agency2, agency3 = st.columns(3)
        with agency1:
            job_code = st.text_input(
                "Código do job",
                key="rec_job_code",
            )
        with agency2:
            account_manager = st.text_input(
                "Atendimento",
                key="rec_account_manager",
            )
        with agency3:
            client_contacts_text = st.text_input(
                "Contatos do cliente",
                key="rec_client_contacts",
            )

        job_folder = st.text_input(
            "Pasta ou link do job",
            key="rec_job_folder",
        )

        agency4, agency5 = st.columns(2)
        with agency4:
            competition_status = st.selectbox(
                "Concorrência",
                competition_options,
                key="rec_competition_status",
            )
        with agency5:
            competitors_text = st.text_input(
                "Agências concorrentes",
                key="rec_competitors",
            )

        campaign_types = st.multiselect(
            "Tipos de campanha",
            campaign_options,
            key="rec_campaign_types",
        )
        agency_services = st.multiselect(
            "Disciplinas da agência",
            service_options,
            key="rec_agency_services",
        )
        production_responsibility = st.multiselect(
            "Responsabilidade pela produção",
            production_options,
            key="rec_production_responsibility",
        )

    with st.expander(
        "Financeiro e faturamento",
        expanded=bool(
            st.session_state.get("rec_payment_terms")
            or st.session_state.get("rec_budget_scope")
        ),
    ):
        budget_scope = st.text_area(
            "Escopo contemplado no budget",
            height=80,
            key="rec_budget_scope",
        )

        finance1, finance2 = st.columns(2)
        with finance1:
            remaining_budget = st.number_input(
                "Saldo restante",
                min_value=0.0,
                step=1000.0,
                key="rec_remaining_budget",
            )
        with finance2:
            payment_terms = st.text_input(
                "Condição de pagamento",
                key="rec_payment_terms",
                placeholder=(
                    "Ex.: 30 dias pós-evento; 90/120 dias; PO + NF"
                ),
            )

        payment1, payment2 = st.columns(2)
        with payment1:
            direct_payment = st.checkbox(
                "Pagamento direto a fornecedor necessário",
                key="rec_direct_payment",
            )
        with payment2:
            advance_payment = st.checkbox(
                "Adiantamento necessário",
                key="rec_advance_payment",
            )

        financial_notes = st.text_area(
            "Observações financeiras",
            height=80,
            key="rec_financial_notes",
        )

    st.markdown("### Produtos, marcas e entregáveis")

    products_df = st.data_editor(
        records_dataframe(
            st.session_state["rec_products_records"],
            PRODUCT_COLUMNS,
        ),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"rec_products_editor_{revision}",
        column_config={
            "name": st.column_config.TextColumn(
                "Produto / marca",
                required=True,
            ),
            "brand": "Marca",
            "role": st.column_config.SelectboxColumn(
                "Papel",
                options=[
                    "Principal",
                    "Secundário",
                    "Alternativo",
                    "Insumo do cliente",
                    "Outro",
                ],
            ),
            "execution_names": "Execuções relacionadas",
            "notes": "Observações",
        },
    )

    deliverables_df = st.data_editor(
        records_dataframe(
            st.session_state["rec_deliverables_records"],
            DELIVERABLE_COLUMNS,
        ),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"rec_deliverables_editor_{revision}",
        column_config={
            "name": st.column_config.TextColumn(
                "Entregável",
                required=True,
            ),
            "category": "Categoria",
            "quantity": st.column_config.NumberColumn(
                "Quantidade",
                min_value=0.0,
            ),
            "unit": "Unidade",
            "required": st.column_config.CheckboxColumn(
                "Obrigatório",
                default=True,
            ),
            "responsible": "Responsável",
            "execution_names": "Execuções relacionadas",
            "notes": "Observações",
        },
    )

    if profile in (
        "Projeto único estruturado",
        "Programa multi-execução",
    ):
        st.markdown("### Estrutura operacional")

        event_format = st.text_area(
            "Formato do evento ou experiência",
            height=90,
            key="rec_event_format",
        )

        op1, op2 = st.columns(2)
        with op1:
            agenda_items_text = st.text_area(
                "Agenda — um item por linha",
                height=150,
                key="rec_agenda_items",
            )
            mandatory_requirements_text = st.text_area(
                "Obrigatoriedades — uma por linha",
                height=130,
                key="rec_mandatory_requirements",
            )
        with op2:
            operational_requirements_text = st.text_area(
                "Requisitos operacionais — um por linha",
                height=150,
                key="rec_operational_requirements",
            )
            decisions_text = st.text_area(
                "Decisões já tomadas — uma por linha",
                height=130,
                key="rec_decisions",
            )

        metrics_df = st.data_editor(
            records_dataframe(
                st.session_state["rec_metrics_records"],
                METRIC_COLUMNS,
            ),
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"rec_metrics_editor_{revision}",
            column_config={
                "name": st.column_config.TextColumn(
                    "Métrica",
                    required=True,
                ),
                "target": "Meta",
                "unit": "Unidade",
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=[
                        "Confirmada",
                        "Estimada",
                        "A definir",
                    ],
                ),
                "execution_names": "Execuções relacionadas",
                "notes": "Observações",
            },
        )
    else:
        event_format = st.session_state.get(
            "rec_event_format",
            "",
        )
        agenda_items_text = st.session_state.get(
            "rec_agenda_items",
            "",
        )
        operational_requirements_text = st.session_state.get(
            "rec_operational_requirements",
            "",
        )
        mandatory_requirements_text = st.session_state.get(
            "rec_mandatory_requirements",
            "",
        )
        decisions_text = st.session_state.get(
            "rec_decisions",
            "",
        )
        metrics_df = records_dataframe(
            st.session_state["rec_metrics_records"],
            METRIC_COLUMNS,
        )

    if profile == "Programa multi-execução":
        st.markdown("### Praças, ondas ou unidades")

        st.caption(
            "Cada linha representa uma execução. Projetos simples não "
            "precisam preencher esta tabela."
        )

        executions_df = st.data_editor(
            records_dataframe(
                st.session_state["rec_executions_records"],
                EXECUTION_COLUMNS,
            ),
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"rec_executions_editor_{revision}",
            column_config={
                "name": st.column_config.TextColumn(
                    "Execução / praça",
                    required=True,
                ),
                "city": "Cidade",
                "state": "UF",
                "venue": "Local",
                "institution": "Instituição",
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=[
                        "Realizado",
                        "Referência",
                        "Em pesquisa",
                        "Em negociação",
                        "Data sugerida",
                        "Confirmado",
                        "Cancelado",
                        "Não informado",
                    ],
                ),
                "priority": st.column_config.NumberColumn(
                    "Prioridade",
                    min_value=1,
                    step=1,
                ),
                "event_date": st.column_config.DateColumn(
                    "Data",
                    format="DD/MM/YYYY",
                ),
                "product_name": "Produto",
                "audience_quantity": st.column_config.NumberColumn(
                    "Público",
                    min_value=0,
                    step=1,
                ),
                "budget_amount": st.column_config.NumberColumn(
                    "Budget",
                    min_value=0.0,
                ),
                "currency": "Moeda",
                "event_format": "Formato",
                "notes": "Observações",
            },
        )
    else:
        executions_df = records_dataframe(
            st.session_state["rec_executions_records"],
            EXECUTION_COLUMNS,
        )

    with st.expander(
        "Referências, dependências e conflitos",
        expanded=bool(
            st.session_state["rec_references_records"]
            or st.session_state.get("rec_contradictions")
        ),
    ):
        references_df = st.data_editor(
            records_dataframe(
                st.session_state["rec_references_records"],
                REFERENCE_COLUMNS,
            ),
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"rec_references_editor_{revision}",
            column_config={
                "title": st.column_config.TextColumn(
                    "Documento / referência",
                    required=True,
                ),
                "reference_type": st.column_config.SelectboxColumn(
                    "Tipo",
                    options=[
                        "Briefing principal",
                        "Planilha complementar",
                        "Report anterior",
                        "Apresentação",
                        "KV / identidade visual",
                        "Cotação",
                        "Link externo",
                        "Dependência futura",
                        "Outro",
                    ],
                ),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=[
                        "Recebido",
                        "Pendente",
                        "Referência",
                        "A atualizar",
                        "Não informado",
                    ],
                ),
                "url_or_location": "Link ou localização",
                "notes": "Observações",
            },
        )

        contradictions_text = st.text_area(
            "Conflitos ou ambiguidades — um por linha",
            height=110,
            key="rec_contradictions",
        )

    submit1, submit2 = st.columns(2)
    with submit1:
        diagnose_submitted = st.form_submit_button(
            "Atualizar diagnóstico",
            use_container_width=True,
        )
    with submit2:
        submitted = st.form_submit_button(
            "Gerar recomendação",
            type="primary",
            use_container_width=True,
        )

# ================================================================
# FORM PROCESSING
# ================================================================
if diagnose_submitted or submitted:
    source_text = st.session_state.get(
        "recommendation_source_text",
        "",
    )
    pasted_text = st.session_state.get(
        "rec_briefing_paste",
        "",
    ).strip()

    if not source_text and not pasted_text and not objective:
        st.error(
            "Envie um briefing, cole um texto ou descreva o objetivo."
        )
        st.stop()

    try:
        parsed = dict(
            st.session_state.get("recommendation_prefill") or {}
        )

        if not parsed:
            manual_context = f"""
Perfil escolhido: {profile}
Projeto: {project_name or 'não informado'}
Cliente: {client_brand or 'não informado'}
Evento: {event_name or 'não informado'}
Objetivo: {objective or 'não informado'}
Público: {audience_profile or 'não informado'}
Quantidade: {quantity or 'não informado'}
Budget: {budget_total or 'não informado'} {budget_currency}
Data do evento: {
    event_date_value.isoformat()
    if event_date_value else 'não informada'
}
Data de entrega: {
    delivery_date_value.isoformat()
    if delivery_date_value else 'não informada'
}
Cidade: {city or 'não informada'}
Estado: {state or 'não informado'}
Tipos permitidos: {', '.join(desired_types)}

Briefing:
{pasted_text or objective}
"""
            with st.spinner("Interpretando o briefing..."):
                parsed = parse_recommendation_brief(
                    manual_context,
                    api_key=gemini_key,
                    model=model,
                ).model_dump()

        products = dataframe_records(
            products_df,
            required_field="name",
            list_fields={"execution_names"},
        )
        deliverables = dataframe_records(
            deliverables_df,
            required_field="name",
            list_fields={"execution_names"},
        )
        metrics = dataframe_records(
            metrics_df,
            required_field="name",
            list_fields={"execution_names"},
        )
        executions = dataframe_records(
            executions_df,
            required_field="name",
        )
        references = dataframe_records(
            references_df,
            required_field="title",
        )

        parsed["briefing_profile"] = profile
        parsed["profile_reason"] = (
            st.session_state.get("rec_profile_reason")
            or "Perfil revisado pelo usuário."
        )
        parsed["project_name"] = project_name or None
        parsed["client_brand"] = client_brand or None
        parsed["event_name"] = event_name or None
        parsed["objective"] = objective or None
        parsed["audience_profile"] = audience_profile or None
        parsed["audience_quantity"] = quantity or None
        parsed["budget_total_brl"] = budget_total or None
        parsed["location_city"] = city or None
        parsed["location_state"] = state or None
        parsed["event_date"] = (
            event_date_value.isoformat()
            if event_date_value else None
        )
        parsed["desired_delivery_date"] = (
            delivery_date_value.isoformat()
            if delivery_date_value else None
        )
        parsed["available_days"] = available_days or None
        parsed["key_message"] = key_message or None
        parsed["expected_result"] = expected_result or None
        parsed["event_format"] = event_format or None
        parsed["desired_types"] = desired_types
        parsed["desired_attributes"] = comma_list(
            desired_attributes_text
        )
        parsed["restrictions"] = comma_list(
            restrictions_text
        )

        parsed["agency_context"] = {
            "job_code": job_code or None,
            "job_folder": job_folder or None,
            "account_manager": account_manager or None,
            "client_contacts": comma_list(
                client_contacts_text
            ),
            "competition_status": competition_status,
            "competitors": comma_list(competitors_text),
            "campaign_types": campaign_types,
            "agency_services": agency_services,
            "production_responsibility": (
                production_responsibility
            ),
        }

        parsed["financial_context"] = {
            "currency": budget_currency,
            "budget_status": budget_status,
            "budget_scope": budget_scope or None,
            "remaining_budget": remaining_budget or None,
            "payment_terms": payment_terms or None,
            "direct_payment_required": direct_payment,
            "advance_payment_required": advance_payment,
            "notes": financial_notes or None,
        }

        parsed["products_or_brands"] = products
        parsed["deliverables"] = deliverables
        parsed["success_metrics"] = metrics
        parsed["executions"] = executions
        parsed["related_references"] = references
        parsed["agenda_items"] = lines_to_list(
            agenda_items_text
        )
        parsed["operational_requirements"] = lines_to_list(
            operational_requirements_text
        )
        parsed["mandatory_requirements"] = lines_to_list(
            mandatory_requirements_text
        )
        parsed["decisions_already_made"] = lines_to_list(
            decisions_text
        )
        parsed["contradictions"] = lines_to_list(
            contradictions_text
        )

        if budget_total and quantity:
            parsed["budget_unit_brl"] = (
                budget_total / quantity
            )
        else:
            parsed["budget_unit_brl"] = None

        updated_diagnostic = build_diagnostic(parsed)
        updated_agenda = generate_service_agenda(
            parsed,
            updated_diagnostic,
        )

        st.session_state["recommendation_prefill"] = parsed
        st.session_state["recommendation_diagnostic"] = (
            updated_diagnostic
        )
        st.session_state["recommendation_service_agenda"] = (
            updated_agenda
        )

        if diagnose_submitted and not submitted:
            st.session_state["recommendation_brief"] = None
            st.session_state["recommendation_results"] = None
            st.success(
                "Diagnóstico atualizado com a estrutura revisada."
            )
        else:
            if budget_currency not in ("BRL", "Não informado"):
                st.warning(
                    "O recomendador atual compara preços em BRL. "
                    "Converta ou revise o budget antes da decisão final."
                )

            candidates = fetch_recommendation_candidates(client)

            with st.spinner("Consultando e pontuando a base..."):
                results = score_candidates(
                    candidates,
                    parsed,
                    limit=12,
                )

            st.session_state["recommendation_brief"] = parsed
            st.session_state["recommendation_results"] = results

        if not st.session_state.get(
            "recommendation_source_text"
        ):
            st.session_state["recommendation_source_text"] = (
                pasted_text
                or parsed.get("source_summary")
                or objective
            )

    except Exception as exc:
        st.exception(exc)

# ================================================================
# FINAL UNDERSTANDING AND RECOMMENDATIONS
# ================================================================
brief = st.session_state.get("recommendation_brief")
results = st.session_state.get("recommendation_results")

if brief:
    st.divider()
    st.subheader("4. Entendimento final")

    st.write(brief.get("source_summary") or "")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(
        "Perfil",
        brief.get("briefing_profile") or "Não informado",
    )
    m2.metric(
        "Budget total",
        format_pt_br_number(
            brief.get("budget_total_brl"),
            prefix="R$ ",
        ) or "Não informado",
    )
    m3.metric(
        "Budget unitário",
        format_pt_br_number(
            brief.get("budget_unit_brl"),
            prefix="R$ ",
        ) or "Não informado",
    )
    m4.metric(
        "Público",
        (
            f"{int(brief['audience_quantity']):,}".replace(
                ",", "."
            )
            if brief.get("audience_quantity")
            else "Não informado"
        ),
    )
    m5.metric(
        "Execuções",
        len(brief.get("executions") or []),
    )

    if brief.get("briefing_profile") == "Programa multi-execução":
        st.info(
            "A recomendação abaixo usa os campos centrais do projeto. "
            "As recomendações específicas por praça serão tratadas em "
            "uma evolução própria."
        )

if results is not None:
    st.divider()
    st.subheader("5. Recomendações")

    if results.empty:
        st.warning(
            "A base ainda não possui itens compatíveis com os filtros."
        )
    else:
        for _, row in results.iterrows():
            title = (
                f"{int(row['rank'])}. {row['name']} "
                f"— {row['total_score']:.0f}/100"
            )

            with st.expander(
                title,
                expanded=int(row["rank"]) <= 3,
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(
                    "Tipo",
                    type_labels.get(
                        row.get("item_type"),
                        row.get("item_type"),
                    ),
                )
                c2.metric(
                    "Fornecedor",
                    row.get("supplier_name")
                    or "Não informado",
                )
                c3.metric(
                    "Estimativa total",
                    format_pt_br_number(
                        row.get("estimated_total"),
                        prefix={
                            "BRL": "R$ ",
                            "USD": "US$ ",
                            "EUR": "€ ",
                        }.get(
                            str(row.get("currency") or ""),
                            "",
                        ),
                    ) or "Não calculada",
                )
                c4.metric(
                    "Preço de referência",
                    format_pt_br_number(
                        row.get("base_price"),
                        prefix={
                            "BRL": "R$ ",
                            "USD": "US$ ",
                            "EUR": "€ ",
                        }.get(
                            str(row.get("currency") or ""),
                            "",
                        ),
                    ) or "Não informado",
                )

                st.write(row.get("description") or "")
                st.success(row.get("reason") or "")

                warnings = row.get("warnings") or []
                if warnings:
                    st.warning(" ".join(warnings))

                score_data = pd.DataFrame(
                    {
                        "Critério": [
                            "Relevância",
                            "Budget",
                            "Quantidade / capacidade",
                            "Prazo",
                            "Localização",
                        ],
                        "Pontos": [
                            row.get("relevance_score"),
                            row.get("budget_score"),
                            row.get("quantity_score"),
                            row.get("time_score"),
                            row.get("location_score"),
                        ],
                    }
                )
                st.dataframe(
                    score_data,
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        st.subheader("Salvar como versão do projeto")

        version_notes = st.text_input(
            "Observação desta versão",
            placeholder=(
                "Ex.: budget revisado; escopo por praça confirmado."
            ),
            key="recommendation_version_notes",
        )

        if st.button(
            "Salvar consulta e resultados na base",
            type="primary",
            use_container_width=True,
        ):
            try:
                saved = save_recommendation(
                    client,
                    brief=brief,
                    briefing_text=st.session_state.get(
                        "recommendation_source_text",
                        "",
                    ),
                    results_df=results,
                    diagnostic=st.session_state.get(
                        "recommendation_diagnostic"
                    ),
                    source_files=brief.get("source_files") or [],
                    version_notes=version_notes,
                )

                adaptive = saved.get("adaptive_counts") or {}
                structured_count = sum(adaptive.values())

                st.success(
                    f"Versão {saved['version_number']} salva com "
                    f"{saved['results_saved']} recomendações e "
                    f"{structured_count} registros estruturados."
                )
                st.page_link(
                    "pages/4_Historico_de_Projetos.py",
                    label="Abrir histórico do projeto",
                    icon="🕘",
                )
            except Exception as exc:
                st.exception(exc)
