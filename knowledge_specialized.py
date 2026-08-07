from __future__ import annotations

import json
import math
from typing import Any

import streamlit as st

from knowledge_details import (
    BOOLEAN_FIELDS,
    DECIMAL_SUFFIXES,
    DETAIL_SCHEMAS,
    INTEGER_FIELDS,
    INTERNAL_FIELDS,
    MONEY_FIELDS,
    WIDE_FIELDS,
    _is_missing,
    render_complete_record,
)
from knowledge_project_links import render_related_projects_panel
from nave_data_client import get_nave_client


ENTITY_CONFIG = {
    "product": {
        "table": "products",
        "title": "Brindes",
        "subtitle": "Explore, compare, consulte a ficha completa e mantenha o repertório de brindes da NAVE atualizado.",
        "category_field": "category",
        "card_fields": ("category", "material", "supplier_name"),
        "list_select": "id,supplier_id,name,category,description,material,sku,tags,source_image_url,raw_data",
    },
    "activation": {
        "table": "activation_solutions",
        "title": "Ativações",
        "subtitle": "Consulte ativações, soluções e experiências com contexto, acervo visual, ficha completa e histórico de projetos.",
        "category_field": "category",
        "card_fields": ("category", "client_brand", "project_name"),
        "list_select": "id,supplier_id,project_id,name,category,record_type,description,client_brand,project_name,event_name,tags,source_image_url,raw_data",
    },
}

LIST_FIELDS = {
    "tags",
    "included_items",
    "excluded_items",
    "missing_fields",
    "infrastructure_requirements",
    "restrictions",
    "rooms_or_areas",
}

NON_EDITABLE_FIELDS = INTERNAL_FIELDS | {
    "supplier_name",
    "media_count",
    "image_count",
    "document_count",
    "has_primary",
}

IMAGE_ASSET_TYPES = {"main_image", "gallery_image"}
DOCUMENT_ASSET_TYPES = {
    "floor_plan",
    "elevation",
    "access_map",
    "technical_sheet",
    "commercial_book",
    "presentation",
    "video",
    "external_link",
    "other",
}


def _rows(response: Any) -> list[dict]:
    return list(getattr(response, "data", None) or [])


def _category_value(entity_type: str, row: dict) -> str:
    if entity_type == "activation":
        return _text(row.get("category")) or _text(row.get("record_type"))
    return _text(row.get(ENTITY_CONFIG[entity_type]["category_field"]))


def _enrich_supplier_names(client: Any, rows: list[dict]) -> list[dict]:
    supplier_ids = sorted({str(row.get("supplier_id")) for row in rows if row.get("supplier_id")})
    if not supplier_ids:
        return rows
    try:
        response = client.table("suppliers").select("id,name").in_("id", supplier_ids).execute()
        names = {str(row.get("id")): str(row.get("name") or "") for row in _rows(response)}
        for row in rows:
            supplier_id = str(row.get("supplier_id") or "")
            if supplier_id and not row.get("supplier_name"):
                row["supplier_name"] = names.get(supplier_id)
    except Exception:
        pass
    return rows


def _archived_entity_ids(client: Any, entity_type: str) -> set[str]:
    try:
        response = (
            client.table("knowledge_curation_states")
            .select("entity_id")
            .eq("entity_type", entity_type)
            .eq("is_archived", True)
            .execute()
        )
        return {str(row.get("entity_id")) for row in _rows(response) if row.get("entity_id")}
    except Exception:
        return set()


def fetch_entities(client: Any, entity_type: str) -> list[dict]:
    config = ENTITY_CONFIG[entity_type]
    response = (
        client.table(config["table"])
        .select(config["list_select"])
        .order("name")
        .limit(4000)
        .execute()
    )
    rows = _enrich_supplier_names(client, _rows(response))
    archived = _archived_entity_ids(client, entity_type)
    return [row for row in rows if str(row.get("id") or "") not in archived]


def fetch_entity(client: Any, entity_type: str, entity_id: str) -> dict | None:
    response = (
        client.table(ENTITY_CONFIG[entity_type]["table"])
        .select("*")
        .eq("id", entity_id)
        .limit(1)
        .execute()
    )
    rows = _enrich_supplier_names(client, _rows(response))
    return rows[0] if rows else None


def _signed_url_value(response: Any) -> str | None:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
    return (
        getattr(response, "signedURL", None)
        or getattr(response, "signedUrl", None)
        or getattr(response, "signed_url", None)
    )


def asset_url(client: Any, asset: dict) -> str | None:
    external = str(asset.get("external_url") or "").strip()
    if external:
        return external
    bucket = str(asset.get("storage_bucket") or "").strip()
    path = str(asset.get("storage_path") or "").strip()
    if not bucket or not path:
        return None
    try:
        return _signed_url_value(client.storage.from_(bucket).create_signed_url(path, 3600))
    except Exception:
        return None


