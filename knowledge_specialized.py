from __future__ import annotations

import hashlib
import json
import math
import re
from html import escape
from typing import Any
from urllib.parse import urlparse

import pandas as pd
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
from nave_table_utils import clean_cover_value


ENTITY_CONFIG = {
    "product": {
        "table": "products",
        "title": "Brindes",
        "subtitle": "Consulte e mantenha o repertório de brindes em uma lista única, com capa, ficha completa, acervo e histórico de projetos.",
        "category_field": "category",
        "page_size": 25,
        "list_select": "id,supplier_id,name,category,description,material,sku,tags,source_image_url,raw_data",
    },
    "activation": {
        "table": "activation_solutions",
        "title": "Ativações",
        "subtitle": "Consulte ativações, soluções e experiências em uma lista única, com capa, contexto, ficha completa, acervo e histórico de projetos.",
        "category_field": "category",
        "page_size": 25,
        "list_select": "id,supplier_id,project_id,name,category,record_type,description,client_brand,project_name,event_name,tags,source_image_url,raw_data",
    },
    "supplier": {
        "table": "suppliers",
        "title": "Fornecedores",
        "subtitle": "Consulte parceiros, contatos, cobertura, logística, repertório associado e projetos relacionados.",
        "category_field": "",
        "page_size": 25,
        "list_select": "*",
    },
}

LIST_FIELDS = {
    "tags", "included_items", "excluded_items", "missing_fields",
    "infrastructure_requirements", "restrictions", "rooms_or_areas",
    "served_states", "served_cities", "local_team_locations",
    "supplier_categories", "specialties", "services_offered", "client_brands",
    "market_segments", "certifications", "direct_states", "partner_states",
    "technical_structure",
}
NON_EDITABLE_FIELDS = INTERNAL_FIELDS | {
    "supplier_name", "media_count", "image_count", "document_count",
    "has_primary", "products_count", "activations_count", "venues_count",
    "coverage_level", "linked_venue_names",
}
IMAGE_ASSET_TYPES = {"main_image", "gallery_image"}
DOCUMENT_ASSET_TYPES = {
    "floor_plan", "elevation", "access_map", "technical_sheet",
    "commercial_book", "presentation", "video", "external_link", "other",
}


def _rows(response: Any) -> list[dict]:
    return list(getattr(response, "data", None) or [])


def _text(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if not _is_missing(item))
    if isinstance(value, dict):
        return " · ".join(
            f"{key}: {item}" for key, item in value.items() if not _is_missing(item)
        )
    return str(value).strip()


def _category_value(entity_type: str, row: dict) -> str:
    if entity_type == "activation":
        return _text(row.get("category")) or _text(row.get("record_type"))
    field = ENTITY_CONFIG[entity_type].get("category_field")
    return _text(row.get(field)) if field else ""


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
            client.table("knowledge_curation_states").select("entity_id")
            .eq("entity_type", entity_type).eq("is_archived", True).execute()
        )
        return {str(row.get("entity_id")) for row in _rows(response) if row.get("entity_id")}
    except Exception:
        return set()


def fetch_entities(client: Any, entity_type: str) -> list[dict]:
    config = ENTITY_CONFIG[entity_type]
    response = client.table(config["table"]).select(config["list_select"]).order("name").limit(4000).execute()
    rows = _enrich_supplier_names(client, _rows(response))
    archived = _archived_entity_ids(client, entity_type)
    return [row for row in rows if str(row.get("id") or "") not in archived]


def fetch_entity(client: Any, entity_type: str, entity_id: str) -> dict | None:
    response = client.table(ENTITY_CONFIG[entity_type]["table"]).select("*").eq("id", entity_id).limit(1).execute()
    rows = _enrich_supplier_names(client, _rows(response))
    return rows[0] if rows else None


def _signed_url_value(response: Any) -> str | None:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
    return getattr(response, "signedURL", None) or getattr(response, "signedUrl", None) or getattr(response, "signed_url", None)


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
        client.table("media_assets").select("*")
        .eq("entity_type", entity_type).eq("entity_id", entity_id)
        .order("is_primary", desc=True).order("sort_order").order("created_at").execute()
    )
    return _rows(response)


