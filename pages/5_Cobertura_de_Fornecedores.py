from __future__ import annotations

import hashlib
import math
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
from supplier_visibility import is_visible_supplier


st.set_page_config(page_title="Fornecedores | NAVE by VOE", page_icon=NAVE_APP_ICON, layout="wide")
enforce_existing_app_access()
apply_nave_branding()


def _rows(response: Any) -> list[dict]:
    return list(getattr(response, "data", None) or [])


def _count_by(rows: list[dict], field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "")
        if value:
            result[value] = result.get(value, 0) + 1
    return result


def _coverage_level(row: dict) -> str:
    if row.get("serves_nationally") is True:
        return "Nacional"
    if row.get("served_states") or row.get("served_cities") or row.get("local_team_locations"):
        return "Regional / local"
    if row.get("base_city") or row.get("base_state"):
        return "Somente base cadastrada"
    return "Cobertura não cadastrada"


def _base_label(row: dict) -> str:
    return ", ".join(str(row.get(field) or "").strip() for field in ("base_city", "base_state") if str(row.get(field) or "").strip())


def _load_suppliers(client: Any) -> list[dict]:
    suppliers = _rows(client.table("suppliers").select("*").order("name").limit(4000).execute())
    products = _rows(client.table("products").select("supplier_id").limit(10000).execute())
    activations = _rows(client.table("activation_solutions").select("supplier_id").limit(10000).execute())
    venues = _rows(client.table("venues").select("id,name,operator_id").limit(10000).execute())

    product_counts = _count_by(products, "supplier_id")
    activation_counts = _count_by(activations, "supplier_id")
    venue_names: dict[str, list[str]] = {}
    for venue in venues:
        operator_id = str(venue.get("operator_id") or "")
        if operator_id:
            venue_names.setdefault(operator_id, []).append(str(venue.get("name") or ""))

    result = []
    for supplier in suppliers:
        supplier_id = str(supplier.get("id") or "")
        linked_names = venue_names.get(supplier_id, [])
        products_count = product_counts.get(supplier_id, 0)
        activations_count = activation_counts.get(supplier_id, 0)
        if not is_visible_supplier(
            supplier,
            linked_venue_names=linked_names,
            products_count=products_count,
            activations_count=activations_count,
        ):
            continue
        item = dict(supplier)
        item["products_count"] = products_count
        item["activations_count"] = activations_count
        item["venues_count"] = len(linked_names)
        item["linked_venue_names"] = linked_names
        item["coverage_level"] = _coverage_level(item)
        result.append(item)
    return result


def _table_key(page: int, rows: list[dict]) -> str:
    ids = "|".join(str(row.get("id") or "") for row in rows)
    return f"suppliers_table_{page}_{hashlib.sha1(ids.encode()).hexdigest()[:10]}"


page_header(
    "Fornecedores",
    "Base de parceiros da NAVE. Locais podem ter um fornecedor/operador relacionado, mas um local não se transforma em fornecedor.",
)
client = get_nave_client()
try:
    suppliers = _load_suppliers(client)
except Exception as exc:
    st.error(f"A NAVE não conseguiu carregar os fornecedores: {exc}")
    st.stop()

national = sum(1 for row in suppliers if row.get("coverage_level") == "Nacional")
regional = sum(1 for row in suppliers if row.get("coverage_level") == "Regional / local")
missing = sum(1 for row in suppliers if row.get("coverage_level") == "Cobertura não cadastrada")
metric_cols = st.columns(4)
metric_cols[0].metric("Fornecedores", len(suppliers))
metric_cols[1].metric("Cobertura nacional", national)
metric_cols[2].metric("Regional / local", regional)
metric_cols[3].metric("Sem cobertura cadastrada", missing)
st.divider()

search_col, coverage_col, per_page_col = st.columns([2, 1, 0.75])
with search_col:
    search = st.text_input("Buscar fornecedor", placeholder="Nome, contato, cidade, cobertura, produto ou solução...")
with coverage_col:
    coverage = st.selectbox("Cobertura", ["Todos", "Nacional", "Regional / local", "Somente base cadastrada", "Cobertura não cadastrada"])
with per_page_col:
    page_size = st.selectbox("Itens por página", [25, 50, 100], index=0)

tokens = [token for token in search.casefold().split() if token]
filtered = []
for row in suppliers:
    if coverage != "Todos" and row.get("coverage_level") != coverage:
        continue
    haystack = " ".join(
        str(row.get(field) or "")
        for field in (
            "name", "contact_name", "email", "phone", "base_city", "base_state",
            "served_states", "served_cities", "coverage_notes", "linked_venue_names",
        )
    ).casefold()
    if tokens and not all(token in haystack for token in tokens):
        continue
    filtered.append(row)

st.caption(f"{len(filtered)} fornecedor(es) encontrado(s)")
pages = max(1, math.ceil(len(filtered) / page_size))
page_key = "suppliers_page_v28032"
page = max(1, min(int(st.session_state.get(page_key, 1) or 1), pages))
st.session_state[page_key] = page
prev_col, info_col, next_col = st.columns([1, 4, 1])
with prev_col:
    if st.button("← Anterior", disabled=page <= 1, width="stretch", key="supplier_prev"):
        st.session_state[page_key] = page - 1; st.rerun()
with info_col:
    st.caption(f"Página {page} de {pages}")
with next_col:
    if st.button("Próxima →", disabled=page >= pages, width="stretch", key="supplier_next"):
        st.session_state[page_key] = page + 1; st.rerun()

start = (page - 1) * page_size
visible = filtered[start:start + page_size]
if not visible:
    st.info("Nenhum fornecedor encontrado com estes filtros.")
    st.stop()

media = fetch_media_assets_batch(client, "supplier", [str(row.get("id") or "") for row in visible])
table_rows = []
for row in visible:
    supplier_id = str(row.get("id") or "")
    try:
        cover = primary_image_url(client, "supplier", row, media.get(supplier_id, [])) or ""
    except Exception:
        cover = ""
    table_rows.append({
        "Capa": clean_cover_value(cover),
        "Fornecedor": str(row.get("name") or ""),
        "Cobertura": str(row.get("coverage_level") or ""),
        "Base": _base_label(row),
        "Brindes": int(row.get("products_count") or 0),
        "Ativações": int(row.get("activations_count") or 0),
        "Locais relacionados": int(row.get("venues_count") or 0),
    })

table_df = pd.DataFrame(table_rows)
event = st.dataframe(
    table_df,
    hide_index=True,
    width="stretch",
    row_height=64,
    on_select="rerun",
    selection_mode="single-row",
    key=_table_key(page, visible),
    column_config={"Capa": st.column_config.ImageColumn("Capa", width="small")},
)
selected_rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])
if not selected_rows:
    st.caption("Selecione uma linha para abrir os dados completos, acervo, edição e projetos relacionados.")
    st.stop()
position = selected_rows[0]
if not isinstance(position, int) or position < 0 or position >= len(visible):
    st.stop()
selected = visible[position]
st.divider()
render_detail(client, "supplier", str(selected.get("id") or ""), record_override=selected)
