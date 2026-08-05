from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import date
from typing import Any

import fitz
import pandas as pd
from supabase import Client, create_client

from document_io import InputDocument
from entity_matching import best_candidate_match
from enrichment_engine import (
    is_blank as enrichment_is_blank,
    merge_record,
)
from media_library import upload_generated_media_asset
from pdf_visuals import prepare_visual_assignments
from taxonomy import (
    annotate_candidate_taxonomy,
    normalize_record_taxonomy,
    normalize_taxonomy_text,
    taxonomy_catalog_rows,
    taxonomy_options,
)


PRODUCT_COLUMNS = {
    "supplier_id",
    "import_id",
    "source_file_id",
    "source_file",
    "source_page",
    "source_image_url",
    "catalog_name",
    "document_year",
    "category",
    "sku",
    "name",
    "description",
    "unit_price",
    "price_min",
    "price_max",
    "currency",
    "price_status",
    "price_reference_qty",
    "price_notes",
    "capacity",
    "capacity_ml",
    "dimensions_raw",
    "material",
    "finish",
    "decoration",
    "origin",
    "development_status",
    "min_order_qty",
    "customizable",
    "licensing_notes",
    "tags",
    "confidence",
    "missing_fields",
    "evidence",
    "raw_data",
}

ACTIVATION_COLUMNS = {
    "supplier_id",
    "project_id",
    "import_id",
    "source_file_id",
    "source_file",
    "source_page",
    "source_image_url",
    "proposal_name",
    "document_year",
    "client_brand",
    "project_name",
    "event_name",
    "category",
    "record_type",
    "name",
    "description",
    "base_price",
    "currency",
    "price_status",
    "pricing_period",
    "price_notes",
    "included_items",
    "excluded_items",
    "infrastructure_requirements",
    "internet_requirement",
    "lead_time_days",
    "setup_window",
    "event_period",
    "location",
    "staff_included",
    "staff_description",
    "validity",
    "payment_terms",
    "discount_percent",
    "negotiated_benefit",
    "customizable",
    "tags",
    "confidence",
    "missing_fields",
    "evidence",
    "raw_data",
}

VENUE_COLUMNS = {
    "operator_id",
    "import_id",
    "source_file_id",
    "source_file",
    "source_page",
    "source_image_url",
    "document_name",
    "document_year",
    "name",
    "venue_type",
    "description",
    "address",
    "neighborhood",
    "city",
    "state",
    "country",
    "postal_code",
    "map_url",
    "website_url",
    "total_area_sqm",
    "indoor_area_sqm",
    "outdoor_area_sqm",
    "ceiling_height_m",
    "standing_capacity",
    "seated_capacity",
    "auditorium_capacity",
    "rooms_or_areas",
    "parking",
    "accessibility",
    "loading_access",
    "kitchen_or_catering",
    "power_supply",
    "internet",
    "air_conditioning",
    "bathrooms",
    "furniture",
    "audiovisual",
    "infrastructure",
    "included_items",
    "excluded_items",
    "restrictions",
    "operating_hours",
    "event_availability",
    "base_price",
    "price_min",
    "price_max",
    "currency",
    "price_status",
    "pricing_period",
    "price_notes",
    "tags",
    "confidence",
    "missing_fields",
    "evidence",
    "raw_data",
}

ARRAY_FIELDS = {
    "tags",
    "missing_fields",
    "included_items",
    "excluded_items",
    "infrastructure_requirements",
    "rooms_or_areas",
    "infrastructure",
    "restrictions",
}


def get_supabase_client(
    url: str | None = None,
    secret_key: str | None = None,
) -> Client:
    resolved_url = url or os.getenv("SUPABASE_URL")
    resolved_key = (
        secret_key
        or os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )

    if not resolved_url or not resolved_key:
        raise RuntimeError(
            "Configure SUPABASE_URL e SUPABASE_SECRET_KEY "
            "nos Secrets do Streamlit."
        )

    return create_client(resolved_url, resolved_key)


def test_connection(client: Client) -> dict[str, Any]:
    response = (
        client.table("suppliers")
        .select("id", count="exact")
        .limit(1)
        .execute()
    )
    return {
        "connected": True,
        "supplier_count": response.count or 0,
    }


def normalize_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


def _json_safe(value: Any) -> Any:
    if _is_missing(value):
        return None

    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(value, (date,)):
        return value.isoformat()

    return value


def dataframe_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []

    records = []
    for row in df.to_dict(orient="records"):
        clean = {
            key: _json_safe(value)
            for key, value in row.items()
        }
        if any(value not in (None, "", [], {}) for value in clean.values()):
            records.append(clean)
    return records


def split_pipe(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        part.strip()
        for part in str(value).split("|")
        if part.strip()
    ]


def _prepare_record(
    raw: dict,
    allowed_columns: set[str],
) -> dict:
    payload = {}

    for key in allowed_columns:
        if key not in raw:
            continue

        value = raw.get(key)
        if key in ARRAY_FIELDS:
            value = split_pipe(value)
        else:
            value = _json_safe(value)

        payload[key] = value

    payload["raw_data"] = _json_safe(raw)
    return payload


def upsert_supplier(
    client: Client,
    supplier: dict,
) -> str | None:
    name = supplier.get("supplier_name") or supplier.get("name")
    if _is_missing(name):
        return None

    normalized = normalize_name(str(name))
    payload = {
        "name": str(name).strip(),
        "normalized_name": normalized,
        "website_url": _json_safe(supplier.get("website_url")),
        "contact_name": _json_safe(supplier.get("contact_name")),
        "contact_role": _json_safe(supplier.get("contact_role")),
        "email": _json_safe(supplier.get("email")),
        "phone": _json_safe(supplier.get("phone")),
        "whatsapp": _json_safe(supplier.get("whatsapp")),
        "instagram_url": _json_safe(supplier.get("instagram_url")),
        "linkedin_url": _json_safe(supplier.get("linkedin_url")),
        "address": _json_safe(supplier.get("address")),
        "notes": _json_safe(supplier.get("notes")),
        "confidence": _json_safe(supplier.get("confidence")),
        "raw_data": _json_safe(supplier),
    }

    scalar_coverage_fields = (
        "base_city",
        "base_state",
        "base_country",
        "travel_pricing_mode",
        "default_travel_cost_brl",
        "freight_pricing_mode",
        "default_freight_cost_brl",
        "travel_lead_days",
        "coverage_notes",
    )
    boolean_coverage_fields = (
        "serves_nationally",
        "has_local_teams",
        "equipment_transport_required",
        "accommodation_required",
    )
    array_coverage_fields = (
        "served_states",
        "served_cities",
        "local_team_locations",
    )

    for field in scalar_coverage_fields:
        value = supplier.get(field)
        if not _is_missing(value):
            payload[field] = _json_safe(value)

    for field in boolean_coverage_fields:
        value = supplier.get(field)
        if value is not None and not _is_missing(value):
            payload[field] = bool(value)

    for field in array_coverage_fields:
        value = split_pipe(supplier.get(field))
        if value:
            payload[field] = value

    lookup = (
        client.table("suppliers")
        .select("*")
        .eq("normalized_name", normalized)
        .limit(1)
        .execute()
    )

    if lookup.data:
        existing = lookup.data[0]
        result = merge_record(
            existing,
            payload,
            allowed_fields=set(payload),
            strategy="enrich_safe",
        )
        changes = result["applied_changes"]

        if changes:
            (
                client.table("suppliers")
                .update(changes)
                .eq("id", existing["id"])
                .execute()
            )

        return existing["id"]

    response = (
        client.table("suppliers")
        .insert(payload)
        .execute()
    )

    return (
        response.data[0]["id"]
        if response.data
        else None
    )


def _supplier_maps(
    client: Client,
    supplier_records: list[dict],
) -> tuple[dict[str, str], int]:
    mapping: dict[str, str] = {}
    saved = 0

    for supplier in supplier_records:
        supplier_id = upsert_supplier(client, supplier)
        name = supplier.get("supplier_name") or supplier.get("name")
        if supplier_id and name:
            mapping[normalize_name(str(name))] = supplier_id
            saved += 1

    return mapping, saved


def _supplier_id_for_record(
    record: dict,
    supplier_map: dict[str, str],
) -> str | None:
    name = record.get("supplier_name") or record.get("operator_name")
    return supplier_map.get(normalize_name(str(name))) if name else None


def _page_count(doc: InputDocument) -> int | None:
    if doc.mime_type != "application/pdf":
        return None
    try:
        pdf = fitz.open(stream=doc.data, filetype="pdf")
        count = pdf.page_count
        pdf.close()
        return count
    except Exception:
        return None


