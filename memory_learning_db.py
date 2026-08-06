from __future__ import annotations

import hashlib
import math
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
from supabase import Client

from memory_cost_parser import normalize_text
from memory_learning_models import (
    BriefingExtraction,
    CostWorkbookResult,
)


COST_BUCKET = "nave-memory-costs"
COST_MAX_FILE_SIZE = 50 * 1024 * 1024

COST_MIME_TYPES = {
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    # Supabase normalizes request MIME values to lowercase.
    # The generic Excel MIME is accepted by existing buckets and
    # avoids the case-sensitive macroEnabled/macroenabled mismatch.
    ".xlsm": "application/vnd.ms-excel",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}


COST_ALLOWED_MIME_TYPES = sorted(
    {
        *COST_MIME_TYPES.values(),
        "application/vnd.ms-excel.sheet.macroenabled.12",
        "application/vnd.ms-excel.sheet.macroEnabled.12",
    }
)

BRIEFING_BUCKET = "nave-memory-briefings"
BRIEFING_MAX_FILE_SIZE = 50 * 1024 * 1024
BRIEFING_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".pptx": (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    ),
    ".txt": "text/plain",
    ".md": "text/markdown",
}

STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "para",
    "por",
    "um",
    "uma",
    "no",
    "na",
    "nos",
    "nas",
    "o",
    "os",
    "que",
    "considerando",
    "proposta",
    "projeto",
    "slide",
    "imagem",
    "registro",
    "visual",
}

SECTION_KEYWORDS = {
    "gifts": {
        "brinde",
        "gift",
        "kit",
        "meia",
        "tatuagem",
        "bolinha",
        "charm",
        "lapis",
        "uniforme",
        "pulseira",
        "credencial",
        "sacola",
        "caneca",
        "botton",
        "chapeu",
        "tiara",
        "embalagem",
    },
    "activations": {
        "ativacao",
        "oficina",
        "jogo",
        "game",
        "photo",
        "foto",
        "experiencia",
        "personalizacao",
        "sampling",
        "origami",
        "pescaria",
        "amarelinha",
        "quebra",
        "colorir",
    },
    "scenography": {
        "infraestrutura",
        "cenografia",
        "portico",
        "estrutura",
        "paisagismo",
        "iluminacao",
        "mobiliario",
        "fachada",
        "revestimento",
        "piso",
        "camarote",
        "palco",
        "stand",
        "estande",
        "ambiente",
    },
    "communication": {
        "kv",
        "comunicacao",
        "adesivacao",
        "sinalizacao",
        "identidade",
        "tela",
        "aplicacao",
        "campanha",
    },
    "journey_operation": {
        "staff",
        "promotor",
        "produtor",
        "seguranca",
        "brigadista",
        "limpeza",
        "fotografo",
        "video",
        "logistica",
        "transporte",
        "montagem",
        "desmontagem",
        "operacao",
        "atendimento",
    },
}


class LearningDataError(RuntimeError):
    pass


def _bucket_identifier(
    bucket: Any,
) -> str:
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


def ensure_cost_bucket(
    client: Client,
) -> None:
    buckets = (
        client.storage.list_buckets()
        or []
    )
    bucket_ids = {
        _bucket_identifier(bucket)
        for bucket in buckets
    }

    options = {
        "public": False,
        "allowed_mime_types": (
            COST_ALLOWED_MIME_TYPES
        ),
    }

    if COST_BUCKET in bucket_ids:
        # Corrige também buckets criados pela V26 com a lista antiga.
        try:
            client.storage.update_bucket(
                COST_BUCKET,
                options=options,
            )
        except Exception:
            # O upload de XLSM usa o MIME genérico do Excel como
            # segunda proteção quando a atualização não está disponível.
            pass
        return

    try:
        client.storage.create_bucket(
            COST_BUCKET,
            options=options,
        )
    except Exception as exc:
        message = str(exc).casefold()

        if (
            "already exists" in message
            or "duplicate" in message
            or "409" in message
        ):
            return

        raise LearningDataError(
            "A NAVE não conseguiu preparar o "
            "armazenamento das planilhas."
        ) from exc


def ensure_briefing_bucket(
    client: Client,
) -> None:
    buckets = (
        client.storage.list_buckets()
        or []
    )
    bucket_ids = {
        _bucket_identifier(bucket)
        for bucket in buckets
    }

    if BRIEFING_BUCKET in bucket_ids:
        return

    try:
        # Sem restrição própria de MIME para evitar diferenças de
        # normalização entre navegador, SDK e Storage.
        client.storage.create_bucket(
            BRIEFING_BUCKET,
            options={
                "public": False,
            },
        )
    except Exception as exc:
        message = str(exc).casefold()

        if (
            "already exists" in message
            or "duplicate" in message
            or "409" in message
        ):
            return

        raise LearningDataError(
            "A NAVE não conseguiu preparar o "
            "armazenamento dos briefings."
        ) from exc


def _safe_filename(
    filename: str,
) -> str:
    path = Path(
        filename or "planilha"
    )
    stem = unicodedata.normalize(
        "NFKD",
        path.stem,
    )
    stem = "".join(
        character
        for character in stem
        if not unicodedata.combining(
            character
        )
    )
    stem = re.sub(
        r"[^a-zA-Z0-9]+",
        "-",
        stem,
    ).strip("-").lower()
    stem = stem or "planilha"
    extension = re.sub(
        r"[^a-z0-9.]",
        "",
        path.suffix.casefold(),
    )
    return stem + extension


