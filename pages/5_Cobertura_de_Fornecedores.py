from __future__ import annotations

import math
import os
from typing import Any

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)

from runtime_ui import report_service_error, require_app_access
from exporters import format_pt_br_number
from curation_ui import (
    VALIDATION_LABELS,
    render_curation_editor,
)
from supabase_db import (
    fetch_curation_states,
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

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Fornecedores",
    "Selecione um fornecedor na tabela para consultar e editar "
    "sua cobertura territorial e seus dados logísticos.",
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

try:
    supplier_states = fetch_curation_states(
        client,
        [
            ("supplier", str(row.get("supplier_id")))
            for _, row in coverage.iterrows()
        ],
    )
except Exception:
    supplier_states = {}

coverage["validation_status"] = coverage.apply(
    lambda row: supplier_states.get(
        (
            "supplier",
            str(row.get("supplier_id")),
        ),
        {},
    ).get(
        "validation_status",
        "not_reviewed",
    ),
    axis=1,
)
coverage["is_archived"] = coverage.apply(
    lambda row: bool(
        supplier_states.get(
            (
                "supplier",
                str(row.get("supplier_id")),
            ),
            {},
        ).get("is_archived", False)
    ),
    axis=1,
)

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

filter1, filter2, filter3, filter4 = st.columns(
    [2.2, 1.3, 1.3, 1]
)

with filter1:
    search = st.text_input(
        "Buscar fornecedor",
        placeholder=(
            "Ex.: TechnoMotion, cenografia, brindes..."
        ),
    )

coverage_options = sorted(
    {
        str(value)
        for value in coverage[
            "coverage_level"
        ].dropna()
        if str(value).strip()
    }
)

with filter2:
    selected_coverage = st.selectbox(
        "Cobertura",
        ["Todos", *coverage_options],
    )

with filter3:
    curation_filter = st.selectbox(
        "Curadoria",
        [
            "Ativos",
            "Não revisados",
            "Em revisão",
            "Validados",
            "Precisam atualização",
            "Arquivados",
            "Todos",
        ],
        key="supplier_curation_filter",
    )

with filter4:
    page_size = st.selectbox(
        "Itens por página",
        [25, 50, 100],
        index=0,
        key="supplier_page_size",
    )

filtered = coverage.copy()

if curation_filter == "Ativos":
    filtered = filtered[
        ~filtered["is_archived"].fillna(False)
    ]
elif curation_filter == "Arquivados":
    filtered = filtered[
        filtered["is_archived"].fillna(False)
    ]
elif curation_filter != "Todos":
    status_map = {
        "Não revisados": "not_reviewed",
        "Em revisão": "in_review",
        "Validados": "validated",
        "Precisam atualização": "needs_update",
    }
    filtered = filtered[
        filtered["validation_status"].fillna(
            "not_reviewed"
        ).eq(status_map[curation_filter])
    ]

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
        searchable.str.contains(
            term,
            regex=False,
        )
    ]

if selected_coverage != "Todos":
    filtered = filtered[
        filtered[
            "coverage_level"
        ].fillna("").eq(selected_coverage)
    ]

filtered = filtered.reset_index(drop=True)

if filtered.empty:
    st.warning(
        "Nenhum fornecedor corresponde aos filtros."
    )
    st.stop()

total_filtered = len(filtered)
total_pages = max(
    1,
    math.ceil(total_filtered / page_size),
)

page_column, summary_column = st.columns(
    [1, 4]
)

with page_column:
    current_page = st.number_input(
        "Página",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key="supplier_current_page",
    )

with summary_column:
    st.caption(
        f"{total_filtered} fornecedor(es) encontrado(s) · "
        f"página {int(current_page)} de {total_pages}"
    )

start_index = (
    int(current_page) - 1
) * page_size
end_index = min(
    start_index + page_size,
    total_filtered,
)

overview = filtered.iloc[
    start_index:end_index
].copy().reset_index(drop=True)

overview["Fornecedor"] = overview[
    "name"
].fillna("Fornecedor sem nome")
overview["Cobertura"] = overview[
    "coverage_level"
].fillna("Cobertura não cadastrada")
overview["Base"] = overview.apply(
    lambda row: ", ".join(
        value
        for value in [
            str(row.get("base_city") or "").strip(),
            str(row.get("base_state") or "").strip(),
        ]
        if value
    )
    or "Não informada",
    axis=1,
)
overview["Nacional"] = overview[
    "serves_nationally"
].apply(
    lambda value: (
        "Sim"
        if value is True
        else "Não"
        if value is False
        else "Não informado"
    )
)
overview["Estados atendidos"] = overview[
    "served_states"
].apply(
    lambda value: _pipe(value).replace(
        " | ",
        ", ",
    )
    or "Não informado"
)
overview["Cidades atendidas"] = overview[
    "served_cities"
].apply(
    lambda value: _pipe(value).replace(
        " | ",
        ", ",
    )
    or "Não informado"
)
overview["Soluções"] = pd.to_numeric(
    overview["activations_count"],
    errors="coerce",
).fillna(0).astype(int)
overview["Produtos"] = pd.to_numeric(
    overview["products_count"],
    errors="coerce",
).fillna(0).astype(int)
overview["Locais"] = pd.to_numeric(
    overview["venues_count"],
    errors="coerce",
).fillna(0).astype(int)
overview["Validação"] = overview[
    "validation_status"
].fillna("not_reviewed").map(
    VALIDATION_LABELS
).fillna("Não revisado")

st.caption(
    "Selecione uma linha para abrir os dados completos e "
    "editar a cobertura."
)

