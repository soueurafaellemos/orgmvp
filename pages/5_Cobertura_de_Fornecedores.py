from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from knowledge_specialized import (
    fetch_media_assets_batch,
    primary_image_url,
    render_detail,
)
from nave_data_client import enforce_existing_app_access, get_nave_client
from nave_table_utils import clean_cover_value
from supplier_geography import (
    supplier_city_options as _geo_supplier_city_options,
    supplier_city_presence as _geo_supplier_city_presence,
    supplier_country_only_geography as _geo_country_only,
    supplier_country_values as _geo_country_values,
)


st.set_page_config(page_title="Fornecedores | NAVE by VOE", page_icon=NAVE_APP_ICON, layout="wide")
enforce_existing_app_access()
apply_nave_branding()


def _rows(response: Any) -> list[dict]:
    return [dict(row) for row in (getattr(response, "data", None) or []) if isinstance(row, dict)]


def _count_by(rows: list[dict], field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "")
        if value:
            result[value] = result.get(value, 0) + 1
    return result


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().replace("/", " ").replace("_", " ").split())


def _is_venue_only_import(row: dict) -> bool:
    """Diferencia um local importado de um fornecedor reconhecido no upload."""
    classification = row.get("classification")
    if not isinstance(classification, dict):
        classification = {}

    contains_products = classification.get("contains_products") is True
    contains_activations = classification.get("contains_services_or_activations") is True
    contains_venues = classification.get("contains_venues_or_spaces") is True
    mode = _normalized(classification.get("suggested_mode"))
    destination = _normalized(row.get("destination_base"))
    document_type = _normalized(row.get("document_type"))

    if contains_products or contains_activations:
        return False
    if contains_venues:
        return True
    venue_signal = any(
        token in f"{mode} {destination} {document_type}"
        for token in ("venue", "local", "locais", "espaco", "espacos")
    )
    supplier_signal = any(
        token in f"{mode} {destination} {document_type}"
        for token in ("fornecedor", "supplier", "produto", "brinde", "ativacao", "solucao")
    )
    return venue_signal and not supplier_signal


def _recognized_supplier_ids(
    products: list[dict],
    activations: list[dict],
    imports: list[dict],
) -> set[str]:
    """Mostra somente fornecedores efetivamente reconhecidos em uploads da NAVE."""
    recognized = {
        str(row.get("supplier_id"))
        for row in [*products, *activations]
        if row.get("supplier_id")
    }
    for row in imports:
        supplier_id = str(row.get("supplier_id") or "")
        if supplier_id and not _is_venue_only_import(row):
            recognized.add(supplier_id)
    return recognized


def _coverage_level(row: dict) -> str:
    # Quando a única granularidade territorial informada é país, mantemos o
    # cadastro em nível Global. Não inferimos nenhuma cidade a partir disso.
    if _geo_country_only(row):
        return "Global"
    if row.get("serves_nationally") is True:
        return "Nacional"
    # Só considera cobertura municipal quando a geografia foi validada como
    # cidade. Países gravados por uploads antigos em served_cities/base_city
    # não transformam o cadastro em fornecedor local/regional.
    if _geo_supplier_city_presence(row) or row.get("served_states"):
        return "Regional / local"
    if row.get("base_state") or _geo_supplier_city_presence(row):
        return "Somente base cadastrada"
    return "Cobertura não cadastrada"


def _base_label(row: dict) -> str:
    base = ", ".join(
        str(row.get(field) or "").strip()
        for field in ("base_city", "base_state")
        if str(row.get(field) or "").strip()
    )
    if base and not _geo_country_only(row):
        return base
    countries = _geo_country_values(row)
    if _geo_country_only(row) and countries:
        return " / ".join(countries)
    return base


