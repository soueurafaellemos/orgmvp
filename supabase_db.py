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

    response = (
        client.table("suppliers")
        .upsert(payload, on_conflict="normalized_name")
        .execute()
    )

    if response.data:
        return response.data[0]["id"]

    lookup = (
        client.table("suppliers")
        .select("id")
        .eq("normalized_name", normalized)
        .limit(1)
        .execute()
    )
    return lookup.data[0]["id"] if lookup.data else None


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
        file_payload = {
            "import_id": import_id,
            "file_name": doc.name,
            "mime_type": doc.mime_type,
            "page_count": _page_count(doc),
            "sha256": hashlib.sha256(doc.data).hexdigest(),
        }
        file_response = (
            client.table("source_files")
            .insert(file_payload)
            .execute()
        )
        if file_response.data:
            file_map[doc.name] = file_response.data[0]["id"]

    return import_id, file_map


def _existing_product(
    client: Client,
    *,
    supplier_id: str | None,
    sku: str | None,
    name: str,
) -> bool:
    query = client.table("products").select("id").limit(1)

    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    else:
        query = query.is_("supplier_id", "null")

    if sku and str(sku).strip():
        query = query.eq("sku", str(sku).strip())
    else:
        query = query.eq("name", name)

    return bool(query.execute().data)


def _existing_activation(
    client: Client,
    *,
    supplier_id: str | None,
    name: str,
    project_name: str | None,
) -> bool:
    query = (
        client.table("activation_solutions")
        .select("id")
        .eq("name", name)
        .limit(1)
    )
    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    else:
        query = query.is_("supplier_id", "null")
    if project_name:
        query = query.eq("project_name", project_name)
    return bool(query.execute().data)


def _existing_venue(
    client: Client,
    *,
    operator_id: str | None,
    name: str,
    city: str | None,
) -> bool:
    query = (
        client.table("venues")
        .select("id")
        .eq("name", name)
        .limit(1)
    )
    if operator_id:
        query = query.eq("operator_id", operator_id)
    else:
        query = query.is_("operator_id", "null")
    if city:
        query = query.eq("city", city)
    return bool(query.execute().data)


