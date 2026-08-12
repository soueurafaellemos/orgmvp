from __future__ import annotations

import hashlib
import math
import time
import re
import unicodedata
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
from supabase import Client

from nave_storage import (
    create_signed_url as storage_signed_url,
    delete_objects,
    put_bytes,
    r2_bucket_marker,
    verify_r2_access,
)

from document_io import InputDocument


MEMORY_BUCKET = "nave-memory"
MEMORY_MAX_FILE_SIZE = 300 * 1024 * 1024
MEMORY_ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
]

MEMORY_VALID_SECTIONS = {
    "strategy",
    "scenography",
    "activations",
    "gifts",
    "journey_operation",
    "communication",
    "content_agenda",
    "partners_sponsorship",
    "pr_esg_legacy",
}

MEMORY_VALID_ITEM_STATUS = {
    "Referência",
    "Proposto",
    "Opção",
    "Recomendado",
    "Aprovado",
    "Descartado",
    "Executado",
    "Não identificado",
}


class MemorySaveError(RuntimeError):
    def __init__(
        self,
        stage: str,
        safe_message: str,
        *,
        original: Exception | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.stage = stage
        self.safe_message = safe_message
        self.original = original



def _bucket_identifier(bucket: Any) -> str:
    if isinstance(bucket, dict):
        return str(bucket.get("id") or bucket.get("name") or "")
    return str(
        getattr(bucket, "id", None)
        or getattr(bucket, "name", None)
        or ""
    )


def ensure_memory_bucket(client: Client) -> None:
    # R2 is the canonical storage for all new NAVE files.
    try:
        verify_r2_access()
    except Exception as exc:
        raise MemorySaveError(
            "armazenamento",
            "A NAVE não conseguiu acessar o armazenamento privado no Cloudflare R2.",
            original=exc,
        ) from exc


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
    critical: bool = True,
) -> str:
    ensure_memory_bucket(client)
    if not file_bytes:
        raise ValueError("O arquivo está vazio.")
    if len(file_bytes) > MEMORY_MAX_FILE_SIZE:
        raise ValueError("O arquivo ultrapassa o limite de 300 MB da Memória.")
    try:
        result = put_bytes(
            path=storage_path,
            data=file_bytes,
            content_type=mime_type,
            cache_control="3600",
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            logical_kind="memory",
        )
        return str(result.get("storage_bucket") or r2_bucket_marker())
    except Exception as exc:
        if critical:
            raise MemorySaveError(
                "upload",
                "A NAVE não conseguiu enviar o arquivo para o Cloudflare R2.",
                original=exc,
            ) from exc
        raise


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
    storage_bucket: str | None = None,
    expires_in: int = 3600,
    download: bool = False,
) -> str | None:
    return storage_signed_url(
        client,
        bucket_name=storage_bucket or MEMORY_BUCKET,
        path=storage_path,
        expires_in=expires_in,
        download=download,
    )


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


def create_memory_project(
    client: Client,
    *,
    project_name: str,
    client_brand: str | None = None,
    event_name: str | None = None,
) -> str:
    """
    Cria sempre um novo projeto da Memória.

    Este fluxo representa uma apresentação final enviada ao cliente.
    Ele nunca procura, atualiza ou reaproveita um projeto existente.
    """
    clean_name = str(
        project_name or ""
    ).strip()

    if not clean_name:
        raise ValueError(
            "Informe o nome do projeto."
        )

    payload = {
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
        "status": "rascunho",
        "raw_data": {
            "source": (
                "memory_final_presentation"
            ),
            "creates_new_project": True,
        },
    }

    inserted = (
        client.table("projects")
        .insert(payload)
        .execute()
    )

    if not inserted.data:
        raise RuntimeError(
            "Não foi possível criar "
            "o projeto da Memória."
        )

    return str(
        inserted.data[0]["id"]
    )


def delete_memory_project(
    client: Client,
    *,
    project_id: str,
) -> None:
    """Remove an orphan Memory project after a failed first save."""
    try:
        (
            client.table("projects")
            .delete()
            .eq("id", project_id)
            .execute()
        )
    except Exception:
        pass



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
    zoom: float = 1.0,
) -> bytes:
    pdf = fitz.open(
        stream=doc.data,
        filetype="pdf",
    )
    try:
        page = pdf.load_page(
            int(page_number) - 1
        )
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(
                zoom,
                zoom,
            ),
            alpha=False,
        )
        return pixmap.tobytes(
            "jpeg",
            jpg_quality=78,
        )
    finally:
        pdf.close()