def _retry(
    operation,
    *,
    attempts: int = 3,
    base_delay: float = 0.6,
):
    last_error = None

    for attempt in range(
        1,
        attempts + 1,
    ):
        try:
            return operation()
        except Exception as exc:
            last_error = exc

            if attempt >= attempts:
                break

            time.sleep(
                base_delay * attempt
            )

    raise last_error


def _upload_cost_file(
    client: Client,
    *,
    storage_path: str,
    file_name: str,
    file_bytes: bytes,
) -> None:
    if not file_bytes:
        raise ValueError(
            "A planilha está vazia."
        )

    if (
        len(file_bytes)
        > COST_MAX_FILE_SIZE
    ):
        raise ValueError(
            "A planilha ultrapassa o limite "
            "de 50 MB."
        )

    suffix = Path(
        file_name
    ).suffix.casefold()
    mime_type = COST_MIME_TYPES.get(
        suffix
    )

    if not mime_type:
        raise ValueError(
            "Formato de planilha não suportado."
        )

    ensure_cost_bucket(client)

    def upload_with(
        content_type: str,
    ):
        return (
            client.storage
            .from_(COST_BUCKET)
            .upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    "content-type": (
                        content_type
                    ),
                    "cache-control": "3600",
                    "upsert": "false",
                },
            )
        )

    try:
        _retry(
            lambda: upload_with(
                mime_type
            )
        )
    except Exception as exc:
        message = str(exc).casefold()

        if (
            suffix == ".xlsm"
            and (
                "invalid_mime_type"
                in message
                or "mime type" in message
                or "415" in message
            )
        ):
            # Compatibilidade com buckets que ainda aceitam apenas
            # o MIME genérico de Excel.
            _retry(
                lambda: upload_with(
                    "application/vnd.ms-excel"
                )
            )
            return

        raise


def _upload_briefing_file(
    client: Client,
    *,
    storage_path: str,
    file_name: str,
    file_bytes: bytes,
) -> None:
    if not file_bytes:
        raise ValueError(
            "O briefing está vazio."
        )

    if (
        len(file_bytes)
        > BRIEFING_MAX_FILE_SIZE
    ):
        raise ValueError(
            "O briefing ultrapassa o limite "
            "de 50 MB."
        )

    suffix = Path(
        file_name
    ).suffix.casefold()
    mime_type = (
        BRIEFING_MIME_TYPES.get(
            suffix
        )
    )

    if not mime_type:
        raise ValueError(
            "Formato de briefing não suportado."
        )

    ensure_briefing_bucket(
        client
    )

    _retry(
        lambda: (
            client.storage
            .from_(BRIEFING_BUCKET)
            .upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    "content-type": (
                        mime_type
                    ),
                    "cache-control": "3600",
                    "upsert": "false",
                },
            )
        )
    )


def _signed_url_value(
    response: Any,
) -> str | None:
    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        return (
            response.get("signedURL")
            or response.get("signedUrl")
            or response.get(
                "signed_url"
            )
        )

    return (
        getattr(
            response,
            "signedURL",
            None,
        )
        or getattr(
            response,
            "signedUrl",
            None,
        )
        or getattr(
            response,
            "signed_url",
            None,
        )
    )


def create_cost_signed_url(
    client: Client,
    storage_path: str | None,
    *,
    expires_in: int = 3600,
    download: bool = False,
) -> str | None:
    path = str(
        storage_path or ""
    ).strip()

    if not path:
        return None

    bucket = client.storage.from_(
        COST_BUCKET
    )

    if download:
        response = (
            bucket.create_signed_url(
                path,
                expires_in,
                {"download": True},
            )
        )
    else:
        response = (
            bucket.create_signed_url(
                path,
                expires_in,
            )
        )

    return _signed_url_value(
        response
    )


def _json_safe(
    value: Any,
) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        if (
            isinstance(value, float)
            and not math.isfinite(
                value
            )
        ):
            return None
        return value

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    if hasattr(value, "item"):
        try:
            return _json_safe(
                value.item()
            )
        except Exception:
            pass

    return str(value)


def _tokens(
    value: Any,
) -> set[str]:
    tokens = {
        token
        for token in normalize_text(
            value
        ).split()
        if (
            len(token) >= 3
            and token not in STOPWORDS
        )
    }

    # Lightweight Portuguese plural normalization improves matches
    # such as pórticos/pórtico and brindes/brinde without requiring
    # an external NLP dependency.
    variants = set(tokens)
    for token in tokens:
        if token.endswith("s") and len(token) > 4:
            variants.add(token[:-1])

    return variants


def _dice(
    first: set[str],
    second: set[str],
) -> float:
    if not first or not second:
        return 0.0

    return (
        2
        * len(
            first.intersection(
                second
            )
        )
        / (
            len(first)
            + len(second)
        )
    )


def _section_hint(
    cost_text: str,
) -> set[str]:
    tokens = _tokens(
        cost_text
    )
    result = set()

    for section, keywords in (
        SECTION_KEYWORDS.items()
    ):
        if tokens.intersection(
            keywords
        ):
            result.add(section)

    return result


