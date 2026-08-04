from __future__ import annotations

import io
import json
from collections import OrderedDict
from typing import Iterable

import pandas as pd

from models import CatalogBatch, CatalogProduct, GlobalRule, ProjectBriefing


def merge_catalog_batches(batches: list[CatalogBatch]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    products: list[dict] = []
    rules: list[dict] = []
    warnings: list[dict] = []

    for batch_index, batch in enumerate(batches, start=1):
        for product in batch.products:
            row = product.model_dump()
            row["tags"] = " | ".join(row.get("tags") or [])
            row["missing_fields"] = " | ".join(row.get("missing_fields") or [])
            row["supplier_name"] = batch.supplier_name
            row["catalog_name"] = batch.catalog_name
            row["document_year"] = batch.document_year
            products.append(row)

        for rule in batch.global_rules:
            row = rule.model_dump()
            row["batch"] = batch_index
            rules.append(row)

        for warning in batch.warnings:
            warnings.append({"batch": batch_index, "warning": warning})

    products_df = pd.DataFrame(products)
    if not products_df.empty:
        # Deduplicação conservadora: SKU quando houver; senão nome + página.
        products_df["_dedupe"] = products_df.apply(
            lambda row: (
                f"sku::{str(row.get('sku')).strip().lower()}"
                if pd.notna(row.get("sku")) and str(row.get("sku")).strip()
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

    return products_df, pd.DataFrame(rules), pd.DataFrame(warnings)


def catalog_json_bytes(batches: list[CatalogBatch]) -> bytes:
    payload = [batch.model_dump() for batch in batches]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def briefing_json_bytes(briefing: ProjectBriefing) -> bytes:
    return json.dumps(
        briefing.model_dump(), ensure_ascii=False, indent=2
    ).encode("utf-8")


def briefing_dataframe(briefing: ProjectBriefing) -> pd.DataFrame:
    rows = []
    for key, value in briefing.model_dump().items():
        if isinstance(value, list):
            value = " | ".join(str(item) for item in value)
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

        for raw_name, df in sheets.items():
            sheet_name = raw_name[:31]
            safe_df = df.copy()
            safe_df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(safe_df), 1), max(len(safe_df.columns) - 1, 0))

            for col_index, column in enumerate(safe_df.columns):
                worksheet.write(0, col_index, column, header_format)
                values = safe_df[column].astype(str) if not safe_df.empty else []
                max_len = max(
                    [len(str(column))]
                    + [min(len(value), 60) for value in values]
                )
                width = min(max(max_len + 2, 12), 42)
                worksheet.set_column(col_index, col_index, width, cell_format)

    return buffer.getvalue()