def fetch_media_assets(client: Any, entity_type: str, entity_id: str) -> list[dict]:
    response = (
        client.table("media_assets")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .order("is_primary", desc=True)
        .order("sort_order")
        .order("created_at")
        .execute()
    )
    return _rows(response)


def fetch_media_assets_batch(client: Any, entity_type: str, entity_ids: list[str]) -> dict[str, list[dict]]:
    clean_ids = [entity_id for entity_id in entity_ids if entity_id]
    if not clean_ids:
        return {}
    try:
        response = (
            client.table("media_assets")
            .select("*")
            .eq("entity_type", entity_type)
            .in_("entity_id", clean_ids)
            .order("is_primary", desc=True)
            .order("sort_order")
            .execute()
        )
    except Exception:
        return {}
    grouped: dict[str, list[dict]] = {}
    for asset in _rows(response):
        grouped.setdefault(str(asset.get("entity_id") or ""), []).append(asset)
    return grouped


def _fallback_image(record: dict) -> str | None:
    candidates: list[Any] = [record.get("source_image_url")]
    raw = record.get("raw_data")
    if isinstance(raw, dict):
        for key in (
            "source_image_url",
            "visual_crop_url",
            "crop_url",
            "image_url",
            "full_slide_url",
            "slide_image_url",
        ):
            candidates.append(raw.get(key))
    for value in candidates:
        if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
            return value.strip()
    return None


def primary_image_url(client: Any, entity_type: str, record: dict, assets: list[dict] | None = None) -> str | None:
    assets = assets if assets is not None else fetch_media_assets(client, entity_type, str(record.get("id") or ""))
    image_assets = [asset for asset in assets if asset.get("asset_type") in IMAGE_ASSET_TYPES or str(asset.get("mime_type") or "").startswith("image/")]
    image_assets.sort(key=lambda asset: (not bool(asset.get("is_primary")), int(asset.get("sort_order") or 0)))
    for asset in image_assets:
        url = asset_url(client, asset)
        if url:
            return url
    return _fallback_image(record)


def _text(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if not _is_missing(item))
    if isinstance(value, dict):
        return " · ".join(f"{key}: {item}" for key, item in value.items() if not _is_missing(item))
    return str(value).strip()


def _filter_rows(entity_type: str, rows: list[dict], *, search: str, category: str) -> list[dict]:
    query = search.casefold().strip()
    result = []
    for row in rows:
        if category != "Todos" and _category_value(entity_type, row) != category:
            continue
        haystack = " ".join(
            _text(row.get(field))
            for field in ("name", "category", "record_type", "description", "client_brand", "project_name", "event_name", "supplier_name", "material", "sku", "tags")
        ).casefold()
        if query and query not in haystack:
            continue
        result.append(row)
    return result


def _card_meta(entity_type: str, record: dict) -> str:
    values = []
    for field in ENTITY_CONFIG[entity_type]["card_fields"]:
        value = _category_value(entity_type, record) if field == "category" else _text(record.get(field))
        if value and value not in values:
            values.append(value)
    return " · ".join(values[:3])


def render_cards(client: Any, entity_type: str, rows: list[dict], *, page: int, page_size: int = 12) -> None:
    start = (page - 1) * page_size
    visible = rows[start:start + page_size]
    if not visible:
        st.info("Nenhum item encontrado com estes filtros.")
        return

    media_by_entity = fetch_media_assets_batch(
        client,
        entity_type,
        [str(record.get("id") or "") for record in visible],
    )

    for start_index in range(0, len(visible), 3):
        columns = st.columns(3)
        for column, record in zip(columns, visible[start_index:start_index + 3]):
            entity_id = str(record.get("id") or "")
            with column:
                with st.container(border=True):
                    try:
                        image = primary_image_url(
                            client, entity_type, record, media_by_entity.get(entity_id, [])
                        )
                    except Exception:
                        image = _fallback_image(record)
                    if image:
                        st.image(image, width="stretch")
                    else:
                        st.markdown("**Sem imagem principal**")
                        st.caption("O acervo visual pode ser complementado na Base de Conhecimento.")
                    st.markdown(f"**{_text(record.get('name')) or 'Sem nome'}**")
                    meta = _card_meta(entity_type, record)
                    if meta:
                        st.caption(meta)
                    if st.button("Ver ficha", key=f"open_{entity_type}_{entity_id}", width="stretch"):
                        st.session_state[f"specialized_selected_{entity_type}"] = entity_id
                        st.rerun()


