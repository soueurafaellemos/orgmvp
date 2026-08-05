from __future__ import annotations

import mimetypes
import re
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from supabase import Client


MEDIA_BUCKET = "nave-media"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

ALLOWED_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
    (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    ),
    (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
]

ASSET_TYPE_LABELS = {
    "main_image": "Imagem principal",
    "gallery_image": "Foto / galeria",
    "floor_plan": "Planta baixa",
    "elevation": "Planta alta / elevação",
    "access_map": "Mapa / acesso",
    "technical_sheet": "Ficha técnica",
    "commercial_book": "Book comercial",
    "presentation": "Apresentação",
    "video": "Vídeo",
    "external_link": "Link externo",
    "other": "Outro",
}

IMAGE_ASSET_TYPES = {
    "main_image",
    "gallery_image",
    "access_map",
}

DOCUMENT_ASSET_TYPES = {
    "floor_plan",
    "elevation",
    "technical_sheet",
    "commercial_book",
    "presentation",
}


def _bucket_identifier(bucket: Any) -> str:
    if isinstance(bucket, dict):
        return str(
            bucket.get("id")
            or bucket.get("name")
            or ""
        )

    return str(
        getattr(bucket, "id", None)
        or getattr(bucket, "name", None)
        or ""
    )


def ensure_media_bucket(client: Client) -> None:
    buckets = client.storage.list_buckets() or []
    bucket_ids = {
        _bucket_identifier(bucket)
        for bucket in buckets
    }

    if MEDIA_BUCKET in bucket_ids:
        return

    client.storage.create_bucket(
        MEDIA_BUCKET,
        options={
            "public": False,
            "allowed_mime_types": ALLOWED_MIME_TYPES,
            "file_size_limit": MAX_FILE_SIZE_BYTES,
        },
    )


def _safe_filename(filename: str) -> str:
    path = Path(filename or "arquivo")
    stem = unicodedata.normalize("NFKD", path.stem)
    stem = "".join(
        character
        for character in stem
        if not unicodedata.combining(character)
    )
    stem = stem.lower().strip()
    stem = re.sub(r"[^a-z0-9]+", "-", stem)
    stem = re.sub(r"-+", "-", stem).strip("-")
    stem = stem or "arquivo"

    extension = re.sub(
        r"[^a-z0-9.]",
        "",
        path.suffix.lower(),
    )
    return f"{stem}{extension}"


def _resolve_mime_type(
    filename: str,
    supplied_mime_type: str | None,
) -> str:
    if supplied_mime_type:
        return supplied_mime_type

    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _signed_url_from_response(response: Any) -> str | None:
    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        return (
            response.get("signedURL")
            or response.get("signedUrl")
            or response.get("signed_url")
        )

    return (
        getattr(response, "signedURL", None)
        or getattr(response, "signed_url", None)
        or getattr(response, "signedUrl", None)
    )


def create_signed_media_url(
    client: Client,
    media: dict,
    *,
    expires_in: int = 3600,
) -> str | None:
    external_url = str(
        media.get("external_url") or ""
    ).strip()
    if external_url:
        return external_url

    bucket = str(
        media.get("storage_bucket") or ""
    ).strip()
    path = str(
        media.get("storage_path") or ""
    ).strip()

    if not bucket or not path:
        return None

    response = (
        client.storage
        .from_(bucket)
        .create_signed_url(
            path,
            expires_in,
        )
    )
    return _signed_url_from_response(response)


def create_signed_download_url(
    client: Client,
    media: dict,
    *,
    expires_in: int = 3600,
) -> str | None:
    bucket = str(
        media.get("storage_bucket") or ""
    ).strip()
    path = str(
        media.get("storage_path") or ""
    ).strip()

    if not bucket or not path:
        return None

    response = (
        client.storage
        .from_(bucket)
        .create_signed_url(
            path,
            expires_in,
            {"download": True},
        )
    )
    return _signed_url_from_response(response)


def fetch_media_assets(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
) -> pd.DataFrame:
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
    return pd.DataFrame(response.data or [])


