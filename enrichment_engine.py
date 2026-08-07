from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from typing import Any

import pandas as pd


PLACEHOLDER_VALUES = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "não informado",
    "nao informado",
    "não informada",
    "nao informada",
    "não disponível",
    "nao disponivel",
    "não se aplica",
    "nao se aplica",
    "indisponível",
    "indisponivel",
    "sem informação",
    "sem informacao",
    "null",
    "none",
}

ARRAY_FIELDS = {
    "tags",
    "missing_fields",
    "included_items",
    "excluded_items",
    "infrastructure_requirements",
    "rooms_or_areas",
    "infrastructure",
    "restrictions",
    "served_states",
    "served_cities",
    "local_team_locations",
    "supplier_categories",
    "specialties",
    "services_offered",
    "client_brands",
    "market_segments",
    "certifications",
    "direct_states",
    "partner_states",
    "technical_structure",
}

DICT_FIELDS = {"raw_data", "profile_data"}

SOURCE_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "import_id",
    "source_file_id",
    "source_file",
    "source_page",
    "source_image_url",
}

CONFIDENCE_FIELDS = {"confidence"}

EVIDENCE_FIELDS = {"evidence"}

STRATEGY_LABELS = {
    "enrich_safe": (
        "Preencher lacunas e sinalizar diferenças "
        "(recomendado)"
    ),
    "prefer_new": (
        "Usar o arquivo mais recente quando houver diferenças"
    ),
    "new_only": "Adicionar somente itens novos",
}


