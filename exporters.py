from __future__ import annotations

import io
import json

import pandas as pd


from models import CatalogBatch, ProjectBriefing


MONEY_COLUMNS = ("unit_price", "price_min", "price_max")
QUANTITY_COLUMNS = ("price_reference_qty", "min_order_qty")

FORMATTED_COLUMN_LABELS = {
    "unit_price_formatted": "Valor unitário",
    "price_min_formatted": "Valor mínimo",
    "price_max_formatted": "Valor máximo",
    "price_reference_qty_formatted": "Qtd. de referência",
    "min_order_qty_formatted": "Pedido mínimo",
}


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


def _currency_prefix(currency: object) -> str:
    normalized = str(currency or "").strip().upper()
    return {
        "BRL": "R$ ",
        "USD": "US$ ",
        "EUR": "€ ",
    }.get(normalized, "")


def format_pt_br_number(
    value: object,
    *,
    decimals: int = 2,
    prefix: str = "",
) -> str:
    """Ex.: 32000 -> R$ 32.000,00."""
    if _is_missing(value):
        return ""

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)

    formatted = f"{numeric:,.{decimals}f}"
    formatted = (
        formatted.replace(",", "__THOUSANDS__")
        .replace(".", ",")
        .replace("__THOUSANDS__", ".")
    )
    return f"{prefix}{formatted}"