def create_import(
    client: Client,
    *,
    classification: dict | None,
    destination_base: str,
    source_documents: list[InputDocument],
    supplier_id: str | None,
    project_id: str | None,
    original_payload: dict,
    warnings: list[dict] | None,
) -> tuple[str, dict[str, str]]:
    classification = classification or {}
    source_names = [doc.name for doc in source_documents]

    import_payload = {
        "document_type": (
            classification.get("document_type")
            or destination_base
        ),
        "destination_base": destination_base,
        "document_title": classification.get("document_title"),
        "supplier_id": supplier_id,
        "project_id": project_id,
        "source_files": source_names,
        "classification": _json_safe(classification),
        "original_payload": _json_safe(original_payload),
        "warnings": _json_safe(warnings or []),
        "status": "importando",
        "imported_records": 0,
    }

    response = (
        client.table("imports")
        .insert(import_payload)
        .execute()
    )
    import_id = response.data[0]["id"]

    file_map: dict[str, str] = {}
    for doc in source_documents:
        source_bytes = doc.original_data or doc.data
        source_mime = doc.original_mime_type or doc.mime_type
        file_payload = {
            "import_id": import_id,
            "file_name": doc.name,
            "mime_type": source_mime,
            "page_count": _page_count(doc),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        file_response = (
            client.table("source_files")
            .insert(file_payload)
            .execute()
        )
        if file_response.data:
            file_map[doc.name] = file_response.data[0]["id"]

    return import_id, file_map


def _find_existing_product(
    client: Client,
    *,
    supplier_id: str | None,
    sku: str | None,
    name: str,
) -> tuple[dict | None, str]:
    query = client.table("products").select("*").limit(1)

    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    else:
        query = query.is_("supplier_id", "null")

    if sku and str(sku).strip():
        query = query.eq("sku", str(sku).strip())
        method = "supplier_and_sku"
    else:
        query = query.eq("name", name)
        method = "supplier_and_name"

    response = query.execute()
    return (
        response.data[0] if response.data else None,
        method,
    )


def _find_existing_activation(
    client: Client,
    *,
    supplier_id: str | None,
    name: str,
    project_name: str | None,
) -> tuple[dict | None, str]:
    query = (
        client.table("activation_solutions")
        .select("*")
        .eq("name", name)
        .limit(1)
    )

    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    else:
        query = query.is_("supplier_id", "null")

    if project_name:
        query = query.eq("project_name", project_name)
        method = "supplier_name_and_project"
    else:
        method = "supplier_and_name"

    response = query.execute()
    return (
        response.data[0] if response.data else None,
        method,
    )


def _find_existing_venue(
    client: Client,
    *,
    operator_id: str | None,
    name: str,
    city: str | None,
) -> tuple[dict | None, str]:
    query = (
        client.table("venues")
        .select("*")
        .eq("name", name)
        .limit(1)
    )

    if operator_id:
        query = query.eq("operator_id", operator_id)
    else:
        query = query.is_("operator_id", "null")

    if city:
        query = query.eq("city", city)
        method = "operator_name_and_city"
    else:
        method = "operator_and_name"

    response = query.execute()
    return (
        response.data[0] if response.data else None,
        method,
    )


def _similar_product_match(
    client: Client,
    *,
    supplier_id: str | None,
    incoming: dict,
) -> dict:
    query = (
        client.table("products")
        .select("*")
        .limit(250)
    )

    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    else:
        query = query.is_("supplier_id", "null")

    response = query.execute()
    return best_candidate_match(
        "product",
        incoming,
        response.data or [],
    )


def _similar_activation_match(
    client: Client,
    *,
    supplier_id: str | None,
    incoming: dict,
) -> dict:
    query = (
        client.table("activation_solutions")
        .select("*")
        .limit(250)
    )

    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    else:
        query = query.is_("supplier_id", "null")

    project_name = incoming.get("project_name")
    if project_name:
        query = query.eq(
            "project_name",
            project_name,
        )

    response = query.execute()
    return best_candidate_match(
        "activation",
        incoming,
        response.data or [],
    )


def _similar_venue_match(
    client: Client,
    *,
    operator_id: str | None,
    incoming: dict,
) -> dict:
    query = (
        client.table("venues")
        .select("*")
        .limit(250)
    )

    if operator_id:
        query = query.eq("operator_id", operator_id)

    city = incoming.get("city")
    if city:
        query = query.eq("city", city)

    response = query.execute()
    return best_candidate_match(
        "venue",
        incoming,
        response.data or [],
    )


def _create_duplicate_candidate(
    client: Client,
    *,
    entity_type: str,
    source_entity_id: str,
    candidate: dict,
    import_id: str,
    source_file_id: str | None,
    source_name: str,
    similarity_score: float,
    match_method: str,
    match_context: dict,
    original_strategy: str,
) -> None:
    payload = {
        "entity_type": entity_type,
        "source_entity_id": source_entity_id,
        "candidate_entity_id": candidate["id"],
        "import_id": import_id,
        "source_file_id": source_file_id,
        "source_name": source_name,
        "candidate_name": (
            candidate.get("name")
            or "Cadastro existente"
        ),
        "similarity_score": similarity_score,
        "match_method": match_method,
        "match_context": _json_safe(match_context),
        "original_strategy": original_strategy,
        "status": "pending",
    }

    existing_response = (
        client.table("knowledge_duplicate_candidates")
        .select("id")
        .eq("entity_type", entity_type)
        .eq("source_entity_id", source_entity_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )

    if existing_response.data:
        (
            client.table("knowledge_duplicate_candidates")
            .update(payload)
            .eq("id", existing_response.data[0]["id"])
            .execute()
        )
    else:
        (
            client.table("knowledge_duplicate_candidates")
            .insert(payload)
            .execute()
        )


DUPLICATE_ENTITY_TABLES = {
    "product": "products",
    "activation": "activation_solutions",
    "venue": "venues",
}

DUPLICATE_ENTITY_COLUMNS = {
    "product": PRODUCT_COLUMNS,
    "activation": ACTIVATION_COLUMNS,
    "venue": VENUE_COLUMNS,
}


def _entity_record(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
) -> dict:
    table = DUPLICATE_ENTITY_TABLES[entity_type]

    response = (
        client.table(table)
        .select("*")
        .eq("id", entity_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}


def fetch_duplicate_candidates(
    client: Client,
    *,
    status: str = "pending",
    limit: int = 100,
) -> pd.DataFrame:
    response = (
        client.table("knowledge_duplicate_candidates")
        .select("*")
        .eq("status", status)
        .order("similarity_score", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = []

    for review in response.data or []:
        entity_type = str(review["entity_type"])
        source = _entity_record(
            client,
            entity_type=entity_type,
            entity_id=str(
                review["source_entity_id"]
            ),
        )
        candidate = _entity_record(
            client,
            entity_type=entity_type,
            entity_id=str(
                review["candidate_entity_id"]
            ),
        )

        rows.append(
            {
                **review,
                "source_record": source,
                "candidate_record": candidate,
                "source_name": (
                    source.get("name")
                    or review.get("source_name")
                ),
                "candidate_name": (
                    candidate.get("name")
                    or review.get("candidate_name")
                ),
            }
        )

    return pd.DataFrame(rows)


def _move_media_to_target(
    client: Client,
    *,
    entity_type: str,
    source_entity_id: str,
    target_entity_id: str,
) -> dict:
    source_response = (
        client.table("media_assets")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", source_entity_id)
        .execute()
    )
    target_response = (
        client.table("media_assets")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", target_entity_id)
        .execute()
    )

    source_assets = source_response.data or []
    target_assets = target_response.data or []

    target_hashes = {
        str(item.get("content_sha256"))
        for item in target_assets
        if item.get("content_sha256")
    }
    target_has_primary = any(
        bool(item.get("is_primary"))
        for item in target_assets
    )

    moved = 0
    duplicates_removed = 0

    for media in source_assets:
        content_hash = str(
            media.get("content_sha256") or ""
        ).strip()

        if content_hash and content_hash in target_hashes:
            bucket = str(
                media.get("storage_bucket") or ""
            ).strip()
            storage_path = str(
                media.get("storage_path") or ""
            ).strip()

            if bucket and storage_path:
                try:
                    (
                        client.storage
                        .from_(bucket)
                        .remove([storage_path])
                    )
                except Exception:
                    pass

            (
                client.table("media_assets")
                .delete()
                .eq("id", media["id"])
                .execute()
            )
            duplicates_removed += 1
            continue

        changes = {
            "entity_id": target_entity_id,
        }

        if media.get("is_primary") and target_has_primary:
            changes["is_primary"] = False
            if media.get("asset_type") == "main_image":
                changes["asset_type"] = "gallery_image"
        elif media.get("is_primary"):
            target_has_primary = True

        (
            client.table("media_assets")
            .update(changes)
            .eq("id", media["id"])
            .execute()
        )
        moved += 1

        if content_hash:
            target_hashes.add(content_hash)

    return {
        "media_moved": moved,
        "duplicate_media_removed": duplicates_removed,
    }


def _move_activation_costs(
    client: Client,
    *,
    source_entity_id: str,
    target_entity_id: str,
) -> dict:
    response = (
        client.table("activation_costs")
        .select("*")
        .eq("solution_id", source_entity_id)
        .execute()
    )

    moved = 0
    duplicates_removed = 0

    for cost in response.data or []:
        description = (
            cost.get("description")
            or "Custo adicional"
        )
        amount = cost.get("amount")

        if _activation_cost_exists(
            client,
            solution_id=target_entity_id,
            description=description,
            amount=amount,
        ):
            (
                client.table("activation_costs")
                .delete()
                .eq("id", cost["id"])
                .execute()
            )
            duplicates_removed += 1
            continue

        (
            client.table("activation_costs")
            .update(
                {
                    "solution_id": target_entity_id,
                }
            )
            .eq("id", cost["id"])
            .execute()
        )
        moved += 1

    return {
        "costs_moved": moved,
        "duplicate_costs_removed": duplicates_removed,
    }


def resolve_duplicate_as_distinct(
    client: Client,
    *,
    review_id: str,
) -> dict:
    response = (
        client.table("knowledge_duplicate_candidates")
        .update(
            {
                "status": "different",
                "resolution_strategy": "keep_separate",
                "resolved_at": (
                    pd.Timestamp.utcnow().isoformat()
                ),
                "resolution_data": {
                    "decision": "different_entities",
                },
            }
        )
        .eq("id", review_id)
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else {"id": review_id, "status": "different"}
    )


def resolve_duplicate_merge(
    client: Client,
    *,
    review_id: str,
    strategy: str = "enrich_safe",
) -> dict:
    review_response = (
        client.table("knowledge_duplicate_candidates")
        .select("*")
        .eq("id", review_id)
        .limit(1)
        .execute()
    )

    if not review_response.data:
        raise ValueError(
            "A correspondência não foi encontrada."
        )

    review = review_response.data[0]
    entity_type = str(review["entity_type"])
    source_entity_id = str(
        review["source_entity_id"]
    )
    target_entity_id = str(
        review["candidate_entity_id"]
    )

    source = _entity_record(
        client,
        entity_type=entity_type,
        entity_id=source_entity_id,
    )
    target = _entity_record(
        client,
        entity_type=entity_type,
        entity_id=target_entity_id,
    )

    if not source or not target:
        raise ValueError(
            "Um dos cadastros já não está disponível."
        )

    allowed_fields = DUPLICATE_ENTITY_COLUMNS[
        entity_type
    ]
    merge_result = merge_record(
        target,
        source,
        allowed_fields=allowed_fields,
        strategy=strategy,
    )

    changes = merge_result["applied_changes"]
    table = DUPLICATE_ENTITY_TABLES[entity_type]

    if changes:
        (
            client.table(table)
            .update(changes)
            .eq("id", target_entity_id)
            .execute()
        )

    media_result = _move_media_to_target(
        client,
        entity_type=entity_type,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
    )

    cost_result = {
        "costs_moved": 0,
        "duplicate_costs_removed": 0,
    }

    if entity_type == "activation":
        cost_result = _move_activation_costs(
            client,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
        )

    (
        client.table(table)
        .delete()
        .eq("id", source_entity_id)
        .execute()
    )

    resolution_data = {
        "target_entity_id": target_entity_id,
        "source_entity_id": source_entity_id,
        "fields_filled": merge_result[
            "filled_fields"
        ],
        "fields_updated": merge_result[
            "updated_fields"
        ],
        "fields_merged": merge_result[
            "merged_fields"
        ],
        "conflicts": merge_result["conflicts"],
        **media_result,
        **cost_result,
    }

    (
        client.table("knowledge_duplicate_candidates")
        .update(
            {
                "status": "merged",
                "resolution_strategy": strategy,
                "resolved_at": (
                    pd.Timestamp.utcnow().isoformat()
                ),
                "resolution_data": _json_safe(
                    resolution_data
                ),
            }
        )
        .eq("id", review_id)
        .execute()
    )

    (
        client.table("knowledge_duplicate_candidates")
        .update(
            {
                "status": "superseded",
                "resolved_at": (
                    pd.Timestamp.utcnow().isoformat()
                ),
                "resolution_data": {
                    "reason": (
                        "source_entity_merged_elsewhere"
                    ),
                    "target_entity_id": target_entity_id,
                },
            }
        )
        .eq("entity_type", entity_type)
        .eq("source_entity_id", source_entity_id)
        .eq("status", "pending")
        .neq("id", review_id)
        .execute()
    )

    return resolution_data


def _record_enrichment_event(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    import_id: str,
    source_file_id: str | None,
    source_file: str | None,
    source_page: int | None,
    match_method: str,
    strategy: str,
    existing: dict,
    incoming: dict,
    result: dict,
) -> None:
    conflicts = result.get("conflicts") or []

    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "import_id": import_id,
        "source_file_id": source_file_id,
        "source_file": source_file,
        "source_page": _json_safe(source_page),
        "match_method": match_method,
        "strategy": strategy,
        "fields_filled": result.get("filled_fields") or [],
        "fields_updated": result.get("updated_fields") or [],
        "fields_merged": result.get("merged_fields") or [],
        "conflict_fields": [
            str(item.get("field"))
            for item in conflicts
            if item.get("field")
        ],
        "before_data": _json_safe(existing),
        "incoming_data": _json_safe(incoming),
        "applied_changes": _json_safe(
            result.get("applied_changes") or {}
        ),
        "conflicts": _json_safe(conflicts),
    }

    (
        client.table("knowledge_enrichment_events")
        .insert(payload)
        .execute()
    )


def _update_import_result(
    client: Client,
    *,
    import_id: str,
    inserted: int,
    enriched: int,
    conflict_records: int,
    skipped: int,
    possible_duplicate_records: int = 0,
    visual_assets_added: int = 0,
    visual_assets_duplicate: int = 0,
    visual_assets_pending: int = 0,
) -> None:
    status = (
        "importado_com_conflitos"
        if conflict_records
        else "importado"
    )

    (
        client.table("imports")
        .update(
            {
                "status": status,
                "imported_records": inserted + enriched,
                "inserted_records": inserted,
                "enriched_records": enriched,
                "conflict_records": conflict_records,
                "skipped_records": skipped,
                "possible_duplicate_records": (
                    possible_duplicate_records
                ),
                "visual_assets_added": visual_assets_added,
                "visual_assets_duplicate": visual_assets_duplicate,
                "visual_assets_pending": visual_assets_pending,
            }
        )
        .eq("id", import_id)
        .execute()
    )


def _strategy_or_legacy(
    existing_strategy: str,
    skip_duplicates: bool | None,
) -> str:
    if skip_duplicates is None:
        return existing_strategy

    return "new_only" if skip_duplicates else "prefer_new"


def _conflict_rows(
    *,
    entity_type: str,
    entity_id: str,
    item_name: str,
    conflicts: list[dict],
) -> list[dict]:
    rows = []

    for item in conflicts:
        rows.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "item_name": item_name,
                "field": item.get("field"),
                "existing_value": item.get(
                    "existing_value"
                ),
                "incoming_value": item.get(
                    "incoming_value"
                ),
                "action": item.get("action"),
            }
        )

    return rows


def _activation_cost_exists(
    client: Client,
    *,
    solution_id: str,
    description: str,
    amount: Any,
) -> bool:
    query = (
        client.table("activation_costs")
        .select("id")
        .eq("solution_id", solution_id)
        .eq("description", description)
        .limit(1)
    )

    if not _is_missing(amount):
        query = query.eq("amount", amount)

    return bool(query.execute().data)



def _record_has_pdf_visual_source(raw: dict) -> bool:
    source_file = str(raw.get("source_file") or "").lower().strip()
    source_page = raw.get("source_page")
    return source_file.endswith(".pdf") and not enrichment_is_blank(
        source_page
    )


def _attach_prepared_visual(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    visual,
    source_file_id: str | None,
) -> str:
    if visual is None:
        return "pending"

    result = upload_generated_media_asset(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
        title=visual.title,
        description=visual.description,
        file_name=visual.file_name,
        file_bytes=visual.file_bytes,
        mime_type=visual.mime_type,
        content_sha256=visual.content_sha256,
        source_file_id=source_file_id,
        source_file=visual.source_file,
        source_page=visual.source_page,
        crop_box=visual.crop_box,
        visual_method=visual.method,
        visual_confidence=visual.confidence,
    )
    return str(result.get("status") or "inserted")


def _count_visual_status(status: str, counters: dict[str, int]) -> None:
    if status == "inserted":
        counters["added"] += 1
    elif status == "duplicate":
        counters["duplicate"] += 1
    else:
        counters["pending"] += 1



def save_catalog(
    client: Client,
    *,
    products_df: pd.DataFrame,
    suppliers_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    alerts_df: pd.DataFrame,
    classification: dict | None,
    source_documents: list[InputDocument],
    existing_strategy: str = "enrich_safe",
    skip_duplicates: bool | None = None,
    auto_extract_visuals: bool = True,
) -> dict:
    strategy = _strategy_or_legacy(
        existing_strategy,
        skip_duplicates,
    )
    custom_taxonomy_aliases = (
        fetch_custom_taxonomy_aliases(client)
    )
    products = [
        normalize_record_taxonomy(
            record,
            "product",
            custom_taxonomy_aliases,
        )
        for record in dataframe_records(products_df)
    ]
    visuals = (
        prepare_visual_assignments(
            products,
            source_documents,
        )
        if auto_extract_visuals
        else [None] * len(products)
    )
    suppliers = dataframe_records(suppliers_df)
    supplier_map, supplier_count = _supplier_maps(
        client,
        suppliers,
    )
    first_supplier_id = next(
        iter(supplier_map.values()),
        None,
    )
    import_id, file_map = create_import(
        client,
        classification=classification,
        destination_base="Base de brindes",
        source_documents=source_documents,
        supplier_id=first_supplier_id,
        project_id=None,
        original_payload={
            "products": products,
            "global_rules": dataframe_records(rules_df),
        },
        warnings=dataframe_records(alerts_df),
    )

    inserted = enriched = skipped = conflict_records = 0
    possible_duplicates = 0
    fields_filled = fields_updated = 0
    visual_counts = {
        "added": 0,
        "duplicate": 0,
        "pending": 0,
    }
    conflict_rows: list[dict] = []

    for row_index, raw in enumerate(products):
        supplier_id = _supplier_id_for_record(
            raw,
            supplier_map,
        )
        item_name = raw.get("name") or "Sem nome"

        payload = _prepare_record(
            raw,
            PRODUCT_COLUMNS,
        )
        payload["supplier_id"] = supplier_id
        payload["import_id"] = import_id
        payload["source_file_id"] = file_map.get(
            str(raw.get("source_file") or "")
        )

        existing, match_method = _find_existing_product(
            client,
            supplier_id=supplier_id,
            sku=raw.get("sku"),
            name=item_name,
        )

        review_match = None

        if not existing:
            similarity = _similar_product_match(
                client,
                supplier_id=supplier_id,
                incoming=payload,
            )

            if similarity["decision"] == "auto":
                existing = similarity["candidate"]
                match_method = similarity["method"]
            elif similarity["decision"] == "review":
                review_match = similarity

        entity_id = None

        if not existing:
            response = (
                client.table("products")
                .insert(payload)
                .execute()
            )

            if response.data:
                entity_id = response.data[0]["id"]
                inserted += 1

                if review_match:
                    _create_duplicate_candidate(
                        client,
                        entity_type="product",
                        source_entity_id=entity_id,
                        candidate=review_match["candidate"],
                        import_id=import_id,
                        source_file_id=payload.get(
                            "source_file_id"
                        ),
                        source_name=item_name,
                        similarity_score=review_match[
                            "score"
                        ],
                        match_method=review_match[
                            "method"
                        ],
                        match_context={
                            "supplier_id": supplier_id,
                            "sku": raw.get("sku"),
                            "category": raw.get(
                                "category"
                            ),
                        },
                        original_strategy=strategy,
                    )
                    possible_duplicates += 1

        elif strategy == "new_only":
            skipped += 1
            continue

        else:
            entity_id = existing["id"]
            result = merge_record(
                existing,
                payload,
                allowed_fields=PRODUCT_COLUMNS,
                strategy=strategy,
            )
            changes = result["applied_changes"]
            conflicts = result["conflicts"]

            if changes:
                (
                    client.table("products")
                    .update(changes)
                    .eq("id", entity_id)
                    .execute()
                )
                enriched += 1

            if conflicts:
                conflict_records += 1
                conflict_rows.extend(
                    _conflict_rows(
                        entity_type="product",
                        entity_id=entity_id,
                        item_name=item_name,
                        conflicts=conflicts,
                    )
                )

            fields_filled += len(
                result["filled_fields"]
            )
            fields_updated += len(
                result["updated_fields"]
            )

            _record_enrichment_event(
                client,
                entity_type="product",
                entity_id=entity_id,
                import_id=import_id,
                source_file_id=payload.get(
                    "source_file_id"
                ),
                source_file=raw.get("source_file"),
                source_page=raw.get("source_page"),
                match_method=match_method,
                strategy=strategy,
                existing=existing,
                incoming=payload,
                result=result,
            )

            if not changes and not conflicts:
                skipped += 1

        if (
            entity_id
            and auto_extract_visuals
            and _record_has_pdf_visual_source(raw)
        ):
            status = _attach_prepared_visual(
                client,
                entity_type="product",
                entity_id=entity_id,
                visual=visuals[row_index],
                source_file_id=payload.get(
                    "source_file_id"
                ),
            )
            _count_visual_status(
                status,
                visual_counts,
            )

    _update_import_result(
        client,
        import_id=import_id,
        inserted=inserted,
        enriched=enriched,
        conflict_records=conflict_records,
        skipped=skipped,
        possible_duplicate_records=possible_duplicates,
        visual_assets_added=visual_counts["added"],
        visual_assets_duplicate=visual_counts[
            "duplicate"
        ],
        visual_assets_pending=visual_counts["pending"],
    )

    return {
        "import_id": import_id,
        "suppliers_saved": supplier_count,
        "records_inserted": inserted,
        "records_enriched": enriched,
        "records_with_conflicts": conflict_records,
        "possible_duplicate_records": possible_duplicates,
        "duplicates_skipped": skipped,
        "fields_filled": fields_filled,
        "fields_updated": fields_updated,
        "conflicts": conflict_rows,
        "costs_inserted": 0,
        "visual_assets_added": visual_counts["added"],
        "visual_assets_duplicate": visual_counts[
            "duplicate"
        ],
        "visual_assets_pending": visual_counts["pending"],
    }


def save_activations(
    client: Client,
    *,
    solutions_df: pd.DataFrame,
    costs_df: pd.DataFrame,
    suppliers_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    alerts_df: pd.DataFrame,
    classification: dict | None,
    source_documents: list[InputDocument],
    existing_strategy: str = "enrich_safe",
    skip_duplicates: bool | None = None,
    auto_extract_visuals: bool = True,
) -> dict:
    strategy = _strategy_or_legacy(
        existing_strategy,
        skip_duplicates,
    )
    custom_taxonomy_aliases = (
        fetch_custom_taxonomy_aliases(client)
    )
    solutions = [
        normalize_record_taxonomy(
            record,
            "activation",
            custom_taxonomy_aliases,
        )
        for record in dataframe_records(solutions_df)
    ]
    visuals = (
        prepare_visual_assignments(
            solutions,
            source_documents,
        )
        if auto_extract_visuals
        else [None] * len(solutions)
    )
    costs = dataframe_records(costs_df)
    suppliers = dataframe_records(suppliers_df)
    supplier_map, supplier_count = _supplier_maps(
        client,
        suppliers,
    )
    first_supplier_id = next(
        iter(supplier_map.values()),
        None,
    )
    import_id, file_map = create_import(
        client,
        classification=classification,
        destination_base="Base de soluções e ativações",
        source_documents=source_documents,
        supplier_id=first_supplier_id,
        project_id=None,
        original_payload={
            "solutions": solutions,
            "cost_components": costs,
            "global_rules": dataframe_records(rules_df),
        },
        warnings=dataframe_records(alerts_df),
    )

    inserted = enriched = skipped = conflict_records = 0
    possible_duplicates = 0
    fields_filled = fields_updated = costs_inserted = 0
    visual_counts = {
        "added": 0,
        "duplicate": 0,
        "pending": 0,
    }
    conflict_rows: list[dict] = []
    local_to_database: dict[str, str] = {}

    for row_index, raw in enumerate(solutions):
        supplier_id = _supplier_id_for_record(
            raw,
            supplier_map,
        )
        item_name = raw.get("name") or "Sem nome"

        payload = _prepare_record(
            raw,
            ACTIVATION_COLUMNS,
        )
        payload["supplier_id"] = supplier_id
        payload["import_id"] = import_id
        payload["source_file_id"] = file_map.get(
            str(raw.get("source_file") or "")
        )

        local_id = str(
            raw.get("solution_id") or ""
        )

        existing, match_method = _find_existing_activation(
            client,
            supplier_id=supplier_id,
            name=item_name,
            project_name=raw.get("project_name"),
        )

        review_match = None

        if not existing:
            similarity = _similar_activation_match(
                client,
                supplier_id=supplier_id,
                incoming=payload,
            )

            if similarity["decision"] == "auto":
                existing = similarity["candidate"]
                match_method = similarity["method"]
            elif similarity["decision"] == "review":
                review_match = similarity

        database_id = None

        if not existing:
            response = (
                client.table("activation_solutions")
                .insert(payload)
                .execute()
            )

            if response.data:
                database_id = response.data[0]["id"]
                inserted += 1

                if review_match:
                    _create_duplicate_candidate(
                        client,
                        entity_type="activation",
                        source_entity_id=database_id,
                        candidate=review_match["candidate"],
                        import_id=import_id,
                        source_file_id=payload.get(
                            "source_file_id"
                        ),
                        source_name=item_name,
                        similarity_score=review_match[
                            "score"
                        ],
                        match_method=review_match[
                            "method"
                        ],
                        match_context={
                            "supplier_id": supplier_id,
                            "project_name": raw.get(
                                "project_name"
                            ),
                            "category": raw.get(
                                "category"
                            ),
                        },
                        original_strategy=strategy,
                    )
                    possible_duplicates += 1

        else:
            database_id = existing["id"]

            if strategy == "new_only":
                skipped += 1
                continue

            result = merge_record(
                existing,
                payload,
                allowed_fields=ACTIVATION_COLUMNS,
                strategy=strategy,
            )
            changes = result["applied_changes"]
            conflicts = result["conflicts"]

            if changes:
                (
                    client.table("activation_solutions")
                    .update(changes)
                    .eq("id", database_id)
                    .execute()
                )
                enriched += 1

            if conflicts:
                conflict_records += 1
                conflict_rows.extend(
                    _conflict_rows(
                        entity_type="activation",
                        entity_id=database_id,
                        item_name=item_name,
                        conflicts=conflicts,
                    )
                )

            fields_filled += len(
                result["filled_fields"]
            )
            fields_updated += len(
                result["updated_fields"]
            )

            _record_enrichment_event(
                client,
                entity_type="activation",
                entity_id=database_id,
                import_id=import_id,
                source_file_id=payload.get(
                    "source_file_id"
                ),
                source_file=raw.get("source_file"),
                source_page=raw.get("source_page"),
                match_method=match_method,
                strategy=strategy,
                existing=existing,
                incoming=payload,
                result=result,
            )

            if not changes and not conflicts:
                skipped += 1

        if database_id:
            if local_id:
                local_to_database[local_id] = database_id

            if (
                auto_extract_visuals
                and _record_has_pdf_visual_source(raw)
            ):
                status = _attach_prepared_visual(
                    client,
                    entity_type="activation",
                    entity_id=database_id,
                    visual=visuals[row_index],
                    source_file_id=payload.get(
                        "source_file_id"
                    ),
                )
                _count_visual_status(
                    status,
                    visual_counts,
                )

    for raw_cost in costs:
        database_solution_id = local_to_database.get(
            str(raw_cost.get("solution_id") or "")
        )

        if not database_solution_id:
            continue

        description = (
            raw_cost.get("description")
            or "Custo adicional"
        )
        amount = _json_safe(raw_cost.get("amount"))

        if _activation_cost_exists(
            client,
            solution_id=database_solution_id,
            description=description,
            amount=amount,
        ):
            continue

        cost_payload = {
            "solution_id": database_solution_id,
            "description": description,
            "amount": amount,
            "currency": (
                raw_cost.get("currency")
                or "Não informado"
            ),
            "treatment": (
                raw_cost.get("treatment")
                or "Não informado"
            ),
            "notes": _json_safe(
                raw_cost.get("notes")
            ),
            "source_page": _json_safe(
                raw_cost.get("source_page")
            ),
            "confidence": _json_safe(
                raw_cost.get("confidence")
            ),
            "raw_data": _json_safe(raw_cost),
        }

        (
            client.table("activation_costs")
            .insert(cost_payload)
            .execute()
        )
        costs_inserted += 1

    _update_import_result(
        client,
        import_id=import_id,
        inserted=inserted,
        enriched=enriched,
        conflict_records=conflict_records,
        skipped=skipped,
        possible_duplicate_records=possible_duplicates,
        visual_assets_added=visual_counts["added"],
        visual_assets_duplicate=visual_counts[
            "duplicate"
        ],
        visual_assets_pending=visual_counts["pending"],
    )

    return {
        "import_id": import_id,
        "suppliers_saved": supplier_count,
        "records_inserted": inserted,
        "records_enriched": enriched,
        "records_with_conflicts": conflict_records,
        "possible_duplicate_records": possible_duplicates,
        "duplicates_skipped": skipped,
        "fields_filled": fields_filled,
        "fields_updated": fields_updated,
        "conflicts": conflict_rows,
        "costs_inserted": costs_inserted,
        "visual_assets_added": visual_counts["added"],
        "visual_assets_duplicate": visual_counts[
            "duplicate"
        ],
        "visual_assets_pending": visual_counts["pending"],
    }


def save_venues(
    client: Client,
    *,
    venues_df: pd.DataFrame,
    contacts_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    alerts_df: pd.DataFrame,
    classification: dict | None,
    source_documents: list[InputDocument],
    existing_strategy: str = "enrich_safe",
    skip_duplicates: bool | None = None,
    auto_extract_visuals: bool = True,
) -> dict:
    strategy = _strategy_or_legacy(
        existing_strategy,
        skip_duplicates,
    )
    custom_taxonomy_aliases = (
        fetch_custom_taxonomy_aliases(client)
    )
    venues = [
        normalize_record_taxonomy(
            record,
            "venue",
            custom_taxonomy_aliases,
        )
        for record in dataframe_records(venues_df)
    ]
    visuals = (
        prepare_visual_assignments(
            venues,
            source_documents,
        )
        if auto_extract_visuals
        else [None] * len(venues)
    )
    contacts = dataframe_records(contacts_df)
    supplier_map, supplier_count = _supplier_maps(
        client,
        contacts,
    )
    first_supplier_id = next(
        iter(supplier_map.values()),
        None,
    )
    import_id, file_map = create_import(
        client,
        classification=classification,
        destination_base="Base de locais e espaços",
        source_documents=source_documents,
        supplier_id=first_supplier_id,
        project_id=None,
        original_payload={
            "venues": venues,
            "global_rules": dataframe_records(rules_df),
        },
        warnings=dataframe_records(alerts_df),
    )

    inserted = enriched = skipped = conflict_records = 0
    possible_duplicates = 0
    fields_filled = fields_updated = 0
    visual_counts = {
        "added": 0,
        "duplicate": 0,
        "pending": 0,
    }
    conflict_rows: list[dict] = []

    for row_index, raw in enumerate(venues):
        operator_id = _supplier_id_for_record(
            raw,
            supplier_map,
        )
        item_name = raw.get("name") or "Sem nome"

        payload = _prepare_record(
            raw,
            VENUE_COLUMNS,
        )
        payload["operator_id"] = operator_id
        payload["import_id"] = import_id
        payload["source_file_id"] = file_map.get(
            str(raw.get("source_file") or "")
        )

        existing, match_method = _find_existing_venue(
            client,
            operator_id=operator_id,
            name=item_name,
            city=raw.get("city"),
        )

        review_match = None

        if not existing:
            similarity = _similar_venue_match(
                client,
                operator_id=operator_id,
                incoming=payload,
            )

            if similarity["decision"] == "auto":
                existing = similarity["candidate"]
                match_method = similarity["method"]
            elif similarity["decision"] == "review":
                review_match = similarity

        entity_id = None

        if not existing:
            response = (
                client.table("venues")
                .insert(payload)
                .execute()
            )

            if response.data:
                entity_id = response.data[0]["id"]
                inserted += 1

                if review_match:
                    _create_duplicate_candidate(
                        client,
                        entity_type="venue",
                        source_entity_id=entity_id,
                        candidate=review_match["candidate"],
                        import_id=import_id,
                        source_file_id=payload.get(
                            "source_file_id"
                        ),
                        source_name=item_name,
                        similarity_score=review_match[
                            "score"
                        ],
                        match_method=review_match[
                            "method"
                        ],
                        match_context={
                            "operator_id": operator_id,
                            "city": raw.get("city"),
                            "venue_type": raw.get(
                                "venue_type"
                            ),
                        },
                        original_strategy=strategy,
                    )
                    possible_duplicates += 1

        elif strategy == "new_only":
            skipped += 1
            continue

        else:
            entity_id = existing["id"]
            result = merge_record(
                existing,
                payload,
                allowed_fields=VENUE_COLUMNS,
                strategy=strategy,
            )
            changes = result["applied_changes"]
            conflicts = result["conflicts"]

            if changes:
                (
                    client.table("venues")
                    .update(changes)
                    .eq("id", entity_id)
                    .execute()
                )
                enriched += 1

            if conflicts:
                conflict_records += 1
                conflict_rows.extend(
                    _conflict_rows(
                        entity_type="venue",
                        entity_id=entity_id,
                        item_name=item_name,
                        conflicts=conflicts,
                    )
                )

            fields_filled += len(
                result["filled_fields"]
            )
            fields_updated += len(
                result["updated_fields"]
            )

            _record_enrichment_event(
                client,
                entity_type="venue",
                entity_id=entity_id,
                import_id=import_id,
                source_file_id=payload.get(
                    "source_file_id"
                ),
                source_file=raw.get("source_file"),
                source_page=raw.get("source_page"),
                match_method=match_method,
                strategy=strategy,
                existing=existing,
                incoming=payload,
                result=result,
            )

            if not changes and not conflicts:
                skipped += 1

        if (
            entity_id
            and auto_extract_visuals
            and _record_has_pdf_visual_source(raw)
        ):
            status = _attach_prepared_visual(
                client,
                entity_type="venue",
                entity_id=entity_id,
                visual=visuals[row_index],
                source_file_id=payload.get(
                    "source_file_id"
                ),
            )
            _count_visual_status(
                status,
                visual_counts,
            )

    _update_import_result(
        client,
        import_id=import_id,
        inserted=inserted,
        enriched=enriched,
        conflict_records=conflict_records,
        skipped=skipped,
        possible_duplicate_records=possible_duplicates,
        visual_assets_added=visual_counts["added"],
        visual_assets_duplicate=visual_counts[
            "duplicate"
        ],
        visual_assets_pending=visual_counts["pending"],
    )

    return {
        "import_id": import_id,
        "suppliers_saved": supplier_count,
        "records_inserted": inserted,
        "records_enriched": enriched,
        "records_with_conflicts": conflict_records,
        "possible_duplicate_records": possible_duplicates,
        "duplicates_skipped": skipped,
        "fields_filled": fields_filled,
        "fields_updated": fields_updated,
        "conflicts": conflict_rows,
        "costs_inserted": 0,
        "visual_assets_added": visual_counts["added"],
        "visual_assets_duplicate": visual_counts[
            "duplicate"
        ],
        "visual_assets_pending": visual_counts["pending"],
    }



def _iso_date_or_none(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None


def save_briefing(
    client: Client,
    *,
    briefing: dict,
    classification: dict | None,
    source_documents: list[InputDocument],
) -> dict:
    project_payload = {
        "project_name": _json_safe(briefing.get("project_name")),
        "client_brand": _json_safe(briefing.get("client_brand")),
        "event_name": _json_safe(briefing.get("event_name")),
        "event_type": _json_safe(briefing.get("event_type")),
        "objective": _json_safe(briefing.get("objective")),
        "audience_profile": _json_safe(briefing.get("audience_profile")),
        "audience_quantity": _json_safe(briefing.get("audience_quantity")),
        "budget_total_brl": _json_safe(briefing.get("budget_total_brl")),
        "budget_unit_brl": _json_safe(briefing.get("budget_unit_brl")),
        "location_city": _json_safe(briefing.get("location_city")),
        "location_state": _json_safe(briefing.get("location_state")),
        "location_country": _json_safe(briefing.get("location_country")),
        "event_date": _iso_date_or_none(briefing.get("event_date")),
        "desired_delivery_date": _iso_date_or_none(
            briefing.get("desired_delivery_date")
        ),
        "available_days": _json_safe(briefing.get("available_days")),
        "creative_concept": _json_safe(briefing.get("creative_concept")),
        "desired_attributes": briefing.get("desired_attributes") or [],
        "restrictions": briefing.get("restrictions") or [],
        "status": "estruturado",
        "raw_data": _json_safe(briefing),
    }

    project_response = (
        client.table("projects")
        .insert(project_payload)
        .execute()
    )
    project_id = project_response.data[0]["id"]

    import_id, _ = create_import(
        client,
        classification=classification,
        destination_base="Base de projetos e briefings",
        source_documents=source_documents,
        supplier_id=None,
        project_id=project_id,
        original_payload={"briefing": briefing},
        warnings=[],
    )

    briefing_payload = {
        "project_id": project_id,
        "import_id": import_id,
        "source_summary": _json_safe(briefing.get("source_summary")),
        "decisions_already_made": (
            briefing.get("decisions_already_made") or []
        ),
        "open_questions": briefing.get("open_questions") or [],
        "contradictions": briefing.get("contradictions") or [],
        "differentiations_by_audience": (
            briefing.get("differentiations_by_audience") or []
        ),
        "products_already_mentioned": (
            briefing.get("products_already_mentioned") or []
        ),
        "confidence": _json_safe(briefing.get("confidence")),
        "raw_data": _json_safe(briefing),
    }

    client.table("project_briefings").insert(
        briefing_payload
    ).execute()

    client.table("imports").update(
        {
            "status": "importado",
            "imported_records": 1,
        }
    ).eq("id", import_id).execute()

    return {
        "import_id": import_id,
        "project_id": project_id,
        "suppliers_saved": 0,
        "records_inserted": 1,
        "duplicates_skipped": 0,
        "costs_inserted": 0,
    }




CURATION_ENTITY_TABLES = {
    "product": "products",
    "activation": "activation_solutions",
    "venue": "venues",
    "supplier": "suppliers",
}

CURATION_EDIT_COLUMNS = {
    "product": PRODUCT_COLUMNS
    | {
        "name",
        "sku",
        "category",
        "supplier_id",
    },
    "activation": ACTIVATION_COLUMNS
    | {
        "name",
        "category",
        "supplier_id",
    },
    "venue": VENUE_COLUMNS
    | {
        "name",
        "venue_type",
        "operator_id",
    },
    "supplier": {
        "name",
        "website_url",
        "contact_name",
        "contact_role",
        "email",
        "phone",
        "whatsapp",
        "instagram_url",
        "linkedin_url",
        "address",
        "notes",
    },
}

CURATION_ARRAY_FIELDS = {
    "tags",
    "included_items",
    "excluded_items",
    "infrastructure_requirements",
    "rooms_or_areas",
    "infrastructure",
    "restrictions",
}


def fetch_supplier_options(
    client: Client,
) -> dict[str, str]:
    response = (
        client.table("suppliers")
        .select("id,name")
        .order("name")
        .limit(2000)
        .execute()
    )

    return {
        str(row["id"]): str(
            row.get("name")
            or "Fornecedor sem nome"
        )
        for row in response.data or []
    }


def fetch_curation_state(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
) -> dict:
    response = (
        client.table("knowledge_curation_states")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else {}


def fetch_curation_states(
    client: Client,
    items: list[tuple[str, str]],
) -> dict[tuple[str, str], dict]:
    if not items:
        return {}

    grouped: dict[str, list[str]] = {}

    for entity_type, entity_id in items:
        grouped.setdefault(
            entity_type,
            [],
        ).append(str(entity_id))

    result = {}

    for entity_type, entity_ids in grouped.items():
        unique_ids = list(
            dict.fromkeys(entity_ids)
        )

        for start in range(
            0,
            len(unique_ids),
            150,
        ):
            chunk = unique_ids[
                start:start + 150
            ]

            response = (
                client.table(
                    "knowledge_curation_states"
                )
                .select("*")
                .eq("entity_type", entity_type)
                .in_("entity_id", chunk)
                .execute()
            )

            for row in response.data or []:
                result[
                    (
                        str(row["entity_type"]),
                        str(row["entity_id"]),
                    )
                ] = row

    return result


def fetch_curation_history(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 100,
) -> pd.DataFrame:
    response = (
        client.table("knowledge_edit_events")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return pd.DataFrame(response.data or [])


def _curation_values_equal(
    first: Any,
    second: Any,
) -> bool:
    return json.dumps(
        _json_safe(first),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ) == json.dumps(
        _json_safe(second),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _clean_curation_update(
    field: str,
    value: Any,
) -> Any:
    if field in CURATION_ARRAY_FIELDS:
        if isinstance(value, str):
            return split_pipe(value)

        if isinstance(value, (list, tuple, set)):
            return [
                item
                for item in value
                if not _is_missing(item)
            ]

        return []

    return _json_safe(value)


def _insert_edit_events(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    events: list[dict],
    editor_name: str | None,
    edit_notes: str | None,
) -> None:
    if not events:
        return

    payload = []

    for event in events:
        payload.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "event_type": event.get(
                    "event_type",
                    "manual_update",
                ),
                "field_name": event["field_name"],
                "field_label": event.get(
                    "field_label"
                ),
                "old_value": _json_safe(
                    event.get("old_value")
                ),
                "new_value": _json_safe(
                    event.get("new_value")
                ),
                "editor_name": editor_name,
                "edit_source": "manual",
                "edit_notes": edit_notes,
            }
        )

    (
        client.table("knowledge_edit_events")
        .insert(payload)
        .execute()
    )


def update_curated_entity(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    updates: dict,
    editor_name: str,
    edit_notes: str | None,
    field_labels: dict[str, str],
    curation_payload: dict,
) -> dict:
    table = CURATION_ENTITY_TABLES.get(
        entity_type
    )

    if not table:
        raise ValueError(
            "Tipo de cadastro não suportado."
        )

    current_response = (
        client.table(table)
        .select("*")
        .eq("id", entity_id)
        .limit(1)
        .execute()
    )

    if not current_response.data:
        raise ValueError(
            "O cadastro não foi encontrado."
        )

    current = current_response.data[0]
    allowed = CURATION_EDIT_COLUMNS[
        entity_type
    ]

    if entity_type in {
        "product",
        "activation",
        "venue",
    }:
        try:
            custom_taxonomy_aliases = (
                fetch_custom_taxonomy_aliases(
                    client
                )
            )
        except Exception:
            custom_taxonomy_aliases = []

        taxonomy_input = {
            **current,
            **updates,
        }
        taxonomy_output = (
            normalize_record_taxonomy(
                taxonomy_input,
                entity_type,
                custom_taxonomy_aliases,
            )
        )

        category_field = (
            "venue_type"
            if entity_type == "venue"
            else "category"
        )

        if category_field in allowed:
            updates[category_field] = (
                taxonomy_output.get(
                    category_field
                )
            )

        if "tags" in allowed:
            updates["tags"] = (
                taxonomy_output.get("tags")
                or []
            )

    cleaned = {}
    events = []

    for field, value in updates.items():
        if field not in allowed:
            continue

        cleaned_value = _clean_curation_update(
            field,
            value,
        )
        old_value = current.get(field)

        if _curation_values_equal(
            old_value,
            cleaned_value,
        ):
            continue

        cleaned[field] = cleaned_value
        events.append(
            {
                "field_name": field,
                "field_label": field_labels.get(
                    field,
                    field,
                ),
                "old_value": old_value,
                "new_value": cleaned_value,
                "event_type": "manual_update",
            }
        )

    if (
        entity_type == "supplier"
        and "name" in cleaned
        and cleaned["name"]
    ):
        cleaned["normalized_name"] = (
            normalize_name(cleaned["name"])
        )

    if cleaned:
        (
            client.table(table)
            .update(cleaned)
            .eq("id", entity_id)
            .execute()
        )

    current_state = fetch_curation_state(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    state_payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "validation_status": (
            curation_payload.get(
                "validation_status"
            )
            or "not_reviewed"
        ),
        "reviewed_at": (
            pd.Timestamp.utcnow().isoformat()
        ),
        "reviewed_by": _json_safe(
            curation_payload.get("reviewed_by")
        ),
        "review_source": _json_safe(
            curation_payload.get("review_source")
        ),
        "next_review_date": _json_safe(
            curation_payload.get(
                "next_review_date"
            )
        ),
        "internal_notes": _json_safe(
            curation_payload.get(
                "internal_notes"
            )
        ),
        "is_archived": bool(
            curation_payload.get("is_archived")
        ),
    }

    for field in (
        "review_source",
        "internal_notes",
        "is_archived",
    ):
        old_value = current_state.get(field)
        new_value = state_payload.get(field)

        if _curation_values_equal(
            old_value,
            new_value,
        ):
            continue

        event_type = "status_update"

        if field == "is_archived":
            event_type = (
                "archive"
                if bool(new_value)
                else "restore"
            )

        events.append(
            {
                "field_name": field,
                "field_label": field_labels.get(
                    field,
                    field,
                ),
                "old_value": old_value,
                "new_value": new_value,
                "event_type": event_type,
            }
        )

    (
        client.table("knowledge_curation_states")
        .upsert(
            state_payload,
            on_conflict="entity_type,entity_id",
        )
        .execute()
    )

    _insert_edit_events(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
        events=events,
        editor_name=editor_name,
        edit_notes=edit_notes,
    )

    return {
        "fields_changed": len(events),
        "record_changes": cleaned,
        "curation_state": state_payload,
    }


def knowledge_entity_dependency_counts(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
) -> dict[str, int]:
    dependencies = {}

    if entity_type == "supplier":
        checks = [
            ("Brindes associados", "products", "supplier_id"),
            (
                "Ativações associadas",
                "activation_solutions",
                "supplier_id",
            ),
            ("Locais associados", "venues", "operator_id"),
        ]
    else:
        checks = [
            (
                "Recomendações salvas",
                "recommendation_results",
                "item_id",
            ),
            (
                "Recomendações por execução",
                "execution_recommendation_results",
                "item_id",
            ),
        ]

    for label, table, field in checks:
        query = (
            client.table(table)
            .select("id", count="exact")
            .eq(field, entity_id)
            .limit(1)
        )

        if entity_type != "supplier":
            query = query.eq(
                "item_type",
                entity_type,
            )

        try:
            response = query.execute()
            dependencies[label] = int(
                response.count or 0
            )
        except Exception:
            dependencies[label] = 0

    return dependencies


def delete_knowledge_entity(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    editor_name: str,
) -> None:
    dependencies = knowledge_entity_dependency_counts(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    if sum(dependencies.values()):
        raise ValueError(
            "O cadastro possui vínculos e deve ser arquivado."
        )

    table = CURATION_ENTITY_TABLES[
        entity_type
    ]

    current_response = (
        client.table(table)
        .select("*")
        .eq("id", entity_id)
        .limit(1)
        .execute()
    )
    current = (
        current_response.data[0]
        if current_response.data
        else {}
    )

    media_response = (
        client.table("media_assets")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .execute()
    )

    for media in media_response.data or []:
        bucket = str(
            media.get("storage_bucket")
            or ""
        ).strip()
        storage_path = str(
            media.get("storage_path")
            or ""
        ).strip()

        if bucket and storage_path:
            try:
                (
                    client.storage
                    .from_(bucket)
                    .remove([storage_path])
                )
            except Exception:
                pass

    (
        client.table("media_assets")
        .delete()
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .execute()
    )

    if entity_type == "activation":
        (
            client.table("activation_costs")
            .delete()
            .eq("solution_id", entity_id)
            .execute()
        )

    (
        client.table(
            "knowledge_duplicate_candidates"
        )
        .delete()
        .eq("entity_type", entity_type)
        .or_(
            f"source_entity_id.eq.{entity_id},"
            f"candidate_entity_id.eq.{entity_id}"
        )
        .execute()
    )

    (
        client.table("knowledge_curation_states")
        .delete()
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .execute()
    )

    _insert_edit_events(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
        events=[
            {
                "field_name": "__record__",
                "field_label": "Cadastro excluído",
                "old_value": current,
                "new_value": None,
                "event_type": "delete",
            }
        ],
        editor_name=editor_name,
        edit_notes=(
            "Exclusão definitiva realizada "
            "pela Administração."
        ),
    )

    (
        client.table(table)
        .delete()
        .eq("id", entity_id)
        .execute()
    )


def fetch_custom_taxonomy_aliases(
    client: Client,
    *,
    include_inactive: bool = False,
) -> list[dict]:
    query = (
        client.table(
            "knowledge_taxonomy_aliases"
        )
        .select("*")
        .order("entity_type")
        .order("canonical_term")
        .order("alias")
        .limit(5000)
    )

    if not include_inactive:
        query = query.eq(
            "is_active",
            True,
        )

    try:
        response = query.execute()
        return response.data or []
    except Exception:
        return []


def upsert_custom_taxonomy_alias(
    client: Client,
    *,
    entity_type: str,
    canonical_term: str,
    alias: str,
    notes: str | None = None,
) -> dict:
    if entity_type not in {
        "product",
        "activation",
        "venue",
    }:
        raise ValueError(
            "Tipo de taxonomia inválido."
        )

    if canonical_term not in taxonomy_options(
        entity_type
    ):
        raise ValueError(
            "A categoria canônica não existe "
            "na taxonomia padrão."
        )

    clean_alias = str(alias or "").strip()

    if len(clean_alias) < 2:
        raise ValueError(
            "Informe uma variação com pelo menos "
            "dois caracteres."
        )

    normalized_alias = normalize_taxonomy_text(
        clean_alias
    )

    default_rows = taxonomy_catalog_rows()

    default_match = next(
        (
            row
            for row in default_rows
            if row["entity_type"] == entity_type
            and row["normalized_alias"]
            == normalized_alias
        ),
        None,
    )

    if default_match:
        if (
            default_match["canonical_term"]
            == canonical_term
        ):
            raise ValueError(
                "Essa variação já faz parte "
                "da taxonomia padrão."
            )

        raise ValueError(
            "Essa variação já aponta para "
            f'"{default_match["canonical_term"]}".'
        )

    payload = {
        "entity_type": entity_type,
        "canonical_term": canonical_term,
        "alias": clean_alias,
        "normalized_alias": normalized_alias,
        "is_active": True,
        "created_by": "Administração da NAVE",
        "notes": _json_safe(notes),
    }

    response = (
        client.table(
            "knowledge_taxonomy_aliases"
        )
        .upsert(
            payload,
            on_conflict=(
                "entity_type,normalized_alias"
            ),
        )
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else payload
    )


def set_custom_taxonomy_alias_active(
    client: Client,
    *,
    alias_id: str,
    is_active: bool,
) -> None:
    (
        client.table(
            "knowledge_taxonomy_aliases"
        )
        .update(
            {
                "is_active": bool(is_active),
            }
        )
        .eq("id", alias_id)
        .execute()
    )


def fetch_taxonomy_audit(
    client: Client,
) -> pd.DataFrame:
    custom_aliases = (
        fetch_custom_taxonomy_aliases(
            client
        )
    )

    table_specs = [
        (
            "product",
            "products",
            "category",
        ),
        (
            "activation",
            "activation_solutions",
            "category",
        ),
        (
            "venue",
            "venues",
            "venue_type",
        ),
    ]

    rows = []

    for (
        entity_type,
        table,
        category_field,
    ) in table_specs:
        frame = _fetch_all_rows(
            client,
            table=table,
            columns=(
                f"id,name,{category_field},"
                "description,tags"
            ),
        )

        if frame.empty:
            continue

        for _, source in frame.iterrows():
            record = source.to_dict()
            normalized = normalize_record_taxonomy(
                record,
                entity_type,
                custom_aliases,
            )

            original = record.get(
                category_field
            )
            canonical = normalized.get(
                category_field
            )
            original_tags = split_pipe(
                record.get("tags")
            )
            new_tags = normalized.get(
                "tags",
                [],
            )

            category_changed = not (
                normalize_taxonomy_text(original)
                == normalize_taxonomy_text(
                    canonical
                )
            )
            tags_changed = set(
                normalize_taxonomy_text(item)
                for item in original_tags
            ) != set(
                normalize_taxonomy_text(item)
                for item in new_tags
            )

            rows.append(
                {
                    "entity_type": entity_type,
                    "entity_id": str(
                        record.get("id")
                    ),
                    "Tipo": {
                        "product": "Brinde",
                        "activation": "Solução / ativação",
                        "venue": "Local / espaço",
                    }[entity_type],
                    "Item": (
                        record.get("name")
                        or "Sem nome"
                    ),
                    "Categoria atual": (
                        original
                        or "Não informada"
                    ),
                    "Categoria NAVE": (
                        canonical
                        or "Não informada"
                    ),
                    "Termos reconhecidos": ", ".join(
                        normalized.get(
                            "taxonomy_terms",
                            [],
                        )
                    )
                    or "Nenhum",
                    "Variações encontradas": ", ".join(
                        normalized.get(
                            "taxonomy_matched_aliases",
                            [],
                        )
                    )
                    or "Nenhuma",
                    "Precisa atualizar": bool(
                        category_changed
                        or tags_changed
                    ),
                    "_category_field": category_field,
                    "_new_category": canonical,
                    "_old_tags": original_tags,
                    "_new_tags": new_tags,
                }
            )

    return pd.DataFrame(rows)


def apply_taxonomy_normalization(
    client: Client,
) -> dict:
    audit = fetch_taxonomy_audit(
        client
    )

    if audit.empty:
        return {
            "updated_records": 0,
            "category_changes": 0,
            "tag_changes": 0,
        }

    updates = audit[
        audit["Precisa atualizar"].eq(True)
    ]

    updated_records = 0
    category_changes = 0
    tag_changes = 0

    table_map = {
        "product": "products",
        "activation": "activation_solutions",
        "venue": "venues",
    }

    for _, row in updates.iterrows():
        entity_type = str(
            row["entity_type"]
        )
        entity_id = str(
            row["entity_id"]
        )
        category_field = str(
            row["_category_field"]
        )

        current_response = (
            client.table(
                table_map[entity_type]
            )
            .select("*")
            .eq("id", entity_id)
            .limit(1)
            .execute()
        )

        if not current_response.data:
            continue

        current = current_response.data[0]
        changes = {}
        events = []

        new_category = row.get(
            "_new_category"
        )

        if (
            new_category
            and normalize_taxonomy_text(
                current.get(category_field)
            )
            != normalize_taxonomy_text(
                new_category
            )
        ):
            changes[category_field] = (
                new_category
            )
            category_changes += 1
            events.append(
                {
                    "field_name": category_field,
                    "field_label": (
                        "Categoria NAVE"
                        if entity_type != "venue"
                        else "Tipo de espaço NAVE"
                    ),
                    "old_value": current.get(
                        category_field
                    ),
                    "new_value": new_category,
                    "event_type": "manual_update",
                }
            )

        old_tags = split_pipe(
            current.get("tags")
        )
        new_tags = list(
            row.get("_new_tags")
            or []
        )

        if set(
            normalize_taxonomy_text(item)
            for item in old_tags
        ) != set(
            normalize_taxonomy_text(item)
            for item in new_tags
        ):
            changes["tags"] = new_tags
            tag_changes += 1
            events.append(
                {
                    "field_name": "tags",
                    "field_label": "Tags da taxonomia",
                    "old_value": old_tags,
                    "new_value": new_tags,
                    "event_type": "manual_update",
                }
            )

        if not changes:
            continue

        (
            client.table(
                table_map[entity_type]
            )
            .update(changes)
            .eq("id", entity_id)
            .execute()
        )

        _insert_edit_events(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
            events=events,
            editor_name="Taxonomia NAVE",
            edit_notes=(
                "Padronização automática de "
                "categorias e termos equivalentes."
            ),
        )

        updated_records += 1

    return {
        "updated_records": updated_records,
        "category_changes": category_changes,
        "tag_changes": tag_changes,
    }


def fetch_supplier_coverage(
    client: Client,
    *,
    limit: int = 1000,
) -> pd.DataFrame:
    response = (
        client.table("supplier_coverage_overview")
        .select("*")
        .order("name")
        .limit(limit)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def fetch_supplier_by_id(
    client: Client,
    supplier_id: str,
) -> dict | None:
    response = (
        client.table("suppliers")
        .select("*")
        .eq("id", supplier_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def update_supplier_coverage(
    client: Client,
    *,
    supplier_id: str,
    payload: dict,
) -> dict:
    arrays = {
        "served_states",
        "served_cities",
        "local_team_locations",
    }
    allowed = {
        "base_city",
        "base_state",
        "base_country",
        "serves_nationally",
        "served_states",
        "served_cities",
        "has_local_teams",
        "local_team_locations",
        "travel_pricing_mode",
        "default_travel_cost_brl",
        "freight_pricing_mode",
        "default_freight_cost_brl",
        "travel_lead_days",
        "equipment_transport_required",
        "accommodation_required",
        "coverage_notes",
    }

    cleaned = {}
    for key in allowed:
        value = payload.get(key)
        if key in arrays:
            cleaned[key] = split_pipe(value)
        else:
            cleaned[key] = _json_safe(value)

    response = (
        client.table("suppliers")
        .update(cleaned)
        .eq("id", supplier_id)
        .execute()
    )
    return response.data[0] if response.data else cleaned



def _fetch_all_rows(
    client: Client,
    *,
    table: str,
    columns: str = "*",
    page_size: int = 1000,
) -> pd.DataFrame:
    rows = []
    start = 0

    while True:
        response = (
            client.table(table)
            .select(columns)
            .range(
                start,
                start + page_size - 1,
            )
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    return pd.DataFrame(rows)


def fetch_base_quality_snapshot(
    client: Client,
) -> dict[str, Any]:
    products = _fetch_all_rows(
        client,
        table="products",
        columns=(
            "id,supplier_id,name,category,description,"
            "unit_price,price_min,price_max,currency,"
            "price_status,min_order_qty,material,"
            "dimensions_raw,capacity,capacity_ml,finish,"
            "customizable,decoration,licensing_notes,"
            "tags,source_file,catalog_name"
        ),
    )

    activations = _fetch_all_rows(
        client,
        table="activation_solutions",
        columns=(
            "id,supplier_id,name,category,description,"
            "base_price,currency,price_status,"
            "lead_time_days,infrastructure_requirements,"
            "internet_requirement,included_items,"
            "excluded_items,location,tags,source_file"
        ),
    )

    venues = _fetch_all_rows(
        client,
        table="venues",
        columns=(
            "id,operator_id,name,venue_type,description,"
            "city,state,standing_capacity,seated_capacity,"
            "auditorium_capacity,base_price,price_min,"
            "price_max,currency,price_status,"
            "infrastructure,power_supply,internet,"
            "air_conditioning,audiovisual,"
            "kitchen_or_catering,bathrooms,furniture,"
            "parking,accessibility,loading_access,"
            "website_url,map_url,document_name"
        ),
    )

    suppliers = _fetch_all_rows(
        client,
        table="suppliers",
        columns=(
            "id,name,website_url,contact_name,email,phone,"
            "whatsapp,base_city,base_state,base_country,"
            "serves_nationally,served_states,served_cities,"
            "local_team_locations,travel_pricing_mode,"
            "default_travel_cost_brl,"
            "freight_pricing_mode,"
            "default_freight_cost_brl,"
            "travel_lead_days,coverage_notes,notes"
        ),
    )

    media = _fetch_all_rows(
        client,
        table="media_asset_counts",
        columns=(
            "entity_type,entity_id,media_count,"
            "image_count,document_count,has_primary"
        ),
    )

    try:
        supplier_overview = _fetch_all_rows(
            client,
            table="supplier_coverage_overview",
            columns=(
                "supplier_id,products_count,"
                "activations_count,venues_count"
            ),
        )
    except Exception:
        supplier_overview = pd.DataFrame()

    try:
        duplicate_response = (
            client.table(
                "knowledge_duplicate_candidates"
            )
            .select("id", count="exact")
            .eq("status", "pending")
            .limit(1)
            .execute()
        )
        pending_duplicates = int(
            duplicate_response.count or 0
        )
    except Exception:
        pending_duplicates = 0

    try:
        curation_states = _fetch_all_rows(
            client,
            table="knowledge_curation_states",
            columns=(
                "entity_type,entity_id,validation_status,"
                "reviewed_at,reviewed_by,next_review_date,"
                "is_archived"
            ),
        )
    except Exception:
        curation_states = pd.DataFrame()

    return {
        "products": products,
        "activations": activations,
        "venues": venues,
        "suppliers": suppliers,
        "media": media,
        "supplier_overview": supplier_overview,
        "curation_states": curation_states,
        "pending_duplicates": pending_duplicates,
    }


def database_counts(client: Client) -> dict[str, int]:
    tables = {
        "Fornecedores": "suppliers",
        "Brindes": "products",
        "Soluções": "activation_solutions",
        "Locais": "venues",
        "Importações": "imports",
    }
    result = {}

    for label, table in tables.items():
        response = (
            client.table(table)
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        result[label] = int(response.count or 0)

    return result


KNOWLEDGE_ENTITY_TABLES = {
    "product": "products",
    "activation": "activation_solutions",
    "venue": "venues",
}


def fetch_enrichment_history(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 20,
) -> pd.DataFrame:
    response = (
        client.table("knowledge_enrichment_events")
        .select(
            "id,entity_type,entity_id,import_id,"
            "source_file,source_page,match_method,strategy,"
            "fields_filled,fields_updated,fields_merged,"
            "conflict_fields,conflicts,created_at"
        )
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def fetch_knowledge_item(
    client: Client,
    *,
    entity_type: str,
    entity_id: str,
) -> dict[str, Any]:
    table = KNOWLEDGE_ENTITY_TABLES.get(entity_type)

    if not table:
        raise ValueError(
            f"Tipo de item não suportado: {entity_type}"
        )

    response = (
        client.table(table)
        .select("*")
        .eq("id", entity_id)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else {}


def fetch_recommendation_candidates(
    client: Client,
    *,
    limit: int = 2000,
    include_archived: bool = False,
) -> pd.DataFrame:
    response = (
        client.table("recommendation_candidates")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    frame = pd.DataFrame(response.data or [])

    if frame.empty:
        return frame

    try:
        custom_taxonomy_aliases = (
            fetch_custom_taxonomy_aliases(
                client
            )
        )
    except Exception:
        custom_taxonomy_aliases = []

    annotations = frame.apply(
        lambda row: annotate_candidate_taxonomy(
            row.to_dict(),
            custom_taxonomy_aliases,
        ),
        axis=1,
    )

    frame["category_nave"] = annotations.apply(
        lambda item: item.get(
            "category_nave"
        )
    )
    frame["taxonomy_terms"] = annotations.apply(
        lambda item: item.get(
            "taxonomy_terms",
            [],
        )
    )
    frame["taxonomy_search_text"] = (
        annotations.apply(
            lambda item: item.get(
                "taxonomy_search_text",
                "",
            )
        )
    )

    keys = [
        (
            str(row.get("item_type")),
            str(row.get("item_id")),
        )
        for _, row in frame.iterrows()
    ]

    try:
        states = fetch_curation_states(
            client,
            keys,
        )
    except Exception:
        states = {}

    frame["validation_status"] = frame.apply(
        lambda row: states.get(
            (
                str(row.get("item_type")),
                str(row.get("item_id")),
            ),
            {},
        ).get(
            "validation_status",
            "not_reviewed",
        ),
        axis=1,
    )

    frame["is_archived"] = frame.apply(
        lambda row: bool(
            states.get(
                (
                    str(row.get("item_type")),
                    str(row.get("item_id")),
                ),
                {},
            ).get("is_archived", False)
        ),
        axis=1,
    )

    frame["reviewed_at"] = frame.apply(
        lambda row: states.get(
            (
                str(row.get("item_type")),
                str(row.get("item_id")),
            ),
            {},
        ).get("reviewed_at"),
        axis=1,
    )

    if not include_archived:
        frame = frame[
            ~frame["is_archived"]
        ]

    return frame.reset_index(drop=True)



def _project_payload_from_brief(brief: dict) -> dict:
    agency = brief.get("agency_context") or {}
    financial = brief.get("financial_context") or {}

    return {
        "project_name": _json_safe(brief.get("project_name")),
        "normalized_name": normalize_name(brief.get("project_name")),
        "client_brand": _json_safe(brief.get("client_brand")),
        "event_name": _json_safe(brief.get("event_name")),
        "briefing_profile": _json_safe(
            brief.get("briefing_profile")
        ),
        "profile_reason": _json_safe(
            brief.get("profile_reason")
        ),
        "agency_job_code": _json_safe(agency.get("job_code")),
        "agency_account_manager": _json_safe(
            agency.get("account_manager")
        ),
        "client_contacts": agency.get("client_contacts") or [],
        "job_folder": _json_safe(agency.get("job_folder")),
        "competition_status": _json_safe(
            agency.get("competition_status")
        ),
        "competitors": agency.get("competitors") or [],
        "campaign_types": agency.get("campaign_types") or [],
        "agency_services": agency.get("agency_services") or [],
        "production_responsibility": (
            agency.get("production_responsibility") or []
        ),
        "budget_status": _json_safe(
            financial.get("budget_status")
        ),
        "budget_currency": _json_safe(
            financial.get("currency")
        ),
        "budget_scope": _json_safe(
            financial.get("budget_scope")
        ),
        "payment_terms": _json_safe(
            financial.get("payment_terms")
        ),
        "key_message": _json_safe(brief.get("key_message")),
        "expected_result": _json_safe(
            brief.get("expected_result")
        ),
        "event_format": _json_safe(brief.get("event_format")),
        "agency_context": _json_safe(agency),
        "financial_context": _json_safe(financial),
        "objective": _json_safe(brief.get("objective")),
        "audience_profile": _json_safe(brief.get("audience_profile")),
        "audience_quantity": _json_safe(
            brief.get("audience_quantity")
        ),
        "budget_total_brl": _json_safe(
            brief.get("budget_total_brl")
        ),
        "budget_unit_brl": _json_safe(
            brief.get("budget_unit_brl")
        ),
        "location_city": _json_safe(brief.get("location_city")),
        "location_state": _json_safe(brief.get("location_state")),
        "event_date": _iso_date_or_none(brief.get("event_date")),
        "desired_delivery_date": _iso_date_or_none(
            brief.get("desired_delivery_date")
        ),
        "available_days": _json_safe(brief.get("available_days")),
        "desired_attributes": brief.get("desired_attributes") or [],
        "restrictions": brief.get("restrictions") or [],
        "status": "em recomendação",
        "raw_data": _json_safe(brief),
    }


def ensure_project_for_recommendation(
    client: Client,
    brief: dict,
) -> str:
    project_name = (
        str(brief.get("project_name") or "").strip()
        or "Projeto sem nome"
    )
    normalized = normalize_name(project_name)

    lookup = (
        client.table("projects")
        .select("id")
        .eq("normalized_name", normalized)
        .order("created_at")
        .limit(1)
        .execute()
    )

    payload = _project_payload_from_brief(brief)
    payload["project_name"] = project_name
    payload["normalized_name"] = normalized

    if lookup.data:
        project_id = lookup.data[0]["id"]
        client.table("projects").update(payload).eq(
            "id", project_id
        ).execute()
        return project_id

    response = (
        client.table("projects")
        .insert(payload)
        .execute()
    )
    return response.data[0]["id"]


def _latest_project_version(
    client: Client,
    project_id: str,
) -> dict | None:
    response = (
        client.table("recommendation_queries")
        .select("id,version_number")
        .eq("project_id", project_id)
        .order("version_number", desc=True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None



def _adaptive_rows(
    *,
    project_id: str,
    query_id: str,
    brief: dict,
) -> dict[str, list[dict]]:
    rows = {
        "project_products": [],
        "project_deliverables": [],
        "project_metrics": [],
        "project_executions": [],
        "project_references": [],
    }

    for item in brief.get("products_or_brands") or []:
        if not item.get("name"):
            continue
        rows["project_products"].append(
            {
                "project_id": project_id,
                "query_id": query_id,
                "name": item.get("name"),
                "brand": _json_safe(item.get("brand")),
                "role": _json_safe(item.get("role")),
                "execution_names": (
                    item.get("execution_names") or []
                ),
                "notes": _json_safe(item.get("notes")),
            }
        )

    for item in brief.get("deliverables") or []:
        if not item.get("name"):
            continue
        rows["project_deliverables"].append(
            {
                "project_id": project_id,
                "query_id": query_id,
                "name": item.get("name"),
                "category": _json_safe(item.get("category")),
                "quantity": _json_safe(item.get("quantity")),
                "unit": _json_safe(item.get("unit")),
                "required": bool(
                    item.get("required", True)
                ),
                "responsible": _json_safe(
                    item.get("responsible")
                ),
                "execution_names": (
                    item.get("execution_names") or []
                ),
                "notes": _json_safe(item.get("notes")),
            }
        )

    for item in brief.get("success_metrics") or []:
        if not item.get("name"):
            continue
        rows["project_metrics"].append(
            {
                "project_id": project_id,
                "query_id": query_id,
                "name": item.get("name"),
                "target": _json_safe(item.get("target")),
                "unit": _json_safe(item.get("unit")),
                "status": _json_safe(item.get("status")),
                "execution_names": (
                    item.get("execution_names") or []
                ),
                "notes": _json_safe(item.get("notes")),
            }
        )

    for item in brief.get("executions") or []:
        if not item.get("name"):
            continue
        rows["project_executions"].append(
            {
                "project_id": project_id,
                "query_id": query_id,
                "name": item.get("name"),
                "city": _json_safe(item.get("city")),
                "state": _json_safe(item.get("state")),
                "venue": _json_safe(item.get("venue")),
                "institution": _json_safe(
                    item.get("institution")
                ),
                "status": _json_safe(item.get("status")),
                "priority": _json_safe(item.get("priority")),
                "event_date": _iso_date_or_none(
                    item.get("event_date")
                ),
                "product_name": _json_safe(
                    item.get("product_name")
                ),
                "audience_quantity": _json_safe(
                    item.get("audience_quantity")
                ),
                "budget_amount": _json_safe(
                    item.get("budget_amount")
                ),
                "currency": _json_safe(item.get("currency")),
                "event_format": _json_safe(
                    item.get("event_format")
                ),
                "notes": _json_safe(item.get("notes")),
            }
        )

    for item in brief.get("related_references") or []:
        if not item.get("title"):
            continue
        rows["project_references"].append(
            {
                "project_id": project_id,
                "query_id": query_id,
                "title": item.get("title"),
                "reference_type": _json_safe(
                    item.get("reference_type")
                ),
                "status": _json_safe(item.get("status")),
                "url_or_location": _json_safe(
                    item.get("url_or_location")
                ),
                "notes": _json_safe(item.get("notes")),
            }
        )

    return rows


def _save_adaptive_rows(
    client: Client,
    *,
    project_id: str,
    query_id: str,
    brief: dict,
) -> dict[str, int]:
    grouped = _adaptive_rows(
        project_id=project_id,
        query_id=query_id,
        brief=brief,
    )
    counts = {}

    for table, rows in grouped.items():
        if rows:
            client.table(table).insert(rows).execute()
        counts[table] = len(rows)

    return counts


def save_recommendation(
    client: Client,
    *,
    brief: dict,
    briefing_text: str,
    results_df: pd.DataFrame,
    diagnostic: dict | None = None,
    source_files: list[str] | None = None,
    version_notes: str | None = None,
    execution_results: dict[str, pd.DataFrame] | None = None,
    execution_briefs: dict[str, dict] | None = None,
) -> dict:
    project_id = ensure_project_for_recommendation(
        client,
        brief,
    )
    latest = _latest_project_version(client, project_id)

    version_number = (
        int(latest.get("version_number") or 0) + 1
        if latest
        else 1
    )
    parent_query_id = latest.get("id") if latest else None

    query_payload = {
        "project_id": project_id,
        "parent_query_id": parent_query_id,
        "version_number": version_number,
        "query_label": f"Versão {version_number}",
        "version_notes": _json_safe(version_notes),
        "project_name": _json_safe(brief.get("project_name")),
        "briefing_profile": _json_safe(
            brief.get("briefing_profile")
        ),
        "adaptive_snapshot": _json_safe(
            {
                "agency_context": brief.get("agency_context") or {},
                "financial_context": (
                    brief.get("financial_context") or {}
                ),
                "products_or_brands": (
                    brief.get("products_or_brands") or []
                ),
                "deliverables": brief.get("deliverables") or [],
                "success_metrics": (
                    brief.get("success_metrics") or []
                ),
                "executions": brief.get("executions") or [],
                "related_references": (
                    brief.get("related_references") or []
                ),
                "agenda_items": brief.get("agenda_items") or [],
                "operational_requirements": (
                    brief.get("operational_requirements") or []
                ),
                "mandatory_requirements": (
                    brief.get("mandatory_requirements") or []
                ),
            }
        ),
        "briefing_text": briefing_text,
        "objective": _json_safe(brief.get("objective")),
        "audience_profile": _json_safe(
            brief.get("audience_profile")
        ),
        "audience_quantity": _json_safe(
            brief.get("audience_quantity")
        ),
        "budget_total_brl": _json_safe(
            brief.get("budget_total_brl")
        ),
        "budget_unit_brl": _json_safe(
            brief.get("budget_unit_brl")
        ),
        "location_city": _json_safe(
            brief.get("location_city")
        ),
        "location_state": _json_safe(
            brief.get("location_state")
        ),
        "event_date": _iso_date_or_none(
            brief.get("event_date")
        ),
        "available_days": _json_safe(
            brief.get("available_days")
        ),
        "desired_types": brief.get("desired_types") or [],
        "desired_attributes": (
            brief.get("desired_attributes") or []
        ),
        "restrictions": brief.get("restrictions") or [],
        "keywords": brief.get("keywords") or [],
        "parsed_brief": _json_safe(brief),
        "readiness_status": _json_safe(
            (diagnostic or {}).get("readiness_status")
        ),
        "completeness_score": _json_safe(
            (diagnostic or {}).get("completeness_score")
        ),
        "diagnostic_snapshot": _json_safe(diagnostic or {}),
        "source_files": _json_safe(
            source_files
            or brief.get("source_files")
            or []
        ),
        "status": "gerada",
    }

    query_response = (
        client.table("recommendation_queries")
        .insert(query_payload)
        .execute()
    )
    query_id = query_response.data[0]["id"]

    adaptive_counts = _save_adaptive_rows(
        client,
        project_id=project_id,
        query_id=query_id,
        brief=brief,
    )

    result_rows = []
    for row in dataframe_records(results_df):
        result_rows.append(
            {
                "query_id": query_id,
                "item_type": row.get("item_type"),
                "item_id": row.get("item_id"),
                "rank": int(row.get("rank") or 0),
                "total_score": row.get("total_score"),
                "relevance_score": row.get("relevance_score"),
                "budget_score": row.get("budget_score"),
                "quantity_score": row.get("quantity_score"),
                "time_score": row.get("time_score"),
                "location_score": row.get("location_score"),
                "estimated_total": row.get("estimated_total"),
                "logistics_estimate": row.get(
                    "logistics_estimate"
                ),
                "coverage_status": row.get("coverage_status"),
                "reason": row.get("reason"),
                "warnings": row.get("warnings") or [],
                "snapshot": row,
            }
        )

    if result_rows:
        client.table("recommendation_results").insert(
            result_rows
        ).execute()

    execution_rows = []

    for execution_name, frame in (
        execution_results or {}
    ).items():
        execution_brief = (
            execution_briefs or {}
        ).get(execution_name, {})
        execution_snapshot = (
            execution_brief.get("active_execution")
            or {"name": execution_name}
        )

        for row in dataframe_records(frame):
            execution_rows.append(
                {
                    "query_id": query_id,
                    "execution_name": execution_name,
                    "execution_snapshot": _json_safe(
                        execution_snapshot
                    ),
                    "item_type": row.get("item_type"),
                    "item_id": row.get("item_id"),
                    "rank": int(row.get("rank") or 0),
                    "total_score": row.get("total_score"),
                    "relevance_score": row.get(
                        "relevance_score"
                    ),
                    "budget_score": row.get("budget_score"),
                    "quantity_score": row.get(
                        "quantity_score"
                    ),
                    "time_score": row.get("time_score"),
                    "location_score": row.get(
                        "location_score"
                    ),
                    "estimated_total": row.get(
                        "estimated_total"
                    ),
                    "logistics_estimate": row.get(
                        "logistics_estimate"
                    ),
                    "coverage_status": row.get(
                        "coverage_status"
                    ),
                    "reason": row.get("reason"),
                    "warnings": row.get("warnings") or [],
                    "snapshot": row,
                }
            )

    if execution_rows:
        client.table(
            "execution_recommendation_results"
        ).insert(execution_rows).execute()

    return {
        "query_id": query_id,
        "project_id": project_id,
        "version_number": version_number,
        "results_saved": len(result_rows),
        "execution_results_saved": len(execution_rows),
        "execution_scopes_saved": len(
            execution_results or {}
        ),
        "adaptive_counts": adaptive_counts,
    }


def fetch_project_history_overview(
    client: Client,
    *,
    limit: int = 500,
) -> pd.DataFrame:
    response = (
        client.table("project_history_overview")
        .select("*")
        .order("latest_activity", desc=True)
        .limit(limit)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def fetch_recommendation_history(
    client: Client,
    *,
    project_id: str | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    query = (
        client.table("recommendation_history_summary")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if project_id:
        query = query.eq("project_id", project_id)
    return pd.DataFrame(query.execute().data or [])


def fetch_recommendation_query(
    client: Client,
    query_id: str,
) -> dict | None:
    response = (
        client.table("recommendation_queries")
        .select("*")
        .eq("id", query_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_recommendation_results(
    client: Client,
    query_id: str,
) -> pd.DataFrame:
    response = (
        client.table("recommendation_results")
        .select("*")
        .eq("query_id", query_id)
        .order("rank")
        .execute()
    )
    return pd.DataFrame(response.data or [])



def fetch_execution_recommendation_results(
    client: Client,
    query_id: str,
    *,
    execution_name: str | None = None,
) -> pd.DataFrame:
    query = (
        client.table("execution_recommendation_results")
        .select("*")
        .eq("query_id", query_id)
        .order("execution_name")
        .order("rank")
    )
    if execution_name:
        query = query.eq("execution_name", execution_name)
    return pd.DataFrame(query.execute().data or [])


def fetch_execution_recommendation_summary(
    client: Client,
    *,
    query_id: str | None = None,
    project_id: str | None = None,
) -> pd.DataFrame:
    query = (
        client.table("execution_recommendation_summary")
        .select("*")
        .order("version_number", desc=True)
        .order("execution_name")
    )
    if query_id:
        query = query.eq("query_id", query_id)
    if project_id:
        query = query.eq("project_id", project_id)
    return pd.DataFrame(query.execute().data or [])


def fetch_recommendation_feedback(
    client: Client,
    query_id: str,
) -> pd.DataFrame:
    response = (
        client.table("recommendation_feedback")
        .select("*")
        .eq("query_id", query_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def save_recommendation_feedback(
    client: Client,
    *,
    query_id: str,
    result_id: str | None,
    item_type: str,
    item_id: str,
    decision: str,
    reason: str | None = None,
    notes: str | None = None,
) -> dict:
    payload = {
        "query_id": query_id,
        "result_id": result_id,
        "item_type": item_type,
        "item_id": item_id,
        "decision": decision,
        "reason": _json_safe(reason),
        "notes": _json_safe(notes),
    }

    response = (
        client.table("recommendation_feedback")
        .upsert(
            payload,
            on_conflict="query_id,item_type,item_id",
        )
        .execute()
    )
    return response.data[0] if response.data else payload
