from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

import pandas as pd


STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do",
    "dos", "e", "em", "entre", "evento", "para", "por", "que", "sem",
    "um", "uma", "uns", "umas", "o", "os", "no", "na", "nos", "nas",
    "ser", "ter", "mais", "muito", "muita", "algo",
}


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


def _number(value: Any) -> float | None:
    if _missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(value: Any) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) >= 3 and token not in STOPWORDS
    }


def _candidate_text(row: dict) -> str:
    tags = row.get("tags")
    if isinstance(tags, list):
        tags = " ".join(str(item) for item in tags)
    return " ".join(
        str(row.get(field) or "")
        for field in (
            "name",
            "category",
            "supplier_name",
            "description",
        )
    ) + " " + str(tags or "")


def _relevance_score(
    row: dict,
    query_tokens: set[str],
) -> tuple[float, list[str]]:
    if not query_tokens:
        return 18.0, ["Sem palavras-chave específicas; aderência neutra."]

    name_tokens = tokens(row.get("name"))
    category_tokens = tokens(row.get("category"))
    all_tokens = tokens(_candidate_text(row))

    name_matches = query_tokens & name_tokens
    category_matches = query_tokens & category_tokens
    all_matches = query_tokens & all_tokens

    score = min(
        35.0,
        len(name_matches) * 8.0
        + len(category_matches - name_matches) * 5.0
        + len(all_matches - name_matches - category_matches) * 3.0,
    )

    reasons = []
    if all_matches:
        reasons.append(
            "Conversa com: " + ", ".join(sorted(all_matches)[:6]) + "."
        )
    else:
        reasons.append("Baixa correspondência textual com o briefing.")

    return score, reasons


def _budget_score(
    row: dict,
    brief: dict,
) -> tuple[float, float | None, list[str], list[str]]:
    budget_total = _number(brief.get("budget_total_brl"))
    quantity = _number(brief.get("audience_quantity"))
    base_price = _number(row.get("base_price"))
    item_type = row.get("item_type")

    warnings = []
    reasons = []

    if base_price is None:
        warnings.append("Preço não informado.")
        return 4.0, None, reasons, warnings

    if item_type == "product":
        if not quantity:
            warnings.append(
                "Quantidade não informada; total do brinde não calculado."
            )
            return 12.0, None, reasons, warnings
        estimated_total = base_price * quantity
    else:
        estimated_total = base_price

    if not budget_total:
        reasons.append("Budget total não informado; avaliação neutra.")
        return 15.0, estimated_total, reasons, warnings

    ratio = estimated_total / budget_total if budget_total else math.inf

    if ratio <= 1:
        if ratio >= 0.45:
            score = 30.0
        elif ratio >= 0.20:
            score = 25.0
        else:
            score = 20.0
        reasons.append("Estimativa dentro do budget informado.")
    elif ratio <= 1.10:
        score = 10.0
        warnings.append("Estimativa até 10% acima do budget.")
    else:
        score = 0.0
        warnings.append("Estimativa acima do budget.")

    return score, estimated_total, reasons, warnings


def _quantity_score(
    row: dict,
    brief: dict,
) -> tuple[float, list[str], list[str]]:
    quantity = _number(brief.get("audience_quantity"))
    item_type = row.get("item_type")
    warnings = []
    reasons = []

    if item_type == "product":
        minimum = _number(row.get("min_order_qty"))
        if not quantity:
            return 8.0, reasons, [
                "Quantidade não informada para validar o pedido mínimo."
            ]
        if minimum is None:
            return 10.0, reasons, ["Pedido mínimo não informado."]
        if quantity >= minimum:
            reasons.append("Quantidade atende ao pedido mínimo.")
            return 15.0, reasons, warnings
        warnings.append("Quantidade abaixo do pedido mínimo.")
        return 0.0, reasons, warnings

    if item_type == "venue":
        capacity = _number(row.get("capacity"))
        if not quantity:
            return 8.0, reasons, [
                "Público não informado para validar a capacidade."
            ]
        if capacity is None:
            return 7.0, reasons, ["Capacidade não informada."]
        if capacity >= quantity:
            reasons.append("Capacidade comporta o público informado.")
            return 15.0, reasons, warnings
        warnings.append("Capacidade inferior ao público informado.")
        return 0.0, reasons, warnings

    return 10.0, ["Escala deve ser validada com o fornecedor."], warnings