def _list_values(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                loaded = json.loads(text)
                if isinstance(loaded, list):
                    return [str(item).strip() for item in loaded if str(item).strip()]
            except Exception:
                pass
        parts = [item.strip() for item in re.split(r"[;|\n]+", text) if item.strip()]
        if len(parts) > 1:
            return parts
        # Vírgula pode separar cidade/UF. Só a tratamos como lista quando o
        # último trecho não parece uma UF de duas letras.
        comma = [item.strip() for item in text.split(",") if item.strip()]
        if len(comma) > 1 and not (len(comma[-1]) == 2 and comma[-1].isalpha()):
            return comma
        return [text]
    return [str(value).strip()]


def _city_state(value: Any, fallback_state: str = "") -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    for pattern in (
        r"^(.+?)\s*[—–]\s*([A-Za-z]{2})$",
        r"^(.+?)\s+-\s+([A-Za-z]{2})$",
        r"^(.+?)\s*[,/]\s*([A-Za-z]{2})$",
    ):
        match = re.match(pattern, text)
        if match:
            return match.group(1).strip(), match.group(2).upper()
    return text, str(fallback_state or "").strip().upper()


def _city_label(city: str, state: str = "") -> str:
    city = str(city or "").strip()
    state = str(state or "").strip().upper()
    return f"{city} — {state}" if city and state else city


def _supplier_city_presence(row: dict) -> dict[tuple[str, str], str]:
    return _geo_supplier_city_presence(row)


def _supplier_city_options(rows: list[dict]) -> dict[str, tuple[str, str]]:
    return _geo_supplier_city_options(rows)

def _load_suppliers(client: Any) -> list[dict]:
    suppliers = _rows(client.table("suppliers").select("*").order("name").limit(4000).execute())
    products = _rows(
        client.table("products")
        .select("id,supplier_id,name,source_image_url,raw_data")
        .limit(10000).execute()
    )
    activations = _rows(
        client.table("activation_solutions")
        .select("id,supplier_id,name,source_image_url,raw_data")
        .limit(10000).execute()
    )
    venues = _rows(client.table("venues").select("id,name,operator_id").limit(10000).execute())
    try:
        imports = _rows(
            client.table("imports")
            .select("supplier_id,destination_base,document_type,classification")
            .limit(10000).execute()
        )
    except Exception:
        imports = []

    recognized_ids = _recognized_supplier_ids(products, activations, imports)
    product_counts = _count_by(products, "supplier_id")
    activation_counts = _count_by(activations, "supplier_id")

    first_product: dict[str, dict] = {}
    for row in products:
        supplier_id = str(row.get("supplier_id") or "")
        if supplier_id and supplier_id not in first_product:
            first_product[supplier_id] = row
    first_activation: dict[str, dict] = {}
    for row in activations:
        supplier_id = str(row.get("supplier_id") or "")
        if supplier_id and supplier_id not in first_activation:
            first_activation[supplier_id] = row

    venue_names: dict[str, list[str]] = {}
    for venue in venues:
        operator_id = str(venue.get("operator_id") or "")
        if operator_id:
            venue_names.setdefault(operator_id, []).append(str(venue.get("name") or ""))

    result = []
    for supplier in suppliers:
        supplier_id = str(supplier.get("id") or "")
        # Regra definitiva: existir tecnicamente em suppliers ou operar um local não basta.
        # O cadastro precisa ter sido reconhecido como fornecedor em um upload, ou aparecer
        # vinculado a produto/ativação extraídos do repertório.
        if not supplier_id:
            continue
        if supplier_id not in recognized_ids and supplier.get("recognized_as_supplier") is not True:
            continue

        linked_names = venue_names.get(supplier_id, [])
        item = dict(supplier)
        item["products_count"] = product_counts.get(supplier_id, 0)
        item["activations_count"] = activation_counts.get(supplier_id, 0)
        item["venues_count"] = len(linked_names)
        item["linked_venue_names"] = linked_names
        item["coverage_level"] = _coverage_level(item)
        item["_representative_product"] = first_product.get(supplier_id)
        item["_representative_activation"] = first_activation.get(supplier_id)
        result.append(item)
    return result


def _table_key(page: int, rows: list[dict]) -> str:
    ids = "|".join(str(row.get("id") or "") for row in rows)
    return f"suppliers_table_{page}_{hashlib.sha1(ids.encode()).hexdigest()[:10]}"


page_header(
    "Fornecedores",
    "Base de parceiros reconhecidos nos uploads da NAVE. Um local pode ter um fornecedor/operador relacionado, mas o local nunca entra nesta lista apenas por existir em Locais e espaços.",
)
client = get_nave_client()
try:
    suppliers = _load_suppliers(client)
except Exception as exc:
    st.error(f"A NAVE não conseguiu carregar os fornecedores: {exc}")
    st.stop()

active_count = sum(1 for row in suppliers if row.get("is_active") is not False)
inactive_count = len(suppliers) - active_count
global_scope = sum(1 for row in suppliers if row.get("coverage_level") == "Global")
city_mapped = sum(1 for row in suppliers if _supplier_city_presence(row))
category_mapped = sum(1 for row in suppliers if _list_values(row.get("supplier_categories")))
metric_cols = st.columns(5)
metric_cols[0].metric("Ativos", active_count)
metric_cols[1].metric("Inativos", inactive_count)
metric_cols[2].metric("Cobertura global", global_scope)
metric_cols[3].metric("Com cidades mapeadas", city_mapped)
metric_cols[4].metric("Com categoria mapeada", category_mapped)
st.divider()

city_options = _supplier_city_options(suppliers)
category_options = sorted({
    category
    for row in suppliers
    for category in _list_values(row.get("supplier_categories"))
    if category
}, key=_normalized)
search_col, status_col, category_col, city_col, coverage_col, per_page_col = st.columns([1.55, 0.8, 1.15, 1.05, 1.0, 0.6])
with search_col:
    search = st.text_input("Buscar fornecedor", placeholder="Nome, categoria, especialidade, serviço, marca ou cidade...")
with status_col:
    selected_status = st.selectbox("Status", ["Ativos", "Inativos", "Todos"], index=0)
with category_col:
    selected_category = st.selectbox("Categoria", ["Todas", *category_options])
with city_col:
    selected_city = st.selectbox("Cidade", ["Todas", *city_options.keys()])
with coverage_col:
    coverage = st.selectbox("Cobertura macro", ["Todos", "Global", "Nacional", "Regional / local", "Somente base cadastrada", "Cobertura não cadastrada"])
with per_page_col:
    page_size = st.selectbox("Itens por página", [25, 50, 100], index=0)

tokens = [token for token in search.casefold().split() if token]
selected_city_key = city_options.get(selected_city)
filtered = []
for row in suppliers:
    is_active = row.get("is_active") is not False
    if selected_status == "Ativos" and not is_active:
        continue
    if selected_status == "Inativos" and is_active:
        continue
    if coverage != "Todos" and row.get("coverage_level") != coverage:
        continue
    if selected_category != "Todas" and selected_category not in _list_values(row.get("supplier_categories")):
        continue
    if selected_city_key:
        wanted_city, wanted_state = selected_city_key
        presences = _supplier_city_presence(row)
        city_match = False
        for (city_key, state_key), _presence in presences.items():
            if city_key != wanted_city:
                continue
            if wanted_state and state_key and wanted_state != state_key:
                continue
            city_match = True
            break
        if not city_match:
            continue
    haystack = " ".join(
        str(row.get(field) or "")
        for field in (
            "name", "contact_name", "email", "phone", "base_city", "base_state",
            "served_states", "served_cities", "coverage_notes", "linked_venue_names",
            "supplier_categories", "specialties", "services_offered", "client_brands",
            "market_segments", "differentiators",
        )
    ).casefold()
    if tokens and not all(token in haystack for token in tokens):
        continue
    filtered.append(row)

st.caption(f"{len(filtered)} fornecedor(es) encontrado(s)")
pages = max(1, math.ceil(len(filtered) / page_size))
page_key = "suppliers_page_v28034"
page = max(1, min(int(st.session_state.get(page_key, 1) or 1), pages))
st.session_state[page_key] = page
prev_col, info_col, next_col = st.columns([1, 4, 1])
with prev_col:
    if st.button("← Anterior", disabled=page <= 1, width="stretch", key="supplier_prev"):
        st.session_state[page_key] = page - 1
        st.rerun()
with info_col:
    st.caption(f"Página {page} de {pages}")
with next_col:
    if st.button("Próxima →", disabled=page >= pages, width="stretch", key="supplier_next"):
        st.session_state[page_key] = page + 1
        st.rerun()

start = (page - 1) * page_size
visible = filtered[start:start + page_size]
if not visible:
    st.info("Nenhum fornecedor encontrado com estes filtros.")
    st.stop()

supplier_ids = [str(row.get("id") or "") for row in visible]
supplier_media = fetch_media_assets_batch(client, "supplier", supplier_ids)
product_ids = [
    str((row.get("_representative_product") or {}).get("id") or "")
    for row in visible
]
activation_ids = [
    str((row.get("_representative_activation") or {}).get("id") or "")
    for row in visible
]
product_media = fetch_media_assets_batch(client, "product", product_ids)
activation_media = fetch_media_assets_batch(client, "activation", activation_ids)

table_rows = []
for row in visible:
    supplier_id = str(row.get("id") or "")
    cover = None
    try:
        cover = primary_image_url(client, "supplier", row, supplier_media.get(supplier_id, []))
    except Exception:
        cover = None

    # Se o fornecedor não tiver logo/capa própria, usa uma imagem validada do seu
    # repertório apenas como capa representativa da lista.
    if not cover:
        representative = row.get("_representative_product") or {}
        rep_id = str(representative.get("id") or "")
        if rep_id:
            try:
                cover = primary_image_url(client, "product", representative, product_media.get(rep_id, []))
            except Exception:
                cover = None
    if not cover:
        representative = row.get("_representative_activation") or {}
        rep_id = str(representative.get("id") or "")
        if rep_id:
            try:
                cover = primary_image_url(client, "activation", representative, activation_media.get(rep_id, []))
            except Exception:
                cover = None

    row_data = {
        "_id": supplier_id,
        "Capa": clean_cover_value(cover),
        "Fornecedor": str(row.get("name") or ""),
        "Status": "Ativo" if row.get("is_active") is not False else "Inativo",
        "Categoria": " · ".join(_list_values(row.get("supplier_categories"))[:2]),
        "Cobertura": str(row.get("coverage_level") or ""),
        "Base": _base_label(row),
        "Brindes": int(row.get("products_count") or 0),
        "Ativações": int(row.get("activations_count") or 0),
        "Locais relacionados": int(row.get("venues_count") or 0),
    }
    if selected_city_key:
        wanted_city, wanted_state = selected_city_key
        presence_label = ""
        for (city_key, state_key), presence in _supplier_city_presence(row).items():
            if city_key == wanted_city and (not wanted_state or not state_key or state_key == wanted_state):
                presence_label = presence
                break
        row_data["Presença na cidade"] = presence_label
    table_rows.append(row_data)

table_df = pd.DataFrame(table_rows)
event = st.dataframe(
    table_df,
    hide_index=True,
    width="stretch",
    row_height=64,
    on_select="rerun",
    selection_mode="single-row",
    key=_table_key(page, visible),
    column_config={
        "_id": None,
        "Capa": st.column_config.ImageColumn("Capa", width="small"),
    },
)
selected_rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])
valid_selected = [
    position for position in selected_rows
    if isinstance(position, int) and 0 <= position < len(visible)
]

