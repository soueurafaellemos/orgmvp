from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

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
    "Envie o briefing, revise o preenchimento automático e consulte a base."
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
        "A IA organiza o briefing. Preço, prazo, escala e localização "
        "continuam sendo avaliados por regras transparentes."
    )

type_labels = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
}

FIELD_KEYS = {
    "project_name": "rec_project_name",
    "objective": "rec_objective",
    "audience_profile": "rec_audience_profile",
    "audience_quantity": "rec_quantity",
    "budget_total_brl": "rec_budget_total",
    "location_city": "rec_city",
    "location_state": "rec_state",
    "event_date": "rec_event_date",
    "available_days": "rec_available_days",
    "desired_types": "rec_desired_types",
    "desired_attributes": "rec_desired_attributes",
    "restrictions": "rec_restrictions",
}


def _set_default_state() -> None:
    defaults = {
        "rec_project_name": "",
        "rec_objective": "",
        "rec_audience_profile": "",
        "rec_quantity": 0,
        "rec_budget_total": 0.0,
        "rec_city": "",
        "rec_state": "",
        "rec_event_date": None,
        "rec_available_days": 0,
        "rec_desired_types": ["product"],
        "rec_desired_attributes": "",
        "rec_restrictions": "",
        "rec_briefing_paste": "",
        "recommendation_diagnostic": None,
        "recommendation_service_agenda": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _to_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _join_list(value) -> str:
    return ", ".join(value or [])


def _split_list(value: str) -> list[str]:
    return [
        item.strip()
        for item in str(value or "").replace("|", ",").split(",")
        if item.strip()
    ]


def _apply_parsed_brief(parsed: dict) -> None:
    st.session_state["rec_project_name"] = (
        parsed.get("project_name") or ""
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
        parsed.get("budget_total_brl") or 0.0
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
    st.session_state["rec_available_days"] = int(
        parsed.get("available_days") or 0
    )
    st.session_state["rec_desired_types"] = (
        parsed.get("desired_types") or ["product"]
    )
    st.session_state["rec_desired_attributes"] = _join_list(
        parsed.get("desired_attributes")
    )
    st.session_state["rec_restrictions"] = _join_list(
        parsed.get("restrictions")
    )


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


_set_default_state()

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
        "Você pode enviar briefing, e-mail exportado, apresentação, "
        "planilha, PDF ou documento."
    ),
    key="recommendation_brief_files",
)

