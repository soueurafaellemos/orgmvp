from __future__ import annotations

import io
import json

import pandas as pd

from models import (
    ActivationBatch,
    CatalogBatch,
    DocumentClassification,
    ProjectBriefing,
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
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "supplier_name" not in df.columns:
        return df
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


def _records(df):
    if df.empty:
        return []
    return df.where(pd.notna(df), None).to_dict("records")


def catalog_json_bytes(
    products_df,
    rules_df,
    alerts_df,
    suppliers_df,
    classification=None,
):
    payload = {
        "classification": (
            classification.model_dump() if classification else None
        ),
        "destination_base": "Base de brindes",
        "suppliers": _records(suppliers_df),
        "products": _records(products_df),
        "global_rules": _records(rules_df),
        "alerts": _records(alerts_df),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
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
        "classification": (
            classification.model_dump() if classification else None
        ),
        "destination_base": "Base de soluções e ativações",
        "suppliers": _records(suppliers_df),
        "solutions": _records(solutions_df),
        "cost_components": _records(costs_df),
        "global_rules": _records(rules_df),
        "alerts": _records(alerts_df),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def briefing_json_bytes(briefing, classification=None):
    payload = {
        "classification": (
            classification.model_dump() if classification else None
        ),
        "destination_base": "Base de projetos e briefings",
        "briefing": briefing.model_dump(),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
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
            safe = df.copy()
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
