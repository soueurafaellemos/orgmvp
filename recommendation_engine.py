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


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "true", "1", "sim", "yes", "s",
    }


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _normalized_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[|,;]", str(value))
    return {
        normalize_text(item)
        for item in values
        if normalize_text(item)
    }


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
            "category_nave",
            "supplier_name",
            "description",
            "taxonomy_search_text",
        )
    ) + " " + str(tags or "")


def _relevance_score(
    row: dict,
    query_tokens: set[str],
) -> tuple[float, list[str]]:
    if not query_tokens:
        return 18.0, [
            "Sem palavras-chave específicas; aderência neutra."
        ]

    name_tokens = tokens(row.get("name"))
    category_tokens = tokens(
        row.get("category_nave")
        or row.get("category")
    )
    all_tokens = tokens(_candidate_text(row))

    name_matches = query_tokens & name_tokens
    category_matches = query_tokens & category_tokens
    all_matches = query_tokens & all_tokens

    score = min(
        35.0,
        len(name_matches) * 8.0
        + len(category_matches - name_matches) * 5.0
        + len(
            all_matches - name_matches - category_matches
        ) * 3.0,
    )

    if all_matches:
        reasons = [
            "Conversa com: "
            + ", ".join(sorted(all_matches)[:6])
            + "."
        ]
    else:
        reasons = [
            "Baixa correspondência textual com o briefing."
        ]

    return score, reasons


def _coverage_score(
    row: dict,
    brief: dict,
) -> tuple[float, str, list[str], list[str]]:
    city = normalize_text(brief.get("location_city"))
    state = normalize_text(brief.get("location_state"))
    item_type = row.get("item_type")

    reasons: list[str] = []
    warnings: list[str] = []

    if not city and not state:
        return (
            5.0,
            "Praça não informada",
            reasons,
            ["Localização do projeto não informada."],
        )

    # Locais são avaliados pela própria localização física.
    if item_type == "venue":
        venue_city = normalize_text(row.get("city"))
        venue_state = normalize_text(row.get("state"))
        venue_location = normalize_text(row.get("location"))

        if city and (
            city == venue_city
            or city in venue_location
        ):
            return (
                10.0,
                "Local exato",
                ["Local situado na cidade do projeto."],
                warnings,
            )

        if state and (
            state == venue_state
            or state in venue_location
        ):
            return (
                7.0,
                "Mesmo estado",
                ["Local situado no mesmo estado."],
                warnings,
            )

        return (
            0.0,
            "Local incompatível",
            reasons,
            ["Local situado fora da praça informada."],
        )

    base_city = normalize_text(row.get("supplier_base_city"))
    base_state = normalize_text(row.get("supplier_base_state"))
    served_cities = _normalized_list(
        row.get("supplier_served_cities")
    )
    served_states = _normalized_list(
        row.get("supplier_served_states")
    )
    local_teams = _normalized_list(
        row.get("supplier_local_team_locations")
    )
    national = _boolean(
        row.get("supplier_serves_nationally")
    )
    has_local_teams = _boolean(
        row.get("supplier_has_local_teams")
    )

    has_coverage_data = any(
        (
            base_city,
            base_state,
            served_cities,
            served_states,
            local_teams,
            national,
        )
    )

    if city and base_city and city == base_city:
        return (
            10.0,
            "Fornecedor local",
            ["Fornecedor baseado na cidade do projeto."],
            warnings,
        )

    if city and (
        city in served_cities
        or city in local_teams
    ):
        return (
            10.0,
            "Cobertura local confirmada",
            ["Atendimento local confirmado na cidade."],
            warnings,
        )

    if state and base_state and state == base_state:
        return (
            8.0,
            "Fornecedor regional",
            ["Fornecedor baseado no mesmo estado."],
            warnings,
        )

    if state and state in served_states:
        return (
            8.0,
            "Cobertura estadual confirmada",
            ["Atendimento confirmado no estado."],
            warnings,
        )

    if national:
        if has_local_teams:
            return (
                8.0,
                "Cobertura nacional com equipes locais",
                [
                    "Fornecedor declara atendimento nacional "
                    "e possui equipes locais."
                ],
                warnings,
            )
        return (
            7.0,
            "Cobertura nacional",
            ["Fornecedor declara atendimento nacional."],
            warnings,
        )

    if not has_coverage_data:
        return (
            4.0,
            "Cobertura não cadastrada",
            reasons,
            [
                "Cobertura territorial do fornecedor ainda "
                "não cadastrada."
            ],
        )

    return (
        1.0,
        "Fora da cobertura cadastrada",
        reasons,
        [
            "A praça não aparece na cobertura cadastrada "
            "do fornecedor."
        ],
    )