def score_cost_memory_match(
    cost_item: dict,
    memory_item: dict,
) -> tuple[float, str]:
    cost_text = " ".join(
        str(
            cost_item.get(key)
            or ""
        )
        for key in [
            "item_name",
            "description",
            "category",
        ]
    )
    memory_text = " ".join(
        str(
            memory_item.get(key)
            or ""
        )
        for key in [
            "title",
            "summary",
            "description",
            "item_type",
            "tags",
        ]
    )

    cost_tokens = _tokens(
        cost_text
    )
    memory_tokens = _tokens(
        memory_text
    )

    lexical = _dice(
        cost_tokens,
        memory_tokens,
    )
    intersection = cost_tokens.intersection(
        memory_tokens
    )
    containment = (
        len(intersection)
        / min(
            len(cost_tokens),
            len(memory_tokens),
        )
        if cost_tokens and memory_tokens
        else 0.0
    )

    score = (
        lexical * 0.52
        + containment * 0.24
    )
    reasons = []

    if lexical > 0:
        reasons.append(
            "termos em comum"
        )

    if containment >= 0.6:
        reasons.append(
            "termos centrais preservados"
        )

    normalized_cost_name = normalize_text(
        cost_item.get(
            "item_name"
        )
    )
    normalized_memory_title = (
        normalize_text(
            memory_item.get(
                "title"
            )
        )
    )

    if (
        normalized_cost_name
        and normalized_memory_title
        and (
            normalized_cost_name
            in normalized_memory_title
            or normalized_memory_title
            in normalized_cost_name
        )
    ):
        score += 0.22
        reasons.append(
            "nome semelhante"
        )

    hinted_sections = _section_hint(
        cost_text
    )
    memory_section = str(
        memory_item.get(
            "section_key"
        )
        or ""
    )

    if (
        memory_section
        and memory_section
        in hinted_sections
    ):
        score += 0.16
        reasons.append(
            "categoria compatível"
        )

    item_type_tokens = _tokens(
        memory_item.get(
            "item_type"
        )
    )
    category_tokens = _tokens(
        cost_item.get(
            "category"
        )
    )

    if item_type_tokens.intersection(
        category_tokens
    ):
        score += 0.08
        reasons.append(
            "tipo compatível"
        )

    return (
        min(
            round(score, 4),
            1.0,
        ),
        ", ".join(reasons)
        or "sem correspondência forte",
    )


def suggest_cost_links(
    cost_items: list[dict],
    memory_items: list[dict],
    *,
    minimum_score: float = 0.22,
) -> list[dict]:
    suggestions = []

    for cost_item in cost_items:
        best_item = None
        best_score = 0.0
        best_reason = ""

        for memory_item in memory_items:
            score, reason = (
                score_cost_memory_match(
                    cost_item,
                    memory_item,
                )
            )

            if score > best_score:
                best_item = memory_item
                best_score = score
                best_reason = reason

        if (
            best_item
            and best_score
            >= minimum_score
        ):
            suggestions.append(
                {
                    "project_id": (
                        cost_item[
                            "project_id"
                        ]
                    ),
                    "cost_item_id": (
                        cost_item["id"]
                    ),
                    "memory_item_id": (
                        best_item["id"]
                    ),
                    "match_score": (
                        best_score
                    ),
                    "match_reason": (
                        best_reason
                    ),
                    "link_status": (
                        "suggested"
                    ),
                }
            )

    return suggestions


def fetch_project_outcome(
    client: Client,
    *,
    project_id: str,
) -> dict:
    response = (
        client.table(
            "memory_project_outcomes"
        )
        .select("*")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else {}
    )


def upsert_project_outcome(
    client: Client,
    *,
    project_id: str,
    values: dict,
) -> None:
    payload = {
        "project_id": project_id,
        **{
            key: _json_safe(value)
            for key, value
            in values.items()
        },
    }

    (
        client.table(
            "memory_project_outcomes"
        )
        .upsert(
            payload,
            on_conflict="project_id",
        )
        .execute()
    )


def update_project_budget(
    client: Client,
    *,
    project_id: str,
    budget_amount: float | None,
    currency: str = "BRL",
) -> None:
    current = fetch_project_outcome(
        client,
        project_id=project_id,
    )

    payload = {
        **current,
        "project_id": project_id,
        "budget_amount": (
            budget_amount
        ),
        "currency": currency,
    }
    payload.pop("created_at", None)
    payload.pop("updated_at", None)

    (
        client.table(
            "memory_project_outcomes"
        )
        .upsert(
            _json_safe(payload),
            on_conflict="project_id",
        )
        .execute()
    )