def render_memory_crop(
    doc: InputDocument,
    page_number: int,
    crop_box: dict,
    *,
    zoom: float = 1.55,
) -> bytes:
    pdf = fitz.open(
        stream=doc.data,
        filetype="pdf",
    )
    try:
        page = pdf.load_page(
            int(page_number) - 1
        )
        rect = page.rect
        x = max(
            0.0,
            min(
                float(crop_box.get("x") or 0),
                1.0,
            ),
        )
        y = max(
            0.0,
            min(
                float(crop_box.get("y") or 0),
                1.0,
            ),
        )
        width = max(
            0.01,
            min(
                float(crop_box.get("width") or 1),
                1.0,
            ),
        )
        height = max(
            0.01,
            min(
                float(crop_box.get("height") or 1),
                1.0,
            ),
        )

        clip = fitz.Rect(
            rect.x0 + rect.width * x,
            rect.y0 + rect.height * y,
            min(
                rect.x1,
                rect.x0 + rect.width * (x + width),
            ),
            min(
                rect.y1,
                rect.y0 + rect.height * (y + height),
            ),
        )

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(
                zoom,
                zoom,
            ),
            clip=clip,
            alpha=False,
        )
        return pixmap.tobytes(
            "jpeg",
            jpg_quality=84,
        )
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


def _clip_text(
    value: Any,
    limit: int,
) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _compact_memory_raw_data(
    extraction: dict,
) -> dict:
    diagnostic = extraction.get(
        "coverage_diagnostic"
    ) or {}

    compact_findings = []
    for finding in (
        diagnostic.get("findings")
        or []
    )[:80]:
        compact_findings.append(
            {
                "source_file": finding.get("source_file"),
                "source_locator": finding.get("source_locator"),
                "detected_information": _clip_text(
                    finding.get("detected_information"),
                    450,
                ),
                "status": finding.get("status"),
                "severity": finding.get("severity"),
                "suggested_action": finding.get("suggested_action"),
                "suggested_destination": finding.get("suggested_destination"),
                "rationale": _clip_text(
                    finding.get("rationale"),
                    500,
                ),
            }
        )

    compact_suggestions = []
    for suggestion in (
        diagnostic.get(
            "suggested_schema_additions"
        )
        or []
    )[:40]:
        compact_suggestions.append(
            {
                "suggestion_type": suggestion.get("suggestion_type"),
                "title": _clip_text(suggestion.get("title"), 220),
                "description": _clip_text(
                    suggestion.get("description"),
                    650,
                ),
                "priority": suggestion.get("priority"),
            }
        )

    inventory_summary = []
    for row in (
        extraction.get("page_inventory")
        or []
    ):
        inventory_summary.append(
            {
                "page_number": row.get("page_number"),
                "is_meaningful": row.get("is_meaningful"),
                "suggested_section": row.get("suggested_section"),
                "suggested_title": _clip_text(
                    row.get("suggested_title"),
                    220,
                ),
                "expected_min_items": row.get("expected_min_items"),
            }
        )

    return _json_safe(
        {
            "project_name": extraction.get("project_name"),
            "client_brand": extraction.get("client_brand"),
            "event_name": extraction.get("event_name"),
            "document_title": extraction.get("document_title"),
            "version_label": extraction.get("version_label"),
            "strategic_summary": _clip_text(
                extraction.get("strategic_summary"),
                5000,
            ),
            "creative_concept": _clip_text(
                extraction.get("creative_concept"),
                2500,
            ),
            "warnings": [
                _clip_text(item, 700)
                for item in (
                    extraction.get("warnings")
                    or []
                )[:60]
                if _clip_text(item, 700)
            ],
            "coverage": extraction.get("coverage") or {},
            "coverage_diagnostic": {
                "mode": (
                    diagnostic.get("mode")
                    or "memory"
                ),
                "summary": _clip_text(
                    diagnostic.get("summary"),
                    1800,
                ),
                "coverage_score": diagnostic.get("coverage_score"),
                "source_units_total": diagnostic.get("source_units_total"),
                "source_units_meaningful": diagnostic.get("source_units_meaningful"),
                "source_units_covered": diagnostic.get("source_units_covered"),
                "structured_records": diagnostic.get("structured_records"),
                "findings": compact_findings,
                "suggested_schema_additions": compact_suggestions,
                "warnings": [
                    _clip_text(item, 500)
                    for item in (
                        diagnostic.get("warnings")
                        or []
                    )[:30]
                    if _clip_text(item, 500)
                ],
            },
            "page_inventory": inventory_summary,
            "slides_count": len(
                extraction.get("slides")
                or []
            ),
            "items_count": len(
                extraction.get("items")
                or []
            ),
        }
    )