def fetch_media_assets_batch(client: Any, entity_type: str, entity_ids: list[str]) -> dict[str, list[dict]]:
    clean_ids = [entity_id for entity_id in entity_ids if entity_id]
    if not clean_ids:
        return {}
    try:
        response = (
            client.table("media_assets").select("*")
            .eq("entity_type", entity_type).in_("entity_id", clean_ids)
            .order("is_primary", desc=True).order("sort_order").execute()
        )
    except Exception:
        return {}
    grouped: dict[str, list[dict]] = {}
    for asset in _rows(response):
        grouped.setdefault(str(asset.get("entity_id") or ""), []).append(asset)
    return grouped


def _valid_http_url(value: Any) -> str | None:
    if isinstance(value, str):
        clean = value.strip()
        if clean.startswith(("http://", "https://")):
            return clean
    return None


def _looks_like_external_photo(url: str) -> bool:
    """Reconhece URLs que podem ser exibidas diretamente como imagem de Local.

    URLs de storage do Supabase são aceitas quando apontam para um arquivo de
    imagem. O bloqueio passa a mirar apenas renders de página/slide, evitando
    rejeitar fotos válidas só por estarem armazenadas pela própria NAVE.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").casefold()
    path = (parsed.path or "").casefold()
    query = (parsed.query or "").casefold()
    if not host:
        return False
    blocked = (
        "rendered_page", "rendered-pages", "rendered_pages",
        "slide_render", "page_render", "slide-render", "page-render",
        "/pages/", "/slides/",
    )
    if any(token in path or token in query for token in blocked):
        return False
    if path.endswith((".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx")):
        return False
    photo_hosts = (
        "wikimedia.org", "squarespace-cdn.com", "cloudfront.net",
        "googleusercontent.com", "wp-content", "images.", "imagekit", "cdn",
    )
    storage_hosts = ("supabase.co", "supabase.in")
    image_ext = path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"))
    image_query = any(token in query for token in ("image", "img", "webp", "jpg", "jpeg", "png"))
    if any(token in host for token in storage_hosts):
        return image_ext or image_query
    return image_ext or image_query or any(token in host or token in path for token in photo_hosts)


def _wikimedia_direct_url(url: str) -> str:
    """Converte páginas File: do Wikimedia Commons em URL redirecionável da imagem."""
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = (parsed.netloc or "").casefold()
    marker = "/wiki/File:"
    if "commons.wikimedia.org" not in host or marker not in parsed.path:
        return url
    from urllib.parse import quote, unquote
    filename = unquote(parsed.path.split(marker, 1)[1]).strip()
    if not filename:
        return url
    return "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + quote(filename, safe="()_,.-")


def _iter_visual_urls(value: Any, *, parent_key: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_visual_urls(item, parent_key=str(key).casefold())
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_visual_urls(item, parent_key=parent_key)
    elif isinstance(value, str):
        url = _valid_http_url(value)
        if not url:
            return
        visual_signal = any(
            token in parent_key
            for token in ("photo", "foto", "image", "imagem", "cover", "capa", "gallery", "galeria", "visual")
        )
        blocked_signal = any(
            token in parent_key
            for token in ("slide", "page", "pagina", "document", "pdf", "plan", "planta", "source_file")
        )
        if visual_signal and not blocked_signal:
            yield url


_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

def _iter_all_http_urls(value: Any):
    """Percorre dados estruturados e textos de evidência atrás de URLs reais.

    Em Locais isso ajuda a recuperar a foto aprovada registrada no PDF visual
    mesmo quando o extrator guardou a URL dentro de evidência/raw_data em vez
    de um campo de imagem dedicado. Apenas URLs que passam pela validação de
    imagem são usadas como capa.
    """
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_all_http_urls(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_all_http_urls(item)
    elif isinstance(value, str):
        clean = _valid_http_url(value)
        if clean:
            yield clean.rstrip(".,;)]}")
        else:
            for match in _URL_PATTERN.findall(value):
                yield match.rstrip(".,;)]}")


def _fallback_image(record: dict, entity_type: str | None = None) -> str | None:
    """Prioriza recortes validados; para locais aceita foto pública explicitamente visual."""
    raw = record.get("raw_data")
    if isinstance(raw, dict):
        for key in (
            "visual_crop_url", "crop_url", "cropped_image_url",
            "product_crop_url", "activation_crop_url", "venue_crop_url",
            "cover_url", "main_image_url", "gallery_image_url", "photo_url",
            "foto_url", "official_photo_url", "imagem_url",
            "approved_photo_url", "foto_url_aprovada", "FOTO_URL_APROVADA",
            "cover_image_url", "venue_photo_url", "venue_image_url",
        ):
            url = _valid_http_url(raw.get(key))
            if url:
                if entity_type == "venue":
                    url = _wikimedia_direct_url(url)
                    if _looks_like_external_photo(url):
                        return url
                else:
                    return url
        if entity_type in {"venue", "supplier"}:
            for url in _iter_visual_urls(raw):
                if entity_type == "venue":
                    url = _wikimedia_direct_url(url)
                    if _looks_like_external_photo(url):
                        return url
                else:
                    return url

    # Alguns volumes visuais guardam a URL da foto dentro de raw_data/evidence
    # sem um nome de campo padronizado. Para Locais, percorremos essas URLs e
    # aceitamos somente links que realmente pareçam imagens (ou File: Commons).
    if entity_type == "venue":
        for value in (raw, record.get("evidence"), record.get("notes")):
            for candidate in _iter_all_http_urls(value):
                url = _wikimedia_direct_url(candidate)
                if _looks_like_external_photo(url):
                    return url

    # Em Locais, source_image_url pode ser a foto oficial pública importada
    # pelo catálogo visual. Esse fallback não é aplicado a Brindes/Ativações.
    if entity_type == "venue":
        for key in ("source_image_url", "photo_url", "foto_url", "official_photo_url", "approved_photo_url"):
            url = _valid_http_url(record.get(key))
            if not url:
                continue
            url = _wikimedia_direct_url(url)
            if _looks_like_external_photo(url):
                return url
    return None


def source_preview_url(record: dict) -> str | None:
    candidates: list[Any] = [record.get("source_image_url")]
    raw = record.get("raw_data")
    if isinstance(raw, dict):
        candidates.extend(raw.get(key) for key in ("source_image_url", "full_slide_url", "slide_image_url", "image_url"))
    for value in candidates:
        url = _valid_http_url(value)
        if url:
            return url
    return None


def _image_assets_for_cover(assets: list[dict]) -> list[dict]:
    images = [
        asset for asset in assets
        if asset.get("asset_type") in IMAGE_ASSET_TYPES
        or str(asset.get("mime_type") or "").startswith("image/")
    ]
    def rank(asset: dict) -> tuple[int, int]:
        if bool(asset.get("is_primary")):
            kind = 0
        elif asset.get("asset_type") == "main_image":
            kind = 1
        elif asset.get("asset_type") == "gallery_image":
            kind = 2
        else:
            kind = 3
        return kind, int(asset.get("sort_order") or 0)
    return sorted(images, key=rank)


def primary_image_url(client: Any, entity_type: str, record: dict, assets: list[dict] | None = None) -> str | None:
    assets = assets if assets is not None else fetch_media_assets(client, entity_type, str(record.get("id") or ""))
    for asset in _image_assets_for_cover(assets):
        url = asset_url(client, asset)
        if url:
            return url
    return _fallback_image(record, entity_type)


DETAIL_CSS = r"""
<style>
.nave-origin-preview { width:100%; max-height:360px; object-fit:contain; background:#F7F8FB; border:1px solid #E1E6EF; border-radius:12px; }
</style>
"""


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
    safe_crop = _fallback_image(record, entity_type)
    if not images and safe_crop:
        images.append((None, safe_crop))

    st.markdown("### Galeria visual")
    if images:
        for start in range(0, len(images), 3):
            columns = st.columns(3)
            for column, (asset, url) in zip(columns, images[start:start + 3]):
                with column:
                    st.image(url, width="stretch")
                    if asset and asset.get("is_primary"):
                        st.caption("Imagem principal")
                    elif asset and _text(asset.get("title")):
                        st.caption(_text(asset.get("title")))
    else:
        st.caption("Ainda não há imagem validada no acervo para este cadastro.")

    origin = source_preview_url(record)
    if origin:
        st.markdown("### Material de origem")
        st.caption("O slide/página de origem é consulta de referência e não vira capa automaticamente.")
        safe = escape(origin, quote=True)
        st.markdown(f'<img class="nave-origin-preview" src="{safe}" alt="Material de origem">', unsafe_allow_html=True)

    if documents:
        st.markdown("### Documentos e referências")
        for asset, url in documents:
            title = _text(asset.get("title")) or _text(asset.get("file_name")) or "Abrir material"
            st.link_button(title, url, width="stretch")

    st.caption("Uploads, exclusões e definição da imagem principal continuam centralizados no acervo da Base de Conhecimento.")
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
                ordered.append((field, label)); seen.add(field)
    for field in record:
        if field in seen or field in NON_EDITABLE_FIELDS or field.startswith("_"):
            continue
        ordered.append((field, _field_label(entity_type, field))); seen.add(field)
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


def _log_edit_events(client: Any, *, entity_type: str, entity_id: str, changes: dict[str, tuple[Any, Any]], source: str, reason: str) -> None:
    events = []
    for field, (old_value, new_value) in changes.items():
        events.append({
            "entity_type": entity_type, "entity_id": entity_id,
            "event_type": "manual_update", "field_name": field,
            "field_label": _field_label(entity_type, field),
            "old_value": _json_safe(old_value), "new_value": _json_safe(new_value),
            "editor_name": None, "edit_source": source or "pagina_especializada",
            "edit_notes": reason,
        })
    if events:
        client.table("knowledge_edit_events").insert(events).execute()


def render_editor(client: Any, entity_type: str, record: dict) -> None:
    st.markdown("### Editar cadastro")
    st.caption("Aqui aparecem também os campos vazios. Ao salvar, a informação passa automaticamente a aparecer na ficha visual.")
    fields = _editor_fields(entity_type, record)
    values: dict[str, Any] = {}
    with st.form(f"specialized_edit_{entity_type}_{record.get('id')}"):
        for field, label in fields:
            old_value = record.get(field)
            key = f"edit_{entity_type}_{record.get('id')}_{field}"
            if field in BOOLEAN_FIELDS or isinstance(old_value, bool):
                current = "Não informado" if old_value is None else ("Sim" if bool(old_value) else "Não")
                options = ["Não informado", "Sim", "Não"]
                values[field] = st.selectbox(label, options, index=options.index(current), key=key)
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
    changes: dict[str, tuple[Any, Any]] = {}; payload: dict[str, Any] = {}
    try:
        for field, _ in fields:
            old_value = record.get(field)
            new_value = _parse_editor_value(field, values[field], old_value)
            if _json_safe(old_value) != _json_safe(new_value):
                payload[field] = new_value; changes[field] = (old_value, new_value)
    except Exception as exc:
        st.error(f"Não foi possível interpretar um dos campos: {exc}"); return
    if not changes:
        st.info("Nenhuma alteração foi identificada."); return
    if not reason.strip():
        st.error("Informe o motivo da edição para preservar a rastreabilidade."); return
    entity_id = str(record.get("id") or "")
    try:
        client.table(ENTITY_CONFIG[entity_type]["table"]).update(payload).eq("id", entity_id).execute()
        _log_edit_events(client, entity_type=entity_type, entity_id=entity_id, changes=changes, source=source.strip() or "pagina_especializada", reason=reason.strip())
    except Exception as exc:
        st.error(f"A NAVE não conseguiu salvar a edição: {exc}"); return
    st.success("Cadastro atualizado."); st.rerun()


def render_detail(client: Any, entity_type: str, entity_id: str, *, record_override: dict | None = None) -> None:
    record = record_override or fetch_entity(client, entity_type, entity_id)
    if not record:
        st.warning("O cadastro selecionado não foi encontrado."); return
    st.markdown(f"## {_text(record.get('name')) or 'Cadastro'}")
    tab_info, tab_gallery, tab_edit = st.tabs(["Ficha", "Galeria", "Editar"])
    with tab_info:
        render_complete_record(entity_type, dict(record), show_related_projects=False)
        st.divider()
        render_related_projects_panel(entity_type, entity_id, client=client, allow_edit=True, heading="Projetos relacionados")
    with tab_gallery:
        render_gallery(client, entity_type, record)
    with tab_edit:
        render_editor(client, entity_type, record)


def _filter_rows(entity_type: str, rows: list[dict], *, search: str, category: str) -> list[dict]:
    tokens = [token for token in search.casefold().strip().split() if token]
    result = []
    for row in rows:
        if category != "Todos" and _category_value(entity_type, row) != category:
            continue
        haystack = " ".join(_text(row.get(field)) for field in (
            "name", "category", "record_type", "description", "client_brand",
            "project_name", "event_name", "supplier_name", "material", "sku", "tags",
        )).casefold()
        if tokens and not all(token in haystack for token in tokens):
            continue
        result.append(row)
    return result


def _table_record(entity_type: str, record: dict, cover: str) -> dict:
    if entity_type == "product":
        return {
            "_id": str(record.get("id") or ""),
            "Capa": clean_cover_value(cover),
            "Brinde": _text(record.get("name")),
            "Categoria": _category_value(entity_type, record),
            "Material": _text(record.get("material")),
            "Fornecedor": _text(record.get("supplier_name")),
            "Código / SKU": _text(record.get("sku")),
        }
    return {
        "_id": str(record.get("id") or ""),
        "Capa": clean_cover_value(cover),
        "Ativação": _text(record.get("name")),
        "Categoria": _category_value(entity_type, record),
        "Marca / cliente": _text(record.get("client_brand")),
        "Projeto": _text(record.get("project_name")),
        "Fornecedor": _text(record.get("supplier_name")),
    }


def _selection_key(entity_type: str, page: int, visible: list[dict]) -> str:
    ids = "|".join(str(row.get("id") or "") for row in visible)
    digest = hashlib.sha1(ids.encode("utf-8")).hexdigest()[:10]
    return f"specialized_table_{entity_type}_{page}_{digest}"


def render_specialized_page(entity_type: str) -> None:
    if entity_type not in {"product", "activation"}:
        raise ValueError("Tipo de página especializada não configurado.")
    config = ENTITY_CONFIG[entity_type]
    client = get_nave_client()
    st.markdown(DETAIL_CSS, unsafe_allow_html=True)
    try:
        from branding import page_header
        page_header(config["title"], config["subtitle"])
    except Exception:
        st.title(config["title"]); st.caption(config["subtitle"])

    try:
        rows = fetch_entities(client, entity_type)
    except Exception as exc:
        st.error(f"A NAVE não conseguiu carregar {config['title'].lower()}: {exc}"); return

    categories = sorted({_category_value(entity_type, row) for row in rows if _category_value(entity_type, row)})
    search_col, category_col, per_page_col = st.columns([2, 1, 0.75])
    with search_col:
        search = st.text_input("Buscar", placeholder="Nome, categoria, descrição, marca, projeto, fornecedor ou tag...")
    with category_col:
        category = st.selectbox("Categoria", ["Todos", *categories])
    with per_page_col:
        page_size = st.selectbox("Itens por página", [25, 50, 100], index=0)

    filtered = _filter_rows(entity_type, rows, search=search, category=category)
    st.caption(f"{len(filtered)} de {len(rows)} cadastros")
    pages = max(1, math.ceil(len(filtered) / page_size))
    page_key = f"specialized_page_{entity_type}"
    current_page = max(1, min(int(st.session_state.get(page_key, 1) or 1), pages))
    st.session_state[page_key] = current_page

    prev_col, info_col, next_col = st.columns([1, 4, 1])
    with prev_col:
        if st.button("← Anterior", key=f"prev_{entity_type}", disabled=current_page <= 1, width="stretch"):
            st.session_state[page_key] = current_page - 1; st.rerun()
    with info_col:
        st.caption(f"Página {current_page} de {pages}")
    with next_col:
        if st.button("Próxima →", key=f"next_{entity_type}", disabled=current_page >= pages, width="stretch"):
            st.session_state[page_key] = current_page + 1; st.rerun()

    start = (current_page - 1) * page_size
    visible = filtered[start:start + page_size]
    if not visible:
        st.info("Nenhum item encontrado com estes filtros."); return

    media_by_entity = fetch_media_assets_batch(client, entity_type, [str(row.get("id") or "") for row in visible])
    table_rows = []
    for record in visible:
        entity_id = str(record.get("id") or "")
        try:
            cover = primary_image_url(client, entity_type, record, media_by_entity.get(entity_id, [])) or ""
        except Exception:
            cover = _fallback_image(record, entity_type) or ""
        table_rows.append(_table_record(entity_type, record, cover))
    table_df = pd.DataFrame(table_rows)
    event = st.dataframe(
        table_df,
        hide_index=True,
        width="stretch",
        row_height=64,
        on_select="rerun",
        selection_mode="single-row",
        key=_selection_key(entity_type, current_page, visible),
        column_config={"Capa": st.column_config.ImageColumn("Capa", width="small")},
    )
    selected_rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])
    if not selected_rows:
        st.caption("Selecione uma linha para abrir a ficha completa, galeria, edição e projetos relacionados.")
        return
    position = selected_rows[0]
    if not isinstance(position, int) or position < 0 or position >= len(visible):
        return
    selected = visible[position]
    st.divider()
    render_detail(client, entity_type, str(selected.get("id") or ""))
