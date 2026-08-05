from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)

from runtime_ui import report_service_error, require_app_access
from exporters import format_pt_br_number
from supabase_db import (
    database_counts,
    fetch_recommendation_candidates,
    get_supabase_client,
)


st.set_page_config(
    page_title="NAVE by VOE | Base de conhecimento",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Base de conhecimento",
    "Explore brindes, soluções e locais já organizados pela NAVE.",
)

try:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )
except Exception:
    url = os.getenv("SUPABASE_URL", "")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

if not url or not key:
    st.error(
        "A base de conhecimento não está disponível. "
        "Consulte a área de Administração."
    )
    st.stop()

try:
    client = get_supabase_client(url, key)
    counts = database_counts(client)
    candidates = fetch_recommendation_candidates(client)
except Exception as exc:
    report_service_error(
        "consulta da base de conhecimento",
        user_message=(
            "Não foi possível consultar a base de conhecimento."
        ),
        exception=exc,
    )
    st.stop()

metric_columns = st.columns(len(counts))
for column, (label, value) in zip(metric_columns, counts.items()):
    column.metric(label, value)

st.divider()

type_labels = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
}

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    search = st.text_input(
        "Buscar",
        placeholder=(
            "Ex.: skate, tecnologia, sustentável, São Paulo..."
        ),
    )

with col2:
    selected_types = st.multiselect(
        "Tipo",
        options=list(type_labels.keys()),
        default=list(type_labels.keys()),
        format_func=lambda value: type_labels[value],
    )

with col3:
    max_price = st.number_input(
        "Valor máximo",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        help="Zero mantém todos os valores.",
    )

filtered = candidates.copy()

if selected_types:
    filtered = filtered[
        filtered["item_type"].isin(selected_types)
    ]

if search.strip():
    normalized = search.strip().lower()
    searchable = (
        filtered["name"].fillna("").astype(str)
        + " "
        + filtered["category"].fillna("").astype(str)
        + " "
        + filtered["supplier_name"].fillna("").astype(str)
        + " "
        + filtered["description"].fillna("").astype(str)
        + " "
        + filtered["location"].fillna("").astype(str)
    ).str.lower()
    filtered = filtered[searchable.str.contains(normalized, regex=False)]

if max_price > 0:
    numeric_price = pd.to_numeric(
        filtered["base_price"],
        errors="coerce",
    )
    filtered = filtered[
        numeric_price.isna() | (numeric_price <= max_price)
    ]

display = filtered.copy()

if display.empty:
    st.info("Nenhum item corresponde aos filtros.")
    st.stop()

display["Tipo"] = display["item_type"].map(type_labels)
display["Valor"] = display.apply(
    lambda row: format_pt_br_number(
        row.get("base_price"),
        prefix={
            "BRL": "R$ ",
            "USD": "US$ ",
            "EUR": "€ ",
        }.get(str(row.get("currency") or ""), ""),
    ),
    axis=1,
)
display["Prazo"] = display["lead_time_days"].apply(
    lambda value: (
        f"{int(value)} dias"
        if pd.notna(value)
        else ""
    )
)
display["Capacidade"] = display["capacity"].apply(
    lambda value: (
        f"{int(value):,}".replace(",", ".")
        if pd.notna(value)
        else ""
    )
)

columns = [
    "Tipo",
    "name",
    "category",
    "supplier_name",
    "Valor",
    "Prazo",
    "Capacidade",
    "location",
]

st.dataframe(
    display[columns].rename(
        columns={
            "name": "Nome",
            "category": "Categoria",
            "supplier_name": "Fornecedor",
            "location": "Localização",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(f"{len(display)} itens encontrados.")
