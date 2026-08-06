from __future__ import annotations

import io
import json

import pandas as pd

from models import (
    ActivationBatch,
    CatalogBatch,
    DocumentClassification,
    ProjectBriefing,
    VenueBatch,
)


def _missing(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


def _join(values) -> str:
    return " | ".join(values or [])


def _serialize_visual_crop(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _prefix(currency) -> str:
    return {
        "BRL": "R$ ",
        "USD": "US$ ",
        "EUR": "€ ",
    }.get(str(currency or "").upper(), "")


def format_pt_br_number(
    value,
    *,
    decimals: int = 2,
    prefix: str = "",
) -> str:
    if _missing(value):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{number:,.{decimals}f}"
    formatted = (
        formatted.replace(",", "__M__")
        .replace(".", ",")
        .replace("__M__", ".")
    )
    return prefix + formatted


def parse_pt_br_number(value) -> float | None:
    if _missing(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = (
        str(value)
        .replace("R$", "")
        .replace("US$", "")
        .replace("€", "")
        .replace(" ", "")
        .strip()
    )
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        pieces = text.split(".")
        if len(pieces) > 2 or (
            len(pieces) == 2 and len(pieces[1]) == 3
        ):
            text = "".join(pieces)
    try:
        return float(text)
    except ValueError:
        return None


def parse_pt_br_integer(value) -> int | None:
    parsed = parse_pt_br_number(value)
    return None if parsed is None else int(round(parsed))


def classification_dataframe(
    classification: DocumentClassification,
) -> pd.DataFrame:
    rows = []
    for key, value in classification.model_dump().items():
        if isinstance(value, list):
            value = _join(value)
        rows.append({"campo": key, "valor": value})
    return pd.DataFrame(rows)


def _contact_row(contact, fallback_name=None) -> dict:
    data = contact.model_dump() if contact else {}
    data["supplier_name"] = (
        data.get("supplier_name") or fallback_name
    )
    data["confidence"] = float(data.get("confidence") or 0.0)

    for field in (
        "website_url",
        "contact_name",
        "contact_role",
        "email",
        "phone",
        "whatsapp",
        "instagram_url",
        "linkedin_url",
        "address",
        "base_city",
        "base_state",
        "base_country",
        "serves_nationally",
        "has_local_teams",
        "travel_pricing_mode",
        "default_travel_cost_brl",
        "freight_pricing_mode",
        "default_freight_cost_brl",
        "travel_lead_days",
        "equipment_transport_required",
        "accommodation_required",
        "coverage_notes",
        "notes",
    ):
        data.setdefault(field, None)

    for field in (
        "served_states",
        "served_cities",
        "local_team_locations",
    ):
        value = data.get(field) or []
        if isinstance(value, (list, tuple)):
            data[field] = " | ".join(
                str(item).strip()
                for item in value
                if str(item).strip()
            )
        else:
            data[field] = value

    has_contact = any(
        data.get(field)
        for field in (
            "website_url",
            "contact_name",
            "email",
            "phone",
            "whatsapp",
            "instagram_url",
            "linkedin_url",
        )
    )
    data["contact_alert"] = (
        "OK"
        if has_contact
        else "ATENÇÃO: contato não encontrado no material"
    )
    return data


def _dedupe_suppliers(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "supplier_name",
                "website_url",
                "contact_name",
                "contact_role",
                "email",
                "phone",
                "whatsapp",
                "instagram_url",
                "linkedin_url",
                "address",
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
                "notes",
                "confidence",
                "contact_alert",
            ]
        )

    df = pd.DataFrame(rows)

    if "supplier_name" not in df.columns:
        df["supplier_name"] = None
    if "confidence" not in df.columns:
        df["confidence"] = 0.0

    df["confidence"] = pd.to_numeric(
        df["confidence"],
        errors="coerce",
    ).fillna(0.0)

    return (
        df.sort_values(
            by=["confidence"],
            ascending=False,
            na_position="last",
        )
        .drop_duplicates(
            subset=["supplier_name"],
            keep="first",
        )
        .reset_index(drop=True)
    )


def merge_catalog_batches(batches):
    products, rules, alerts, suppliers = [], [], [], []

    for batch_index, batch in enumerate(batches, 1):
        suppliers.append(
            _contact_row(batch.supplier_contact, batch.supplier_name)
        )
        contact = suppliers[-1]

        for product in batch.products:
            row = product.model_dump()
            row["visual_crop"] = _serialize_visual_crop(
                row.get("visual_crop")
            )
            row["supplier_name"] = (
                product.supplier_name or batch.supplier_name
            )
            row["supplier_website"] = contact.get("website_url")
            row["supplier_email"] = contact.get("email")
            row["supplier_phone"] = contact.get("phone")
            row["supplier_whatsapp"] = contact.get("whatsapp")
            row["catalog_name"] = batch.catalog_name
            row["document_year"] = batch.document_year

            missing = list(row.get("missing_fields") or [])
            quality = []
            if _missing(row["supplier_name"]):
                row["supplier_alert"] = (
                    "ALERTA: fornecedor não identificado"
                )
                quality.append("Fornecedor não identificado")
            else:
                row["supplier_alert"] = "OK"

            has_price = any(
                row.get(field) is not None
                for field in ("unit_price", "price_min", "price_max")
            )
            if row.get("price_status") == "Sob consulta":
                row["price_alert"] = "ATENÇÃO: preço sob consulta"
            elif not has_price:
                row["price_alert"] = "ALERTA: preço não informado"
                if "unit_price" not in missing:
                    missing.append("unit_price")
                quality.append("Preço não informado")
            else:
                row["price_alert"] = "OK"

            row["image_reference"] = (
                f"{row.get('source_file')} — página "
                f"{row.get('source_page')}"
                if row.get("source_page")
                else row.get("source_file")
            )
            row["tags"] = _join(row.get("tags"))
            row["missing_fields"] = _join(missing)
            row["data_quality_alerts"] = _join(quality)
            products.append(row)

        for rule in batch.global_rules:
            rule_row = rule.model_dump()
            rule_row["batch"] = batch_index
            rules.append(rule_row)

        for warning in batch.warnings:
            alerts.append(
                {
                    "severity": "Informativo",
                    "record_name": None,
                    "message": warning,
                }
            )

    products_df = pd.DataFrame(products)
    if not products_df.empty:
        products_df["_dedupe"] = products_df.apply(
            lambda row: (
                f"sku::{str(row.get('sku')).strip().lower()}"
                if not _missing(row.get("sku"))
                else (
                    f"name::{str(row.get('name')).strip().lower()}::"
                    f"{row.get('source_page')}"
                )
            ),
            axis=1,
        )
        products_df = (
            products_df.sort_values(
                "confidence",
                ascending=False,
                na_position="last",
            )
            .drop_duplicates("_dedupe")
            .drop(columns="_dedupe")
            .reset_index(drop=True)
        )

    return (
        products_df,
        pd.DataFrame(rules),
        pd.DataFrame(alerts),
        _dedupe_suppliers(suppliers),
    )


def merge_activation_batches(batches):
    solutions, costs, rules, alerts, suppliers = [], [], [], [], []

    for batch_index, batch in enumerate(batches, 1):
        suppliers.append(
            _contact_row(batch.supplier_contact, batch.supplier_name)
        )
        contact = suppliers[-1]

        for solution_index, solution in enumerate(batch.solutions, 1):
            row = solution.model_dump()
            row["visual_crop"] = _serialize_visual_crop(
                row.get("visual_crop")
            )
            row["supplier_name"] = (
                solution.supplier_name or batch.supplier_name
            )
            row["supplier_website"] = contact.get("website_url")
            row["supplier_email"] = contact.get("email")
            row["supplier_phone"] = contact.get("phone")
            row["supplier_whatsapp"] = contact.get("whatsapp")
            row["proposal_name"] = batch.proposal_name
            row["client_brand"] = (
                solution.client_brand or batch.client_brand
            )
            row["project_name"] = (
                solution.project_name or batch.project_name
            )
            row["document_year"] = batch.document_year
            solution_id = f"{batch_index}-{solution_index}"
            row["solution_id"] = solution_id

            required_additional = 0.0
            summary = []
            for component in solution.additional_costs:
                component_row = component.model_dump()
                component_row["solution_id"] = solution_id
                component_row["solution_name"] = solution.name
                component_row["supplier_name"] = row["supplier_name"]
                costs.append(component_row)
                if (
                    component.amount is not None
                    and component.treatment == "Adicional obrigatório"
                ):
                    required_additional += float(component.amount)
                summary.append(
                    f"{component.description}: "
                    f"{format_pt_br_number(component.amount, prefix=_prefix(component.currency)) or 'sem valor'} "
                    f"[{component.treatment}]"
                )

            row["additional_costs_total"] = (
                required_additional or None
            )
            row["estimated_total"] = (
                float(solution.base_price) + required_additional
                if solution.base_price is not None
                else None
            )
            row["estimated_total_is_derived"] = (
                solution.base_price is not None
                and required_additional > 0
            )
            row["additional_costs_summary"] = _join(summary)
            row["included_items"] = _join(solution.included_items)
            row["excluded_items"] = _join(solution.excluded_items)
            row["infrastructure_requirements"] = _join(
                solution.infrastructure_requirements
            )
            row["tags"] = _join(solution.tags)
            row["image_reference"] = (
                f"{row.get('source_file')} — página "
                f"{row.get('source_page')}"
                if row.get("source_page")
                else row.get("source_file")
            )

            quality = []
            if _missing(row["supplier_name"]):
                row["supplier_alert"] = (
                    "ALERTA: fornecedor não identificado"
                )
                quality.append("Fornecedor não identificado")
            else:
                row["supplier_alert"] = "OK"

            if solution.price_status == "Sob consulta":
                row["price_alert"] = "ATENÇÃO: preço sob consulta"
            elif solution.base_price is None:
                row["price_alert"] = (
                    "ALERTA: valor-base não informado"
                )
                quality.append("Valor-base não informado")
            else:
                row["price_alert"] = "OK"

            if solution.lead_time_days is None:
                row["lead_time_alert"] = (
                    "ATENÇÃO: prazo não informado"
                )
                quality.append("Prazo não informado")
            else:
                row["lead_time_alert"] = "OK"

            row["missing_fields"] = _join(solution.missing_fields)
            row["data_quality_alerts"] = _join(quality)
            row.pop("additional_costs", None)
            solutions.append(row)

        for rule in batch.global_rules:
            rule_row = rule.model_dump()
            rule_row["batch"] = batch_index
            rules.append(rule_row)

        for warning in batch.warnings:
            alerts.append(
                {
                    "severity": "Informativo",
                    "record_name": None,
                    "message": warning,
                }
            )

    solutions_df = pd.DataFrame(solutions)
    if not solutions_df.empty:
        solutions_df = (
            solutions_df.sort_values(
                "confidence",
                ascending=False,
                na_position="last",
            )
            .drop_duplicates(
                ["supplier_name", "name", "source_page"],
                keep="first",
            )
            .reset_index(drop=True)
        )

    return (
        solutions_df,
        pd.DataFrame(costs),
        pd.DataFrame(rules),
        pd.DataFrame(alerts),
        _dedupe_suppliers(suppliers),
    )



def merge_venue_batches(batches):
    venues, rules, alerts, contacts = [], [], [], []

    for batch_index, batch in enumerate(batches, 1):
        contacts.append(
            _contact_row(batch.venue_contact, batch.operator_name)
        )
        contact = contacts[-1]

        for venue in batch.venues:
            row = venue.model_dump()
            row["visual_crop"] = _serialize_visual_crop(
                row.get("visual_crop")
            )
            row["operator_name"] = (
                venue.operator_name or batch.operator_name
            )
            row["contact_website"] = (
                venue.website_url or contact.get("website_url")
            )
            row["contact_name"] = contact.get("contact_name")
            row["contact_email"] = contact.get("email")
            row["contact_phone"] = contact.get("phone")
            row["contact_whatsapp"] = contact.get("whatsapp")
            row["document_name"] = batch.document_name
            row["document_year"] = batch.document_year

            row["rooms_or_areas"] = _join(venue.rooms_or_areas)
            row["infrastructure"] = _join(venue.infrastructure)
            row["included_items"] = _join(venue.included_items)
            row["excluded_items"] = _join(venue.excluded_items)
            row["restrictions"] = _join(venue.restrictions)
            row["tags"] = _join(venue.tags)
            row["missing_fields"] = _join(venue.missing_fields)

            row["image_reference"] = (
                f"{row.get('source_file')} — página "
                f"{row.get('source_page')}"
                if row.get("source_page")
                else row.get("source_file")
            )

            quality = []

            if _missing(row.get("address")) and (
                _missing(row.get("city"))
                or _missing(row.get("state"))
            ):
                row["location_alert"] = (
                    "ALERTA: localização não identificada"
                )
                quality.append("Localização não identificada")
            else:
                row["location_alert"] = "OK"

            has_capacity = any(
                row.get(field) is not None
                for field in (
                    "standing_capacity",
                    "seated_capacity",
                    "auditorium_capacity",
                )
            )
            if not has_capacity:
                row["capacity_alert"] = (
                    "ATENÇÃO: capacidade não informada"
                )
                quality.append("Capacidade não informada")
            else:
                row["capacity_alert"] = "OK"

            has_price = any(
                row.get(field) is not None
                for field in (
                    "base_price",
                    "price_min",
                    "price_max",
                )
            )
            if venue.price_status == "Sob consulta":
                row["price_alert"] = "ATENÇÃO: preço sob consulta"
            elif not has_price:
                row["price_alert"] = (
                    "ATENÇÃO: preço de locação não informado"
                )
                quality.append("Preço não informado")
            else:
                row["price_alert"] = "OK"

            row["data_quality_alerts"] = _join(quality)
            venues.append(row)

        for rule in batch.global_rules:
            rule_row = rule.model_dump()
            rule_row["batch"] = batch_index
            rules.append(rule_row)

        for warning in batch.warnings:
            alerts.append(
                {
                    "severity": "Informativo",
                    "record_name": None,
                    "message": warning,
                }
            )

    venues_df = pd.DataFrame(venues)
    if not venues_df.empty:
        venues_df = (
            venues_df.sort_values(
                "confidence",
                ascending=False,
                na_position="last",
            )
            .drop_duplicates(
                ["name", "city", "source_page"],
                keep="first",
            )
            .reset_index(drop=True)
        )

    return (
        venues_df,
        pd.DataFrame(rules),
        pd.DataFrame(alerts),
        _dedupe_suppliers(contacts),
    )


def prepare_venues_for_editor(df):
    editor = df.copy()

    for column in (
        "base_price",
        "price_min",
        "price_max",
    ):
        if column in editor.columns:
            editor[column + "_formatted"] = editor.apply(
                lambda row, col=column: format_pt_br_number(
                    row.get(col),
                    prefix=_prefix(row.get("currency")),
                ),
                axis=1,
            )

    for column in (
        "standing_capacity",
        "seated_capacity",
        "auditorium_capacity",
    ):
        if column in editor.columns:
            editor[column + "_formatted"] = editor[column].apply(
                lambda value: format_pt_br_number(
                    value,
                    decimals=0,
                )
            )

    for column in (
        "total_area_sqm",
        "indoor_area_sqm",
        "outdoor_area_sqm",
        "ceiling_height_m",
    ):
        if column in editor.columns:
            editor[column + "_formatted"] = editor[column].apply(
                lambda value: format_pt_br_number(
                    value,
                    decimals=2,
                )
            )

    raw_columns = [
        "base_price",
        "price_min",
        "price_max",
        "standing_capacity",
        "seated_capacity",
        "auditorium_capacity",
        "total_area_sqm",
        "indoor_area_sqm",
        "outdoor_area_sqm",
        "ceiling_height_m",
    ]
    return editor.drop(
        columns=[
            column
            for column in raw_columns
            if column in editor.columns
        ]
    )


def normalize_editor_venues(df):
    normalized = df.copy()

    for column in (
        "base_price",
        "price_min",
        "price_max",
        "total_area_sqm",
        "indoor_area_sqm",
        "outdoor_area_sqm",
        "ceiling_height_m",
    ):
        formatted = column + "_formatted"
        if formatted in normalized.columns:
            normalized[column] = normalized[formatted].apply(
                parse_pt_br_number
            )

    for column in (
        "standing_capacity",
        "seated_capacity",
        "auditorium_capacity",
    ):
        formatted = column + "_formatted"
        if formatted in normalized.columns:
            normalized[column] = normalized[formatted].apply(
                parse_pt_br_integer
            )

    return normalized.drop(
        columns=[
            column
            for column in normalized.columns
            if column.endswith("_formatted")
        ]
    )


def _classification_payload(classification):
    if classification is None:
        return None
    if isinstance(classification, dict):
        return classification
    if hasattr(classification, "model_dump"):
        return classification.model_dump()
    return classification


def venue_json_bytes(
    venues_df,
    rules_df,
    alerts_df,
    contacts_df,
    classification=None,
):
    payload = {
        "classification": _classification_payload(
            classification
        ),
        "destination_base": "Base de locais e espaços",
        "contacts": _records(contacts_df),
        "venues": _records(venues_df),
        "global_rules": _records(rules_df),
        "alerts": _records(alerts_df),
    }
    return json.dumps(
        _json_safe_value(payload),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")


def prepare_products_for_editor(df):
    editor = df.copy()
    for column in ("unit_price", "price_min", "price_max"):
        if column in editor.columns:
            editor[column + "_formatted"] = editor.apply(
                lambda row, col=column: format_pt_br_number(
                    row.get(col),
                    prefix=_prefix(row.get("currency")),
                ),
                axis=1,
            )
    for column in ("price_reference_qty", "min_order_qty"):
        if column in editor.columns:
            editor[column + "_formatted"] = editor[column].apply(
                lambda value: format_pt_br_number(value, decimals=0)
            )
    return editor.drop(
        columns=[
            col
            for col in (
                "unit_price",
                "price_min",
                "price_max",
                "price_reference_qty",
                "min_order_qty",
            )
            if col in editor.columns
        ]
    )


def normalize_editor_products(df):
    normalized = df.copy()
    for column in ("unit_price", "price_min", "price_max"):
        formatted = column + "_formatted"
        if formatted in normalized.columns:
            normalized[column] = normalized[formatted].apply(
                parse_pt_br_number
            )
    for column in ("price_reference_qty", "min_order_qty"):
        formatted = column + "_formatted"
        if formatted in normalized.columns:
            normalized[column] = normalized[formatted].apply(
                parse_pt_br_integer
            )
    return normalized.drop(
        columns=[
            col
            for col in normalized.columns
            if col.endswith("_formatted")
        ]
    )


def prepare_activations_for_editor(df):
    editor = df.copy()
    for column in (
        "base_price",
        "additional_costs_total",
        "estimated_total",
    ):
        if column in editor.columns:
            editor[column + "_formatted"] = editor.apply(
                lambda row, col=column: format_pt_br_number(
                    row.get(col),
                    prefix=_prefix(row.get("currency")),
                ),
                axis=1,
            )
    if "lead_time_days" in editor.columns:
        editor["lead_time_days_formatted"] = editor[
            "lead_time_days"
        ].apply(lambda value: format_pt_br_number(value, decimals=0))
    return editor.drop(
        columns=[
            col
            for col in (
                "base_price",
                "additional_costs_total",
                "estimated_total",
                "lead_time_days",
            )
            if col in editor.columns
        ]
    )


def normalize_editor_activations(df):
    normalized = df.copy()
    for column in (
        "base_price",
        "additional_costs_total",
        "estimated_total",
    ):
        formatted = column + "_formatted"
        if formatted in normalized.columns:
            normalized[column] = normalized[formatted].apply(
                parse_pt_br_number
            )
    if "lead_time_days_formatted" in normalized.columns:
        normalized["lead_time_days"] = normalized[
            "lead_time_days_formatted"
        ].apply(parse_pt_br_integer)
    return normalized.drop(
        columns=[
            col
            for col in normalized.columns
            if col.endswith("_formatted")
        ]
    )


def briefing_dataframe(briefing):
    rows = []
    for key, value in briefing.model_dump().items():
        if isinstance(value, list):
            value = _join(value)
        elif key in ("budget_total_brl", "budget_unit_brl"):
            value = format_pt_br_number(value, prefix="R$ ")
        elif key == "audience_quantity":
            value = format_pt_br_number(value, decimals=0)
        rows.append({"campo": key, "valor": value})
    return pd.DataFrame(rows)


def _drop_blank_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=(df.columns if df is not None else None))

    cleaned = df.copy()
    text_view = cleaned.fillna("").astype(str).apply(
        lambda column: column.str.strip()
    )
    return cleaned.loc[(text_view != "").any(axis=1)].reset_index(drop=True)


def _json_safe_value(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, dict):
        return {
            key: _json_safe_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]

    return value


def _records(df):
    cleaned = _drop_blank_rows(df)
    if cleaned.empty:
        return []

    records = cleaned.to_dict("records")
    return [
        {
            key: _json_safe_value(value)
            for key, value in record.items()
        }
        for record in records
    ]


def catalog_json_bytes(
    products_df,
    rules_df,
    alerts_df,
    suppliers_df,
    classification=None,
):
    payload = {
        "classification": _classification_payload(
            classification
        ),
        "destination_base": "Base de brindes",
        "suppliers": _records(suppliers_df),
        "products": _records(products_df),
        "global_rules": _records(rules_df),
        "alerts": _records(alerts_df),
    }
    return json.dumps(
        _json_safe_value(payload),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")


def activation_json_bytes(
    solutions_df,
    costs_df,
    rules_df,
    alerts_df,
    suppliers_df,
    classification=None,
):
    payload = {
        "classification": _classification_payload(
            classification
        ),
        "destination_base": "Base de soluções e ativações",
        "suppliers": _records(suppliers_df),
        "solutions": _records(solutions_df),
        "cost_components": _records(costs_df),
        "global_rules": _records(rules_df),
        "alerts": _records(alerts_df),
    }
    return json.dumps(
        _json_safe_value(payload),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")


def briefing_json_bytes(briefing, classification=None):
    payload = {
        "classification": _classification_payload(
            classification
        ),
        "destination_base": "Base de projetos e briefings",
        "briefing": briefing.model_dump(),
    }
    return json.dumps(
        _json_safe_value(payload),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")


def to_xlsx_bytes(sheets):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        header = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#E8E8E8",
                "border": 1,
                "text_wrap": True,
            }
        )
        cell = workbook.add_format(
            {
                "border": 1,
                "text_wrap": True,
                "valign": "top",
            }
        )
        alert = workbook.add_format(
            {
                "bg_color": "#FDE9E7",
                "font_color": "#B42318",
                "border": 1,
            }
        )

        for raw_name, df in sheets.items():
            name = raw_name[:31]
            safe = _drop_blank_rows(df)
            safe.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            ws.freeze_panes(1, 0)
            if len(safe.columns):
                ws.autofilter(
                    0,
                    0,
                    max(len(safe), 1),
                    len(safe.columns) - 1,
                )
            for index, column in enumerate(safe.columns):
                ws.write(0, index, column, header)
                values = (
                    safe[column].astype(str).tolist()
                    if not safe.empty
                    else []
                )
                width = min(
                    max(
                        [len(str(column))]
                        + [min(len(value), 60) for value in values]
                    )
                    + 2,
                    44,
                )
                ws.set_column(index, index, max(width, 12), cell)
                if (
                    not safe.empty
                    and "alert" in column.lower()
                ):
                    ws.conditional_format(
                        1,
                        index,
                        len(safe),
                        index,
                        {
                            "type": "text",
                            "criteria": "containing",
                            "value": "ALERTA",
                            "format": alert,
                        },
                    )
    return buffer.getvalue()