supplier_event = st.dataframe(
    overview[
        [
            "Fornecedor",
            "Cobertura",
            "Base",
            "Nacional",
            "Estados atendidos",
            "Cidades atendidas",
            "Soluções",
            "Produtos",
            "Locais",
            "Validação",
        ]
    ],
    use_container_width=True,
    hide_index=True,
    row_height=52,
    key=(
        f"supplier_navigation_table_"
        f"{int(current_page)}_"
        f"{selected_coverage}"
    ),
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Fornecedor": st.column_config.TextColumn(
            "Fornecedor",
            width="medium",
        ),
        "Cobertura": st.column_config.TextColumn(
            "Cobertura",
            width="medium",
        ),
        "Estados atendidos": (
            st.column_config.TextColumn(
                "Estados atendidos",
                width="medium",
            )
        ),
        "Cidades atendidas": (
            st.column_config.TextColumn(
                "Cidades atendidas",
                width="large",
            )
        ),
        "Validação": st.column_config.TextColumn(
            "Validação",
            width="medium",
        ),
    },
)


def _selected_rows(event) -> list[int]:
    try:
        return list(event.selection.rows)
    except Exception:
        try:
            return list(
                event.get(
                    "selection",
                    {},
                ).get("rows", [])
            )
        except Exception:
            return []


selected_supplier_rows = _selected_rows(
    supplier_event
)

focus = st.session_state.get(
    "nave_curation_focus"
)

if selected_supplier_rows:
    selected_overview = overview.iloc[
        selected_supplier_rows[0]
    ].to_dict()
elif (
    isinstance(focus, dict)
    and focus.get("entity_type") == "supplier"
):
    focus_id = str(focus.get("entity_id"))
    focused_rows = coverage[
        coverage["supplier_id"].astype(str).eq(
            focus_id
        )
    ]

    if focused_rows.empty:
        st.warning(
            "O fornecedor direcionado não foi localizado."
        )
        st.stop()

    selected_overview = focused_rows.iloc[
        0
    ].to_dict()
    selected_overview["Fornecedor"] = (
        selected_overview.get("name")
        or "Fornecedor sem nome"
    )
    selected_overview["Cobertura"] = (
        selected_overview.get("coverage_level")
        or "Cobertura não cadastrada"
    )
    selected_overview["Base"] = ", ".join(
        value
        for value in [
            str(
                selected_overview.get("base_city")
                or ""
            ).strip(),
            str(
                selected_overview.get("base_state")
                or ""
            ).strip(),
        ]
        if value
    ) or "Não informada"
    selected_overview["Soluções"] = int(
        selected_overview.get(
            "activations_count"
        )
        or 0
    )
    selected_overview["Produtos"] = int(
        selected_overview.get(
            "products_count"
        )
        or 0
    )
    selected_overview["Locais"] = int(
        selected_overview.get(
            "venues_count"
        )
        or 0
    )

    st.info(
        "Fornecedor aberto a partir do painel "
        "de prontidão."
    )

    if st.button(
        "Fechar fornecedor direcionado",
        key="close_supplier_curation_focus",
    ):
        st.session_state.pop(
            "nave_curation_focus",
            None,
        )
        st.rerun()
else:
    st.info(
        "Selecione um fornecedor na tabela para consultar "
        "seus dados e editar a cobertura."
    )
    st.stop()

supplier_id = str(
    selected_overview.get("supplier_id") or ""
)
selected_label = str(
    selected_overview.get("Fornecedor")
    or "Fornecedor"
)

try:
    supplier = fetch_supplier_by_id(
        client,
        supplier_id,
    )
except Exception as exc:
    report_service_error(
        "consulta do fornecedor selecionado",
        user_message=(
            "Não foi possível abrir este fornecedor."
        ),
        exception=exc,
    )
    st.stop()

if not supplier:
    st.error("Fornecedor não encontrado.")
    st.stop()

st.divider()
st.subheader(selected_label)

detail1, detail2, detail3, detail4, detail5 = (
    st.columns(5)
)

detail1.metric(
    "Cobertura",
    selected_overview.get("Cobertura")
    or "Não cadastrada",
)
detail2.metric(
    "Base",
    selected_overview.get("Base")
    or "Não informada",
)
detail3.metric(
    "Soluções",
    int(selected_overview.get("Soluções") or 0),
)
detail4.metric(
    "Produtos",
    int(selected_overview.get("Produtos") or 0),
)
detail5.metric(
    "Locais",
    int(selected_overview.get("Locais") or 0),
)

contact1, contact2, contact3 = st.columns(3)

with contact1:
    st.markdown("**Contato**")
    st.write(
        supplier.get("contact_name")
        or supplier.get("email")
        or "Não informado"
    )

with contact2:
    st.markdown("**Telefone / WhatsApp**")
    st.write(
        supplier.get("whatsapp")
        or supplier.get("phone")
        or "Não informado"
    )

with contact3:
    st.markdown("**Site**")
    website = supplier.get("website_url")
    if website:
        st.link_button(
            "Abrir site",
            website,
            use_container_width=True,
        )
    else:
        st.write("Não informado")

st.divider()
st.subheader("Curadoria")

render_curation_editor(
    client,
    entity_type="supplier",
    entity_id=supplier_id,
    record=supplier,
    supplier_options={},
)

st.divider()
st.subheader("Editar cobertura e logística")


pricing_modes = [
    "Não informado",
    "Incluído no valor",
    "Adicionar estimativa",
    "Sob consulta",
]

with st.form(f"supplier_coverage_form_{supplier_id}"):
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