def fetch_media_counts(
    client: Client,
    items: list[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    if not items:
        return {}

    result: dict[tuple[str, str], int] = {}
    grouped: dict[str, list[str]] = {}

    for entity_type, entity_id in items:
        grouped.setdefault(entity_type, []).append(
            str(entity_id)
        )

    for entity_type, entity_ids in grouped.items():
        unique_ids = list(dict.fromkeys(entity_ids))

        for start in range(0, len(unique_ids), 150):
            chunk = unique_ids[start:start + 150]

            response = (
                client.table("media_asset_counts")
                .select(
                    "entity_type,entity_id,media_count"
                )
                .eq("entity_type", entity_type)
                .in_("entity_id", chunk)
                .execute()
            )

            for row in response.data or []:
                key = (
                    str(row.get("entity_type")),
                    str(row.get("entity_id")),
                )
                result[key] = int(
                    row.get("media_count") or 0
                )

    return result


def fetch_primary_media_assets(
    client: Client,
    items: list[tuple[str, str]],
) -> dict[tuple[str, str], dict]:
    if not items:
        return {}

    result: dict[tuple[str, str], dict] = {}
    grouped: dict[str, list[str]] = {}

    for entity_type, entity_id in items:
        grouped.setdefault(entity_type, []).append(
            str(entity_id)
        )

    for entity_type, entity_ids in grouped.items():
        unique_ids = list(dict.fromkeys(entity_ids))

        for start in range(0, len(unique_ids), 150):
            chunk = unique_ids[start:start + 150]

            response = (
                client.table("media_assets")
                .select(
                    "id,entity_type,entity_id,asset_type,"
                    "storage_bucket,storage_path,external_url,"
                    "file_name,mime_type,is_primary"
                )
                .eq("entity_type", entity_type)
                .eq("is_primary", True)
                .in_("entity_id", chunk)
                .execute()
            )

            for row in response.data or []:
                key = (
                    str(row.get("entity_type")),
                    str(row.get("entity_id")),
                )
                result[key] = row

    return result


def fetch_primary_media_urls(
    client: Client,
    items: list[tuple[str, str]],
    *,
    expires_in: int = 3600,
) -> dict[tuple[str, str], str]:
    assets = fetch_primary_media_assets(
        client,
        items,
    )
    result: dict[tuple[str, str], str] = {}

    for key, media in assets.items():
        try:
            url = create_signed_media_url(
                client,
                media,
                expires_in=expires_in,
            )
        except Exception:
            url = None

        if url:
            result[key] = url

    return result


def upload_media_asset(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    asset_type: str,
    title: str,
    description: str | None,
    file_name: str,
    file_bytes: bytes,
    mime_type: str | None,
    is_primary: bool = False,
) -> dict:
    ensure_media_bucket(client)

    if not file_bytes:
        raise ValueError("O arquivo está vazio.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            "O arquivo ultrapassa o limite de 50 MB."
        )

    resolved_mime = _resolve_mime_type(
        file_name,
        mime_type,
    )
    if resolved_mime not in ALLOWED_MIME_TYPES:
        raise ValueError(
            "Este tipo de arquivo ainda não é suportado."
        )

    safe_name = _safe_filename(file_name)
    storage_path = (
        f"{entity_type}/{entity_id}/"
        f"{uuid4().hex}_{safe_name}"
    )

    (
        client.storage
        .from_(MEDIA_BUCKET)
        .upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": resolved_mime,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
    )

    try:
        if is_primary:
            (
                client.table("media_assets")
                .update({"is_primary": False})
                .eq("entity_type", entity_type)
                .eq("entity_id", entity_id)
                .eq("is_primary", True)
                .execute()
            )

        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "asset_type": asset_type,
            "title": title.strip() or file_name,
            "description": (
                description.strip()
                if description
                else None
            ),
            "storage_bucket": MEDIA_BUCKET,
            "storage_path": storage_path,
            "file_name": file_name,
            "mime_type": resolved_mime,
            "file_size_bytes": len(file_bytes),
            "is_primary": bool(is_primary),
        }

        response = (
            client.table("media_assets")
            .insert(payload)
            .execute()
        )
        return response.data[0] if response.data else payload

    except Exception:
        try:
            (
                client.storage
                .from_(MEDIA_BUCKET)
                .remove([storage_path])
            )
        except Exception:
            pass
        raise


def add_external_media_link(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    asset_type: str,
    title: str,
    external_url: str,
    description: str | None,
    is_primary: bool = False,
) -> dict:
    if is_primary:
        (
            client.table("media_assets")
            .update({"is_primary": False})
            .eq("entity_type", entity_type)
            .eq("entity_id", entity_id)
            .eq("is_primary", True)
            .execute()
        )

    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "asset_type": asset_type,
        "title": title.strip() or "Link externo",
        "description": (
            description.strip()
            if description
            else None
        ),
        "external_url": external_url.strip(),
        "is_primary": bool(is_primary),
    }

    response = (
        client.table("media_assets")
        .insert(payload)
        .execute()
    )
    return response.data[0] if response.data else payload


def delete_media_asset(
    client: Client,
    media: dict,
) -> None:
    bucket = str(
        media.get("storage_bucket") or ""
    ).strip()
    path = str(
        media.get("storage_path") or ""
    ).strip()

    if bucket and path:
        (
            client.storage
            .from_(bucket)
            .remove([path])
        )

    (
        client.table("media_assets")
        .delete()
        .eq("id", str(media["id"]))
        .execute()
    )


def format_file_size(
    file_size_bytes: Any,
) -> str:
    try:
        size = int(file_size_bytes or 0)
    except (TypeError, ValueError):
        return ""

    if size <= 0:
        return ""

    units = ["B", "KB", "MB", "GB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}".replace(
                ".0 ",
                " ",
            )
        value /= 1024

    return ""