def parse_pt_br_number(value: object) -> float | None:
    """Aceita 32000, 32.000, 32.000,00, R$ 32.000,00 ou 35.5."""
    if _is_missing(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    text = (
        str(value)
        .strip()
        .replace("R$", "")
        .replace("US$", "")
        .replace("€", "")
        .replace(" ", "")
    )

    if not text:
        return None

    # Padrão brasileiro completo: 1.234,56
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        # Vírgula é decimal: 1234,56
        text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2:
            # 1.234.567
            text = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3:
            # 32.000 no padrão brasileiro.
            text = "".join(parts)
        # 35.5 permanece decimal.

    try:
        return float(text)
    except ValueError:
        return None


def parse_pt_br_integer(value: object) -> int | None:
    parsed = parse_pt_br_number(value)
    return None if parsed is None else int(round(parsed))


def prepare_products_for_editor(products_df: pd.DataFrame) -> pd.DataFrame:
    """Cria uma visão amigável, preservando os números na base técnica."""
    editor_df = products_df.copy()

    for column in MONEY_COLUMNS:
        formatted_column = f"{column}_formatted"
        editor_df[formatted_column] = editor_df.apply(
            lambda row, col=column: format_pt_br_number(
                row.get(col),
                decimals=2,
                prefix=_currency_prefix(row.get("currency")),
            ),
            axis=1,
        )

    for column in QUANTITY_COLUMNS:
        formatted_column = f"{column}_formatted"
        editor_df[formatted_column] = editor_df[column].apply(
            lambda value: format_pt_br_number(value, decimals=0)
        )

    editor_df = editor_df.drop(
        columns=[
            column
            for column in MONEY_COLUMNS + QUANTITY_COLUMNS
            if column in editor_df.columns
        ]
    )

    # Coloca os campos amigáveis junto das informações comerciais.
    preferred_order = [
        "source_file",
        "supplier_name",
        "supplier_alert",
        "catalog_name",
        "document_year",
        "source_page",
        "category",
        "sku",
        "name",
        "description",
        "unit_price_formatted",
        "price_min_formatted",
        "price_max_formatted",
        "currency",
        "price_status",
        "price_reference_qty_formatted",
        "price_notes",
        "price_alert",
        "capacity",
        "capacity_ml",
        "dimensions_raw",
        "material",
        "finish",
        "decoration",
        "origin",
        "development_status",
        "min_order_qty_formatted",
        "customizable",
        "licensing_notes",
        "tags",
        "confidence",
        "missing_fields",
        "data_quality_alerts",
        "evidence",
    ]
    existing = [column for column in preferred_order if column in editor_df.columns]
    remaining = [
        column for column in editor_df.columns if column not in existing
    ]
    return editor_df[existing + remaining]


def normalize_editor_products(editor_df: pd.DataFrame) -> pd.DataFrame:
    """Converte a visualização brasileira de volta para números técnicos."""
    normalized = editor_df.copy()

    for column in MONEY_COLUMNS:
        formatted_column = f"{column}_formatted"
        if formatted_column in normalized.columns:
            normalized[column] = normalized[formatted_column].apply(
                parse_pt_br_number
            )

    for column in QUANTITY_COLUMNS:
        formatted_column = f"{column}_formatted"
        if formatted_column in normalized.columns:
            normalized[column] = normalized[formatted_column].apply(
                parse_pt_br_integer
            )

    formatted_columns = [
        column
        for column in normalized.columns
        if column.endswith("_formatted")
    ]
    normalized = normalized.drop(columns=formatted_columns)

    for column in PRODUCT_COLUMN_ORDER:
        if column not in normalized.columns:
            normalized[column] = None

    remaining = [
        column
        for column in normalized.columns
        if column not in PRODUCT_COLUMN_ORDER
    ]
    return normalized[PRODUCT_COLUMN_ORDER + remaining]


PRODUCT_COLUMN_ORDER = [
    "source_file",
    "supplier_name",
    "supplier_alert",
    "catalog_name",
    "document_year",
    "source_page",
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
    "price_alert",
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
    "data_quality_alerts",
    "evidence",
]


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return bool(str(value).strip())


def _append_missing_field(existing: list[str], field: str) -> list[str]:
    cleaned = [item for item in existing if item]
    if field not in cleaned:
        cleaned.append(field)
    return cleaned


def merge_catalog_batches(
    batches: list[CatalogBatch],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    products: list[dict] = []
    rules: list[dict] = []
    warnings: list[dict] = []

    for batch_index, batch in enumerate(batches, start=1):
        for product in batch.products:
            row = product.model_dump()

            supplier_name = (
                product.supplier_name
                if _has_value(product.supplier_name)
                else batch.supplier_name
            )
            row["supplier_name"] = supplier_name
            row["catalog_name"] = batch.catalog_name
            row["document_year"] = batch.document_year

            missing_fields = list(row.get("missing_fields") or [])
            quality_alerts: list[str] = []

            if not _has_value(supplier_name):
                row["supplier_alert"] = "ALERTA: fornecedor não identificado"
                missing_fields = _append_missing_field(
                    missing_fields,
                    "supplier_name",
                )
                quality_alerts.append("Fornecedor não identificado")
                warnings.append(
                    {
                        "severity": "Alto",
                        "type": "Campo ausente",
                        "field": "supplier_name",
                        "supplier_name": None,
                        "sku": row.get("sku"),
                        "product_name": row.get("name"),
                        "source_page": row.get("source_page"),
                        "message": (
                            "O fornecedor não foi identificado no documento."
                        ),
                    }
                )
            else:
                row["supplier_alert"] = "OK"

            price_status = row.get("price_status") or "Não informado"
            has_numeric_price = any(
                row.get(field) is not None
                for field in ("unit_price", "price_min", "price_max")
            )

            if price_status == "Sob consulta":
                row["price_alert"] = "ATENÇÃO: preço sob consulta"
                quality_alerts.append("Preço sob consulta")
                missing_fields = _append_missing_field(
                    missing_fields,
                    "unit_price",
                )
                warnings.append(
                    {
                        "severity": "Médio",
                        "type": "Preço",
                        "field": "unit_price",
                        "supplier_name": supplier_name,
                        "sku": row.get("sku"),
                        "product_name": row.get("name"),
                        "source_page": row.get("source_page"),
                        "message": (
                            "O catálogo informa preço sob consulta; "
                            "é necessária cotação."
                        ),
                    }
                )
            elif not has_numeric_price:
                row["price_status"] = "Não informado"
                row["price_alert"] = "ALERTA: preço não informado"
                quality_alerts.append("Preço não informado")
                missing_fields = _append_missing_field(
                    missing_fields,
                    "unit_price",
                )
                warnings.append(
                    {
                        "severity": "Alto",
                        "type": "Preço",
                        "field": "unit_price",
                        "supplier_name": supplier_name,
                        "sku": row.get("sku"),
                        "product_name": row.get("name"),
                        "source_page": row.get("source_page"),
                        "message": (
                            "Nenhum preço foi encontrado para este produto."
                        ),
                    }
                )
            else:
                row["price_alert"] = "OK"
                if price_status == "Não informado":
                    row["price_status"] = (
                        "Faixa de preço"
                        if row.get("price_min") is not None
                        or row.get("price_max") is not None
                        else "Informado"
                    )

            row["tags"] = " | ".join(row.get("tags") or [])
            row["missing_fields"] = " | ".join(missing_fields)
            row["data_quality_alerts"] = " | ".join(quality_alerts)
            products.append(row)

        for rule in batch.global_rules:
            rule_row = rule.model_dump()
            rule_row["batch"] = batch_index
            rules.append(rule_row)

        for warning in batch.warnings:
            warnings.append(
                {
                    "severity": "Informativo",
                    "type": "Agente",
                    "field": None,
                    "supplier_name": batch.supplier_name,
                    "sku": None,
                    "product_name": None,
                    "source_page": None,
                    "message": warning,
                }
            )

    products_df = pd.DataFrame(products)

    if not products_df.empty:
        products_df["_dedupe"] = products_df.apply(
            lambda row: (
                f"sku::{str(row.get('sku')).strip().lower()}"
                if pd.notna(row.get("sku"))
                and str(row.get("sku")).strip()
                else (
                    f"name::{str(row.get('name')).strip().lower()}::"
                    f"{str(row.get('source_page'))}"
                )
            ),
            axis=1,
        )

        products_df = (
            products_df.sort_values(
                by=["confidence"],
                ascending=False,
                na_position="last",
            )
            .drop_duplicates(subset=["_dedupe"], keep="first")
            .drop(columns=["_dedupe"])
            .reset_index(drop=True)
        )

        for column in PRODUCT_COLUMN_ORDER:
            if column not in products_df.columns:
                products_df[column] = None

        remaining = [
            column
            for column in products_df.columns
            if column not in PRODUCT_COLUMN_ORDER
        ]
        products_df = products_df[
            PRODUCT_COLUMN_ORDER + remaining
        ]

    warnings_df = pd.DataFrame(warnings)
    if not warnings_df.empty:
        warning_order = [
            "severity",
            "type",
            "field",
            "supplier_name",
            "sku",
            "product_name",
            "source_page",
            "message",
        ]
        for column in warning_order:
            if column not in warnings_df.columns:
                warnings_df[column] = None
        warnings_df = warnings_df[warning_order]

    return products_df, pd.DataFrame(rules), warnings_df


def catalog_json_bytes(
    products_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    warnings_df: pd.DataFrame,
) -> bytes:
    payload = {
        "products": products_df.where(
            pd.notna(products_df), None
        ).to_dict(orient="records"),
        "global_rules": rules_df.where(
            pd.notna(rules_df), None
        ).to_dict(orient="records"),
        "alerts": warnings_df.where(
            pd.notna(warnings_df), None
        ).to_dict(orient="records"),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def briefing_json_bytes(briefing: ProjectBriefing) -> bytes:
    return json.dumps(
        briefing.model_dump(),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def briefing_dataframe(briefing: ProjectBriefing) -> pd.DataFrame:
    rows = []
    monetary_fields = {"budget_total_brl", "budget_unit_brl"}
    quantity_fields = {"audience_quantity"}

    for key, value in briefing.model_dump().items():
        if isinstance(value, list):
            value = " | ".join(str(item) for item in value)
        elif key in monetary_fields:
            value = format_pt_br_number(
                value,
                decimals=2,
                prefix="R$ ",
            )
        elif key in quantity_fields:
            value = format_pt_br_number(value, decimals=0)

        rows.append({"campo": key, "valor": value})

    return pd.DataFrame(rows)


def to_xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book

        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#E8E8E8",
                "border": 1,
                "text_wrap": True,
                "valign": "top",
            }
        )
        cell_format = workbook.add_format(
            {
                "border": 1,
                "text_wrap": True,
                "valign": "top",
            }
        )
        alert_format = workbook.add_format(
            {
                "bg_color": "#FDE9E7",
                "font_color": "#B42318",
                "border": 1,
                "text_wrap": True,
                "valign": "top",
            }
        )
        attention_format = workbook.add_format(
            {
                "bg_color": "#FFF4CE",
                "font_color": "#7A4E00",
                "border": 1,
                "text_wrap": True,
                "valign": "top",
            }
        )

        for raw_name, df in sheets.items():
            sheet_name = raw_name[:31]
            safe_df = df.copy()
            safe_df.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)

            if len(safe_df.columns) > 0:
                worksheet.autofilter(
                    0,
                    0,
                    max(len(safe_df), 1),
                    len(safe_df.columns) - 1,
                )

            money_format = workbook.add_format(
                {
                    "num_format": 'R$ #,##0.00',
                    "border": 1,
                    "valign": "top",
                }
            )
            integer_format = workbook.add_format(
                {
                    "num_format": "#,##0",
                    "border": 1,
                    "valign": "top",
                }
            )

            for col_index, column in enumerate(safe_df.columns):
                worksheet.write(
                    0,
                    col_index,
                    column,
                    header_format,
                )
                values = (
                    safe_df[column].astype(str).tolist()
                    if not safe_df.empty
                    else []
                )
                max_len = max(
                    [len(str(column))]
                    + [min(len(value), 60) for value in values]
                )
                width = min(max(max_len + 2, 12), 42)

                if column in MONEY_COLUMNS:
                    selected_format = money_format
                elif column in QUANTITY_COLUMNS:
                    selected_format = integer_format
                else:
                    selected_format = cell_format

                worksheet.set_column(
                    col_index,
                    col_index,
                    width,
                    selected_format,
                )

            if not safe_df.empty:
                for alert_column in (
                    "supplier_alert",
                    "price_alert",
                    "data_quality_alerts",
                ):
                    if alert_column in safe_df.columns:
                        column_index = safe_df.columns.get_loc(alert_column)
                        worksheet.conditional_format(
                            1,
                            column_index,
                            len(safe_df),
                            column_index,
                            {
                                "type": "text",
                                "criteria": "containing",
                                "value": "ALERTA",
                                "format": alert_format,
                            },
                        )
                        worksheet.conditional_format(
                            1,
                            column_index,
                            len(safe_df),
                            column_index,
                            {
                                "type": "text",
                                "criteria": "containing",
                                "value": "ATENÇÃO",
                                "format": attention_format,
                            },
                        )

    return buffer.getvalue()