def _time_score(
    row: dict,
    brief: dict,
) -> tuple[float, list[str], list[str]]:
    available = _number(brief.get("available_days"))
    lead = _number(row.get("lead_time_days"))
    warnings = []
    reasons = []

    if row.get("item_type") != "activation":
        return 7.0, reasons, warnings

    if not available:
        return 5.0, reasons, ["Prazo disponível não informado."]

    if lead is None:
        return 4.0, reasons, ["Prazo da solução não informado."]

    if lead <= available:
        reasons.append("Prazo compatível com a janela disponível.")
        return 10.0, reasons, warnings

    warnings.append("Prazo maior que a janela disponível.")
    return 0.0, reasons, warnings


def _location_score(
    row: dict,
    brief: dict,
) -> tuple[float, list[str], list[str]]:
    city = normalize_text(brief.get("location_city"))
    state = normalize_text(brief.get("location_state"))
    item_type = row.get("item_type")
    candidate_city = normalize_text(row.get("city"))
    candidate_state = normalize_text(row.get("state"))
    candidate_location = normalize_text(row.get("location"))

    if not city and not state:
        return 5.0, [], ["Localização do projeto não informada."]

    if item_type == "product":
        return 5.0, ["Logística do produto ainda deve ser cotada."], []

    if city and (
        city == candidate_city
        or city in candidate_location
    ):
        return 10.0, ["Localização compatível com a cidade."], []

    if state and (
        state == candidate_state
        or state in candidate_location
    ):
        return 7.0, ["Localização compatível com o estado."], []

    if not candidate_city and not candidate_location:
        return 4.0, [], ["Localização do item não informada."]

    if item_type == "activation":
        return 3.0, [], [
            "Atendimento em outra cidade deve ser validado."
        ]

    return 0.0, [], ["Local em cidade diferente da informada."]


def score_candidates(
    candidates_df: pd.DataFrame,
    brief: dict,
    *,
    limit: int = 12,
) -> pd.DataFrame:
    if candidates_df is None or candidates_df.empty:
        return pd.DataFrame()

    desired_types = set(brief.get("desired_types") or [])
    query_parts = [
        brief.get("objective"),
        brief.get("audience_profile"),
        " ".join(brief.get("desired_attributes") or []),
        " ".join(brief.get("keywords") or []),
        brief.get("source_summary"),
    ]
    query_tokens = tokens(" ".join(str(item or "") for item in query_parts))

    rows = []

    for raw in candidates_df.to_dict(orient="records"):
        if desired_types and raw.get("item_type") not in desired_types:
            continue

        relevance, relevance_reasons = _relevance_score(
            raw, query_tokens
        )
        budget, estimated_total, budget_reasons, budget_warnings = (
            _budget_score(raw, brief)
        )
        quantity, quantity_reasons, quantity_warnings = (
            _quantity_score(raw, brief)
        )
        time_score, time_reasons, time_warnings = (
            _time_score(raw, brief)
        )
        location, location_reasons, location_warnings = (
            _location_score(raw, brief)
        )

        total = relevance + budget + quantity + time_score + location

        reasons = (
            relevance_reasons
            + budget_reasons
            + quantity_reasons
            + time_reasons
            + location_reasons
        )
        warnings = (
            budget_warnings
            + quantity_warnings
            + time_warnings
            + location_warnings
        )

        row = dict(raw)
        row.update(
            {
                "total_score": round(total, 2),
                "relevance_score": round(relevance, 2),
                "budget_score": round(budget, 2),
                "quantity_score": round(quantity, 2),
                "time_score": round(time_score, 2),
                "location_score": round(location, 2),
                "estimated_total": estimated_total,
                "reason": " ".join(reasons),
                "warnings": warnings,
            }
        )
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).sort_values(
        by=["total_score", "relevance_score"],
        ascending=False,
    ).reset_index(drop=True)

    result["rank"] = result.index + 1
    return result.head(limit)