def render_gallery(client: Any, entity_type: str, record: dict) -> None:
    entity_id = str(record.get("id") or "")
    assets = fetch_media_assets(client, entity_type, entity_id)
    images: list[tuple[dict | None, str]] = []
    documents: list[tuple[dict, str]] = []
    for asset in assets:
        url = asset_url(client, asset)
        if not url:
            continue
        is_image = asset.get("asset_type") in IMAGE_ASSET_TYPES or str(asset.get("mime_type") or "").startswith("image/")
        if is_image:
            images.append((asset, url))
        elif asset.get("asset_type") in DOCUMENT_ASSET_TYPES:
            documents.append((asset, url))

    fallback = _fallback_image(record)
    if not images and fallback:
        images.append((None, fallback))

    st.markdown("### Galeria visual")
    if images:
        for start in range(0, len(images), 3):
            columns = st.columns(3)
            for column, (asset, url) in zip(columns, images[start:start + 3]):
                with column:
                    st.image(url, width="stretch")
                    if asset:
                        title = _text(asset.get("title"))
                        if title:
                            st.caption(title)
                        if asset.get("is_primary"):
                            st.caption("Imagem principal")
    else:
        st.caption("Nenhuma imagem foi associada a este cadastro ainda.")

    if documents:
        st.markdown("### Documentos e referências")
        for asset, url in documents:
            title = _text(asset.get("title")) or _text(asset.get("file_name")) or "Abrir material"
            st.link_button(title, url, width="stretch")

    st.caption("A gestão de uploads, exclusões e imagem principal continua usando o acervo central da Base de Conhecimento.")
    st.page_link("pages/2_Consultar_Base.py", label="Abrir Base de Conhecimento")


def _field_label(entity_type: str, field: str) -> str:
    for _, fields in DETAIL_SCHEMAS.get(entity_type, []):
        for key, label in fields:
            if key == field:
                return label
    return field.replace("_", " ").strip().capitalize()


def _editor_fields(entity_type: str, record: dict) -> list[tuple[str, str]]:
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, fields in DETAIL_SCHEMAS.get(entity_type, []):
        for field, label in fields:
            if field in record and field not in NON_EDITABLE_FIELDS and field not in seen:
                ordered.append((field, label))
                seen.add(field)
    for field in record:
        if field in seen or field in NON_EDITABLE_FIELDS:
            continue
        if field.startswith("_"):
            continue
        ordered.append((field, _field_label(entity_type, field)))
        seen.add(field)
    return ordered


def _serialize_for_editor(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "\n".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _parse_decimal(text: str) -> float | None:
    value = text.strip()
    if not value:
        return None
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    return float(value)


def _parse_editor_value(field: str, value: Any, old_value: Any) -> Any:
    if field in BOOLEAN_FIELDS or isinstance(old_value, bool):
        if value == "Não informado":
            return None
        return value == "Sim"
    text = str(value or "").strip()
    if not text:
        return None
    if field in INTEGER_FIELDS or (isinstance(old_value, int) and not isinstance(old_value, bool)):
        return int(round(_parse_decimal(text) or 0))
    if field in MONEY_FIELDS or field in DECIMAL_SUFFIXES or isinstance(old_value, float):
        return _parse_decimal(text)
    if field in LIST_FIELDS or isinstance(old_value, (list, tuple, set)):
        return [line.strip().lstrip("•-").strip() for line in text.splitlines() if line.strip()]
    if isinstance(old_value, dict):
        return json.loads(text)
    return text


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _log_edit_events(
    client: Any,
    *,
    entity_type: str,
    entity_id: str,
    changes: dict[str, tuple[Any, Any]],
    source: str,
    reason: str,
) -> None:
    events = []
    for field, (old_value, new_value) in changes.items():
        events.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "event_type": "manual_update",
                "field_name": field,
                "field_label": _field_label(entity_type, field),
                "old_value": _json_safe(old_value),
                "new_value": _json_safe(new_value),
                "editor_name": None,
                "edit_source": source or "pagina_especializada",
                "edit_notes": reason,
            }
        )
    if events:
        client.table("knowledge_edit_events").insert(events).execute()


