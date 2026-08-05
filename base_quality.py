from __future__ import annotations

from collections import Counter
from typing import Any, Callable

import pandas as pd


TYPE_LABELS = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
    "supplier": "Fornecedores",
}

STATUS_ORDER = {
    "Pronto para recomendação": 0,
    "Em evolução": 1,
    "Prioritário": 2,
}

STATUS_ICONS = {
    "Pronto para recomendação": "●",
    "Em evolução": "◐",
    "Prioritário": "○",
}


def is_blank(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        normalized = value.strip().casefold()
        return normalized in {
            "",
            "-",
            "--",
            "não informado",
            "nao informado",
            "não informada",
            "nao informada",
            "não disponível",
            "nao disponivel",
            "sem informação",
            "sem informacao",
            "null",
            "none",
        }

    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0

    return False


def any_value(
    record: dict,
    fields: list[str],
) -> bool:
    return any(
        not is_blank(record.get(field))
        for field in fields
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return not is_blank(value)


def _supplier_present(record: dict) -> bool:
    return any_value(
        record,
        ["supplier_id", "supplier_name", "operator_id"],
    )


def _price_present(record: dict) -> bool:
    return any_value(
        record,
        [
            "unit_price",
            "base_price",
            "price_min",
            "price_max",
        ],
    )


def _price_or_status(record: dict) -> bool:
    return (
        _price_present(record)
        or not is_blank(record.get("price_status"))
    )


def _capacity_present(record: dict) -> bool:
    return any_value(
        record,
        [
            "capacity",
            "capacity_ml",
            "standing_capacity",
            "seated_capacity",
            "auditorium_capacity",
        ],
    )


def _technical_product(record: dict) -> bool:
    return any_value(
        record,
        [
            "material",
            "dimensions_raw",
            "capacity",
            "capacity_ml",
            "finish",
        ],
    )


def _personalization_product(record: dict) -> bool:
    return (
        record.get("customizable") is not None
        or any_value(
            record,
            ["decoration", "licensing_notes"],
        )
    )


def _infrastructure_activation(record: dict) -> bool:
    return any_value(
        record,
        [
            "infrastructure_requirements",
            "internet_requirement",
            "included_items",
            "excluded_items",
        ],
    )


def _infrastructure_venue(record: dict) -> bool:
    return any_value(
        record,
        [
            "infrastructure",
            "power_supply",
            "internet",
            "air_conditioning",
            "audiovisual",
            "kitchen_or_catering",
            "bathrooms",
            "furniture",
        ],
    )


def _venue_access(record: dict) -> bool:
    return any_value(
        record,
        [
            "parking",
            "accessibility",
            "loading_access",
            "map_url",
        ],
    )


def _supplier_contact(record: dict) -> bool:
    return any_value(
        record,
        [
            "email",
            "phone",
            "whatsapp",
            "website_url",
            "contact_name",
        ],
    )


def _supplier_base(record: dict) -> bool:
    return any_value(
        record,
        ["base_city", "base_state"],
    )


def _supplier_coverage(record: dict) -> bool:
    return (
        record.get("serves_nationally") is True
        or any_value(
            record,
            [
                "served_states",
                "served_cities",
                "local_team_locations",
            ],
        )
    )


def _supplier_logistics(record: dict) -> bool:
    return any_value(
        record,
        [
            "travel_pricing_mode",
            "default_travel_cost_brl",
            "freight_pricing_mode",
            "default_freight_cost_brl",
        ],
    )


def _supplier_repertoire(record: dict) -> bool:
    counts = [
        record.get("products_count"),
        record.get("activations_count"),
        record.get("venues_count"),
    ]

    for value in counts:
        try:
            if int(value or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue

    return False


def _media_present(record: dict) -> bool:
    try:
        return int(record.get("media_count") or 0) > 0
    except (TypeError, ValueError):
        return False


def _source_present(record: dict) -> bool:
    return any_value(
        record,
        ["source_file", "document_name", "catalog_name"],
    )


SCHEMAS: dict[str, list[dict]] = {
    "product": [
        {
            "label": "Nome",
            "weight": 10,
            "check": lambda r: not is_blank(r.get("name")),
            "critical": True,
        },
        {
            "label": "Categoria",
            "weight": 8,
            "check": lambda r: not is_blank(r.get("category")),
            "critical": True,
        },
        {
            "label": "Descrição",
            "weight": 8,
            "check": lambda r: not is_blank(r.get("description")),
        },
        {
            "label": "Fornecedor",
            "weight": 12,
            "check": _supplier_present,
            "critical": True,
        },
        {
            "label": "Preço",
            "weight": 16,
            "check": _price_present,
            "critical": True,
        },
        {
            "label": "Moeda",
            "weight": 4,
            "check": lambda r: not is_blank(r.get("currency")),
        },
        {
            "label": "Pedido mínimo",
            "weight": 5,
            "check": lambda r: not is_blank(r.get("min_order_qty")),
        },
        {
            "label": "Informações técnicas",
            "weight": 9,
            "check": _technical_product,
        },
        {
            "label": "Personalização",
            "weight": 6,
            "check": _personalization_product,
        },
        {
            "label": "Imagem / arquivo",
            "weight": 13,
            "check": _media_present,
        },
        {
            "label": "Tags",
            "weight": 4,
            "check": lambda r: not is_blank(r.get("tags")),
        },
        {
            "label": "Documento de origem",
            "weight": 5,
            "check": _source_present,
        },
    ],
    "activation": [
        {
            "label": "Nome",
            "weight": 10,
            "check": lambda r: not is_blank(r.get("name")),
            "critical": True,
        },
        {
            "label": "Categoria",
            "weight": 8,
            "check": lambda r: not is_blank(r.get("category")),
            "critical": True,
        },
        {
            "label": "Descrição",
            "weight": 10,
            "check": lambda r: not is_blank(r.get("description")),
            "critical": True,
        },
        {
            "label": "Fornecedor",
            "weight": 12,
            "check": _supplier_present,
            "critical": True,
        },
        {
            "label": "Preço",
            "weight": 15,
            "check": _price_present,
            "critical": True,
        },
        {
            "label": "Prazo",
            "weight": 8,
            "check": lambda r: not is_blank(r.get("lead_time_days")),
        },
        {
            "label": "Infraestrutura / escopo",
            "weight": 10,
            "check": _infrastructure_activation,
        },
        {
            "label": "Localização",
            "weight": 5,
            "check": lambda r: not is_blank(r.get("location")),
        },
        {
            "label": "Imagem / arquivo",
            "weight": 14,
            "check": _media_present,
        },
        {
            "label": "Tags",
            "weight": 4,
            "check": lambda r: not is_blank(r.get("tags")),
        },
        {
            "label": "Documento de origem",
            "weight": 4,
            "check": _source_present,
        },
    ],
    "venue": [
        {
            "label": "Nome",
            "weight": 10,
            "check": lambda r: not is_blank(r.get("name")),
            "critical": True,
        },
        {
            "label": "Tipo de espaço",
            "weight": 8,
            "check": lambda r: not is_blank(r.get("venue_type")),
        },
        {
            "label": "Descrição",
            "weight": 8,
            "check": lambda r: not is_blank(r.get("description")),
        },
        {
            "label": "Cidade",
            "weight": 10,
            "check": lambda r: not is_blank(r.get("city")),
            "critical": True,
        },
        {
            "label": "Estado",
            "weight": 4,
            "check": lambda r: not is_blank(r.get("state")),
        },
        {
            "label": "Capacidade",
            "weight": 14,
            "check": _capacity_present,
            "critical": True,
        },
        {
            "label": "Preço / condição",
            "weight": 12,
            "check": _price_or_status,
            "critical": True,
        },
        {
            "label": "Infraestrutura",
            "weight": 11,
            "check": _infrastructure_venue,
        },
        {
            "label": "Acessos",
            "weight": 6,
            "check": _venue_access,
        },
        {
            "label": "Imagem / arquivo",
            "weight": 13,
            "check": _media_present,
        },
        {
            "label": "Site / mapa",
            "weight": 4,
            "check": lambda r: any_value(
                r,
                ["website_url", "map_url"],
            ),
        },
    ],
    "supplier": [
        {
            "label": "Nome",
            "weight": 15,
            "check": lambda r: not is_blank(r.get("name")),
            "critical": True,
        },
        {
            "label": "Contato",
            "weight": 15,
            "check": _supplier_contact,
        },
        {
            "label": "Cidade / estado base",
            "weight": 15,
            "check": _supplier_base,
            "critical": True,
        },
        {
            "label": "Cobertura territorial",
            "weight": 20,
            "check": _supplier_coverage,
            "critical": True,
        },
        {
            "label": "Custos logísticos",
            "weight": 10,
            "check": _supplier_logistics,
        },
        {
            "label": "Prazo logístico",
            "weight": 5,
            "check": lambda r: not is_blank(
                r.get("travel_lead_days")
            ),
        },
        {
            "label": "Observações",
            "weight": 5,
            "check": lambda r: any_value(
                r,
                ["coverage_notes", "notes"],
            ),
        },
        {
            "label": "Repertório associado",
            "weight": 10,
            "check": _supplier_repertoire,
        },
        {
            "label": "Site",
            "weight": 5,
            "check": lambda r: not is_blank(
                r.get("website_url")
            ),
        },
    ],
}


def score_record(
    entity_type: str,
    record: dict,
) -> dict:
    schema = SCHEMAS[entity_type]
    score = 0
    missing = []
    critical_missing = []

    for field in schema:
        available = bool(field["check"](record))

        if available:
            score += int(field["weight"])
        else:
            missing.append(field["label"])

            if field.get("critical"):
                critical_missing.append(
                    field["label"]
                )

    score = max(0, min(int(score), 100))

    if score >= 70 and not critical_missing:
        status = "Pronto para recomendação"
    elif score >= 50:
        status = "Em evolução"
    else:
        status = "Prioritário"

    return {
        "quality_score": score,
        "quality_status": status,
        "missing_fields_quality": missing,
        "critical_missing": critical_missing,
        "has_media": _media_present(record),
        "has_price": (
            _price_or_status(record)
            if entity_type == "venue"
            else _price_present(record)
            if entity_type in {"product", "activation"}
            else _supplier_logistics(record)
        ),
    }


def build_quality_records(
    snapshot: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    media = snapshot.get(
        "media",
        pd.DataFrame(),
    )
    media_map = {}

    if not media.empty:
        for _, row in media.iterrows():
            media_map[
                (
                    str(row.get("entity_type")),
                    str(row.get("entity_id")),
                )
            ] = int(row.get("media_count") or 0)

    curation = snapshot.get(
        "curation_states",
        pd.DataFrame(),
    )
    curation_map = {}

    if not curation.empty:
        curation_map = {
            (
                str(row.get("entity_type")),
                str(row.get("entity_id")),
            ): row.to_dict()
            for _, row in curation.iterrows()
        }

    supplier_names = {}
    supplier_counts = {}

    suppliers = snapshot.get(
        "suppliers",
        pd.DataFrame(),
    )
    overview = snapshot.get(
        "supplier_overview",
        pd.DataFrame(),
    )

    if not suppliers.empty:
        supplier_names = {
            str(row.get("id")): row.get("name")
            for _, row in suppliers.iterrows()
        }

    if not overview.empty:
        supplier_counts = {
            str(row.get("supplier_id")): {
                "products_count": row.get(
                    "products_count"
                ),
                "activations_count": row.get(
                    "activations_count"
                ),
                "venues_count": row.get(
                    "venues_count"
                ),
            }
            for _, row in overview.iterrows()
        }

    rows = []

    table_map = {
        "product": snapshot.get(
            "products",
            pd.DataFrame(),
        ),
        "activation": snapshot.get(
            "activations",
            pd.DataFrame(),
        ),
        "venue": snapshot.get(
            "venues",
            pd.DataFrame(),
        ),
        "supplier": suppliers,
    }

    for entity_type, frame in table_map.items():
        if frame is None or frame.empty:
            continue

        for _, source_row in frame.iterrows():
            record = source_row.to_dict()
            entity_id = str(
                record.get("id") or ""
            )

            if entity_type == "product":
                supplier_id = str(
                    record.get("supplier_id") or ""
                )
                record["supplier_name"] = (
                    supplier_names.get(supplier_id)
                )
            elif entity_type == "activation":
                supplier_id = str(
                    record.get("supplier_id") or ""
                )
                record["supplier_name"] = (
                    supplier_names.get(supplier_id)
                )
            elif entity_type == "venue":
                supplier_id = str(
                    record.get("operator_id") or ""
                )
                record["supplier_name"] = (
                    supplier_names.get(supplier_id)
                )
            else:
                record.update(
                    supplier_counts.get(
                        entity_id,
                        {},
                    )
                )

            if entity_type != "supplier":
                record["media_count"] = media_map.get(
                    (entity_type, entity_id),
                    0,
                )

            result = score_record(
                entity_type,
                record,
            )

            curation_state = curation_map.get(
                (entity_type, entity_id),
                {},
            )

            rows.append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "Tipo": TYPE_LABELS[entity_type],
                    "Item": (
                        record.get("name")
                        or "Sem nome"
                    ),
                    "Fornecedor": (
                        record.get("supplier_name")
                        or record.get("name")
                        if entity_type == "supplier"
                        else record.get("supplier_name")
                        or "Não informado"
                    ),
                    "Cidade": (
                        record.get("city")
                        or record.get("base_city")
                        or "Não informada"
                    ),
                    "Pontuação": result[
                        "quality_score"
                    ],
                    "Status": result[
                        "quality_status"
                    ],
                    "Mídia": (
                        "Sim"
                        if result["has_media"]
                        else "Não"
                    ),
                    "Preço / logística": (
                        "Sim"
                        if result["has_price"]
                        else "Não"
                    ),
                    "Lacunas críticas": ", ".join(
                        result["critical_missing"]
                    )
                    or "Nenhuma",
                    "Outras lacunas": ", ".join(
                        field
                        for field in result[
                            "missing_fields_quality"
                        ]
                        if field not in result[
                            "critical_missing"
                        ]
                    )
                    or "Nenhuma",
                    "Validação": {
                        "not_reviewed": "Não revisado",
                        "in_review": "Em revisão",
                        "validated": "Validado",
                        "needs_update": "Precisa de atualização",
                        "archived": "Arquivado",
                    }.get(
                        str(
                            curation_state.get(
                                "validation_status"
                            )
                            or "not_reviewed"
                        ),
                        "Não revisado",
                    ),
                    "Arquivado": (
                        "Sim"
                        if bool(
                            curation_state.get(
                                "is_archived"
                            )
                        )
                        else "Não"
                    ),
                    "_missing": result[
                        "missing_fields_quality"
                    ],
                }
            )

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    result["_status_order"] = result[
        "Status"
    ].map(STATUS_ORDER)

    return result.sort_values(
        by=[
            "_status_order",
            "Pontuação",
            "Tipo",
            "Item",
        ],
        ascending=[
            False,
            True,
            True,
            True,
        ],
    ).reset_index(drop=True)


def type_summary(
    quality: pd.DataFrame,
) -> pd.DataFrame:
    if quality.empty:
        return pd.DataFrame()

    quality = quality[
        quality["Arquivado"].ne("Sim")
    ].copy()

    if quality.empty:
        return pd.DataFrame()

    rows = []

    for entity_type, group in quality.groupby(
        "entity_type",
        sort=False,
    ):
        total = len(group)
        ready = int(
            group["Status"]
            .eq("Pronto para recomendação")
            .sum()
        )
        with_media = int(
            group["Mídia"].eq("Sim").sum()
        )
        with_price = int(
            group[
                "Preço / logística"
            ].eq("Sim").sum()
        )

        rows.append(
            {
                "Tipo": TYPE_LABELS[entity_type],
                "Cadastros": total,
                "Pontuação média": round(
                    float(group["Pontuação"].mean()),
                    1,
                ),
                "Prontos": ready,
                "% prontos": round(
                    ready / total * 100,
                    1,
                ),
                "% com mídia": round(
                    with_media / total * 100,
                    1,
                ),
                "% com preço / logística": round(
                    with_price / total * 100,
                    1,
                ),
            }
        )

    return pd.DataFrame(rows)


def missing_field_summary(
    quality: pd.DataFrame,
) -> pd.DataFrame:
    if quality.empty:
        return pd.DataFrame()

    quality = quality[
        quality["Arquivado"].ne("Sim")
    ].copy()

    if quality.empty:
        return pd.DataFrame()

    rows = []

    for entity_type, group in quality.groupby(
        "entity_type",
        sort=False,
    ):
        counter = Counter()

        for missing in group["_missing"]:
            counter.update(missing or [])

        total = len(group)

        for field, count in counter.most_common():
            rows.append(
                {
                    "Tipo": TYPE_LABELS[
                        entity_type
                    ],
                    "Campo ausente": field,
                    "Cadastros afetados": count,
                    "% do tipo": round(
                        count / total * 100,
                        1,
                    ),
                }
            )

    return pd.DataFrame(rows).sort_values(
        by=[
            "Cadastros afetados",
            "% do tipo",
        ],
        ascending=False,
    ).reset_index(drop=True)


def overall_readiness(
    quality: pd.DataFrame,
) -> dict:
    quality = quality[
        quality["Arquivado"].ne("Sim")
    ].copy()

    if quality.empty:
        return {
            "score": 0,
            "total": 0,
            "ready": 0,
            "priority": 0,
            "with_media": 0,
        }

    total = len(quality)

    return {
        "score": round(
            float(quality["Pontuação"].mean()),
            1,
        ),
        "total": total,
        "ready": int(
            quality["Status"]
            .eq("Pronto para recomendação")
            .sum()
        ),
        "priority": int(
            quality["Status"]
            .eq("Prioritário")
            .sum()
        ),
        "with_media": int(
            quality["Mídia"].eq("Sim").sum()
        ),
    }