def _safe_text_array(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    return [
        str(item).strip()
        for item in values
        if str(item).strip()
    ]


def _safe_confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return max(0.0, min(number, 1.0))


def _same_source(
    left: Any,
    right: Any,
) -> bool:
    left_name = Path(
        str(left or "")
    ).name.casefold()
    right_name = Path(
        str(right or "")
    ).name.casefold()
    return bool(left_name) and left_name == right_name


def _preflight_memory_save(
    client: Client,
) -> None:
    try:
        for table_name in (
            "memory_documents",
            "memory_pages",
            "memory_items",
        ):
            (
                client.table(table_name)
                .select("id")
                .limit(1)
                .execute()
            )
    except Exception as exc:
        raise MemorySaveError(
            "estrutura",
            (
                "A estrutura da Memória não está disponível no Supabase. "
                "Execute novamente o SQL inicial da Memória antes de salvar."
            ),
            original=exc,
        ) from exc

    ensure_memory_bucket(client)



def _slide_map(extraction: dict, source_file: str) -> dict[int, dict]:
    result = {}
    for slide in extraction.get("slides", []):
        if str(slide.get("source_file") or "") != source_file:
            continue
        page = int(slide.get("source_page") or 0)
        if page > 0:
            result[page] = slide
    return result


def _selected_pages(
    source_file: str,
    items: list[dict],
    *,
    page_count: int,
) -> list[int]:
    pages = {1}

    for item in items:
        item_source = item.get(
            "source_file"
        )
        if item_source and not _same_source(
            item_source,
            source_file,
        ):
            continue

        page = int(
            item.get("source_page")
            or 0
        )
        if 1 <= page <= page_count:
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
    progress_callback=None,
) -> dict:
    def progress(
        done: int,
        total: int,
        message: str,
    ) -> None:
        if progress_callback:
            progress_callback(
                done,
                total,
                message,
            )

    if (
        source_document.mime_type
        != "application/pdf"
    ):
        raise MemorySaveError(
            "arquivo",
            "A apresentação precisa estar em PDF.",
        )

    progress(
        0,
        6,
        "Verificando a estrutura da Memória...",
    )
    _preflight_memory_save(client)

    source_bytes = (
        source_document.original_data
        or source_document.data
    )
    content_hash = hashlib.sha256(
        source_bytes
    ).hexdigest()
    page_count = _document_page_count(
        source_document
    )

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
            "document_id": (
                duplicate.data[0]["id"]
            ),
            "items_saved": 0,
            "pages_saved": 0,
            "visual_crops_saved": 0,
            "warnings": [],
        }

    compact_raw_data = (
        _compact_memory_raw_data(
            extraction
        )
    )

    document_payload = {
        "project_id": project_id,
        "title": (
            str(document_title).strip()
            or source_document.name
        ),
        "file_name": source_document.name,
        "mime_type": "application/pdf",
        "version_label": (
            str(version_label).strip()
            if version_label
            else None
        ),
        "document_status": (
            document_status
            if document_status in {
                "sent_to_client",
                "revision",
                "approved",
                "executed",
                "internal_reference",
            }
            else "sent_to_client"
        ),
        "page_count": page_count,
        "content_sha256": content_hash,
        "extraction_status": "processando",
        "strategic_summary": (
            extraction.get(
                "strategic_summary"
            )
        ),
        "creative_concept": (
            extraction.get(
                "creative_concept"
            )
        ),
        "client_brand": extraction.get(
            "client_brand"
        ),
        "event_name": extraction.get(
            "event_name"
        ),
        "raw_data": compact_raw_data,
    }

    progress(
        1,
        6,
        "Criando o documento da Memória...",
    )

    try:
        inserted = (
            client.table("memory_documents")
            .insert(document_payload)
            .execute()
        )
    except Exception as exc:
        raise MemorySaveError(
            "documento",
            (
                "A NAVE não conseguiu criar o registro da "
                "apresentação no Supabase."
            ),
            original=exc,
        ) from exc

    if not inserted.data:
        raise MemorySaveError(
            "documento",
            (
                "O Supabase não confirmou a criação "
                "da apresentação."
            ),
        )

    document_id = str(
        inserted.data[0]["id"]
    )
    uploaded_paths: list[str] = []
    warnings: list[str] = []

    try:
        progress(
            2,
            6,
            "Enviando o PDF original...",
        )
        original_path = (
            f"projects/{project_id}/"
            f"documents/{document_id}/"
            f"original/"
            f"{_safe_filename(source_document.name)}"
        )
        _upload_bytes(
            client,
            storage_path=original_path,
            file_bytes=source_bytes,
            mime_type="application/pdf",
            critical=True,
        )
        uploaded_paths.append(
            original_path
        )

        (
            client.table("memory_documents")
            .update(
                {
                    "storage_bucket": (
                        r2_bucket_marker()
                    ),
                    "storage_path": (
                        original_path
                    ),
                }
            )
            .eq("id", document_id)
            .execute()
        )

        slide_map = _slide_map(
            extraction,
            source_document.name,
        )
        pages = _selected_pages(
            source_document.name,
            selected_items,
            page_count=page_count,
        )
        page_ids: dict[int, str] = {}

        progress(
            3,
            6,
            (
                f"Preservando {len(pages)} "
                "slide(s) para consulta..."
            ),
        )

        for index, page_number in enumerate(
            pages,
            start=1,
        ):
            try:
                page_bytes = _render_pdf_page(
                    source_document,
                    page_number,
                )
                page_hash = hashlib.sha256(
                    page_bytes
                ).hexdigest()
                page_path = (
                    f"projects/{project_id}/"
                    f"documents/{document_id}/"
                    f"pages/{page_number:04d}_"
                    f"{page_hash[:12]}.jpg"
                )

                _upload_bytes(
                    client,
                    storage_path=page_path,
                    file_bytes=page_bytes,
                    mime_type="image/jpeg",
                    critical=False,
                )
                uploaded_paths.append(
                    page_path
                )

                slide = slide_map.get(
                    page_number,
                    {},
                )
                page_response = (
                    client.table("memory_pages")
                    .insert(
                        {
                            "project_id": project_id,
                            "document_id": (
                                document_id
                            ),
                            "page_number": (
                                page_number
                            ),
                            "slide_title": (
                                slide.get(
                                    "slide_title"
                                )
                                or (
                                    "Capa"
                                    if page_number == 1
                                    else None
                                )
                            ),
                            "slide_summary": (
                                slide.get(
                                    "slide_summary"
                                )
                            ),
                            "primary_section": (
                                slide.get(
                                    "primary_section"
                                )
                                if slide.get(
                                    "primary_section"
                                )
                                in MEMORY_VALID_SECTIONS
                                else None
                            ),
                            "storage_bucket": (
                                r2_bucket_marker()
                            ),
                            "storage_path": (
                                page_path
                            ),
                            "content_sha256": (
                                page_hash
                            ),
                            "raw_data": _json_safe(
                                slide
                            ),
                        }
                    )
                    .execute()
                )

                if page_response.data:
                    page_ids[
                        page_number
                    ] = str(
                        page_response
                        .data[0]["id"]
                    )

            except Exception as exc:
                warnings.append(
                    (
                        f"O slide {page_number} não "
                        "recebeu uma imagem separada. "
                        "O PDF original permanece disponível. "
                        f"Detalhe técnico: {exc}"
                    )
                )

        progress(
            4,
            6,
            (
                f"Salvando {len(selected_items)} "
                "conteúdo(s) decupado(s)..."
            ),
        )

        source_rows_by_order: dict[int, dict] = {}
        item_payloads = []

        for sort_order, item in enumerate(
            selected_items,
            start=1,
        ):
            item_source = item.get(
                "source_file"
            )
            if item_source and not _same_source(
                item_source,
                source_document.name,
            ):
                continue

            page_number = int(
                item.get("source_page")
                or 0
            )
            if not (
                1 <= page_number <= page_count
            ):
                warnings.append(
                    (
                        "Um conteúdo foi ignorado por "
                        "não possuir um número de slide válido: "
                        + str(
                            item.get("title")
                            or "Sem título"
                        )
                    )
                )
                continue

            section_key = str(
                item.get("section_key")
                or "strategy"
            )
            if (
                section_key
                not in MEMORY_VALID_SECTIONS
            ):
                section_key = "strategy"

            item_status = str(
                item.get("status")
                or "Não identificado"
            )
            if (
                item_status
                not in MEMORY_VALID_ITEM_STATUS
            ):
                item_status = (
                    "Não identificado"
                )

            payload = {
                "project_id": project_id,
                "document_id": document_id,
                "page_id": page_ids.get(
                    page_number
                ),
                "source_page": page_number,
                "section_key": section_key,
                "item_type": (
                    str(
                        item.get(
                            "item_type"
                        )
                        or "Conteúdo"
                    )[:250]
                ),
                "title": (
                    str(
                        item.get("title")
                        or "Sem título"
                    )[:500]
                ),
                "summary": _clip_text(
                    item.get("summary"),
                    4000,
                ),
                "description": _clip_text(
                    item.get("description"),
                    12000,
                ),
                "item_status": item_status,
                "tags": _safe_text_array(
                    item.get("tags")
                ),
                "objectives": _safe_text_array(
                    item.get("objectives")
                ),
                "audiences": _safe_text_array(
                    item.get("audiences")
                ),
                "mechanics": _safe_text_array(
                    item.get("mechanics")
                ),
                "technologies": _safe_text_array(
                    item.get("technologies")
                ),
                "journey_stage": _clip_text(
                    item.get("journey_stage"),
                    500,
                ),
                "slide_title": _clip_text(
                    item.get("slide_title"),
                    700,
                ),
                "visual_crop": _json_safe(
                    item.get("visual_crop")
                ),
                "confidence": _safe_confidence(
                    item.get("confidence")
                ),
                "evidence": _clip_text(
                    item.get("evidence"),
                    2500,
                ),
                "sort_order": sort_order,
                "raw_data": _json_safe(
                    {
                        "extraction_origin": (
                            item.get(
                                "extraction_origin"
                            )
                        ),
                        "source_file": (
                            item.get(
                                "source_file"
                            )
                        ),
                        "source_page": (
                            page_number
                        ),
                    }
                ),
            }
            item_payloads.append(
                payload
            )
            source_rows_by_order[
                sort_order
            ] = item

        inserted_items: list[dict] = []
        chunk_size = 30

        for start_index in range(
            0,
            len(item_payloads),
            chunk_size,
        ):
            chunk = item_payloads[
                start_index:
                start_index + chunk_size
            ]
            try:
                response = (
                    client.table("memory_items")
                    .insert(chunk)
                    .execute()
                )
                inserted_items.extend(
                    response.data or []
                )
            except Exception as chunk_exc:
                for payload in chunk:
                    try:
                        response = (
                            client.table(
                                "memory_items"
                            )
                            .insert(payload)
                            .execute()
                        )
                        inserted_items.extend(
                            response.data or []
                        )
                    except Exception as item_exc:
                        warnings.append(
                            (
                                "Um conteúdo não pôde ser "
                                "salvo: "
                                + str(
                                    payload.get("title")
                                    or "Sem título"
                                )
                                + ". Detalhe técnico: "
                                + str(item_exc)
                            )
                        )

        if item_payloads and not inserted_items:
            raise MemorySaveError(
                "conteúdos",
                (
                    "Nenhum conteúdo decupado pôde ser salvo. "
                    "A análise foi preservada na tela para nova tentativa."
                ),
            )

        progress(
            5,
            6,
            "Criando as imagens das fichas...",
        )

        crop_count = 0
        for inserted_item in inserted_items:
            sort_order = int(
                inserted_item.get(
                    "sort_order"
                )
                or 0
            )
            source_item = (
                source_rows_by_order.get(
                    sort_order
                )
            )
            if not source_item:
                continue

            crop_box = source_item.get(
                "visual_crop"
            )
            if not crop_box:
                continue

            try:
                page_number = int(
                    source_item.get(
                        "source_page"
                    )
                    or 0
                )
                crop_bytes = render_memory_crop(
                    source_document,
                    page_number,
                    crop_box,
                )
                crop_hash = hashlib.sha256(
                    crop_bytes
                ).hexdigest()
                item_id = str(
                    inserted_item["id"]
                )
                crop_path = (
                    f"projects/{project_id}/"
                    f"documents/{document_id}/"
                    f"items/{item_id}/"
                    f"{crop_hash[:16]}.jpg"
                )

                _upload_bytes(
                    client,
                    storage_path=crop_path,
                    file_bytes=crop_bytes,
                    mime_type="image/jpeg",
                    critical=False,
                )
                uploaded_paths.append(
                    crop_path
                )

                (
                    client.table("memory_items")
                    .update(
                        {
                            "visual_storage_bucket": (
                                r2_bucket_marker()
                            ),
                            "visual_storage_path": (
                                crop_path
                            ),
                            "visual_content_sha256": (
                                crop_hash
                            ),
                        }
                    )
                    .eq("id", item_id)
                    .execute()
                )
                crop_count += 1
            except Exception as exc:
                warnings.append(
                    (
                        "Uma ficha usará o slide completo "
                        "porque o recorte não pôde ser salvo. "
                        f"Detalhe técnico: {exc}"
                    )
                )

        final_raw_data = {
            **compact_raw_data,
            "save_warnings": [
                _clip_text(item, 900)
                for item in warnings[:120]
            ],
        }

        (
            client.table("memory_documents")
            .update(
                {
                    "extraction_status": "pronto",
                    "items_count": len(
                        inserted_items
                    ),
                    "rendered_pages_count": len(
                        page_ids
                    ),
                    "visual_crops_count": (
                        crop_count
                    ),
                    "raw_data": _json_safe(
                        final_raw_data
                    ),
                }
            )
            .eq("id", document_id)
            .execute()
        )

        progress(
            6,
            6,
            "Projeto salvo na Memória.",
        )

        return {
            "status": "saved",
            "document_id": document_id,
            "items_saved": len(
                inserted_items
            ),
            "pages_saved": len(
                page_ids
            ),
            "visual_crops_saved": (
                crop_count
            ),
            "warnings": warnings,
        }

    except MemorySaveError:
        if uploaded_paths:
            try:
                delete_objects(
                    client,
                    bucket_name=r2_bucket_marker(),
                    paths=uploaded_paths,
                )
            except Exception:
                pass
        try:
            (
                client.table(
                    "memory_documents"
                )
                .delete()
                .eq("id", document_id)
                .execute()
            )
        except Exception:
            pass
        raise

    except Exception as exc:
        if uploaded_paths:
            try:
                delete_objects(
                    client,
                    bucket_name=r2_bucket_marker(),
                    paths=uploaded_paths,
                )
            except Exception:
                pass
        try:
            (
                client.table(
                    "memory_documents"
                )
                .delete()
                .eq("id", document_id)
                .execute()
            )
        except Exception:
            pass
        raise MemorySaveError(
            "finalização",
            (
                "O salvamento foi interrompido antes da finalização. "
                "A análise continua disponível para uma nova tentativa."
            ),
            original=exc,
        ) from exc



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
        .select("storage_bucket,storage_path")
        .eq("id", document_id)
        .limit(1)
        .execute()
    )
    page_response = (
        client.table("memory_pages")
        .select("storage_bucket,storage_path")
        .eq("document_id", document_id)
        .execute()
    )
    item_response = (
        client.table("memory_items")
        .select("visual_storage_bucket,visual_storage_path")
        .eq("document_id", document_id)
        .execute()
    )

    by_bucket: dict[str, list[str]] = {}
    for row in document_response.data or []:
        path = str(row.get("storage_path") or "").strip()
        if path:
            by_bucket.setdefault(str(row.get("storage_bucket") or MEMORY_BUCKET), []).append(path)
    for row in page_response.data or []:
        path = str(row.get("storage_path") or "").strip()
        if path:
            by_bucket.setdefault(str(row.get("storage_bucket") or MEMORY_BUCKET), []).append(path)
    for row in item_response.data or []:
        path = str(row.get("visual_storage_path") or "").strip()
        if path:
            by_bucket.setdefault(str(row.get("visual_storage_bucket") or MEMORY_BUCKET), []).append(path)

    for bucket_name, paths in by_bucket.items():
        delete_objects(client, bucket_name=bucket_name, paths=paths)

    client.table("memory_documents").delete().eq("id", document_id).execute()
