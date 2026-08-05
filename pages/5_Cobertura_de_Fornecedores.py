from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)

from runtime_ui import report_service_error
from exporters import format_pt_br_number
from supabase_db import (
    fetch_supplier_by_id,
    fetch_supplier_coverage,
    get_supabase_client,
    update_supplier_coverage,
)


st.set_page_config(
    page_title="NAVE by VOE | Fornecedores",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_nave_branding()
page_header(
    "Fornecedores",
    "Organize a cobertura territorial e os dados logísticos "
    "que ajudam a qualificar as recomendações.",
)

try:
    supabase_url = st.secrets.get("SUPABASE_URL", "")
    supabase_key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get(
            "SUPABASE_SERVICE_ROLE_KEY",
            "",
        ),
    )
except Exception:
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            "",
        )
    )

if not supabase_url or not supabase_key:
    st.error(
        "A base de fornecedores não está disponível. "
        "Consulte a área de Administração."
    )
    st.stop()

client = get_supabase_client(
    supabase_url,
    supabase_key,
)


def _pipe(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " | ".join(
            str(item).strip()
            for item in value
            if str(item).strip()
        )
    return str(value)


def _bool_index(value: Any) -> int:
    return 1 if value is True else 0


try:
    coverage = fetch_supplier_coverage(client)
except Exception as exc:
    report_service_error(
        "consulta de fornecedores",
        user_message=(
            "Não foi possível carregar os fornecedores."
        ),
        exception=exc,
    )
    st.stop()

if coverage.empty:
    st.info(
        "Ainda não existem fornecedores cadastrados."
    )
    st.stop()

total = len(coverage)
national = int(
    coverage["coverage_level"]
    .fillna("")
    .eq("Nacional")
    .sum()
)
regional = int(
    coverage["coverage_level"]
    .fillna("")
    .eq("Regional / local")
    .sum()
)
missing = int(
    coverage["coverage_level"]
    .fillna("")
    .eq("Cobertura não cadastrada")
    .sum()
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Fornecedores", total)
m2.metric("Cobertura nacional", national)
m3.metric("Regional / local", regional)
m4.metric("Sem cobertura cadastrada", missing)

st.divider()

search = st.text_input(
    "Buscar fornecedor",
    placeholder="Ex.: TechnoMotion, cenografia, brindes...",
)

filtered = coverage.copy()

if search.strip():
    term = search.strip().lower()
    searchable = (
        filtered["name"].fillna("").astype(str)
        + " "
        + filtered["base_city"].fillna("").astype(str)
        + " "
        + filtered["base_state"].fillna("").astype(str)
        + " "
        + filtered["coverage_level"].fillna("").astype(str)
    ).str.lower()
    filtered = filtered[
        searchable.str.contains(term, regex=False)
    ]

if filtered.empty:
    st.warning("Nenhum fornecedor corresponde à busca.")
    st.stop()

overview = filtered.copy()
overview["Base"] = overview.apply(
    lambda row: ", ".join(
        value
        for value in [
            str(row.get("base_city") or "").strip(),
            str(row.get("base_state") or "").strip(),
        ]
        if value
    ) or "Não informada",
    axis=1,
)
overview["Nacional"] = overview[
    "serves_nationally"
].apply(
    lambda value: (
        "Sim" if value is True
        else "Não" if value is False
        else "Não informado"
    )
)
overview["Deslocamento"] = overview[
    "default_travel_cost_brl"
].apply(
    lambda value: (
        format_pt_br_number(value, prefix="R$ ")
        or ""
    )
)
overview["Frete"] = overview[
    "default_freight_cost_brl"
].apply(
    lambda value: (
        format_pt_br_number(value, prefix="R$ ")
        or ""
    )
)

st.dataframe(
    overview[
        [
            "name",
            "coverage_level",
            "Base",
            "Nacional",
            "served_states",
            "served_cities",
            "Deslocamento",
            "Frete",
            "activations_count",
            "products_count",
            "venues_count",
        ]
    ].rename(
        columns={
            "name": "Fornecedor",
            "coverage_level": "Cobertura",
            "served_states": "Estados atendidos",
            "served_cities": "Cidades atendidas",
            "activations_count": "Soluções",
            "products_count": "Produtos",
            "venues_count": "Locais",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("Editar cobertura")

placeholder = "Selecione um fornecedor"

supplier_options = {
    str(row.get("name")): str(row.get("supplier_id"))
    for _, row in filtered.iterrows()
}

selected_label = st.selectbox(
    "Fornecedor",
    [placeholder, *supplier_options.keys()],
)

if selected_label == placeholder:
    st.info(
        "Selecione um fornecedor para cadastrar sua área de atuação."
    )
    st.stop()

supplier_id = supplier_options[selected_label]
supplier = fetch_supplier_by_id(
    client,
    supplier_id,
)

if not supplier:
    st.error("Fornecedor não encontrado.")
    st.stop()

pricing_modes = [
    "Não informado",
    "Incluído no valor",
    "Adicionar estimativa",
    "Sob consulta",
]

with st.form("supplier_coverage_form"):
    st.markdown(f"### {selected_label}")

    base1, base2, base3 = st.columns(3)
    with base1:
        base_city = st.text_input(
            "Cidade-base",
            value=supplier.get("base_city") or "",
        )
    with base2:
        base_state = st.text_input(
            "Estado-base",
            value=supplier.get("base_state") or "",
            placeholder="Ex.: SP",
        )
    with base3:
        base_country = st.text_input(
            "País-base",
            value=(
                supplier.get("base_country")
                or "Brasil"
            ),
        )

    scope1, scope2 = st.columns(2)
    with scope1:
        serves_nationally = st.checkbox(
            "Atende nacionalmente",
            value=bool(
                supplier.get("serves_nationally")
                or False
            ),
        )
    with scope2:
        has_local_teams = st.checkbox(
            "Possui equipes locais",
            value=bool(
                supplier.get("has_local_teams")
                or False
            ),
        )

    served_states = st.text_input(
        "Estados atendidos",
        value=_pipe(
            supplier.get("served_states")
        ),
        placeholder="SP | RJ | PE | AM",
        help="Separe os itens com |",
    )
    served_cities = st.text_input(
        "Cidades atendidas",
        value=_pipe(
            supplier.get("served_cities")
        ),
        placeholder="São Paulo | Recife | Manaus",
        help="Separe os itens com |",
    )
    local_team_locations = st.text_input(
        "Onde possui equipes locais",
        value=_pipe(
            supplier.get("local_team_locations")
        ),
        placeholder="São Paulo | Rio de Janeiro",
        help="Separe os itens com |",
    )

    st.markdown("#### Deslocamento de equipe ou equipamento")

    travel1, travel2, travel3 = st.columns(3)
    with travel1:
        current_travel_mode = (
            supplier.get("travel_pricing_mode")
            or "Não informado"
        )
        travel_pricing_mode = st.selectbox(
            "Tratamento do deslocamento",
            pricing_modes,
            index=(
                pricing_modes.index(current_travel_mode)
                if current_travel_mode in pricing_modes
                else 0
            ),
        )
    with travel2:
        default_travel_cost_brl = st.number_input(
            "Estimativa padrão de deslocamento",
            min_value=0.0,
            value=float(
                supplier.get(
                    "default_travel_cost_brl"
                )
                or 0
            ),
            step=500.0,
        )
    with travel3:
        travel_lead_days = st.number_input(
            "Dias adicionais de logística",
            min_value=0,
            value=int(
                supplier.get("travel_lead_days")
                or 0
            ),
            step=1,
        )

    requirement1, requirement2 = st.columns(2)
    with requirement1:
        equipment_transport_required = st.checkbox(
            "Normalmente exige transporte de equipamento",
            value=bool(
                supplier.get(
                    "equipment_transport_required"
                )
                or False
            ),
        )
    with requirement2:
        accommodation_required = st.checkbox(
            "Normalmente exige hospedagem fora da base",
            value=bool(
                supplier.get(
                    "accommodation_required"
                )
                or False
            ),
        )

    st.markdown("#### Frete de produtos")

    freight1, freight2 = st.columns(2)
    with freight1:
        current_freight_mode = (
            supplier.get("freight_pricing_mode")
            or "Não informado"
        )
        freight_pricing_mode = st.selectbox(
            "Tratamento do frete",
            pricing_modes,
            index=(
                pricing_modes.index(current_freight_mode)
                if current_freight_mode in pricing_modes
                else 0
            ),
        )
    with freight2:
        default_freight_cost_brl = st.number_input(
            "Estimativa padrão de frete",
            min_value=0.0,
            value=float(
                supplier.get(
                    "default_freight_cost_brl"
                )
                or 0
            ),
            step=500.0,
        )

    coverage_notes = st.text_area(
        "Observações de cobertura",
        value=(
            supplier.get("coverage_notes")
            or ""
        ),
        height=110,
        placeholder=(
            "Ex.: atende Nordeste por parceiro local; "
            "valores variam conforme quantidade de operadores."
        ),
    )

    submitted = st.form_submit_button(
        "Salvar cobertura do fornecedor",
        type="primary",
        use_container_width=True,
    )

if submitted:
    try:
        update_supplier_coverage(
            client,
            supplier_id=supplier_id,
            payload={
                "base_city": base_city or None,
                "base_state": base_state or None,
                "base_country": base_country or "Brasil",
                "serves_nationally": serves_nationally,
                "served_states": served_states,
                "served_cities": served_cities,
                "has_local_teams": has_local_teams,
                "local_team_locations": (
                    local_team_locations
                ),
                "travel_pricing_mode": (
                    travel_pricing_mode
                ),
                "default_travel_cost_brl": (
                    default_travel_cost_brl
                    if default_travel_cost_brl > 0
                    else None
                ),
                "freight_pricing_mode": (
                    freight_pricing_mode
                ),
                "default_freight_cost_brl": (
                    default_freight_cost_brl
                    if default_freight_cost_brl > 0
                    else None
                ),
                "travel_lead_days": (
                    travel_lead_days
                    if travel_lead_days > 0
                    else None
                ),
                "equipment_transport_required": (
                    equipment_transport_required
                ),
                "accommodation_required": (
                    accommodation_required
                ),
                "coverage_notes": (
                    coverage_notes or None
                ),
            },
        )
        st.success("Cobertura atualizada.")
        st.rerun()
    except Exception as exc:
        report_service_error(
            "atualização do fornecedor",
            user_message=(
                "Não foi possível atualizar este fornecedor."
            ),
            exception=exc,
        )
