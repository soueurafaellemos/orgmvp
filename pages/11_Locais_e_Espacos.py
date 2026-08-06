from __future__ import annotations

import importlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from knowledge_details import render_complete_record
from media_library import create_signed_media_url
from venue_types import (
    ALL_VENUE_TYPES,
    UNDEFINED_VENUE_TYPE,
    display_venue_type,
    filter_records_by_type,
    normalize_venue_type,
    safe_type_from_record,
    venue_group,
    venue_type_options,
)


st.set_page_config(
    page_title="Locais e espaços | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
apply_nave_branding()


TYPE_COLORS = {
    "Galpão / Fábrica": "#E8EDF7",
    "Centro de Convenções / Pavilhão": "#DFF7FA",
    "Espaço de Eventos": "#EEF1F7",
    "Casas de Show": "#F6EAF1",
    "Teatros / Auditórios": "#EDEAF7",
    "Hotéis": "#E8F4F0",
    "Bares": "#FFF2DA",
    "Restaurantes": "#FFF0E8",
    "Galerias de Arte": "#F2ECF8",
    "Estádios": "#EAF4E5",
    UNDEFINED_VENUE_TYPE: "#EEF0F4",
}


ASSET_TYPE_LABELS = {
    "main_image": "Imagem principal",
    "gallery_image": "Imagem",
    "floor_plan": "Planta baixa",
    "elevation": "Elevação",
    "access_map": "Mapa de acesso",
    "technical_sheet": "Ficha técnica",
}
PLAN_ASSET_TYPES = {"floor_plan", "elevation", "access_map", "technical_sheet"}
DOCUMENT_MIME_PREFIXES = ("application/", "text/")


def _is_http_url(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith("http://") or text.startswith("https://")


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (str(item.get("kind") or ""), str(item.get("url") or "").strip())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _scan_raw_data_urls(value: Any, *, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            found.extend(_scan_raw_data_urls(item, path=next_path))
        return found
    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            next_path = f"{path}[{index}]" if path else str(index)
            found.extend(_scan_raw_data_urls(item, path=next_path))
        return found
    if _is_http_url(value):
        found.append((path.casefold(), str(value).strip()))
    return found


def _asset_label(asset: dict[str, Any], fallback: str) -> str:
    asset_type = str(asset.get("asset_type") or "").strip()
    file_name = str(asset.get("file_name") or "").strip()
    if file_name:
        return file_name
    return ASSET_TYPE_LABELS.get(asset_type, fallback)


def _resolve_asset_url(client: Client, asset: dict[str, Any]) -> str | None:
    try:
        return create_signed_media_url(client, asset)
    except Exception:
        external = str(asset.get("external_url") or "").strip()
        return external or None


def _media_for_record(record: dict[str, Any], media_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target = str(record.get("id") or "")
    assets = [
        dict(asset)
        for asset in media_rows
        if str(asset.get("entity_id") or "") == target
    ]
    def _sort_key(asset: dict[str, Any]) -> tuple[int, int, str]:
        primary = 0 if bool(asset.get("is_primary")) else 1
        sort_order = asset.get("sort_order")
        try:
            order = int(float(sort_order))
        except (TypeError, ValueError):
            order = 9999
        created = str(asset.get("created_at") or "")
        return (primary, order, created)
    return sorted(assets, key=_sort_key)


def _build_record_gallery(record: dict[str, Any], media_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    client = _database_client()
    images: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []

    source_image = str(record.get("source_image_url") or "").strip()
    if source_image:
        images.append({"kind": "image", "label": "Imagem de origem", "url": source_image, "source": "Cadastro do local"})

    for asset in _media_for_record(record, media_rows):
        url = _resolve_asset_url(client, asset)
        if not url:
            continue
        mime_type = str(asset.get("mime_type") or "").strip().casefold()
        asset_type = str(asset.get("asset_type") or "").strip()
        label = _asset_label(asset, "Documento associado")
        source = "Acervo da NAVE"
        item = {"label": label, "url": url, "source": source, "asset_type": asset_type, "mime_type": mime_type}
        if mime_type.startswith("image/"):
            if asset_type in PLAN_ASSET_TYPES:
                plans.append({"kind": "plan", **item})
            else:
                images.append({"kind": "image", **item})
        else:
            kind = "plan_document" if asset_type in PLAN_ASSET_TYPES else "document"
            documents.append({"kind": kind, **item})

    raw_data = _json_dict(record.get("raw_data"))
    for raw_key, url in _scan_raw_data_urls(raw_data):
        if url == source_image:
            continue
        label = raw_key.replace("_", " ").replace(".", " / ").strip(" /") or "Material associado"
        item = {"label": label.capitalize(), "url": url, "source": "Dados estruturados"}
        if any(term in raw_key for term in ("planta", "floor_plan", "floorplan", "mapa", "elevation")):
            plans.append({"kind": "plan", **item})
        elif any(term in raw_key for term in ("ficha", "technical_sheet", "brochure", "pdf", "documento")):
            documents.append({"kind": "document", **item})
        elif any(term in raw_key for term in ("foto", "photo", "image", "imagem")):
            images.append({"kind": "image", **item})

    return {
        "images": _dedupe_items(images),
        "plans": _dedupe_items(plans),
        "documents": _dedupe_items(documents),
    }


def _render_visual_gallery(title: str, items: list[dict[str, Any]], *, empty_message: str) -> None:
    st.markdown(f"#### {title}")
    if not items:
        st.caption(empty_message)
        return
    lead = items[0]
    st.image(lead["url"], caption=lead.get("label") or title, use_container_width=True)
    if len(items) > 1:
        cols = st.columns(2)
        for index, item in enumerate(items[1:]):
            with cols[index % 2]:
                st.image(item["url"], caption=item.get("label") or title, use_container_width=True)


def _render_document_links(title: str, items: list[dict[str, Any]], *, empty_message: str) -> None:
    st.markdown(f"#### {title}")
    if not items:
        st.caption(empty_message)
        return
    for item in items:
        label = str(item.get("label") or "Documento")
        source = str(item.get("source") or "")
        suffix = f" · {source}" if source else ""
        st.markdown(f"- [{label}]({item['url']}){suffix}")


def _mapping_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        return {}


def _flatten_mapping(
    value: Any,
    *,
    prefix: str = "",
) -> dict[str, str]:
    result: dict[str, str] = {}
    mapping = _mapping_to_dict(value)
    for key, item in mapping.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        nested = _mapping_to_dict(item)
        if nested:
            result.update(_flatten_mapping(nested, prefix=path))
            continue
        if item is not None and str(item).strip():
            result[path.casefold()] = str(item).strip()
    return result


def _client_from_existing_runtime() -> Client | None:
    """Reuse the connection already established by the NAVE when available."""
    for key in (
        "database_client",
        "supabase_client",
        "db_client",
        "client",
    ):
        try:
            candidate = st.session_state.get(key)
        except Exception:
            candidate = None
        if candidate is not None and hasattr(candidate, "table"):
            return candidate

    module_function_candidates = {
        "runtime_ui": (
            "get_database_client",
            "get_supabase_client",
            "database_client",
        ),
        "supabase_db": (
            "get_database_client",
            "get_supabase_client",
            "create_database_client",
            "create_supabase_client",
            "database_client",
        ),
    }
    for module_name, function_names in module_function_candidates.items():
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        for function_name in function_names:
            candidate = getattr(module, function_name, None)
            if candidate is None:
                continue
            if hasattr(candidate, "table"):
                return candidate
            if callable(candidate):
                try:
                    resolved = candidate()
                except TypeError:
                    continue
                except Exception:
                    continue
                if resolved is not None and hasattr(resolved, "table"):
                    return resolved
    return None


def _secret_pair() -> tuple[str, str]:
    """Resolve the Supabase credentials without assuming one TOML layout."""
    flat: dict[str, str] = {}
    try:
        flat.update(_flatten_mapping(st.secrets))
    except Exception:
        pass

    for key, value in os.environ.items():
        if value and str(value).strip():
            flat.setdefault(str(key).casefold(), str(value).strip())

    url_names = (
        "supabase_url",
        "url",
        "project_url",
        "api_url",
    )
    key_names = (
        "supabase_service_role_key",
        "supabase_service_key",
        "service_role_key",
        "supabase_key",
        "supabase_anon_key",
        "anon_key",
        "api_key",
        "key",
    )

    def find_value(names: tuple[str, ...]) -> str:
        # Prefer an exact top-level key, then nested paths such as
        # connections.supabase.url or database.supabase.key.
        for name in names:
            direct = flat.get(name.casefold())
            if direct:
                return direct
        for name in names:
            suffix = f".{name.casefold()}"
            for path, value in flat.items():
                if path.endswith(suffix) and value:
                    return value
        return ""

    return find_value(url_names), find_value(key_names)


@st.cache_resource(show_spinner=False)
def _database_client() -> Client:
    existing = _client_from_existing_runtime()
    if existing is not None:
        return existing

    url, key = _secret_pair()
    if not url or not key:
        raise RuntimeError(
            "A conexão já usada pela NAVE não foi localizada e as "
            "credenciais do Supabase não puderam ser resolvidas nos Secrets."
        )
    return create_client(url, key)

def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


@st.cache_data(ttl=120, show_spinner=False)
def _load_venues() -> list[dict[str, Any]]:
    client = _database_client()
    response = (
        client.table("venues")
        .select("*")
        .limit(5000)
        .execute()
    )
    records = [dict(record) for record in (response.data or [])]

    # Some historical schemas do not have archived_at. Filter only when the
    # field exists, and sort in Python so the query does not depend on columns
    # that may differ between NAVE versions.
    records = [
        record
        for record in records
        if not record.get("archived_at")
    ]
    return sorted(
        records,
        key=lambda record: str(record.get("name") or "").casefold(),
    )


@st.cache_data(ttl=120, show_spinner=False)
def _load_media() -> list[dict[str, Any]]:
    client = _database_client()
    try:
        response = (
            client.table("media_assets")
            .select("*")
            .eq("entity_type", "venue")
            .limit(10000)
            .execute()
        )
        return [dict(record) for record in (response.data or [])]
    except Exception:
        # The venue list must continue working even when an older database
        # version has no generic media table yet.
        return []

def _media_index(
    media_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for asset in media_rows:
        entity_id = str(asset.get("entity_id") or "")
        if not entity_id:
            continue
        summary = index.setdefault(
            entity_id,
            {
                "count": 0,
                "has_image": False,
                "has_plan": False,
                "cover_url": None,
            },
        )
        summary["count"] += 1
        asset_type = str(asset.get("asset_type") or "")
        mime_type = str(asset.get("mime_type") or "")
        external_url = str(asset.get("external_url") or "").strip()
        is_image = mime_type.startswith("image/") or asset_type in {
            "main_image",
            "gallery_image",
        }
        is_plan = asset_type in {
            "floor_plan",
            "elevation",
            "access_map",
            "technical_sheet",
        }
        summary["has_image"] = summary["has_image"] or is_image
        summary["has_plan"] = summary["has_plan"] or is_plan
        if (
            not summary["cover_url"]
            and external_url
            and (
                bool(asset.get("is_primary"))
                or asset_type == "main_image"
                or is_image
            )
        ):
            summary["cover_url"] = external_url
    return index


def _has_photo(record: dict[str, Any], media: dict[str, Any]) -> bool:
    if media.get("has_image"):
        return True
    if str(record.get("source_image_url") or "").strip():
        return True
    raw_data = _json_dict(record.get("raw_data"))
    for key, value in raw_data.items():
        key_text = str(key).casefold()
        if any(term in key_text for term in ("foto", "photo", "image")):
            if value:
                return True
    return False


def _has_plan(record: dict[str, Any], media: dict[str, Any]) -> bool:
    if media.get("has_plan"):
        return True
    raw_data = _json_dict(record.get("raw_data"))
    for key, value in raw_data.items():
        key_text = str(key).casefold()
        if any(
            term in key_text
            for term in (
                "planta",
                "floor_plan",
                "floorplan",
                "technical_sheet",
                "ficha_tecnica",
                "mapa_tecnico",
            )
        ) and value:
            return True
    return False


def _capacity(record: dict[str, Any]) -> int | None:
    values = []
    for field in (
        "standing_capacity",
        "seated_capacity",
        "auditorium_capacity",
        "capacity",
    ):
        try:
            value = record.get(field)
            if value is not None and str(value).strip():
                values.append(int(float(value)))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def _format_capacity(value: int | None) -> str:
    if value is None:
        return "Não informado"
    return f"{value:,}".replace(",", ".")


def _record_search_text(record: dict[str, Any]) -> str:
    fields = (
        record.get("name"),
        record.get("venue_type"),
        record.get("description"),
        record.get("city"),
        record.get("state"),
        record.get("neighborhood"),
        record.get("address"),
        record.get("tags"),
    )
    return " ".join(str(value or "") for value in fields).casefold()


def _type_badge(label: str) -> str:
    color = TYPE_COLORS.get(label, "#EEF0F4")
    return (
        '<span style="display:inline-block;padding:.32rem .62rem;'
        f'border-radius:999px;background:{color};color:#121B42;'
        'font-size:.73rem;font-weight:750;letter-spacing:.01em;">'
        f"{label}</span>"
    )


def _save_manual_type(
    record: dict[str, Any],
    selected_label: str,
) -> None:
    client = _database_client()
    previous_value = str(record.get("venue_type") or "").strip() or None
    new_value = (
        None
        if selected_label == UNDEFINED_VENUE_TYPE
        else selected_label
    )

    raw_data = _json_dict(record.get("raw_data"))
    if previous_value and not raw_data.get("venue_type_original"):
        raw_data["venue_type_original"] = previous_value
    raw_data["venue_type_classification"] = {
        "source": "manual",
        "manual": True,
        "previous_value": previous_value,
        "current_value": new_value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    (
        client.table("venues")
        .update(
            {
                "venue_type": new_value,
                "raw_data": raw_data,
            }
        )
        .eq("id", record["id"])
        .execute()
    )
    _load_venues.clear()


def _safe_classification_batch(
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    client = _database_client()
    updated = 0
    unchanged = 0

    for record in records:
        raw_data = _json_dict(record.get("raw_data"))
        classification = raw_data.get("venue_type_classification")
        if isinstance(classification, dict) and classification.get("manual"):
            unchanged += 1
            continue

        current = normalize_venue_type(record.get("venue_type"))
        if current:
            # Normalize only equivalent values. Never replace a valid type.
            if str(record.get("venue_type") or "").strip() == current:
                unchanged += 1
                continue
            suggested = current
        else:
            suggested = safe_type_from_record(record)

        if not suggested:
            unchanged += 1
            continue

        if not raw_data.get("venue_type_original"):
            original = str(record.get("venue_type") or "").strip()
            if original:
                raw_data["venue_type_original"] = original
        raw_data["venue_type_classification"] = {
            "source": "safe_exact_alias",
            "manual": False,
            "current_value": suggested,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        (
            client.table("venues")
            .update(
                {
                    "venue_type": suggested,
                    "raw_data": raw_data,
                }
            )
            .eq("id", record["id"])
            .execute()
        )
        updated += 1

    _load_venues.clear()
    return updated, unchanged


page_header(
    "Locais e espaços",
    (
        "Consulte espaços, capacidades, estruturas, imagens e materiais "
        "técnicos. O tipo organiza a busca sem excluir registros ainda "
        "não classificados."
    ),
)

try:
    venues = _load_venues()
    media_rows = _load_media()
except Exception as exc:
    st.error(
        "A NAVE não conseguiu carregar os locais. A página agora usa a "
        "mesma conexão do restante da plataforma; consulte os detalhes "
        "técnicos abaixo para identificar uma eventual restrição do banco."
    )
    with st.expander("Detalhes técnicos", expanded=True):
        st.code(f"{type(exc).__name__}: {exc}")
    st.stop()

media_by_venue = _media_index(media_rows)

total = len(venues)
typed = sum(bool(normalize_venue_type(row.get("venue_type"))) for row in venues)
undefined = total - typed
with_photo = sum(
    _has_photo(row, media_by_venue.get(str(row.get("id")), {}))
    for row in venues
)
with_plan = sum(
    _has_plan(row, media_by_venue.get(str(row.get("id")), {}))
    for row in venues
)

metric_cols = st.columns(4)
metric_cols[0].metric("Locais", total)
metric_cols[1].metric("Com tipo definido", typed)
metric_cols[2].metric("Tipo não definido", undefined)
metric_cols[3].metric("Com foto", with_photo)

st.markdown("### Encontrar um local")
filter_cols = st.columns([2.2, 1.8, 1.2, 1.2])
with filter_cols[0]:
    search = st.text_input(
        "Buscar",
        placeholder="Nome, bairro, cidade, estrutura ou palavra-chave",
    ).strip().casefold()
with filter_cols[1]:
    selected_type = st.selectbox(
        "Tipo de local",
        options=venue_type_options(include_all=True),
        index=0,
    )
with filter_cols[2]:
    selected_state = st.selectbox(
        "Estado",
        options=["Todos"] + sorted(
            {
                str(row.get("state") or "").strip()
                for row in venues
                if str(row.get("state") or "").strip()
            }
        ),
    )
with filter_cols[3]:
    selected_media = st.selectbox(
        "Acervo",
        options=[
            "Todos",
            "Com foto",
            "Sem foto",
            "Com planta",
            "Sem planta",
        ],
    )

filtered = filter_records_by_type(venues, selected_type)
if search:
    filtered = [
        row
        for row in filtered
        if search in _record_search_text(row)
    ]
if selected_state != "Todos":
    filtered = [
        row
        for row in filtered
        if str(row.get("state") or "").strip() == selected_state
    ]
if selected_media != "Todos":
    selected_rows = []
    for row in filtered:
        media = media_by_venue.get(str(row.get("id")), {})
        photo = _has_photo(row, media)
        plan = _has_plan(row, media)
        keep = {
            "Com foto": photo,
            "Sem foto": not photo,
            "Com planta": plan,
            "Sem planta": not plan,
        }[selected_media]
        if keep:
            selected_rows.append(row)
    filtered = selected_rows

st.caption(
    f"{len(filtered)} resultado(s). Locais sem classificação continuam "
    "disponíveis em Todos e em Tipo não definido."
)

table_rows = []
for row in filtered:
    venue_id = str(row.get("id") or "")
    media = media_by_venue.get(venue_id, {})
    cover = (
        media.get("cover_url")
        or str(row.get("source_image_url") or "").strip()
        or None
    )
    label = display_venue_type(row.get("venue_type"))
    table_rows.append(
        {
            "_id": venue_id,
            "Capa": cover,
            "Local": str(row.get("name") or "Sem nome"),
            "Tipo": label,
            "Grupo": venue_group(row.get("venue_type")),
            "Cidade": str(row.get("city") or "Não informado"),
            "Estado": str(row.get("state") or ""),
            "Capacidade": _format_capacity(_capacity(row)),
            "Foto": "Sim" if _has_photo(row, media) else "Não",
            "Planta": "Sim" if _has_plan(row, media) else "Não",
        }
    )

table_df = pd.DataFrame(table_rows)
if table_df.empty:
    st.info("Nenhum local corresponde aos filtros selecionados.")
    selected_record = None
else:
    event = st.dataframe(
        table_df.drop(columns=["_id"]),
        hide_index=True,
        width="stretch",
        height=min(620, 86 + len(table_df) * 36),
        on_select="rerun",
        selection_mode="single-row",
        key="nave_venue_type_table",
        column_config={
            "Capa": st.column_config.ImageColumn(
                "Capa",
                width="small",
                help="Imagem principal quando houver URL pública disponível.",
            ),
            "Local": st.column_config.TextColumn("Local", width="large"),
            "Tipo": st.column_config.TextColumn("Tipo", width="medium"),
            "Grupo": st.column_config.TextColumn("Grupo", width="medium"),
            "Cidade": st.column_config.TextColumn("Cidade", width="medium"),
            "Estado": st.column_config.TextColumn("UF", width="small"),
            "Capacidade": st.column_config.TextColumn(
                "Capacidade máxima",
                width="small",
            ),
            "Foto": st.column_config.TextColumn("Foto", width="small"),
            "Planta": st.column_config.TextColumn("Planta", width="small"),
        },
    )

    selected_rows = event.selection.rows if event else []
    selected_record = None
    if selected_rows:
        selected_id = str(table_df.iloc[selected_rows[0]]["_id"])
        selected_record = next(
            (
                row
                for row in venues
                if str(row.get("id") or "") == selected_id
            ),
            None,
        )

if selected_record:
    st.divider()
    current_label = display_venue_type(selected_record.get("venue_type"))
    title_cols = st.columns([4, 1.4])
    with title_cols[0]:
        st.markdown(f"## {selected_record.get('name') or 'Local'}")
        st.markdown(_type_badge(current_label), unsafe_allow_html=True)
        location = " · ".join(
            part
            for part in (
                str(selected_record.get("neighborhood") or "").strip(),
                str(selected_record.get("city") or "").strip(),
                str(selected_record.get("state") or "").strip(),
            )
            if part
        )
        if location:
            st.caption(location)
    with title_cols[1]:
        media = media_by_venue.get(str(selected_record.get("id")), {})
        st.metric("Materiais associados", int(media.get("count") or 0))

    with st.expander("Editar tipo de local", expanded=False):
        options = venue_type_options()
        current_index = (
            options.index(current_label)
            if current_label in options
            else options.index(UNDEFINED_VENUE_TYPE)
        )
        selected_label = st.selectbox(
            "Tipo de local",
            options=options,
            index=current_index,
            key=f"venue_type_edit_{selected_record['id']}",
        )
        st.caption(
            "Tipo não definido mantém o local na base e nas recomendações "
            "gerais. A escolha manual fica registrada e tem prioridade."
        )
        if st.button(
            "Salvar tipo",
            key=f"venue_type_save_{selected_record['id']}",
        ):
            try:
                _save_manual_type(selected_record, selected_label)
                st.success("Tipo do local atualizado.")
                st.rerun()
            except Exception as exc:
                st.error("Não foi possível salvar o tipo do local.")
                with st.expander("Detalhes técnicos"):
                    st.code(str(exc))

    gallery = _build_record_gallery(selected_record, media_rows)
    visual_count = len(gallery["images"])
    plan_count = len(gallery["plans"])
    document_count = len(gallery["documents"])

    st.markdown("### Conteúdos do local")
    info_cols = st.columns(3)
    info_cols[0].metric("Imagens", visual_count)
    info_cols[1].metric("Plantas e mapas", plan_count)
    info_cols[2].metric("Documentos", document_count)

    details_tab, gallery_tab, docs_tab = st.tabs(
        [
            "Ficha completa",
            "Galeria visual",
            "Plantas e documentos",
        ]
    )
    with details_tab:
        render_complete_record("venue", selected_record)
    with gallery_tab:
        _render_visual_gallery(
            "Galeria de imagens",
            gallery["images"],
            empty_message=(
                "Nenhuma imagem pública foi encontrada para este local ainda."
            ),
        )
        st.markdown("---")
        _render_visual_gallery(
            "Plantas, mapas e peças técnicas em imagem",
            gallery["plans"],
            empty_message=(
                "Nenhuma planta ou mapa em formato de imagem foi associado até o momento."
            ),
        )
    with docs_tab:
        _render_document_links(
            "Documentos associados",
            gallery["documents"],
            empty_message=(
                "Nenhum documento associado foi localizado para este local."
            ),
        )
        if selected_record.get("source_file"):
            st.markdown("#### Origem do cadastro")
            st.markdown(
                f"- Arquivo de origem: **{selected_record.get('source_file')}**"
            )
            if selected_record.get("source_page") not in (None, ""):
                st.markdown(
                    f"- Página de origem: **{selected_record.get('source_page')}**"
                )
else:
    st.info("Selecione um local na tabela para abrir a ficha completa, a galeria visual e os documentos associados.")

with st.expander("Classificar registros existentes com correspondência segura"):
    st.write(
        "A NAVE analisa somente campos explícitos de categoria e aplica um "
        "tipo quando encontra uma correspondência exata. Nome e descrição "
        "não são usados para adivinhar. Registros ambíguos permanecem como "
        "Tipo não definido. Classificações manuais não são substituídas."
    )
    if st.button("Aplicar classificação segura", key="safe_venue_type_batch"):
        try:
            with st.spinner("Classificando os registros seguros..."):
                updated, unchanged = _safe_classification_batch(venues)
            st.success(
                f"{updated} registro(s) classificados. "
                f"{unchanged} mantido(s) sem alteração."
            )
            st.rerun()
        except Exception as exc:
            st.error("Não foi possível concluir a classificação segura.")
            with st.expander("Detalhes técnicos"):
                st.code(str(exc))
