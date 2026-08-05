from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from recommendation_engine import score_candidates


def execution_display_name(
    execution: dict,
    *,
    index: int,
) -> str:
    name = str(execution.get("name") or "").strip()
    city = str(execution.get("city") or "").strip()
    institution = str(execution.get("institution") or "").strip()

    if name:
        return name
    if institution and city:
        return f"{institution} — {city}"
    if institution:
        return institution
    if city:
        return city
    return f"Execução {index}"


def build_execution_brief(
    project_brief: dict,
    execution: dict,
    *,
    execution_name: str,
) -> dict:
    brief = deepcopy(project_brief)

    brief["event_name"] = execution_name
    brief["location_city"] = execution.get("city") or None
    brief["location_state"] = execution.get("state") or None
    brief["event_date"] = execution.get("event_date") or None
    brief["audience_quantity"] = (
        execution.get("audience_quantity") or None
    )

    execution_budget = execution.get("budget_amount")
    if execution_budget:
        brief["budget_total_brl"] = execution_budget
        quantity = brief.get("audience_quantity")
        brief["budget_unit_brl"] = (
            execution_budget / quantity
            if quantity
            else None
        )
    else:
        # O budget global não pode ser tratado automaticamente como
        # budget individual de cada praça.
        brief["budget_total_brl"] = None
        brief["budget_unit_brl"] = None

    product_name = execution.get("product_name")
    keywords = list(brief.get("keywords") or [])

    for value in (
        execution_name,
        execution.get("city"),
        execution.get("state"),
        execution.get("institution"),
        execution.get("venue"),
        execution.get("event_format"),
        product_name,
    ):
        if value and str(value).strip():
            keywords.append(str(value).strip())

    brief["keywords"] = list(dict.fromkeys(keywords))

    execution_attributes = [
        value
        for value in (
            product_name,
            execution.get("event_format"),
            execution.get("institution"),
        )
        if value
    ]
    brief["desired_attributes"] = list(
        dict.fromkeys(
            list(brief.get("desired_attributes") or [])
            + execution_attributes
        )
    )

    base_summary = str(brief.get("source_summary") or "").strip()
    execution_context = (
        f"Escopo específico: {execution_name}. "
        f"Cidade: {execution.get('city') or 'não informada'}. "
        f"Estado: {execution.get('state') or 'não informado'}. "
        f"Instituição/local: "
        f"{execution.get('institution') or execution.get('venue') or 'não informado'}. "
        f"Produto: {product_name or 'não informado'}. "
        f"Público: {execution.get('audience_quantity') or 'não informado'}. "
        f"Budget local: {execution_budget or 'não informado'}."
    )
    brief["source_summary"] = (
        base_summary + "\n\n" + execution_context
    ).strip()

    brief["active_execution"] = {
        **execution,
        "name": execution_name,
    }
    return brief


def score_execution_recommendations(
    candidates_df: pd.DataFrame,
    project_brief: dict,
    *,
    limit: int = 12,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    results: dict[str, pd.DataFrame] = {}
    briefs: dict[str, dict] = {}

    executions = project_brief.get("executions") or []

    for index, execution in enumerate(executions, start=1):
        if not isinstance(execution, dict):
            continue

        name = execution_display_name(
            execution,
            index=index,
        )

        # Evita colisão de nomes sem perder legibilidade.
        unique_name = name
        suffix = 2
        while unique_name in briefs:
            unique_name = f"{name} ({suffix})"
            suffix += 1

        execution_brief = build_execution_brief(
            project_brief,
            execution,
            execution_name=unique_name,
        )

        execution_results = score_candidates(
            candidates_df,
            execution_brief,
            limit=limit,
        )

        briefs[unique_name] = execution_brief
        results[unique_name] = execution_results

    return results, briefs
