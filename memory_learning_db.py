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
from memory_learning_models import CostWorkbookResult


COST_BUCKET = "nave-memory-costs"
COST_MAX_FILE_SIZE = 50 * 1024 * 1024

COST_MIME_TYPES = {
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    ".xlsm": (
        "application/vnd.ms-excel.sheet.macroEnabled.12"
    ),
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
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

    if COST_BUCKET in bucket_ids:
        return

    try:
        client.storage.create_bucket(
            COST_BUCKET,
            options={
                "public": False,
                "allowed_mime_types": list(
                    COST_MIME_TYPES.values()
                ),
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
            "armazenamento das planilhas."
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

    _retry(
        lambda: (
            client.storage
            .from_(COST_BUCKET)
            .upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    "content-type": mime_type,
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


def build_item_learning_maps(
    client: Client,
    *,
    project_id: str,
) -> tuple[
    dict[str, dict],
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
    links = fetch_cost_links(
        client,
        project_id=project_id,
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

    if not links.empty:
        for _, link_row in (
            links.iterrows()
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

    return (
        outcome_map,
        linked_costs,
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


def delete_memory_project(
    client: Client,
    *,
    project_id: str,
) -> dict:
    """
    Exclui integralmente um projeto criado pela Memória.

    Os arquivos privados são removidos antes do registro principal.
    As relações de banco são apagadas por ON DELETE CASCADE.
    """
    from memory_db import MEMORY_BUCKET

    document_response = (
        client.table(
            "memory_documents"
        )
        .select(
            "storage_path"
        )
        .eq(
            "project_id",
            project_id,
        )
        .execute()
    )

    page_response = (
        client.table(
            "memory_pages"
        )
        .select(
            "storage_path"
        )
        .eq(
            "project_id",
            project_id,
        )
        .execute()
    )

    item_response = (
        client.table(
            "memory_items"
        )
        .select(
            "visual_storage_path"
        )
        .eq(
            "project_id",
            project_id,
        )
        .execute()
    )

    cost_response = (
        client.table(
            "memory_cost_documents"
        )
        .select(
            "storage_path"
        )
        .eq(
            "project_id",
            project_id,
        )
        .execute()
    )

    memory_paths = []

    for row in (
        document_response.data
        or []
    ):
        if row.get(
            "storage_path"
        ):
            memory_paths.append(
                row["storage_path"]
            )

    for row in (
        page_response.data
        or []
    ):
        if row.get(
            "storage_path"
        ):
            memory_paths.append(
                row["storage_path"]
            )

    for row in (
        item_response.data
        or []
    ):
        if row.get(
            "visual_storage_path"
        ):
            memory_paths.append(
                row[
                    "visual_storage_path"
                ]
            )

    cost_paths = [
        row["storage_path"]
        for row in (
            cost_response.data
            or []
        )
        if row.get(
            "storage_path"
        )
    ]

    try:
        _remove_storage_paths(
            client,
            bucket_name=(
                MEMORY_BUCKET
            ),
            paths=memory_paths,
        )

        _remove_storage_paths(
            client,
            bucket_name=(
                COST_BUCKET
            ),
            paths=cost_paths,
        )
    except Exception as exc:
        raise LearningDataError(
            "Não foi possível remover todos os "
            "arquivos privados do projeto. "
            "O registro não foi excluído."
        ) from exc

    deleted = (
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

    return {
        "project_id": project_id,
        "memory_files_removed": len(
            set(memory_paths)
        ),
        "cost_files_removed": len(
            set(cost_paths)
        ),
        "project_deleted": True,
        "database_response": (
            deleted.data
            or []
        ),
    }