def render_editor(client: Any, entity_type: str, record: dict) -> None:
    st.markdown("### Editar cadastro")
    st.caption(
        "Aqui aparecem também os campos vazios. Ao salvar um valor, ele passa "
        "automaticamente a aparecer na ficha visual."
    )

    fields = _editor_fields(entity_type, record)
    values: dict[str, Any] = {}
    with st.form(f"specialized_edit_{entity_type}_{record.get('id')}"):
        for field, label in fields:
            old_value = record.get(field)
            key = f"edit_{entity_type}_{record.get('id')}_{field}"
            if field in BOOLEAN_FIELDS or isinstance(old_value, bool):
                current = "Não informado" if old_value is None else ("Sim" if bool(old_value) else "Não")
                values[field] = st.selectbox(label, ["Não informado", "Sim", "Não"], index=["Não informado", "Sim", "Não"].index(current), key=key)
            elif field in WIDE_FIELDS or field in LIST_FIELDS or isinstance(old_value, (dict, list, tuple, set)):
                values[field] = st.text_area(label, value=_serialize_for_editor(old_value), key=key)
            else:
                values[field] = st.text_input(label, value=_serialize_for_editor(old_value), key=key)

        st.markdown("#### Rastreabilidade da alteração")
        source = st.text_input("Fonte da atualização", placeholder="Ex.: cliente, fornecedor, proposta revisada, visita técnica...")
        reason = st.text_area("Motivo da edição", placeholder="Explique brevemente o que está sendo corrigido ou completado.")
        submitted = st.form_submit_button("Salvar alterações", type="primary", width="stretch")

    if not submitted:
        return

    changes: dict[str, tuple[Any, Any]] = {}
    payload: dict[str, Any] = {}
    try:
        for field, _ in fields:
            old_value = record.get(field)
            new_value = _parse_editor_value(field, values[field], old_value)
            if _json_safe(old_value) != _json_safe(new_value):
                payload[field] = new_value
                changes[field] = (old_value, new_value)
    except Exception as exc:
        st.error(f"Não foi possível interpretar um dos campos: {exc}")
        return

    if not changes:
        st.info("Nenhuma alteração foi identificada.")
        return
    if not reason.strip():
        st.error("Informe o motivo da edição para preservar a rastreabilidade.")
        return

    entity_id = str(record.get("id") or "")
    try:
        (
            client.table(ENTITY_CONFIG[entity_type]["table"])
            .update(payload)
            .eq("id", entity_id)
            .execute()
        )
        _log_edit_events(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            source=source.strip() or "pagina_especializada",
            reason=reason.strip(),
        )
    except Exception as exc:
        st.error(f"A NAVE não conseguiu salvar a edição: {exc}")
        return

    st.success("Cadastro atualizado. Os novos dados já passam a aparecer na ficha.")
    st.session_state[f"specialized_refresh_{entity_type}"] = True
    st.rerun()


def render_detail(client: Any, entity_type: str, entity_id: str) -> None:
    record = fetch_entity(client, entity_type, entity_id)
    if not record:
        st.warning("O cadastro selecionado não foi encontrado.")
        st.session_state.pop(f"specialized_selected_{entity_type}", None)
        return

    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.markdown(f"## {_text(record.get('name')) or 'Cadastro'}")
        meta = _card_meta(entity_type, record)
        if meta:
            st.caption(meta)
    with top_right:
        if st.button("Voltar à lista", key=f"back_{entity_type}_{entity_id}", width="stretch"):
            st.session_state.pop(f"specialized_selected_{entity_type}", None)
            st.rerun()

    tab_info, tab_gallery, tab_edit = st.tabs(["Ficha", "Galeria", "Editar"])
    with tab_info:
        render_complete_record(entity_type, dict(record), show_related_projects=False)
        # Ficha completa já mostra o bloco em modo leitura. Nesta área especializada,
        # repetimos apenas se for necessário editar os vínculos.
        st.divider()
        render_related_projects_panel(
            entity_type,
            entity_id,
            client=client,
            allow_edit=True,
            heading="Gerenciar projetos relacionados",
        )
    with tab_gallery:
        render_gallery(client, entity_type, record)
    with tab_edit:
        render_editor(client, entity_type, record)


def render_specialized_page(entity_type: str) -> None:
    if entity_type not in ENTITY_CONFIG:
        raise ValueError("Tipo de página especializada não configurado.")
    config = ENTITY_CONFIG[entity_type]
    client = get_nave_client()

    try:
        from branding import page_header
        page_header(config["title"], config["subtitle"])
    except Exception:
        st.title(config["title"])
        st.caption(config["subtitle"])

    selected_id = st.session_state.get(f"specialized_selected_{entity_type}")
    if selected_id:
        render_detail(client, entity_type, str(selected_id))
        return

    try:
        rows = fetch_entities(client, entity_type)
    except Exception as exc:
        st.error(f"A NAVE não conseguiu carregar {config['title'].lower()}: {exc}")
        return

    categories = sorted({_category_value(entity_type, row) for row in rows if _category_value(entity_type, row)})
    search_col, category_col = st.columns([2, 1])
    with search_col:
        search = st.text_input("Buscar", placeholder="Nome, categoria, descrição, marca, projeto ou tag...")
    with category_col:
        category = st.selectbox("Categoria", ["Todos", *categories])

    filtered = _filter_rows(entity_type, rows, search=search, category=category)
    st.caption(f"{len(filtered)} de {len(rows)} cadastros")

    page_size = 12
    pages = max(1, math.ceil(len(filtered) / page_size))
    page = st.number_input("Página", min_value=1, max_value=pages, value=1, step=1, key=f"specialized_page_{entity_type}")
    render_cards(client, entity_type, filtered, page=int(page), page_size=page_size)