def _normalized_text(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_blank(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        return _normalized_text(value) in PLACEHOLDER_VALUES

    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0

    return False


def _json_safe(value: Any) -> Any:
    if is_blank(value):
        return None

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def _list_value(value: Any) -> list[Any]:
    if is_blank(value):
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, (tuple, set)):
        return list(value)

    if isinstance(value, str) and "|" in value:
        return [
            item.strip()
            for item in value.split("|")
            if item.strip()
        ]

    return [value]


def merge_lists(
    current: Any,
    incoming: Any,
) -> list[Any]:
    result = []
    seen = set()

    for item in _list_value(current) + _list_value(incoming):
        if is_blank(item):
            continue

        if isinstance(item, dict):
            marker = json.dumps(
                _json_safe(item),
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        else:
            marker = _normalized_text(item)

        if marker in seen:
            continue

        seen.add(marker)
        result.append(_json_safe(item))

    return result


def values_equal(
    current: Any,
    incoming: Any,
) -> bool:
    if is_blank(current) and is_blank(incoming):
        return True

    if isinstance(current, (list, tuple, set)) or isinstance(
        incoming,
        (list, tuple, set),
    ):
        current_markers = {
            _normalized_text(item)
            for item in _list_value(current)
            if not is_blank(item)
        }
        incoming_markers = {
            _normalized_text(item)
            for item in _list_value(incoming)
            if not is_blank(item)
        }
        return current_markers == incoming_markers

    if isinstance(current, dict) or isinstance(incoming, dict):
        return json.dumps(
            _json_safe(current),
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ) == json.dumps(
            _json_safe(incoming),
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

    try:
        current_number = float(current)
        incoming_number = float(incoming)
        return abs(current_number - incoming_number) < 0.000001
    except (TypeError, ValueError):
        pass

    return _normalized_text(current) == _normalized_text(incoming)


def _merge_dicts(
    current: dict | None,
    incoming: dict | None,
    *,
    prefer_new: bool,
) -> dict:
    result = deepcopy(current or {})

    for key, value in (incoming or {}).items():
        if is_blank(value):
            continue

        if key not in result or is_blank(result.get(key)):
            result[key] = _json_safe(value)
            continue

        if isinstance(result.get(key), dict) and isinstance(
            value,
            dict,
        ):
            result[key] = _merge_dicts(
                result.get(key),
                value,
                prefer_new=prefer_new,
            )
            continue

        if isinstance(result.get(key), list) or isinstance(
            value,
            list,
        ):
            result[key] = merge_lists(
                result.get(key),
                value,
            )
            continue

        if prefer_new and not values_equal(
            result.get(key),
            value,
        ):
            result[key] = _json_safe(value)

    return result


def _merge_evidence(
    current: Any,
    incoming: Any,
) -> str | None:
    values = []

    for value in (current, incoming):
        if is_blank(value):
            continue

        text = str(value).strip()
        marker = _normalized_text(text)

        if marker not in {
            _normalized_text(item)
            for item in values
        }:
            values.append(text)

    return "\n\n".join(values) if values else None


def _confidence_value(value: Any) -> float | None:
    if is_blank(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def merge_record(
    existing: dict,
    incoming: dict,
    *,
    allowed_fields: set[str],
    strategy: str,
) -> dict:
    if strategy not in {
        "enrich_safe",
        "prefer_new",
    }:
        raise ValueError(
            f"Estratégia de enriquecimento inválida: {strategy}"
        )

    prefer_new = strategy == "prefer_new"

    applied_changes: dict[str, Any] = {}
    filled_fields: list[str] = []
    updated_fields: list[str] = []
    merged_fields: list[str] = []
    conflicts: list[dict] = []

    for field in sorted(allowed_fields):
        if field in SOURCE_FIELDS:
            continue

        incoming_value = incoming.get(field)

        if is_blank(incoming_value):
            continue

        current_value = existing.get(field)

        if field in DICT_FIELDS:
            merged = _merge_dicts(
                current_value
                if isinstance(current_value, dict)
                else {},
                incoming_value
                if isinstance(incoming_value, dict)
                else {},
                prefer_new=prefer_new,
            )

            if not values_equal(current_value, merged):
                applied_changes[field] = merged
                merged_fields.append(field)
            continue

        if field in ARRAY_FIELDS:
            merged = merge_lists(
                current_value,
                incoming_value,
            )

            if not values_equal(current_value, merged):
                applied_changes[field] = merged
                merged_fields.append(field)
            continue

        if field in EVIDENCE_FIELDS:
            merged = _merge_evidence(
                current_value,
                incoming_value,
            )

            if not values_equal(current_value, merged):
                applied_changes[field] = merged
                merged_fields.append(field)
            continue

        if field in CONFIDENCE_FIELDS:
            current_confidence = _confidence_value(
                current_value
            )
            incoming_confidence = _confidence_value(
                incoming_value
            )

            candidates = [
                value
                for value in (
                    current_confidence,
                    incoming_confidence,
                )
                if value is not None
            ]

            if candidates:
                best = max(candidates)
                if not values_equal(current_value, best):
                    applied_changes[field] = best
                    updated_fields.append(field)
            continue

        if is_blank(current_value):
            applied_changes[field] = _json_safe(
                incoming_value
            )
            filled_fields.append(field)
            continue

        if values_equal(current_value, incoming_value):
            continue

        conflict = {
            "field": field,
            "existing_value": _json_safe(current_value),
            "incoming_value": _json_safe(incoming_value),
            "action": (
                "updated_with_new_value"
                if prefer_new
                else "kept_existing_value"
            ),
        }
        conflicts.append(conflict)

        if prefer_new:
            applied_changes[field] = _json_safe(
                incoming_value
            )
            updated_fields.append(field)

    # Remove fields from missing_fields when they have just been filled.
    current_missing = merge_lists(
        existing.get("missing_fields"),
        incoming.get("missing_fields"),
    )

    if current_missing:
        filled_markers = {
            _normalized_text(field)
            for field in filled_fields
        }
        cleaned_missing = [
            item
            for item in current_missing
            if _normalized_text(item) not in filled_markers
        ]

        if not values_equal(
            existing.get("missing_fields"),
            cleaned_missing,
        ):
            applied_changes["missing_fields"] = cleaned_missing

    return {
        "applied_changes": applied_changes,
        "filled_fields": filled_fields,
        "updated_fields": updated_fields,
        "merged_fields": merged_fields,
        "conflicts": conflicts,
    }
