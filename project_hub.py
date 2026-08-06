from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from memory_db import (
    fetch_memory_projects_overview,
)
from supabase_db import (
    fetch_project_history_overview,
)


def _first_present(
    row: pd.Series,
    columns: list[str],
    default: Any = None,
) -> Any:
    for column in columns:
        value = row.get(column)

        if value is None:
            continue

        try:
            if pd.isna(value):
                continue
        except (
            TypeError,
            ValueError,
        ):
            pass

        if str(value).strip():
            return value

    return default


def _numeric(
    series: pd.Series,
) -> pd.Series:
    return pd.to_numeric(
        series,
        errors="coerce",
    ).fillna(0)


def _date_text(
    value: Any,
) -> str:
    if value is None:
        return "Não informada"

    try:
        if pd.isna(value):
            return "Não informada"
    except (
        TypeError,
        ValueError,
    ):
        pass

    text = str(value).strip()
    return (
        text[:10]
        if text
        else "Não informada"
    )


def fetch_unified_projects(
    client,
) -> pd.DataFrame:
    try:
        recommendation_projects = (
            fetch_project_history_overview(
                client
            )
        )
    except Exception:
        recommendation_projects = (
            pd.DataFrame()
        )

    try:
        memory_projects = (
            fetch_memory_projects_overview(
                client
            )
        )
    except Exception:
        memory_projects = pd.DataFrame()

    if (
        recommendation_projects.empty
        and memory_projects.empty
    ):
        return pd.DataFrame()

    recommendation_columns = [
        "project_id",
        "project_name",
        "client_brand",
        "event_name",
        "recommendation_versions",
        "latest_completeness_score",
        "latest_readiness_status",
        "budget_total_brl",
        "latest_activity",
    ]

    memory_columns = [
        "project_id",
        "project_name",
        "client_brand",
        "event_name",
        "memory_documents_count",
        "memory_items_count",
        "memory_pages_count",
        "latest_memory_activity",
    ]

    recommendation = (
        recommendation_projects.reindex(
            columns=recommendation_columns
        )
        if not recommendation_projects.empty
        else pd.DataFrame(
            columns=recommendation_columns
        )
    )

    memory = (
        memory_projects.reindex(
            columns=memory_columns
        )
        if not memory_projects.empty
        else pd.DataFrame(
            columns=memory_columns
        )
    )

    merged = recommendation.merge(
        memory,
        on="project_id",
        how="outer",
        suffixes=(
            "_recommendation",
            "_memory",
        ),
    )

    merged["project_name"] = (
        merged.apply(
            lambda row: _first_present(
                row,
                [
                    "project_name_recommendation",
                    "project_name_memory",
                ],
                "Projeto sem nome",
            ),
            axis=1,
        )
    )
    merged["client_brand"] = (
        merged.apply(
            lambda row: _first_present(
                row,
                [
                    "client_brand_recommendation",
                    "client_brand_memory",
                ],
                "Não informado",
            ),
            axis=1,
        )
    )
    merged["event_name"] = (
        merged.apply(
            lambda row: _first_present(
                row,
                [
                    "event_name_recommendation",
                    "event_name_memory",
                ],
                "Não informado",
            ),
            axis=1,
        )
    )

    for column in [
        "recommendation_versions",
        "latest_completeness_score",
        "budget_total_brl",
        "memory_documents_count",
        "memory_items_count",
        "memory_pages_count",
    ]:
        if column not in merged:
            merged[column] = 0

        merged[column] = _numeric(
            merged[column]
        )

    merged["latest_activity_unified"] = (
        merged.apply(
            lambda row: max(
                [
                    text
                    for text in [
                        str(
                            row.get(
                                "latest_activity"
                            )
                            or ""
                        ),
                        str(
                            row.get(
                                "latest_memory_activity"
                            )
                            or ""
                        ),
                    ]
                    if text
                ],
                default="",
            ),
            axis=1,
        )
    )

    merged["has_recommendations"] = (
        merged[
            "recommendation_versions"
        ].gt(0)
    )
    merged["has_memory"] = (
        merged[
            "memory_documents_count"
        ].gt(0)
    )

    return (
        merged.sort_values(
            "latest_activity_unified",
            ascending=False,
            na_position="last",
        )
        .reset_index(drop=True)
    )


def unified_project_table(
    projects: pd.DataFrame,
    *,
    search: str,
    page_size: int,
    current_page: int,
) -> tuple[
    pd.DataFrame,
    int,
    int,
]:
    visible = projects.copy()

    if search.strip():
        term = search.strip().casefold()
        searchable = (
            visible["project_name"]
            .fillna("")
            .astype(str)
            + " "
            + visible["client_brand"]
            .fillna("")
            .astype(str)
            + " "
            + visible["event_name"]
            .fillna("")
            .astype(str)
        ).str.casefold()

        visible = visible[
            searchable.str.contains(
                term,
                regex=False,
            )
        ]

    visible = visible.reset_index(
        drop=True
    )
    total = len(visible)
    pages = max(
        1,
        math.ceil(
            total / page_size
        ),
    )

    safe_page = min(
        max(
            int(current_page),
            1,
        ),
        pages,
    )
    start = (
        safe_page - 1
    ) * page_size
    end = min(
        start + page_size,
        total,
    )

    page = visible.iloc[
        start:end
    ].copy().reset_index(
        drop=True
    )

    if page.empty:
        return page, total, pages

    page["Projeto"] = page[
        "project_name"
    ].fillna(
        "Projeto sem nome"
    )
    page["Cliente"] = page[
        "client_brand"
    ].fillna(
        "Não informado"
    )
    page["Evento"] = page[
        "event_name"
    ].fillna(
        "Não informado"
    )
    page["Briefings / recomendações"] = (
        page[
            "recommendation_versions"
        ].astype(int)
    )
    page["Apresentações"] = page[
        "memory_documents_count"
    ].astype(int)
    page["Conteúdos"] = page[
        "memory_items_count"
    ].astype(int)
    page["Última atualização"] = page[
        "latest_activity_unified"
    ].apply(
        _date_text
    )

    return page, total, pages


def selected_rows(
    event,
) -> list[int]:
    try:
        return list(
            event.selection.rows
        )
    except Exception:
        try:
            return list(
                event.get(
                    "selection",
                    {},
                ).get(
                    "rows",
                    [],
                )
            )
        except Exception:
            return []