def _logistics_estimate(
    row: dict,
    brief: dict,
    coverage_status: str,
) -> tuple[float, list[str], list[str]]:
    item_type = row.get("item_type")
    city = normalize_text(brief.get("location_city"))
    state = normalize_text(brief.get("location_state"))

    reasons: list[str] = []
    warnings: list[str] = []

    if item_type == "venue" or (not city and not state):
        return 0.0, reasons, warnings

    if coverage_status in {
        "Fornecedor local",
        "Cobertura local confirmada",
        "Local exato",
    }:
        return 0.0, reasons, warnings

    if item_type == "product":
        mode = str(
            row.get("supplier_freight_pricing_mode") or ""
        ).strip()
        amount = _number(
            row.get("supplier_default_freight_cost_brl")
        )
        label = "frete"
    else:
        mode = str(
            row.get("supplier_travel_pricing_mode") or ""
        ).strip()
        amount = _number(
            row.get("supplier_default_travel_cost_brl")
        )
        label = "deslocamento"

    if mode == "Incluído no valor":
        reasons.append(
            f"Custo de {label} informado como incluído."
        )
        return 0.0, reasons, warnings

    if mode == "Adicionar estimativa" and amount:
        reasons.append(
            f"Estimativa de {label} adicionada ao total."
        )
        return amount, reasons, warnings

    if mode == "Sob consulta":
        warnings.append(
            f"Custo de {label} deve ser consultado."
        )
        return 0.0, reasons, warnings

    warnings.append(
        f"Custo de {label} não informado para esta praça."
    )
    return 0.0, reasons, warnings


def _budget_score(
    row: dict,
    brief: dict,
    logistics_estimate: float,
) -> tuple[
    float,
    float | None,
    list[str],
    list[str],
]:
    budget_total = _number(brief.get("budget_total_brl"))
    quantity = _number(brief.get("audience_quantity"))
    base_price = _number(row.get("base_price"))
    item_type = row.get("item_type")

    warnings: list[str] = []
    reasons: list[str] = []

    if base_price is None:
        warnings.append("Preço não informado.")
        return 4.0, None, reasons, warnings

    if item_type == "product":
        if not quantity:
            warnings.append(
                "Quantidade não informada; total do produto "
                "não calculado."
            )
            return 12.0, None, reasons, warnings
        estimated_total = base_price * quantity
    else:
        estimated_total = base_price

    estimated_total += logistics_estimate

    if not budget_total:
        reasons.append(
            "Budget total não informado; avaliação financeira neutra."
        )
        return 15.0, estimated_total, reasons, warnings

    ratio = (
        estimated_total / budget_total
        if budget_total
        else math.inf
    )

    if ratio <= 1:
        if ratio >= 0.45:
            score = 30.0
        elif ratio >= 0.20:
            score = 25.0
        else:
            score = 20.0
        reasons.append(
            "Estimativa dentro do budget informado."
        )
    elif ratio <= 1.10:
        score = 10.0
        warnings.append(
            "Estimativa até 10% acima do budget."
        )
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
    warnings: list[str] = []
    reasons: list[str] = []

    if item_type == "product":
        minimum = _number(row.get("min_order_qty"))
        if not quantity:
            return 8.0, reasons, [
                "Quantidade não informada para validar "
                "o pedido mínimo."
            ]
        if minimum is None:
            return 10.0, reasons, [
                "Pedido mínimo não informado."
            ]
        if quantity >= minimum:
            reasons.append(
                "Quantidade atende ao pedido mínimo."
            )
            return 15.0, reasons, warnings
        warnings.append(
            "Quantidade abaixo do pedido mínimo."
        )
        return 0.0, reasons, warnings

    if item_type == "venue":
        capacity = _number(row.get("capacity"))
        if not quantity:
            return 8.0, reasons, [
                "Público não informado para validar a capacidade."
            ]
        if capacity is None:
            return 7.0, reasons, [
                "Capacidade não informada."
            ]
        if capacity >= quantity:
            reasons.append(
                "Capacidade comporta o público informado."
            )
            return 15.0, reasons, warnings
        warnings.append(
            "Capacidade inferior ao público informado."
        )
        return 0.0, reasons, warnings

    return (
        10.0,
        ["Escala deve ser validada com o fornecedor."],
        warnings,
    )