st.text_area(
    "Texto do briefing ou e-mail",
    height=170,
    placeholder=(
        "Cole aqui o briefing redigido pelo atendimento. "
        "Também pode complementar os arquivos enviados."
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
                "Lendo documentos e organizando o briefing..."
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
            service_agenda = generate_service_agenda(
                parsed,
                diagnostic,
            )

            st.session_state["recommendation_prefill"] = parsed
            st.session_state["recommendation_diagnostic"] = diagnostic
            st.session_state["recommendation_service_agenda"] = (
                service_agenda
            )
            st.session_state["recommendation_source_text"] = (
                _source_text_for_history(parsed)
            )
            st.success(
                "Briefing lido. Revise o diagnóstico e os campos abaixo."
            )

        except Exception as exc:
            st.exception(exc)

prefill = st.session_state.get("recommendation_prefill")
diagnostic = st.session_state.get("recommendation_diagnostic")

if prefill and diagnostic:
    st.divider()
    st.subheader("2. Diagnóstico do briefing")

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

    if status == "Pronto para recomendar":
        st.success(diagnostic.get("recommended_next_step") or "")
    elif status == "Recomendação possível com ressalvas":
        st.warning(diagnostic.get("recommended_next_step") or "")
    else:
        st.error(diagnostic.get("recommended_next_step") or "")

    tab_critical, tab_important, tab_enrichment = st.tabs(
        [
            f"Críticas ({len(critical)})",
            f"Importantes ({len(important)})",
            f"Enriquecimento ({len(enrichment)})",
        ]
    )

    def render_issues(items, empty_message):
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

    with tab_critical:
        render_issues(
            critical,
            "Nenhuma pendência crítica identificada.",
        )

    with tab_important:
        render_issues(
            important,
            "Nenhuma pendência importante identificada.",
        )

    with tab_enrichment:
        render_issues(
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

    with st.expander("Visualizar pauta completa"):
        st.text_area(
            "Pauta",
            value=agenda,
            height=340,
            disabled=True,
            label_visibility="collapsed",
        )

st.divider()
st.subheader("3. Revise e complete")

with st.form("recommendation_form"):
    project_name = st.text_input(
        "Nome do projeto",
        key="rec_project_name",
    )

    col_context_1, col_context_2 = st.columns(2)

    with col_context_1:
        objective = st.text_area(
            "Objetivo principal",
            height=110,
            key="rec_objective",
        )

    with col_context_2:
        audience_profile = st.text_area(
            "Perfil do público",
            height=110,
            key="rec_audience_profile",
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        budget_total = st.number_input(
            "Budget total",
            min_value=0.0,
            step=1000.0,
            key="rec_budget_total",
        )

    with col2:
        quantity = st.number_input(
            "Quantidade / público",
            min_value=0,
            step=1,
            key="rec_quantity",
        )

    with col3:
        available_days = st.number_input(
            "Prazo disponível em dias",
            min_value=0,
            step=1,
            key="rec_available_days",
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        city = st.text_input(
            "Cidade",
            key="rec_city",
        )

    with col5:
        state = st.text_input(
            "Estado",
            key="rec_state",
        )

    with col6:
        event_date_value = st.date_input(
            "Data do evento",
            key="rec_event_date",
            min_value=date.today(),
        )

    desired_types = st.multiselect(
        "O que pode entrar na recomendação?",
        options=list(type_labels.keys()),
        format_func=lambda value: type_labels[value],
        key="rec_desired_types",
    )

    col_attributes, col_restrictions = st.columns(2)

    with col_attributes:
        desired_attributes_text = st.text_input(
            "Atributos desejados",
            placeholder=(
                "Ex.: tecnológico, sustentável, colecionável"
            ),
            key="rec_desired_attributes",
        )

    with col_restrictions:
        restrictions_text = st.text_input(
            "Restrições",
            placeholder=(
                "Ex.: sem eletrônicos, produção nacional"
            ),
            key="rec_restrictions",
        )

    if budget_total and quantity:
        st.caption(
            "Budget bruto por pessoa: "
            + format_pt_br_number(
                budget_total / quantity,
                prefix="R$ ",
            )
        )

    submit_col1, submit_col2 = st.columns(2)

    with submit_col1:
        diagnose_submitted = st.form_submit_button(
            "Atualizar diagnóstico",
            use_container_width=True,
        )

    with submit_col2:
        submitted = st.form_submit_button(
            "Gerar recomendação",
            type="primary",
            use_container_width=True,
        )

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
Nome do projeto: {project_name or 'não informado'}
Objetivo: {objective or 'não informado'}
Perfil do público: {audience_profile or 'não informado'}
Budget total: {budget_total or 'não informado'}
Quantidade ou público: {quantity or 'não informado'}
Prazo disponível em dias: {
    available_days or 'não informado'
}
Cidade: {city or 'não informada'}
Estado: {state or 'não informado'}
Data do evento: {
    event_date_value.isoformat()
    if event_date_value else 'não informada'
}
Tipos permitidos: {', '.join(desired_types)}
Atributos desejados: {desired_attributes_text}
Restrições: {restrictions_text}

Briefing:
{pasted_text or objective}
"""
            with st.spinner("Interpretando o briefing..."):
                parsed = parse_recommendation_brief(
                    manual_context,
                    api_key=gemini_key,
                    model=model,
                ).model_dump()

        # O que o usuário revisou no formulário tem prioridade.
        parsed["project_name"] = project_name or None
        parsed["objective"] = objective or None
        parsed["audience_profile"] = audience_profile or None
        parsed["budget_total_brl"] = budget_total or None
        parsed["audience_quantity"] = quantity or None
        parsed["available_days"] = available_days or None
        parsed["location_city"] = city or None
        parsed["location_state"] = state or None
        parsed["event_date"] = (
            event_date_value.isoformat()
            if event_date_value
            else None
        )
        parsed["desired_types"] = desired_types
        parsed["desired_attributes"] = _split_list(
            desired_attributes_text
        )
        parsed["restrictions"] = _split_list(
            restrictions_text
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
                "Diagnóstico atualizado com os campos revisados."
            )
        else:
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

brief = st.session_state.get("recommendation_brief")
results = st.session_state.get("recommendation_results")

if brief:
    st.divider()
    st.subheader("4. Entendimento final")

    st.write(brief.get("source_summary") or "")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Budget total",
        format_pt_br_number(
            brief.get("budget_total_brl"),
            prefix="R$ ",
        ) or "Não informado",
    )
    m2.metric(
        "Budget unitário",
        format_pt_br_number(
            brief.get("budget_unit_brl"),
            prefix="R$ ",
        ) or "Não informado",
    )
    m3.metric(
        "Público",
        (
            f"{int(brief['audience_quantity']):,}".replace(
                ",", "."
            )
            if brief.get("audience_quantity")
            else "Não informado"
        ),
    )
    m4.metric(
        "Prazo",
        (
            f"{int(brief['available_days'])} dias"
            if brief.get("available_days")
            else "Não informado"
        ),
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
                )
                st.success(
                    f"Consulta salva com "
                    f"{saved['results_saved']} resultados. "
                    f"ID: {saved['query_id']}"
                )
            except Exception as exc:
                st.exception(exc)
