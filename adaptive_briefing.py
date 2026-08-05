from __future__ import annotations

import math
from typing import Any

import pandas as pd


PROFILE_OPTIONS = [
    "Entrega simples",
    "Projeto único estruturado",
    "Programa multi-execução",
]

PRODUCT_COLUMNS = [
    "name",
    "brand",
    "role",
    "execution_names",
    "notes",
]

DELIVERABLE_COLUMNS = [
    "name",
    "category",
    "quantity",
    "unit",
    "required",
    "responsible",
    "execution_names",
    "notes",
]

METRIC_COLUMNS = [
    "name",
    "target",
    "unit",
    "status",
    "execution_names",
    "notes",
]

EXECUTION_COLUMNS = [
    "name",
    "city",
    "state",
    "venue",
    "institution",
    "status",
    "priority",
    "event_date",
    "product_name",
    "audience_quantity",
    "budget_amount",
    "currency",
    "event_format",
    "notes",
]

REFERENCE_COLUMNS = [
    "title",
    "reference_type",
    "status",
    "url_or_location",
    "notes",
]


def records_dataframe(
    records: list[dict] | None,
    columns: list[str],
) -> pd.DataFrame:
    frame = pd.DataFrame(records or [])
    for column in columns:
        if column not in frame.columns:
            frame[column] = None

    # Streamlit Data Editor lida melhor com listas como texto editável.
    for column in ("execution_names",):
        if column in frame.columns:
            frame[column] = frame[column].apply(
                lambda value: (
                    ", ".join(str(item) for item in value)
                    if isinstance(value, (list, tuple))
                    else value
                )
            )

    # DateColumn espera objetos date/datetime, não strings livres.
    if "event_date" in frame.columns:
        frame["event_date"] = pd.to_datetime(
            frame["event_date"],
            errors="coerce",
        ).dt.date

    return frame[columns]


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
    if isinstance(value, tuple):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
    if isinstance(value, float) and math.isnan(value):
        return []
    return [
        item.strip()
        for item in str(value).replace("|", ",").split(",")
        if item.strip()
    ]


def dataframe_records(
    frame: pd.DataFrame | None,
    *,
    required_field: str,
    list_fields: set[str] | None = None,
) -> list[dict]:
    if frame is None or frame.empty:
        return []

    list_fields = list_fields or set()
    records = []

    for raw in frame.to_dict(orient="records"):
        cleaned = {}
        for key, value in raw.items():
            if key in list_fields:
                cleaned[key] = _list_value(value)
            else:
                cleaned[key] = _clean_scalar(value)

        if not cleaned.get(required_field):
            continue

        records.append(cleaned)

    return records


def lines_to_list(value: str | None) -> list[str]:
    return [
        line.strip(" -•\t")
        for line in str(value or "").splitlines()
        if line.strip(" -•\t")
    ]


def list_to_lines(value: list[str] | None) -> str:
    return "\n".join(str(item) for item in (value or []))


def comma_list(value: str | None) -> list[str]:
    return [
        item.strip()
        for item in str(value or "").replace("|", ",").split(",")
        if item.strip()
    ]


def list_to_comma(value: list[str] | None) -> str:
    return ", ".join(str(item) for item in (value or []))


def nested_count(brief: dict) -> dict[str, int]:
    return {
        "products": len(brief.get("products_or_brands") or []),
        "deliverables": len(brief.get("deliverables") or []),
        "metrics": len(brief.get("success_metrics") or []),
        "executions": len(brief.get("executions") or []),
        "references": len(brief.get("related_references") or []),
    }