def _time_score(
    row: dict,
    brief: dict,
    coverage_status: str,
) -> tuple[float, list[str], list[str]]:
    available = _number(brief.get("available_days"))
    lead = _number(row.get("lead_time_days"))
    travel_lead = _number(
        row.get("supplier_travel_lead_days")
    )

    warnings: list[str] = []
    reasons: list[str] = []

    if row.get("item_type") != "activation":
        return 7.0, reasons, warnings

    if not available:
        return 5.0, reasons, [
            "Prazo disponível não informado."
        ]

    if lead is None:
        return 4.0, reasons, [
            "Prazo da solução não informado."
        ]

    effective_lead = lead
    if (
        travel_lead
        and coverage_status not in {
            "Fornecedor local",
            "Cobertura local confirmada",
        }
    ):
        effective_lead += travel_lead
        reasons.append(
            "Prazo logístico de deslocamento considerado."
        )

    if effective_lead <= available:
        reasons.append(
            "Prazo compatível com a janela disponível."
        )
        return 10.0, reasons, warnings

    warnings.append(
        "Prazo total maior que a janela disponível."
    )
    return 0.0, reasons, warnings


def score_candidates(
    candidates_df: pd.DataFrame,
    brief: dict,
    *,
    limit: int = 12,
) -> pd.DataFrame:
    if candidates_df is None or candidates_df.empty:
        return pd.DataFrame()

    desired_types = set(
        brief.get("desired_types") or []
    )
    query_parts = [
        brief.get("objective"),
        brief.get("audience_profile"),
        " ".join(
            brief.get("desired_attributes") or []
        ),
        " ".join(brief.get("keywords") or []),
        brief.get("source_summary"),
    ]
    query_tokens = tokens(
        " ".join(str(item or "") for item in query_parts)
    )

    rows = []

    for raw in candidates_df.to_dict(orient="records"):
        if (
            desired_types
            and raw.get("item_type") not in desired_types
        ):
            continue

        relevance, relevance_reasons = _relevance_score(
            raw,
            query_tokens,
        )

        (
            location,
            coverage_status,
            location_reasons,
            location_warnings,
        ) = _coverage_score(raw, brief)

        (
            logistics_estimate,
            logistics_reasons,
            logistics_warnings,
        ) = _logistics_estimate(
            raw,
            brief,
            coverage_status,
        )

        (
            budget,
            estimated_total,
            budget_reasons,
            budget_warnings,
        ) = _budget_score(
            raw,
            brief,
            logistics_estimate,
        )

        (
            quantity,
            quantity_reasons,
            quantity_warnings,
        ) = _quantity_score(raw, brief)

        (
            time_score,
            time_reasons,
            time_warnings,
        ) = _time_score(
            raw,
            brief,
            coverage_status,
        )

        total = (
            relevance
            + budget
            + quantity
            + time_score
            + location
        )

        reasons = (
            relevance_reasons
            + location_reasons
            + logistics_reasons
            + budget_reasons
            + quantity_reasons
            + time_reasons
        )
        warnings = (
            location_warnings
            + logistics_warnings
            + budget_warnings
            + quantity_warnings
            + time_warnings
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
                "coverage_status": coverage_status,
                "logistics_estimate": (
                    round(logistics_estimate, 2)
                    if logistics_estimate
                    else 0.0
                ),
                "estimated_total": estimated_total,
                "reason": " ".join(reasons),
                "warnings": list(dict.fromkeys(warnings)),
            }
        )
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).sort_values(
        by=[
            "total_score",
            "location_score",
            "relevance_score",
        ],
        ascending=False,
    ).reset_index(drop=True)

    result["rank"] = result.index + 1
    return result.head(limit)
