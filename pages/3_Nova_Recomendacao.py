from __future__ import annotations

import os
from datetime import date

import pandas as pd
import streamlit as st

from exporters import format_pt_br_number
from gemini_extractor import parse_recommendation_brief
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
    "Cruza o briefing com os registros existentes e explica a aderência."
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
        "Esta primeira versão usa regras transparentes. "
        "Preço, prazo, capacidade e localização pesam na nota."
    )

type_labels = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
}

with st.form("recommendation_form"):
    project_name = st.text_input("Nome do projeto")

    briefing_text = st.text_area(
        "Briefing",
        height=180,
        placeholder=(
            "Descreva o evento, público, objetivo, conceito e o que "
            "você está procurando."
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        budget_total = st.number_input(
            "Budget total",
            min_value=0.0,
            value=0.0,
            step=1000.0,
        )

    with col2:
        quantity = st.number_input(
            "Quantidade / público",
            min_value=0,
            value=0,
            step=1,
        )

    with col3:
        available_days = st.number_input(
            "Prazo disponível em dias",
            min_value=0,
            value=0,
            step=1,
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        city = st.text_input("Cidade")

    with col5:
        state = st.text_input("Estado")

    with col6:
        event_date = st.date_input(
            "Data do evento",
            value=None,
            min_value=date.today(),
        )

    desired_types = st.multiselect(
        "O que pode entrar na recomendação?",
        options=list(type_labels.keys()),
        default=["product"],
        format_func=lambda value: type_labels[value],
    )

    submitted = st.form_submit_button(
        "Gerar recomendação",
        type="primary",
        use_container_width=True,
    )

if submitted:
    if not briefing_text.strip():
        st.error("Descreva o briefing.")
        st.stop()

    explicit_context = f"""
Nome do projeto: {project_name or 'não informado'}
Budget total: {budget_total if budget_total else 'não informado'}
Quantidade ou público: {quantity if quantity else 'não informado'}
Prazo disponível em dias: {
    available_days if available_days else 'não informado'
}
Cidade: {city or 'não informada'}
Estado: {state or 'não informado'}
Data do evento: {
    event_date.isoformat() if event_date else 'não informada'
}
Tipos permitidos: {', '.join(desired_types)}

Briefing:
{briefing_text}
"""

    try:
        with st.spinner("Interpretando briefing e consultando a base..."):
            parsed = parse_recommendation_brief(
                explicit_context,
                api_key=gemini_key,
                model=model,
            ).model_dump()

            # Campos preenchidos no formulário têm prioridade.
            if project_name:
                parsed["project_name"] = project_name
            if budget_total:
                parsed["budget_total_brl"] = budget_total
            if quantity:
                parsed["audience_quantity"] = quantity
            if available_days:
                parsed["available_days"] = available_days
            if city:
                parsed["location_city"] = city
            if state:
                parsed["location_state"] = state
            if event_date:
                parsed["event_date"] = event_date.isoformat()
            if desired_types:
                parsed["desired_types"] = desired_types

            if (
                parsed.get("budget_total_brl")
                and parsed.get("audience_quantity")
            ):
                parsed["budget_unit_brl"] = (
                    parsed["budget_total_brl"]
                    / parsed["audience_quantity"]
                )

            candidates = fetch_recommendation_candidates(client)
            results = score_candidates(
                candidates,
                parsed,
                limit=12,
            )

        st.session_state["recommendation_brief"] = parsed
        st.session_state["recommendation_results"] = results
        st.session_state["recommendation_source_text"] = briefing_text

    except Exception as exc:
        st.exception(exc)

brief = st.session_state.get("recommendation_brief")
results = st.session_state.get("recommendation_results")

if brief:
    st.divider()
    st.subheader("Entendimento do briefing")
    st.write(brief.get("source_summary"))

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
            f"{int(brief['audience_quantity']):,}".replace(",", ".")
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
    st.subheader("Recomendações")

    if results.empty:
        st.warning(
            "A base ainda não possui itens compatíveis com os filtros."
        )
    else:
        type_labels_reverse = type_labels

        for _, row in results.iterrows():
            title = (
                f"{int(row['rank'])}. {row['name']} "
                f"— {row['total_score']:.0f}/100"
            )
            with st.expander(title, expanded=int(row["rank"]) <= 3):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(
                    "Tipo",
                    type_labels_reverse.get(
                        row.get("item_type"),
                        row.get("item_type"),
                    ),
                )
                c2.metric(
                    "Fornecedor",
                    row.get("supplier_name") or "Não informado",
                )
                c3.metric(
                    "Estimativa total",
                    format_pt_br_number(
                        row.get("estimated_total"),
                        prefix={
                            "BRL": "R$ ",
                            "USD": "US$ ",
                            "EUR": "€ ",
                        }.get(str(row.get("currency") or ""), ""),
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
                        }.get(str(row.get("currency") or ""), ""),
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
                    f"Consulta salva com {saved['results_saved']} "
                    f"resultados. ID: {saved['query_id']}"
                )
            except Exception as exc:
                st.exception(exc)