def fetch_feedback_entries(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_feedback_entries"
        )
        .select("*")
        .eq("project_id", project_id)
        .order(
            "feedback_date",
            desc=True,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def add_feedback_entry(
    client: Client,
    *,
    project_id: str,
    values: dict,
) -> None:
    payload = {
        "project_id": project_id,
        **{
            key: _json_safe(value)
            for key, value
            in values.items()
        },
    }

    (
        client.table(
            "memory_feedback_entries"
        )
        .insert(payload)
        .execute()
    )


def delete_feedback_entry(
    client: Client,
    *,
    feedback_id: str,
) -> None:
    (
        client.table(
            "memory_feedback_entries"
        )
        .delete()
        .eq("id", feedback_id)
        .execute()
    )


def fetch_item_outcomes(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_item_outcomes"
        )
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def upsert_item_outcome(
    client: Client,
    *,
    project_id: str,
    item_id: str,
    values: dict,
) -> None:
    payload = {
        "project_id": project_id,
        "item_id": item_id,
        **{
            key: _json_safe(value)
            for key, value
            in values.items()
        },
    }

    (
        client.table(
            "memory_item_outcomes"
        )
        .upsert(
            payload,
            on_conflict="item_id",
        )
        .execute()
    )


def fetch_cost_documents(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_cost_documents"
        )
        .select("*")
        .eq("project_id", project_id)
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def fetch_cost_items(
    client: Client,
    *,
    project_id: str,
    cost_document_ids: list[str]
    | None = None,
) -> pd.DataFrame:
    query = (
        client.table(
            "memory_cost_items"
        )
        .select("*")
        .eq("project_id", project_id)
        .order("source_sheet")
        .order("source_row")
    )

    if cost_document_ids:
        query = query.in_(
            "cost_document_id",
            cost_document_ids,
        )

    response = query.execute()

    return pd.DataFrame(
        response.data or []
    )


def fetch_cost_links(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_cost_links"
        )
        .select("*")
        .eq("project_id", project_id)
        .order(
            "match_score",
            desc=True,
        )
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def _insert_chunks(
    client: Client,
    *,
    table_name: str,
    rows: list[dict],
    chunk_size: int = 100,
) -> list[dict]:
    inserted = []

    for start in range(
        0,
        len(rows),
        chunk_size,
    ):
        chunk = rows[
            start : start + chunk_size
        ]

        response = (
            client.table(
                table_name
            )
            .insert(chunk)
            .execute()
        )
        inserted.extend(
            response.data or []
        )

    return inserted


def save_cost_document(
    client: Client,
    *,
    project_id: str,
    file_name: str,
    file_bytes: bytes,
    parsed: CostWorkbookResult,
    memory_items: list[dict],
) -> dict:
    content_hash = hashlib.sha256(
        file_bytes
    ).hexdigest()

    duplicate = (
        client.table(
            "memory_cost_documents"
        )
        .select("id")
        .eq("project_id", project_id)
        .eq(
            "content_sha256",
            content_hash,
        )
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
            "links_suggested": 0,
        }

    summary = {
        "included_items": sum(
            item.item_status
            == "included"
            for item in parsed.items
        ),
        "optional_items": sum(
            item.item_status
            == "optional"
            for item in parsed.items
        ),
        "pending_items": sum(
            item.item_status
            in {
                "pending",
                "no_value",
            }
            for item in parsed.items
        ),
    }

    document_payload = {
        "project_id": project_id,
        "title": parsed.title,
        "file_name": file_name,
        "mime_type": (
            COST_MIME_TYPES.get(
                Path(
                    file_name
                ).suffix.casefold()
            )
            or "application/octet-stream"
        ),
        "sheet_name": (
            parsed.sheet_name
        ),
        "header_row": (
            parsed.header_row
        ),
        "content_sha256": (
            content_hash
        ),
        "extraction_status": "pronto",
        "total_items": len(
            parsed.items
        ),
        "included_items": (
            summary["included_items"]
        ),
        "optional_items": (
            summary["optional_items"]
        ),
        "pending_items": (
            summary["pending_items"]
        ),
        "total_base": (
            parsed.total_base
        ),
        "fees_total": (
            parsed.fees_total
        ),
        "charges_total": (
            parsed.charges_total
        ),
        "client_total": (
            parsed.client_total
        ),
        "currency": parsed.currency,
        "macros_present": (
            parsed.macros_present
        ),
        "metadata": _json_safe(
            parsed.metadata
        ),
        "diagnostic": {
            "warnings": (
                parsed.warnings
            ),
            "unknown_columns": (
                parsed.unknown_columns
            ),
        },
        "raw_data": {
            "project_name": (
                parsed.project_name
            ),
            "event_date": (
                parsed.event_date
            ),
            "presentation_date": (
                parsed.presentation_date
            ),
        },
    }

    inserted_document = (
        client.table(
            "memory_cost_documents"
        )
        .insert(
            _json_safe(
                document_payload
            )
        )
        .execute()
    )

    if not inserted_document.data:
        raise LearningDataError(
            "Não foi possível criar o "
            "registro da planilha."
        )

    document_id = str(
        inserted_document.data[0]["id"]
    )
    storage_path = (
        f"projects/{project_id}/"
        f"costs/{document_id}/"
        f"{_safe_filename(file_name)}"
    )

    try:
        _upload_cost_file(
            client,
            storage_path=storage_path,
            file_name=file_name,
            file_bytes=file_bytes,
        )

        (
            client.table(
                "memory_cost_documents"
            )
            .update(
                {
                    "storage_bucket": (
                        COST_BUCKET
                    ),
                    "storage_path": (
                        storage_path
                    ),
                }
            )
            .eq("id", document_id)
            .execute()
        )

        item_payloads = []

        for item in parsed.items:
            data = item.model_dump()
            item_payloads.append(
                {
                    "project_id": (
                        project_id
                    ),
                    "cost_document_id": (
                        document_id
                    ),
                    **_json_safe(data),
                }
            )

        inserted_items = _insert_chunks(
            client,
            table_name=(
                "memory_cost_items"
            ),
            rows=item_payloads,
        )

        suggestions = (
            suggest_cost_links(
                inserted_items,
                memory_items,
            )
        )

        if suggestions:
            _insert_chunks(
                client,
                table_name=(
                    "memory_cost_links"
                ),
                rows=suggestions,
            )

        return {
            "status": "saved",
            "document_id": (
                document_id
            ),
            "items_saved": len(
                inserted_items
            ),
            "links_suggested": len(
                suggestions
            ),
        }

    except Exception:
        try:
            (
                client.storage
                .from_(COST_BUCKET)
                .remove(
                    [storage_path]
                )
            )
        except Exception:
            pass

        try:
            (
                client.table(
                    "memory_cost_documents"
                )
                .delete()
                .eq("id", document_id)
                .execute()
            )
        except Exception:
            pass

        raise


def save_cost_correlations(
    client: Client,
    *,
    project_id: str,
    correlations: list[dict],
) -> None:
    cost_item_ids = [
        str(
            row["cost_item_id"]
        )
        for row in correlations
        if row.get(
            "cost_item_id"
        )
    ]

    if cost_item_ids:
        (
            client.table(
                "memory_cost_links"
            )
            .delete()
            .in_(
                "cost_item_id",
                cost_item_ids,
            )
            .execute()
        )

    rows = []

    for correlation in correlations:
        memory_item_id = (
            correlation.get(
                "memory_item_id"
            )
        )

        if not memory_item_id:
            continue

        rows.append(
            {
                "project_id": (
                    project_id
                ),
                "cost_item_id": (
                    correlation[
                        "cost_item_id"
                    ]
                ),
                "memory_item_id": (
                    memory_item_id
                ),
                "match_score": (
                    correlation.get(
                        "match_score"
                    )
                ),
                "match_reason": (
                    correlation.get(
                        "match_reason"
                    )
                ),
                "link_status": (
                    "confirmed"
                ),
            }
        )

    if rows:
        _insert_chunks(
            client,
            table_name=(
                "memory_cost_links"
            ),
            rows=rows,
        )


def delete_cost_document(
    client: Client,
    *,
    document_id: str,
) -> None:
    response = (
        client.table(
            "memory_cost_documents"
        )
        .select(
            "storage_path"
        )
        .eq("id", document_id)
        .limit(1)
        .execute()
    )

    storage_path = (
        response.data[0].get(
            "storage_path"
        )
        if response.data
        else None
    )

    if storage_path:
        try:
            (
                client.storage
                .from_(COST_BUCKET)
                .remove(
                    [storage_path]
                )
            )
        except Exception:
            pass

    (
        client.table(
            "memory_cost_documents"
        )
        .delete()
        .eq("id", document_id)
        .execute()
    )




def create_briefing_signed_url(
    client: Client,
    storage_path: str | None,
    *,
    expires_in: int = 3600,
    download: bool = False,
) -> str | None:
    path = str(
        storage_path or ""
    ).strip()

    if not path:
        return None

    bucket = client.storage.from_(
        BRIEFING_BUCKET
    )

    if download:
        response = (
            bucket.create_signed_url(
                path,
                expires_in,
                {"download": True},
            )
        )
    else:
        response = (
            bucket.create_signed_url(
                path,
                expires_in,
            )
        )

    return _signed_url_value(
        response
    )


def fetch_briefing_documents(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_briefing_documents"
        )
        .select("*")
        .eq(
            "project_id",
            project_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def fetch_briefing_requirements(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_briefing_requirements"
        )
        .select("*")
        .eq(
            "project_id",
            project_id,
        )
        .order(
            "sort_order"
        )
        .order(
            "created_at"
        )
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def fetch_briefing_links(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    response = (
        client.table(
            "memory_briefing_links"
        )
        .select("*")
        .eq(
            "project_id",
            project_id,
        )
        .order(
            "match_score",
            desc=True,
        )
        .execute()
    )

    return pd.DataFrame(
        response.data or []
    )


def score_briefing_memory_match(
    requirement: dict,
    memory_item: dict,
) -> tuple[float, str]:
    requirement_text = " ".join(
        str(
            requirement.get(key)
            or ""
        )
        for key in [
            "title",
            "description",
            "requirement_type",
            "tags",
        ]
    )
    memory_text = " ".join(
        str(
            memory_item.get(key)
            or ""
        )
        for key in [
            "title",
            "summary",
            "description",
            "item_type",
            "tags",
        ]
    )

    requirement_tokens = _tokens(
        requirement_text
    )
    memory_tokens = _tokens(
        memory_text
    )
    lexical = _dice(
        requirement_tokens,
        memory_tokens,
    )
    score = lexical * 0.72
    reasons = []

    if lexical > 0:
        reasons.append(
            "termos em comum"
        )

    requirement_title = normalize_text(
        requirement.get(
            "title"
        )
    )
    memory_title = normalize_text(
        memory_item.get(
            "title"
        )
    )

    if (
        requirement_title
        and memory_title
        and (
            requirement_title
            in memory_title
            or memory_title
            in requirement_title
        )
    ):
        score += 0.22
        reasons.append(
            "título semelhante"
        )

    requirement_type = str(
        requirement.get(
            "requirement_type"
        )
        or ""
    )
    section_key = str(
        memory_item.get(
            "section_key"
        )
        or ""
    )

    compatible = {
        "deliverable": {
            "activations",
            "gifts",
            "scenography",
            "communication",
            "journey_operation",
        },
        "mandatory": {
            "strategy",
            "activations",
            "gifts",
            "scenography",
            "communication",
            "journey_operation",
        },
        "objective": {
            "strategy",
        },
        "restriction": {
            "strategy",
            "journey_operation",
            "scenography",
        },
        "operation": {
            "journey_operation",
        },
        "communication": {
            "communication",
        },
        "audience": {
            "strategy",
        },
    }

    if section_key in compatible.get(
        requirement_type,
        set(),
    ):
        score += 0.10
        reasons.append(
            "seção compatível"
        )

    return (
        min(
            round(score, 4),
            1.0,
        ),
        ", ".join(reasons)
        or "sem correspondência forte",
    )


def suggest_briefing_links(
    requirements: list[dict],
    memory_items: list[dict],
    *,
    minimum_score: float = 0.18,
) -> list[dict]:
    suggestions = []

    for requirement in requirements:
        best_item = None
        best_score = 0.0
        best_reason = ""

        for memory_item in memory_items:
            score, reason = (
                score_briefing_memory_match(
                    requirement,
                    memory_item,
                )
            )

            if score > best_score:
                best_item = memory_item
                best_score = score
                best_reason = reason

        if (
            best_item
            and best_score
            >= minimum_score
        ):
            suggestions.append(
                {
                    "project_id": (
                        requirement[
                            "project_id"
                        ]
                    ),
                    "requirement_id": (
                        requirement["id"]
                    ),
                    "memory_item_id": (
                        best_item["id"]
                    ),
                    "match_score": (
                        best_score
                    ),
                    "match_reason": (
                        best_reason
                    ),
                    "link_status": (
                        "suggested"
                    ),
                    "adherence_status": (
                        "not_assessed"
                    ),
                }
            )

    return suggestions


def save_briefing_document(
    client: Client,
    *,
    project_id: str,
    file_name: str,
    file_bytes: bytes,
    extraction: BriefingExtraction,
    memory_items: list[dict],
) -> dict:
    content_hash = hashlib.sha256(
        file_bytes
    ).hexdigest()

    duplicate = (
        client.table(
            "memory_briefing_documents"
        )
        .select("id")
        .eq(
            "project_id",
            project_id,
        )
        .eq(
            "content_sha256",
            content_hash,
        )
        .limit(1)
        .execute()
    )

    if duplicate.data:
        return {
            "status": "duplicate",
            "document_id": (
                duplicate.data[0]["id"]
            ),
            "requirements_saved": 0,
            "links_suggested": 0,
        }

    document_payload = {
        "project_id": project_id,
        "title": (
            extraction.title
            or Path(
                file_name
            ).stem
        ),
        "file_name": file_name,
        "mime_type": (
            BRIEFING_MIME_TYPES.get(
                Path(
                    file_name
                ).suffix.casefold()
            )
            or "application/octet-stream"
        ),
        "content_sha256": (
            content_hash
        ),
        "extraction_status": "pronto",
        "requirements_count": len(
            extraction.requirements
        ),
        "budget_amount": (
            extraction.budget_amount
        ),
        "currency": (
            extraction.currency
        ),
        "objective": (
            extraction.objective
        ),
        "audience": (
            extraction.audience
        ),
        "metadata": _json_safe(
            {
                "project_name": (
                    extraction.project_name
                ),
                "client_brand": (
                    extraction.client_brand
                ),
                "event_name": (
                    extraction.event_name
                ),
                "event_date": (
                    extraction.event_date
                ),
                "venue": (
                    extraction.venue
                ),
                "audience_quantity": (
                    extraction.audience_quantity
                ),
            }
        ),
        "diagnostic": {
            "warnings": (
                extraction.warnings
            ),
        },
    }

    inserted_document = (
        client.table(
            "memory_briefing_documents"
        )
        .insert(
            _json_safe(
                document_payload
            )
        )
        .execute()
    )

    if not inserted_document.data:
        raise LearningDataError(
            "Não foi possível criar o "
            "registro do briefing."
        )

    document_id = str(
        inserted_document.data[0]["id"]
    )
    storage_path = (
        f"projects/{project_id}/"
        f"briefings/{document_id}/"
        f"{_safe_filename(file_name)}"
    )

    try:
        _upload_briefing_file(
            client,
            storage_path=storage_path,
            file_name=file_name,
            file_bytes=file_bytes,
        )

        (
            client.table(
                "memory_briefing_documents"
            )
            .update(
                {
                    "storage_bucket": (
                        BRIEFING_BUCKET
                    ),
                    "storage_path": (
                        storage_path
                    ),
                }
            )
            .eq(
                "id",
                document_id,
            )
            .execute()
        )

        requirement_payloads = []

        for sort_order, requirement in enumerate(
            extraction.requirements,
            start=1,
        ):
            requirement_payloads.append(
                {
                    "project_id": (
                        project_id
                    ),
                    "briefing_document_id": (
                        document_id
                    ),
                    "requirement_type": (
                        requirement.requirement_type
                    ),
                    "title": (
                        requirement.title
                    ),
                    "description": (
                        requirement.description
                    ),
                    "priority": (
                        requirement.priority
                    ),
                    "mandatory": (
                        requirement.mandatory
                    ),
                    "source_reference": (
                        requirement.source_reference
                    ),
                    "source_quote": (
                        requirement.source_quote
                    ),
                    "tags": (
                        requirement.tags
                    ),
                    "sort_order": (
                        sort_order
                    ),
                }
            )

        inserted_requirements = (
            _insert_chunks(
                client,
                table_name=(
                    "memory_briefing_requirements"
                ),
                rows=requirement_payloads,
            )
            if requirement_payloads
            else []
        )

        suggestions = (
            suggest_briefing_links(
                inserted_requirements,
                memory_items,
            )
        )

        if suggestions:
            _insert_chunks(
                client,
                table_name=(
                    "memory_briefing_links"
                ),
                rows=suggestions,
            )

        if (
            extraction.budget_amount
            is not None
        ):
            update_project_budget(
                client,
                project_id=project_id,
                budget_amount=(
                    extraction.budget_amount
                ),
                currency=(
                    extraction.currency
                ),
            )

        return {
            "status": "saved",
            "document_id": (
                document_id
            ),
            "requirements_saved": len(
                inserted_requirements
            ),
            "links_suggested": len(
                suggestions
            ),
        }

    except Exception:
        try:
            (
                client.storage
                .from_(BRIEFING_BUCKET)
                .remove(
                    [storage_path]
                )
            )
        except Exception:
            pass

        try:
            (
                client.table(
                    "memory_briefing_documents"
                )
                .delete()
                .eq(
                    "id",
                    document_id,
                )
                .execute()
            )
        except Exception:
            pass

        raise


def save_briefing_adherence(
    client: Client,
    *,
    project_id: str,
    rows: list[dict],
) -> None:
    requirement_ids = [
        str(
            row["requirement_id"]
        )
        for row in rows
        if row.get(
            "requirement_id"
        )
    ]

    if requirement_ids:
        (
            client.table(
                "memory_briefing_links"
            )
            .delete()
            .in_(
                "requirement_id",
                requirement_ids,
            )
            .execute()
        )

    payloads = []

    for row in rows:
        requirement_id = str(
            row["requirement_id"]
        )
        adherence_status = (
            row.get(
                "adherence_status"
            )
            or "not_assessed"
        )
        evidence = row.get(
            "evidence"
        )
        notes = row.get(
            "notes"
        )

        (
            client.table(
                "memory_briefing_requirements"
            )
            .update(
                {
                    "adherence_status": (
                        adherence_status
                    ),
                    "adherence_evidence": (
                        evidence
                    ),
                    "adherence_notes": (
                        notes
                    ),
                }
            )
            .eq(
                "id",
                requirement_id,
            )
            .eq(
                "project_id",
                project_id,
            )
            .execute()
        )

        memory_item_id = row.get(
            "memory_item_id"
        )

        if not memory_item_id:
            continue

        payloads.append(
            {
                "project_id": (
                    project_id
                ),
                "requirement_id": (
                    requirement_id
                ),
                "memory_item_id": (
                    memory_item_id
                ),
                "match_score": (
                    row.get(
                        "match_score"
                    )
                ),
                "match_reason": (
                    row.get(
                        "match_reason"
                    )
                    or "Correlação revisada manualmente"
                ),
                "link_status": "confirmed",
                "adherence_status": (
                    adherence_status
                ),
                "evidence": (
                    evidence
                ),
                "notes": notes,
            }
        )

    if payloads:
        _insert_chunks(
            client,
            table_name=(
                "memory_briefing_links"
            ),
            rows=payloads,
        )


def delete_briefing_document(
    client: Client,
    *,
    document_id: str,
) -> None:
    response = (
        client.table(
            "memory_briefing_documents"
        )
        .select(
            "storage_path"
        )
        .eq(
            "id",
            document_id,
        )
        .limit(1)
        .execute()
    )

    storage_path = (
        response.data[0].get(
            "storage_path"
        )
        if response.data
        else None
    )

    if storage_path:
        try:
            (
                client.storage
                .from_(BRIEFING_BUCKET)
                .remove(
                    [storage_path]
                )
            )
        except Exception:
            pass

    (
        client.table(
            "memory_briefing_documents"
        )
        .delete()
        .eq(
            "id",
            document_id,
        )
        .execute()
    )


def build_item_learning_maps(
    client: Client,
    *,
    project_id: str,
) -> tuple[
    dict[str, dict],
    dict[str, list[dict]],
    dict[str, list[dict]],
]:
    outcomes = fetch_item_outcomes(
        client,
        project_id=project_id,
    )
    costs = fetch_cost_items(
        client,
        project_id=project_id,
    )
    cost_links = fetch_cost_links(
        client,
        project_id=project_id,
    )
    briefing_requirements = (
        fetch_briefing_requirements(
            client,
            project_id=project_id,
        )
    )
    briefing_links = (
        fetch_briefing_links(
            client,
            project_id=project_id,
        )
    )

    outcome_map = {}

    if not outcomes.empty:
        outcome_map = {
            str(row["item_id"]): (
                row.to_dict()
            )
            for _, row
            in outcomes.iterrows()
        }

    cost_map = {}

    if not costs.empty:
        cost_map = {
            str(row["id"]): (
                row.to_dict()
            )
            for _, row
            in costs.iterrows()
        }

    linked_costs: dict[
        str,
        list[dict],
    ] = {}

    if not cost_links.empty:
        for _, link_row in (
            cost_links.iterrows()
        ):
            link = link_row.to_dict()
            item_id = str(
                link.get(
                    "memory_item_id"
                )
                or ""
            )
            cost = cost_map.get(
                str(
                    link.get(
                        "cost_item_id"
                    )
                    or ""
                )
            )

            if not item_id or not cost:
                continue

            linked_costs.setdefault(
                item_id,
                [],
            ).append(
                {
                    **cost,
                    "link_status": (
                        link.get(
                            "link_status"
                        )
                    ),
                    "match_score": (
                        link.get(
                            "match_score"
                        )
                    ),
                    "match_reason": (
                        link.get(
                            "match_reason"
                        )
                    ),
                }
            )

    requirement_map = {}

    if not briefing_requirements.empty:
        requirement_map = {
            str(row["id"]): (
                row.to_dict()
            )
            for _, row
            in briefing_requirements.iterrows()
        }

    linked_requirements: dict[
        str,
        list[dict],
    ] = {}

    if not briefing_links.empty:
        for _, link_row in (
            briefing_links.iterrows()
        ):
            link = link_row.to_dict()
            item_id = str(
                link.get(
                    "memory_item_id"
                )
                or ""
            )
            requirement = (
                requirement_map.get(
                    str(
                        link.get(
                            "requirement_id"
                        )
                        or ""
                    )
                )
            )

            if (
                not item_id
                or not requirement
            ):
                continue

            linked_requirements.setdefault(
                item_id,
                [],
            ).append(
                {
                    **requirement,
                    "link_status": (
                        link.get(
                            "link_status"
                        )
                    ),
                    "match_score": (
                        link.get(
                            "match_score"
                        )
                    ),
                    "match_reason": (
                        link.get(
                            "match_reason"
                        )
                    ),
                    "adherence_status": (
                        requirement.get(
                            "adherence_status"
                        )
                        or link.get(
                            "adherence_status"
                        )
                    ),
                    "evidence": (
                        requirement.get(
                            "adherence_evidence"
                        )
                        or link.get(
                            "evidence"
                        )
                    ),
                    "notes": (
                        requirement.get(
                            "adherence_notes"
                        )
                        or link.get(
                            "notes"
                        )
                    ),
                }
            )

    return (
        outcome_map,
        linked_costs,
        linked_requirements,
    )


def _remove_storage_paths(
    client: Client,
    *,
    bucket_name: str,
    paths: list[str],
    chunk_size: int = 100,
) -> None:
    unique_paths = list(
        dict.fromkeys(
            str(path).strip()
            for path in paths
            if str(path or "").strip()
        )
    )

    for start in range(
        0,
        len(unique_paths),
        chunk_size,
    ):
        chunk = unique_paths[
            start : start + chunk_size
        ]

        if chunk:
            (
                client.storage
                .from_(bucket_name)
                .remove(chunk)
            )


def _delete_project_rows(
    client: Client,
    *,
    table_name: str,
    project_id: str,
) -> str | None:
    try:
        (
            client.table(
                table_name
            )
            .delete()
            .eq(
                "project_id",
                project_id,
            )
            .execute()
        )
        return None
    except Exception as exc:
        message = str(exc)

        if (
            "does not exist"
            in message.casefold()
            or "42p01" in message.casefold()
        ):
            return None

        return (
            table_name
            + ": "
            + message
        )


def delete_memory_project(
    client: Client,
    *,
    project_id: str,
) -> dict:
    """
    Remove o projeto da Memória sem apagar histórico de recomendações.

    Se a linha de ``projects`` estiver referenciada por versões de
    recomendação ou outro módulo, apenas os dados da Memória são
    excluídos. Assim o projeto desaparece da lista da Memória sem
    quebrar o histórico da NAVE.
    """
    from memory_db import (
        MEMORY_BUCKET,
    )

    storage_warnings = []
    database_warnings = []

    def select_paths(
        table_name: str,
        column_name: str,
    ) -> list[str]:
        try:
            response = (
                client.table(
                    table_name
                )
                .select(
                    column_name
                )
                .eq(
                    "project_id",
                    project_id,
                )
                .execute()
            )
            return [
                str(
                    row.get(
                        column_name
                    )
                ).strip()
                for row in (
                    response.data
                    or []
                )
                if str(
                    row.get(
                        column_name
                    )
                    or ""
                ).strip()
            ]
        except Exception:
            return []

    memory_paths = [
        *select_paths(
            "memory_documents",
            "storage_path",
        ),
        *select_paths(
            "memory_pages",
            "storage_path",
        ),
        *select_paths(
            "memory_items",
            "visual_storage_path",
        ),
    ]
    cost_paths = select_paths(
        "memory_cost_documents",
        "storage_path",
    )
    briefing_paths = select_paths(
        "memory_briefing_documents",
        "storage_path",
    )

    for bucket_name, paths in [
        (
            MEMORY_BUCKET,
            memory_paths,
        ),
        (
            COST_BUCKET,
            cost_paths,
        ),
        (
            BRIEFING_BUCKET,
            briefing_paths,
        ),
    ]:
        try:
            _remove_storage_paths(
                client,
                bucket_name=(
                    bucket_name
                ),
                paths=paths,
            )
        except Exception as exc:
            storage_warnings.append(
                bucket_name
                + ": "
                + str(exc)
            )

    # Remove explicitamente as camadas da Memória. Não dependemos de
    # apagar a linha principal de projects para acionar cascatas.
    for table_name in [
        "memory_briefing_links",
        "memory_briefing_requirements",
        "memory_briefing_documents",
        "memory_cost_links",
        "memory_cost_items",
        "memory_cost_documents",
        "memory_feedback_entries",
        "memory_item_outcomes",
        "memory_project_outcomes",
        "memory_documents",
    ]:
        warning = _delete_project_rows(
            client,
            table_name=table_name,
            project_id=project_id,
        )

        if warning:
            database_warnings.append(
                warning
            )

    if database_warnings:
        raise LearningDataError(
            "Parte dos dados do projeto não pôde ser removida: "
            + " | ".join(
                database_warnings
            )
        )

    project_record_deleted = False
    project_record_retained = False
    project_delete_message = None

    try:
        (
            client.table(
                "projects"
            )
            .delete()
            .eq(
                "id",
                project_id,
            )
            .execute()
        )
        project_record_deleted = True

    except Exception as exc:
        message = str(exc)
        normalized = message.casefold()

        if (
            "foreign key constraint"
            in normalized
            or "recommendation_versions"
            in normalized
            or "23503" in normalized
            or "409" in normalized
        ):
            # O projeto continua disponível em Projetos porque possui
            # histórico associado, mas deixa de aparecer na Memória.
            project_record_retained = True
            project_delete_message = (
                "O cadastro geral foi preservado porque "
                "está associado ao histórico de recomendações."
            )
        else:
            raise

    return {
        "project_id": project_id,
        "memory_files_removed": len(
            set(memory_paths)
        ),
        "cost_files_removed": len(
            set(cost_paths)
        ),
        "briefing_files_removed": len(
            set(briefing_paths)
        ),
        "project_record_deleted": (
            project_record_deleted
        ),
        "project_record_retained": (
            project_record_retained
        ),
        "message": (
            project_delete_message
        ),
        "storage_warnings": (
            storage_warnings
        ),
    }

