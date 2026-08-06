from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
from supabase import Client

from document_io import InputDocument


MEMORY_BUCKET = "nave-memory"
MEMORY_MAX_FILE_SIZE = 100 * 1024 * 1024
MEMORY_ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
]


def _bucket_identifier(bucket: Any) -> str:
    if isinstance(bucket, dict):
        return str(bucket.get("id") or bucket.get("name") or "")
    return str(
        getattr(bucket, "id", None)
        or getattr(bucket, "name", None)
        or ""
    )


def ensure_memory_bucket(client: Client) -> None:
    bucket_ids = {
        _bucket_identifier(bucket)
        for bucket in (client.storage.list_buckets() or [])
    }
    if MEMORY_BUCKET in bucket_ids:
        return

    client.storage.create_bucket(
        MEMORY_BUCKET,
        options={
            "public": False,
            "allowed_mime_types": MEMORY_ALLOWED_MIME_TYPES,
            "file_size_limit": MEMORY_MAX_FILE_SIZE,
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
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    stem = stem or "arquivo"
    extension = re.sub(r"[^a-z0-9.]", "", path.suffix.lower())
    return f"{stem}{extension}"


def _upload_bytes(
    client: Client,
    *,
    storage_path: str,
    file_bytes: bytes,
    mime_type: str,
) -> None:
    ensure_memory_bucket(client)

    if not file_bytes:
        raise ValueError("O arquivo está vazio.")

    if len(file_bytes) > MEMORY_MAX_FILE_SIZE:
        raise ValueError(
            "O arquivo ultrapassa o limite de 100 MB da Memória."
        )

    client.storage.from_(MEMORY_BUCKET).upload(
        path=storage_path,
        file=file_bytes,
        file_options={
            "content-type": mime_type,
            "cache-control": "3600",
            "upsert": "false",
        },
    )


def _signed_url_value(response: Any) -> str | None:
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
        or getattr(response, "signedUrl", None)
        or getattr(response, "signed_url", None)
    )


def create_memory_signed_url(
    client: Client,
    storage_path: str | None,
    *,
    expires_in: int = 3600,
    download: bool = False,
) -> str | None:
    path = str(storage_path or "").strip()
    if not path:
        return None

    if download:
        response = client.storage.from_(MEMORY_BUCKET).create_signed_url(
            path,
            expires_in,
            {"download": True},
        )
    else:
        response = client.storage.from_(MEMORY_BUCKET).create_signed_url(
            path,
            expires_in,
        )
    return _signed_url_value(response)


def normalize_project_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def fetch_memory_project_options(client: Client) -> pd.DataFrame:
    response = (
        client.table("projects")
        .select("id,project_name,client_brand,event_name,status,created_at")
        .order("project_name")
        .limit(2000)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def ensure_memory_project(
    client: Client,
    *,
    project_name: str,
    client_brand: str | None = None,
    event_name: str | None = None,
) -> str:
    clean_name = str(project_name or "").strip()
    if not clean_name:
        raise ValueError("Informe o nome do projeto.")

    normalized = normalize_project_name(clean_name)
    response = (
        client.table("projects")
        .select("id")
        .eq("normalized_name", normalized)
        .order("created_at")
        .limit(1)
        .execute()
    )

    payload = {
        "project_name": clean_name,
        "normalized_name": normalized,
        "client_brand": str(client_brand).strip() if client_brand else None,
        "event_name": str(event_name).strip() if event_name else None,
        "status": "memória",
        "raw_data": {"source": "memory"},
    }

    if response.data:
        project_id = str(response.data[0]["id"])
        client.table("projects").update(
            {
                key: value
                for key, value in payload.items()
                if value not in (None, "")
            }
        ).eq("id", project_id).execute()
        return project_id

    inserted = client.table("projects").insert(payload).execute()
    if not inserted.data:
        raise RuntimeError("Não foi possível criar o projeto.")
    return str(inserted.data[0]["id"])



def update_memory_project_metadata(
    client: Client,
    *,
    project_id: str,
    project_name: str,
    client_brand: str | None,
    event_name: str | None,
) -> None:
    clean_name = str(
        project_name or ""
    ).strip()

    if not clean_name:
        raise ValueError(
            "O projeto precisa ter um nome."
        )

    client.table("projects").update(
        {
            "project_name": clean_name,
            "normalized_name": (
                normalize_project_name(
                    clean_name
                )
            ),
            "client_brand": (
                str(client_brand).strip()
                if client_brand
                else None
            ),
            "event_name": (
                str(event_name).strip()
                if event_name
                else None
            ),
        }
    ).eq(
        "id",
        project_id,
    ).execute()


def update_memory_document_metadata(
    client: Client,
    *,
    document_id: str,
    title: str,
    version_label: str | None,
    document_status: str,
) -> None:
    clean_title = str(
        title or ""
    ).strip()

    if not clean_title:
        raise ValueError(
            "A apresentação precisa ter um título."
        )

    client.table(
        "memory_documents"
    ).update(
        {
            "title": clean_title,
            "version_label": (
                str(version_label).strip()
                if version_label
                else None
            ),
            "document_status": (
                document_status
            ),
        }
    ).eq(
        "id",
        document_id,
    ).execute()


def fetch_memory_projects_overview(client: Client) -> pd.DataFrame:
    response = (
        client.table("memory_project_overview")
        .select("*")
        .order("latest_memory_activity", desc=True)
        .limit(1000)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def _render_pdf_page(
    doc: InputDocument,
    page_number: int,
    *,
    zoom: float = 1.15,
) -> bytes:
    pdf = fitz.open(stream=doc.data, filetype="pdf")
    try:
        page = pdf.load_page(int(page_number) - 1)
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            alpha=False,
        )
        return pixmap.tobytes("png")
    finally:
        pdf.close()


def render_memory_crop(
    doc: InputDocument,
    page_number: int,
    crop_box: dict,
    *,
    zoom: float = 1.8,
) -> bytes:
    pdf = fitz.open(stream=doc.data, filetype="pdf")
    try:
        page = pdf.load_page(int(page_number) - 1)
        rect = page.rect
        x = max(0.0, min(float(crop_box.get("x") or 0), 1.0))
        y = max(0.0, min(float(crop_box.get("y") or 0), 1.0))
        width = max(0.01, min(float(crop_box.get("width") or 1), 1.0))
        height = max(0.01, min(float(crop_box.get("height") or 1), 1.0))

        clip = fitz.Rect(
            rect.x0 + rect.width * x,
            rect.y0 + rect.height * y,
            min(rect.x1, rect.x0 + rect.width * (x + width)),
            min(rect.y1, rect.y0 + rect.height * (y + height)),
        )

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            clip=clip,
            alpha=False,
        )
        return pixmap.tobytes("png")
    finally:
        pdf.close()


def _document_page_count(doc: InputDocument) -> int:
    pdf = fitz.open(stream=doc.data, filetype="pdf")
    try:
        return int(pdf.page_count)
    finally:
        pdf.close()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return str(value)


def _slide_map(extraction: dict, source_file: str) -> dict[int, dict]:
    result = {}
    for slide in extraction.get("slides", []):
        if str(slide.get("source_file") or "") != source_file:
            continue
        page = int(slide.get("source_page") or 0)
        if page > 0:
            result[page] = slide
    return result


def _selected_pages(source_file: str, items: list[dict]) -> list[int]:
    pages = {1}
    for item in items:
        if str(item.get("source_file") or "") != source_file:
            continue
        page = int(item.get("source_page") or 0)
        if page > 0:
            pages.add(page)
    return sorted(pages)


def save_memory_presentation(
    client: Client,
    *,
    project_id: str,
    source_document: InputDocument,
    extraction: dict,
    selected_items: list[dict],
    document_title: str,
    version_label: str | None,
    document_status: str,
) -> dict:
    if source_document.mime_type != "application/pdf":
        raise ValueError("A apresentação precisa estar em PDF.")

    source_bytes = source_document.original_data or source_document.data
    content_hash = hashlib.sha256(source_bytes).hexdigest()

    duplicate = (
        client.table("memory_documents")
        .select("id")
        .eq("project_id", project_id)
        .eq("content_sha256", content_hash)
        .limit(1)
        .execute()
    )
    if duplicate.data:
        return {
            "status": "duplicate",
            "document_id": duplicate.data[0]["id"],
            "items_saved": 0,
            "pages_saved": 0,
            "visual_crops_saved": 0,
        }

    ensure_memory_bucket(client)
    page_count = _document_page_count(source_document)

    document_payload = {
        "project_id": project_id,
        "title": str(document_title).strip() or source_document.name,
        "file_name": source_document.name,
        "mime_type": "application/pdf",
        "version_label": str(version_label).strip() if version_label else None,
        "document_status": document_status,
        "page_count": page_count,
        "content_sha256": content_hash,
        "extraction_status": "processando",
        "strategic_summary": extraction.get("strategic_summary"),
        "creative_concept": extraction.get("creative_concept"),
        "client_brand": extraction.get("client_brand"),
        "event_name": extraction.get("event_name"),
        "raw_data": _json_safe(extraction),
    }

    inserted = client.table("memory_documents").insert(document_payload).execute()
    if not inserted.data:
        raise RuntimeError("Não foi possível criar o documento da Memória.")

    document_id = str(inserted.data[0]["id"])
    uploaded_paths: list[str] = []

    try:
        original_path = (
            f"projects/{project_id}/documents/{document_id}/"
            f"original/{_safe_filename(source_document.name)}"
        )
        _upload_bytes(
            client,
            storage_path=original_path,
            file_bytes=source_bytes,
            mime_type="application/pdf",
        )
        uploaded_paths.append(original_path)

        client.table("memory_documents").update(
            {
                "storage_bucket": MEMORY_BUCKET,
                "storage_path": original_path,
            }
        ).eq("id", document_id).execute()

        slide_map = _slide_map(extraction, source_document.name)
        pages = _selected_pages(source_document.name, selected_items)
        page_ids: dict[int, str] = {}

        for page_number in pages:
            page_bytes = _render_pdf_page(source_document, page_number)
            page_hash = hashlib.sha256(page_bytes).hexdigest()
            page_path = (
                f"projects/{project_id}/documents/{document_id}/"
                f"pages/{page_number:04d}_{page_hash[:12]}.png"
            )

            _upload_bytes(
                client,
                storage_path=page_path,
                file_bytes=page_bytes,
                mime_type="image/png",
            )
            uploaded_paths.append(page_path)

            slide = slide_map.get(page_number, {})
            page_response = client.table("memory_pages").insert(
                {
                    "project_id": project_id,
                    "document_id": document_id,
                    "page_number": page_number,
                    "slide_title": slide.get("slide_title")
                    or ("Capa" if page_number == 1 else None),
                    "slide_summary": slide.get("slide_summary"),
                    "primary_section": slide.get("primary_section"),
                    "storage_bucket": MEMORY_BUCKET,
                    "storage_path": page_path,
                    "content_sha256": page_hash,
                    "raw_data": _json_safe(slide),
                }
            ).execute()

            if page_response.data:
                page_ids[page_number] = str(page_response.data[0]["id"])

        items_saved = 0
        crop_count = 0

        for sort_order, item in enumerate(selected_items, start=1):
            if str(item.get("source_file") or "") != source_document.name:
                continue

            page_number = int(item.get("source_page") or 0)
            if page_number <= 0:
                continue

            item_response = client.table("memory_items").insert(
                {
                    "project_id": project_id,
                    "document_id": document_id,
                    "page_id": page_ids.get(page_number),
                    "source_page": page_number,
                    "section_key": item.get("section_key"),
                    "item_type": item.get("item_type") or "Conteúdo",
                    "title": item.get("title") or "Sem título",
                    "summary": item.get("summary"),
                    "description": item.get("description"),
                    "item_status": item.get("status") or "Não identificado",
                    "tags": item.get("tags") or [],
                    "objectives": item.get("objectives") or [],
                    "audiences": item.get("audiences") or [],
                    "mechanics": item.get("mechanics") or [],
                    "technologies": item.get("technologies") or [],
                    "journey_stage": item.get("journey_stage"),
                    "slide_title": item.get("slide_title"),
                    "visual_crop": item.get("visual_crop"),
                    "confidence": item.get("confidence"),
                    "evidence": item.get("evidence"),
                    "sort_order": sort_order,
                    "raw_data": _json_safe(item),
                }
            ).execute()

            if not item_response.data:
                continue

            item_id = str(item_response.data[0]["id"])
            items_saved += 1

            crop_box = item.get("visual_crop")
            if not crop_box:
                continue

            try:
                crop_bytes = render_memory_crop(
                    source_document,
                    page_number,
                    crop_box,
                )
                crop_hash = hashlib.sha256(crop_bytes).hexdigest()
                crop_path = (
                    f"projects/{project_id}/documents/{document_id}/"
                    f"items/{item_id}/{crop_hash[:16]}.png"
                )

                _upload_bytes(
                    client,
                    storage_path=crop_path,
                    file_bytes=crop_bytes,
                    mime_type="image/png",
                )
                uploaded_paths.append(crop_path)

                client.table("memory_items").update(
                    {
                        "visual_storage_bucket": MEMORY_BUCKET,
                        "visual_storage_path": crop_path,
                        "visual_content_sha256": crop_hash,
                    }
                ).eq("id", item_id).execute()
                crop_count += 1
            except Exception:
                pass

        client.table("memory_documents").update(
            {
                "extraction_status": "pronto",
                "items_count": items_saved,
                "rendered_pages_count": len(page_ids),
                "visual_crops_count": crop_count,
            }
        ).eq("id", document_id).execute()

        return {
            "status": "saved",
            "document_id": document_id,
            "items_saved": items_saved,
            "pages_saved": len(page_ids),
            "visual_crops_saved": crop_count,
        }

    except Exception:
        if uploaded_paths:
            try:
                client.storage.from_(MEMORY_BUCKET).remove(uploaded_paths)
            except Exception:
                pass
        try:
            client.table("memory_documents").delete().eq(
                "id", document_id
            ).execute()
        except Exception:
            pass
        raise


def fetch_memory_documents(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table("memory_documents")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def fetch_memory_pages(
    client: Client,
    *,
    project_id: str,
    document_ids: list[str] | None = None,
) -> pd.DataFrame:
    query = (
        client.table("memory_pages")
        .select("*")
        .eq("project_id", project_id)
        .order("page_number")
    )
    if document_ids:
        query = query.in_("document_id", document_ids)
    return pd.DataFrame(query.execute().data or [])


def fetch_memory_items(
    client: Client,
    *,
    project_id: str,
    document_ids: list[str] | None = None,
) -> pd.DataFrame:
    query = (
        client.table("memory_items")
        .select("*")
        .eq("project_id", project_id)
        .order("section_key")
        .order("sort_order")
        .order("source_page")
    )
    if document_ids:
        query = query.in_("document_id", document_ids)
    return pd.DataFrame(query.execute().data or [])


def update_memory_item(
    client: Client,
    *,
    item_id: str,
    section_key: str,
    item_type: str,
    title: str,
    summary: str | None,
    description: str | None,
    item_status: str,
    tags: list[str],
) -> None:
    client.table("memory_items").update(
        {
            "section_key": section_key,
            "item_type": str(item_type).strip() or "Conteúdo",
            "title": str(title).strip() or "Sem título",
            "summary": str(summary).strip() if summary else None,
            "description": str(description).strip() if description else None,
            "item_status": item_status,
            "tags": [
                str(tag).strip()
                for tag in tags
                if str(tag).strip()
            ],
        }
    ).eq("id", item_id).execute()


def delete_memory_document(
    client: Client,
    *,
    document_id: str,
) -> None:
    document_response = (
        client.table("memory_documents")
        .select("storage_path")
        .eq("id", document_id)
        .limit(1)
        .execute()
    )
    page_response = (
        client.table("memory_pages")
        .select("storage_path")
        .eq("document_id", document_id)
        .execute()
    )
    item_response = (
        client.table("memory_items")
        .select("visual_storage_path")
        .eq("document_id", document_id)
        .execute()
    )

    paths = []
    for row in document_response.data or []:
        if row.get("storage_path"):
            paths.append(row["storage_path"])
    for row in page_response.data or []:
        if row.get("storage_path"):
            paths.append(row["storage_path"])
    for row in item_response.data or []:
        if row.get("visual_storage_path"):
            paths.append(row["visual_storage_path"])

    if paths:
        client.storage.from_(MEMORY_BUCKET).remove(list(dict.fromkeys(paths)))

    client.table("memory_documents").delete().eq("id", document_id).execute()