def save_catalog(
    client: Client,
    *,
    products_df: pd.DataFrame,
    suppliers_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    alerts_df: pd.DataFrame,
    classification: dict | None,
    source_documents: list[InputDocument],
    skip_duplicates: bool = True,
) -> dict:
    products = dataframe_records(products_df)
    suppliers = dataframe_records(suppliers_df)
    supplier_map, supplier_count = _supplier_maps(client, suppliers)

    first_supplier_id = next(iter(supplier_map.values()), None)
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

    inserted = 0
    duplicates = 0

    for raw in products:
        supplier_id = _supplier_id_for_record(raw, supplier_map)
        if skip_duplicates and _existing_product(
            client,
            supplier_id=supplier_id,
            sku=raw.get("sku"),
            name=raw.get("name") or "Sem nome",
        ):
            duplicates += 1
            continue

        payload = _prepare_record(raw, PRODUCT_COLUMNS)
        payload["supplier_id"] = supplier_id
        payload["import_id"] = import_id
        payload["source_file_id"] = file_map.get(
            str(raw.get("source_file") or "")
        )
        client.table("products").insert(payload).execute()
        inserted += 1

    client.table("imports").update(
        {
            "status": "importado",
            "imported_records": inserted,
        }
    ).eq("id", import_id).execute()

    return {
        "import_id": import_id,
        "suppliers_saved": supplier_count,
        "records_inserted": inserted,
        "duplicates_skipped": duplicates,
        "costs_inserted": 0,
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
    skip_duplicates: bool = True,
) -> dict:
    solutions = dataframe_records(solutions_df)
    costs = dataframe_records(costs_df)
    suppliers = dataframe_records(suppliers_df)
    supplier_map, supplier_count = _supplier_maps(client, suppliers)

    first_supplier_id = next(iter(supplier_map.values()), None)
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

    inserted = 0
    duplicates = 0
    costs_inserted = 0
    local_to_database: dict[str, str] = {}

    for raw in solutions:
        supplier_id = _supplier_id_for_record(raw, supplier_map)
        if skip_duplicates and _existing_activation(
            client,
            supplier_id=supplier_id,
            name=raw.get("name") or "Sem nome",
            project_name=raw.get("project_name"),
        ):
            duplicates += 1
            continue

        payload = _prepare_record(raw, ACTIVATION_COLUMNS)
        payload["supplier_id"] = supplier_id
        payload["import_id"] = import_id
        payload["source_file_id"] = file_map.get(
            str(raw.get("source_file") or "")
        )

        response = (
            client.table("activation_solutions")
            .insert(payload)
            .execute()
        )
        if response.data:
            inserted += 1
            local_id = str(raw.get("solution_id") or "")
            if local_id:
                local_to_database[local_id] = response.data[0]["id"]

    for raw_cost in costs:
        database_solution_id = local_to_database.get(
            str(raw_cost.get("solution_id") or "")
        )
        if not database_solution_id:
            continue

        payload = {
            "solution_id": database_solution_id,
            "description": raw_cost.get("description") or "Custo adicional",
            "amount": _json_safe(raw_cost.get("amount")),
            "currency": raw_cost.get("currency") or "Não informado",
            "treatment": raw_cost.get("treatment") or "Não informado",
            "notes": _json_safe(raw_cost.get("notes")),
            "source_page": _json_safe(raw_cost.get("source_page")),
            "confidence": _json_safe(raw_cost.get("confidence")),
            "raw_data": _json_safe(raw_cost),
        }
        client.table("activation_costs").insert(payload).execute()
        costs_inserted += 1

    client.table("imports").update(
        {
            "status": "importado",
            "imported_records": inserted,
        }
    ).eq("id", import_id).execute()

    return {
        "import_id": import_id,
        "suppliers_saved": supplier_count,
        "records_inserted": inserted,
        "duplicates_skipped": duplicates,
        "costs_inserted": costs_inserted,
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
    skip_duplicates: bool = True,
) -> dict:
    venues = dataframe_records(venues_df)
    contacts = dataframe_records(contacts_df)
    supplier_map, supplier_count = _supplier_maps(client, contacts)

    first_supplier_id = next(iter(supplier_map.values()), None)
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

    inserted = 0
    duplicates = 0

    for raw in venues:
        operator_id = _supplier_id_for_record(raw, supplier_map)
        if skip_duplicates and _existing_venue(
            client,
            operator_id=operator_id,
            name=raw.get("name") or "Sem nome",
            city=raw.get("city"),
        ):
            duplicates += 1
            continue

        payload = _prepare_record(raw, VENUE_COLUMNS)
        payload["operator_id"] = operator_id
        payload["import_id"] = import_id
        payload["source_file_id"] = file_map.get(
            str(raw.get("source_file") or "")
        )
        client.table("venues").insert(payload).execute()
        inserted += 1

    client.table("imports").update(
        {
            "status": "importado",
            "imported_records": inserted,
        }
    ).eq("id", import_id).execute()

    return {
        "import_id": import_id,
        "suppliers_saved": supplier_count,
        "records_inserted": inserted,
        "duplicates_skipped": duplicates,
        "costs_inserted": 0,
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


def fetch_recommendation_candidates(
    client: Client,
    *,
    limit: int = 2000,
) -> pd.DataFrame:
    response = (
        client.table("recommendation_candidates")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def save_recommendation(
    client: Client,
    *,
    brief: dict,
    briefing_text: str,
    results_df: pd.DataFrame,
) -> dict:
    query_payload = {
        "project_name": _json_safe(brief.get("project_name")),
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
        "status": "gerada",
    }

    query_response = (
        client.table("recommendation_queries")
        .insert(query_payload)
        .execute()
    )
    query_id = query_response.data[0]["id"]

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
                "reason": row.get("reason"),
                "warnings": row.get("warnings") or [],
                "snapshot": row,
            }
        )

    if result_rows:
        client.table("recommendation_results").insert(
            result_rows
        ).execute()

    return {
        "query_id": query_id,
        "results_saved": len(result_rows),
    }
