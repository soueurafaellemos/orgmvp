from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlparse
import re

import pandas as pd

from nave_runtime_fixes import apply_runtime_fixes


# ``branding`` importa este módulo antes dos extratores nas páginas da NAVE.
# Aplicar aqui mantém o hotfix transversal sem duplicar código em cada página.
apply_runtime_fixes()


COVER_COLUMN_NAMES = ("Capa", "capa")
_MISSING_COVER_TEXT = {"none", "nan", "null", "<na>", "n/a", "na"}
_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".avif",
    ".bmp",
    ".tif",
    ".tiff",
)
_PHOTO_KEY_HINTS = (
    "foto",
    "photo",
    "image",
    "imagem",
    "capa",
    "cover",
    "visual",
    "gallery",
    "galeria",
)
_URL_RE = re.compile(r"https?://[^\s\]\[\)\(<>\"']+", re.IGNORECASE)


def clean_cover_value(value: Any) -> str:
    """Nunca deixa None/NaN aparecer como texto na coluna de capa."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.casefold() in _MISSING_COVER_TEXT:
        return ""
    return text


def sanitize_cover_dataframe(data: Any) -> Any:
    """Copia DataFrames e limpa apenas colunas chamadas Capa/capa."""
    if not isinstance(data, pd.DataFrame):
        return data
    cover_columns = [
        name for name in COVER_COLUMN_NAMES if name in data.columns
    ]
    if not cover_columns:
        return data
    result = data.copy()
    for column in cover_columns:
        result[column] = result[column].map(clean_cover_value)
    return result


def _normalize_name(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _wikimedia_direct_url(url: str) -> str:
    """Converte página File: do Commons para endpoint de redirecionamento da imagem."""
    text = str(url or "").strip()
    if not text:
        return ""

    parsed = urlparse(text)
    host = parsed.netloc.casefold()
    marker = "/wiki/File:"
    if "commons.wikimedia.org" not in host or marker not in parsed.path:
        return text

    file_name = parsed.path.split(marker, 1)[1]
    if not file_name:
        return text

    # Special:Redirect/file aceita o nome da mídia e devolve o arquivo real.
    return (
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
        + quote(file_name, safe="()_,.-")
    )


def _looks_like_image_url(value: Any) -> bool:
    text = _wikimedia_direct_url(str(value or "").strip())
    if not text.startswith(("http://", "https://")):
        return False

    lowered = text.casefold()
    parsed = urlparse(text)
    path = parsed.path.casefold()
    query = parsed.query.casefold()

    if path.endswith((".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx")):
        return False
    if any(token in lowered for token in ("/slides/", "slide=", "page=", "pageno=")):
        return False

    if path.endswith(_IMAGE_EXTENSIONS):
        return True

    if any(token in query for token in ("format=jpg", "format=jpeg", "format=png", "format=webp", "f=webp")):
        return True

    image_hosts = (
        "images.",
        "image.",
        "img.",
        "cdn.",
        "cloudinary.com",
        "squarespace-cdn.com",
        "wikimedia.org",
        "supabase.co",
        "supabase.in",
        "storage.googleapis.com",
    )
    if any(token in parsed.netloc.casefold() for token in image_hosts):
        return True

    # URLs de WordPress / uploads são frequentemente imagens mesmo com parâmetros.
    if "/wp-content/uploads/" in path:
        return True

    return False


def _extract_photo_urls(value: Any, *, key_hint: str = "") -> list[str]:
    """Extrai URLs de imagem de estruturas arbitrárias sem aceitar páginas/documentos."""
    found: list[str] = []

    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key or "").casefold()
            found.extend(_extract_photo_urls(item, key_hint=key_text))
        return found

    if isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_extract_photo_urls(item, key_hint=key_hint))
        return found

    if value is None:
        return found

    text = str(value).strip()
    if not text:
        return found

    candidates = [text] if text.startswith(("http://", "https://")) else _URL_RE.findall(text)
    hinted = any(token in key_hint for token in _PHOTO_KEY_HINTS)

    for candidate in candidates:
        candidate = _wikimedia_direct_url(candidate.rstrip(".,;:"))
        if _looks_like_image_url(candidate):
            found.append(candidate)
        elif hinted and candidate.startswith(("http://", "https://")):
            # Mesmo em campo explicitamente visual, não aceitar página genérica como capa.
            continue

    return found


def _asset_url(client: Any, asset: Mapping[str, Any]) -> str:
    external = clean_cover_value(asset.get("external_url"))
    if _looks_like_image_url(external):
        return _wikimedia_direct_url(external)

    bucket = clean_cover_value(asset.get("storage_bucket"))
    path = clean_cover_value(asset.get("storage_path"))
    if not bucket or not path:
        return ""

    try:
        response = client.storage.from_(bucket).create_signed_url(path, 60 * 60 * 24)
        if isinstance(response, Mapping):
            signed = (
                response.get("signedURL")
                or response.get("signedUrl")
                or response.get("signed_url")
            )
            if signed:
                return str(signed)
    except Exception:
        pass

    try:
        response = client.storage.from_(bucket).get_public_url(path)
        if isinstance(response, str):
            return response
        if isinstance(response, Mapping):
            return str(
                response.get("publicUrl")
                or response.get("publicURL")
                or response.get("public_url")
                or ""
            )
    except Exception:
        pass

    return ""


def _record_cover_url(record: Mapping[str, Any]) -> str:
    """Prioriza fotos aprovadas e campos visuais do Local."""
    priority_keys = (
        "FOTO_URL_APROVADA",
        "foto_url_aprovada",
        "approved_photo_url",
        "official_photo_url",
        "venue_photo_url",
        "venue_image_url",
        "main_image_url",
        "cover_image_url",
        "cover_url",
        "photo_url",
        "foto_url",
        "imagem_url",
        "source_image_url",
    )

    for key in priority_keys:
        value = record.get(key)
        for url in _extract_photo_urls(value, key_hint=key.casefold()):
            return url

    raw_data = record.get("raw_data")
    if isinstance(raw_data, Mapping):
        for key in priority_keys:
            value = raw_data.get(key)
            for url in _extract_photo_urls(value, key_hint=key.casefold()):
                return url

        for url in _extract_photo_urls(raw_data, key_hint="raw_data"):
            return url

    for field in ("evidence", "notes", "description"):
        for url in _extract_photo_urls(record.get(field), key_hint=field):
            return url

    return ""


def _media_cover_map(client: Any, venue_ids: list[str]) -> dict[str, str]:
    if not venue_ids:
        return {}

    try:
        response = (
            client.table("media_assets")
            .select("*")
            .eq("entity_type", "venue")
            .in_("entity_id", venue_ids)
            .execute()
        )
        rows = list(response.data or [])
    except Exception:
        return {}

    def rank(asset: Mapping[str, Any]) -> tuple[int, int, int, str]:
        asset_type = str(asset.get("asset_type") or "").casefold()
        primary = 0 if bool(asset.get("is_primary")) else 1
        type_rank = 0 if asset_type == "main_image" else 1 if asset_type == "gallery_image" else 2
        try:
            sort_order = int(asset.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0
        return primary, type_rank, sort_order, str(asset.get("created_at") or "")

    rows.sort(key=rank)
    result: dict[str, str] = {}
    for asset in rows:
        venue_id = str(asset.get("entity_id") or "")
        if not venue_id or venue_id in result:
            continue

        mime_type = str(asset.get("mime_type") or "").casefold()
        asset_type = str(asset.get("asset_type") or "").casefold()
        imageish = (
            mime_type.startswith("image/")
            or asset_type in {"main_image", "gallery_image"}
        )
        if not imageish:
            continue

        url = _asset_url(client, asset)
        if url:
            result[venue_id] = url

    return result


def _enrichment_cover_map(client: Any, venue_ids: list[str]) -> dict[str, str]:
    """Recupera a foto de imports/enriquecimentos quando ainda não foi espelhada no venue."""
    if not venue_ids:
        return {}

    try:
        response = (
            client.table("knowledge_enrichment_events")
            .select("entity_id,incoming_data,applied_changes,before_data,created_at")
            .eq("entity_type", "venue")
            .in_("entity_id", venue_ids)
            .order("created_at", desc=True)
            .execute()
        )
        rows = list(response.data or [])
    except Exception:
        return {}

    result: dict[str, str] = {}
    for row in rows:
        venue_id = str(row.get("entity_id") or "")
        if not venue_id or venue_id in result:
            continue
        for field in ("applied_changes", "incoming_data", "before_data"):
            for url in _extract_photo_urls(row.get(field), key_hint=field):
                result[venue_id] = url
                break
            if venue_id in result:
                break
    return result


def _fetch_venues(client: Any, ids: list[str], names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    if ids:
        try:
            response = client.table("venues").select("*").in_("id", ids).execute()
            for row in response.data or []:
                item = dict(row)
                key = str(item.get("id") or "")
                if key and key not in seen:
                    rows.append(item)
                    seen.add(key)
        except Exception:
            pass

    # Fallback por nome: a tabela de Locais pode chegar à renderização sem _id visível.
    unresolved_names = [name for name in names if name]
    if unresolved_names:
        for field in ("name", "venue_name", "local"):
            try:
                response = (
                    client.table("venues")
                    .select("*")
                    .in_(field, unresolved_names)
                    .execute()
                )
                got_any = False
                for row in response.data or []:
                    item = dict(row)
                    key = str(item.get("id") or "")
                    if key and key not in seen:
                        rows.append(item)
                        seen.add(key)
                    got_any = True
                if got_any:
                    break
            except Exception:
                continue

    return rows


def hydrate_venue_covers(data: Any) -> Any:
    """Preenche a coluna Capa da lista de Locais usando o acervo validado já existente."""
    if not isinstance(data, pd.DataFrame):
        return data

    cover_column = next((name for name in COVER_COLUMN_NAMES if name in data.columns), None)
    if not cover_column or "Local" not in data.columns:
        return sanitize_cover_dataframe(data)

    result = sanitize_cover_dataframe(data)
    missing_mask = result[cover_column].map(clean_cover_value).eq("")
    if not bool(missing_mask.any()):
        return result

    try:
        from nave_data_client import get_nave_client

        client = get_nave_client()
    except Exception:
        return result

    missing_indices = list(result.index[missing_mask])
    id_column = "_id" if "_id" in result.columns else "id" if "id" in result.columns else None

    row_ids: dict[Any, str] = {}
    ids: list[str] = []
    if id_column:
        for idx in missing_indices:
            value = clean_cover_value(result.at[idx, id_column])
            if value:
                row_ids[idx] = value
                ids.append(value)

    names = [clean_cover_value(result.at[idx, "Local"]) for idx in missing_indices]
    venues = _fetch_venues(client, list(dict.fromkeys(ids)), list(dict.fromkeys(names)))

    by_id = {str(row.get("id") or ""): row for row in venues if row.get("id")}
    by_name: dict[str, dict[str, Any]] = {}
    for row in venues:
        for field in ("name", "venue_name", "local", "title"):
            normalized = _normalize_name(row.get(field))
            if normalized and normalized not in by_name:
                by_name[normalized] = row

    venue_ids = list(by_id.keys())
    media_map = _media_cover_map(client, venue_ids)
    enrichment_map = _enrichment_cover_map(client, venue_ids)

    for idx in missing_indices:
        venue: dict[str, Any] | None = None
        row_id = row_ids.get(idx)
        if row_id:
            venue = by_id.get(row_id)

        if venue is None:
            venue = by_name.get(_normalize_name(result.at[idx, "Local"]))

        if not venue:
            continue

        venue_id = str(venue.get("id") or "")
        cover = (
            media_map.get(venue_id)
            or _record_cover_url(venue)
            or enrichment_map.get(venue_id)
        )
        if cover:
            result.at[idx, cover_column] = cover

    return result


def _install_early_venue_cover_guard() -> None:
    """Instala a correção antes de a página de Locais criar a tabela."""
    try:
        import streamlit as st
    except Exception:
        return

    current = st.dataframe
    if getattr(current, "_nave_venue_cover_guard", False):
        return

    def guarded_dataframe(data=None, *args, **kwargs):
        prepared = data
        if isinstance(data, pd.DataFrame) and "Local" in data.columns:
            prepared = hydrate_venue_covers(data)

            cover_column = next(
                (name for name in COVER_COLUMN_NAMES if name in prepared.columns),
                None,
            )
            if cover_column:
                column_config = dict(kwargs.get("column_config") or {})
                column_config[cover_column] = st.column_config.ImageColumn(
                    "Capa",
                    width="small",
                    help="Imagem principal validada do local.",
                )
                kwargs["column_config"] = column_config
                kwargs.setdefault("row_height", 64)

        return current(prepared, *args, **kwargs)

    guarded_dataframe._nave_venue_cover_guard = True
    guarded_dataframe._nave_original_dataframe = current
    st.dataframe = guarded_dataframe


# Esta instalação precisa acontecer no import, não apenas dentro de
# apply_nave_branding(). Assim Locais recebe a correção mesmo quando a página
# renderiza a tabela antes do branding terminar de instalar seus wrappers.
_install_early_venue_cover_guard()