if valid_selected:
    selected_suppliers = [visible[position] for position in valid_selected]
    active_selected = [row for row in selected_suppliers if row.get("is_active") is not False]
    inactive_selected = [row for row in selected_suppliers if row.get("is_active") is False]

    with st.expander("Disponibilidade do fornecedor", expanded=False):
        st.caption(
            "Fornecedores inativos permanecem integralmente na base e podem ser "
            "consultados ou reativados, mas não entram nas recomendações de Brindes "
            "e Ativações enquanto estiverem inativos."
        )
        reason = st.text_input(
            "Motivo da inativação (opcional)",
            key=f"supplier_inactive_reason_{_table_key(page, visible)}",
            placeholder="Ex.: bloqueado pelo grupo, problema comercial, não homologado...",
        )
        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button(
                f"Inativar selecionado(s) ({len(active_selected)})",
                disabled=not active_selected,
                width="stretch",
                key=f"supplier_inactivate_{_table_key(page, visible)}",
            ):
                now = datetime.now(timezone.utc).isoformat()
                for supplier in active_selected:
                    client.table("suppliers").update({
                        "is_active": False,
                        "inactive_reason": reason.strip() or None,
                        "status_updated_at": now,
                    }).eq("id", str(supplier.get("id") or "")).execute()
                st.success(f"{len(active_selected)} fornecedor(es) inativado(s).")
                st.rerun()
        with action_cols[1]:
            if st.button(
                f"Reativar selecionado(s) ({len(inactive_selected)})",
                disabled=not inactive_selected,
                width="stretch",
                key=f"supplier_reactivate_{_table_key(page, visible)}",
            ):
                now = datetime.now(timezone.utc).isoformat()
                for supplier in inactive_selected:
                    client.table("suppliers").update({
                        "is_active": True,
                        "inactive_reason": None,
                        "status_updated_at": now,
                    }).eq("id", str(supplier.get("id") or "")).execute()
                st.success(f"{len(inactive_selected)} fornecedor(es) reativado(s).")
                st.rerun()

if not valid_selected:
    st.caption("Selecione uma linha para abrir os dados completos, acervo, edição e projetos relacionados.")
    st.stop()
position = valid_selected[0]
if not isinstance(position, int) or position < 0 or position >= len(visible):
    st.stop()
selected = visible[position]
st.divider()
render_detail(client, "supplier", str(selected.get("id") or ""), record_override=selected)
