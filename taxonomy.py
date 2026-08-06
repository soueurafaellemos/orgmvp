from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Iterable

from taxonomy_research_data import (
    RESEARCH_DATE,
    RESEARCH_SOURCES,
    TERM_DEFINITIONS,
)


DOMAIN_LABELS = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
}

DIMENSION_LABELS = {
    "event_format": "Formato de evento",
    "experience_format": "Formato de experiência",
    "mechanic": "Mecânica",
    "technology": "Tecnologia",
    "objective": "Objetivo",
    "production_service": "Serviço de produção",
    "product_category": "Categoria de brinde",
    "venue_type": "Tipo de espaço",
    "venue_attribute": "Atributo do espaço",
}


# ------------------------------------------------------------------
# Normalização e estrutura
# ------------------------------------------------------------------
def normalize_taxonomy_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold().replace("&", " e ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[|,;\n]", str(value))
    return [
        str(item).strip()
        for item in values
        if str(item).strip()
    ]


def taxonomy_dimensions(entity_type: str | None = None) -> list[str]:
    dimensions: list[str] = []
    for term in TERM_DEFINITIONS:
        if entity_type and term["entity_type"] != entity_type:
            continue
        dimension = str(term["dimension"])
        if dimension not in dimensions:
            dimensions.append(dimension)
    return dimensions


def taxonomy_terms_for_dimension(
    entity_type: str,
    dimension: str,
) -> list[str]:
    return sorted(
        {
            str(term["canonical_term"])
            for term in TERM_DEFINITIONS
            if term["entity_type"] == entity_type
            and term["dimension"] == dimension
        }
    )


def taxonomy_options(entity_type: str) -> list[str]:
    """Categories available in the manual category selector."""
    return sorted(
        {
            str(term["canonical_term"])
            for term in TERM_DEFINITIONS
            if term["entity_type"] == entity_type
            and bool(term.get("primary_eligible"))
        }
    )


def taxonomy_source_rows() -> list[dict]:
    return [
        {"source_id": source_id, **source}
        for source_id, source in RESEARCH_SOURCES.items()
    ]


def taxonomy_term_rows() -> list[dict]:
    return [
        {
            **term,
            "entity_label": DOMAIN_LABELS.get(
                term["entity_type"], term["entity_type"]
            ),
            "dimension_label": DIMENSION_LABELS.get(
                term["dimension"], term["dimension"]
            ),
            "source_count": len(term.get("source_ids") or []),
            "alias_count": len(term.get("aliases") or []),
        }
        for term in TERM_DEFINITIONS
    ]


def _term_lookup() -> dict[tuple[str, str, str], dict]:
    return {
        (
            str(term["entity_type"]),
            str(term["dimension"]),
            str(term["canonical_term"]),
        ): term
        for term in TERM_DEFINITIONS
    }


def _terms_by_canonical(
    entity_type: str,
    canonical_term: str,
) -> list[dict]:
    return [
        term
        for term in TERM_DEFINITIONS
        if term["entity_type"] == entity_type
        and term["canonical_term"] == canonical_term
    ]


def _infer_custom_dimension(row: dict) -> str:
    entity_type = str(row.get("entity_type") or "")
    canonical = str(row.get("canonical_term") or "")
    matches = _terms_by_canonical(entity_type, canonical)

    if len(matches) == 1:
        return str(matches[0]["dimension"])

    stored = str(row.get("dimension") or "").strip()
    if stored in DIMENSION_LABELS:
        return stored

    return {
        "product": "product_category",
        "venue": "venue_type",
        "activation": "experience_format",
    }.get(entity_type, "experience_format")


# ------------------------------------------------------------------
# Aliases padrão e personalizados
# ------------------------------------------------------------------
def default_alias_rows() -> list[dict]:
    rows: list[dict] = []
    for term in TERM_DEFINITIONS:
        for alias in term.get("aliases") or []:
            rows.append(
                {
                    "entity_type": term["entity_type"],
                    "dimension": term["dimension"],
                    "canonical_key": term["key"],
                    "canonical_term": term["canonical_term"],
                    "parent": term.get("parent"),
                    "alias": alias,
                    "normalized_alias": normalize_taxonomy_text(alias),
                    "semantic_tags": term.get("semantic_tags") or [],
                    "source_ids": term.get("source_ids") or [],
                    "confidence": term.get("confidence", "Média"),
                    "research_status": term.get(
                        "research_status", "Pesquisado"
                    ),
                    "alias_basis": term.get(
                        "alias_basis",
                        "Pesquisa setorial + expansão linguística",
                    ),
                    "primary_eligible": bool(
                        term.get("primary_eligible")
                    ),
                    "source": "research",
                    "is_active": True,
                }
            )
    return rows


def _active_custom_rows(
    custom_aliases: Iterable[dict] | None,
) -> list[dict]:
    lookup = _term_lookup()
    rows: list[dict] = []

    for source_row in custom_aliases or []:
        row = dict(source_row)
        if not row.get("is_active", True):
            continue

        entity_type = str(row.get("entity_type") or "")
        canonical_term = str(row.get("canonical_term") or "")
        alias = str(row.get("alias") or "").strip()
        dimension = _infer_custom_dimension(row)

        if (
            entity_type not in DOMAIN_LABELS
            or not canonical_term
            or not alias
        ):
            continue

        term = lookup.get(
            (entity_type, dimension, canonical_term), {}
        )
        rows.append(
            {
                **row,
                "entity_type": entity_type,
                "dimension": dimension,
                "canonical_key": row.get("canonical_key")
                or term.get("key"),
                "canonical_term": canonical_term,
                "parent": term.get("parent"),
                "normalized_alias": row.get("normalized_alias")
                or normalize_taxonomy_text(alias),
                "semantic_tags": term.get("semantic_tags") or [],
                "source_ids": term.get("source_ids") or [],
                "confidence": row.get("confidence") or "Curadoria VOE",
                "research_status": "Personalizado",
                "alias_basis": "Curadoria VOE",
                "primary_eligible": bool(
                    term.get("primary_eligible")
                ),
                "source": "custom",
                "is_active": True,
            }
        )
    return rows


def taxonomy_catalog_rows(
    custom_aliases: Iterable[dict] | None = None,
) -> list[dict]:
    rows = default_alias_rows()
    rows.extend(_active_custom_rows(custom_aliases))

    # Keep different dimensions separate. Inside one dimension, a custom
    # alias overrides the research alias with the same normalized spelling.
    unique: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = (
            str(row["entity_type"]),
            str(row["dimension"]),
            str(row["normalized_alias"]),
            str(row["canonical_term"]),
        )
        unique[key] = row
    return list(unique.values())


def aliases_for_canonical(
    entity_type: str,
    canonical_term: str,
    custom_aliases: Iterable[dict] | None = None,
    dimension: str | None = None,
) -> list[str]:
    aliases = [
        str(row["alias"])
        for row in taxonomy_catalog_rows(custom_aliases)
        if row["entity_type"] == entity_type
        and row["canonical_term"] == canonical_term
        and (dimension is None or row["dimension"] == dimension)
    ]
    return list(dict.fromkeys(aliases))


def _alias_index(
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
    dimension: str | None = None,
) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for row in taxonomy_catalog_rows(custom_aliases):
        if row["entity_type"] != entity_type:
            continue
        if dimension is not None and row["dimension"] != dimension:
            continue
        normalized = str(row["normalized_alias"])
        if normalized:
            index.setdefault(normalized, []).append(row)
    return index


def _phrase_present(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return bool(
        re.search(
            rf"(?:^|\s){re.escape(phrase)}(?:$|\s)",
            text,
        )
    )


def _unique_canonical_rows(rows: Iterable[dict]) -> list[dict]:
    unique: dict[tuple[str, str], dict] = {}
    for row in rows:
        unique[(str(row["dimension"]), str(row["canonical_term"]))] = row
    return list(unique.values())


def _resolve_ambiguous_alias(
    normalized_query: str,
    rows: list[dict],
) -> dict | None:
    unique_rows = _unique_canonical_rows(rows)
    if len(unique_rows) == 1:
        return unique_rows[0]

    # A literal canonical name is stronger than a generic shared alias.
    canonical_matches = [
        row
        for row in unique_rows
        if normalize_taxonomy_text(row["canonical_term"])
        == normalized_query
    ]
    if len(canonical_matches) == 1:
        return canonical_matches[0]

    # Do not silently force a shared generic expression into one category.
    return None


def _row_result(
    row: dict,
    *,
    confidence: float,
    method: str,
) -> dict:
    return {
        "canonical": row["canonical_term"],
        "canonical_key": row.get("canonical_key"),
        "dimension": row["dimension"],
        "dimension_label": DIMENSION_LABELS.get(
            row["dimension"], row["dimension"]
        ),
        "parent": row.get("parent"),
        "matched_alias": row["alias"],
        "confidence": round(float(confidence), 4),
        "method": method,
        "source_ids": row.get("source_ids") or [],
        "research_status": row.get(
            "research_status", "Pesquisado"
        ),
        "primary_eligible": bool(row.get("primary_eligible")),
    }


# ------------------------------------------------------------------
# Matching conservador
# ------------------------------------------------------------------
def match_taxonomy(
    value: Any,
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
    *,
    dimension: str | None = None,
    allow_fuzzy: bool = True,
) -> dict | None:
    normalized = normalize_taxonomy_text(value)
    if not normalized:
        return None

    index = _alias_index(entity_type, custom_aliases, dimension)
    exact_rows = index.get(normalized) or []
    if exact_rows:
        resolved = _resolve_ambiguous_alias(normalized, exact_rows)
        if resolved:
            return _row_result(
                resolved,
                confidence=1.0,
                method="exact_alias",
            )
        return None

    phrase_matches: list[tuple[int, dict]] = []
    for alias, rows in index.items():
        if len(alias) < 4 or not _phrase_present(normalized, alias):
            continue
        resolved = _resolve_ambiguous_alias(alias, rows)
        if resolved:
            phrase_matches.append((len(alias), resolved))

    if phrase_matches:
        phrase_matches.sort(key=lambda item: item[0], reverse=True)
        return _row_result(
            phrase_matches[0][1],
            confidence=0.96,
            method="phrase_alias",
        )

    if not allow_fuzzy or len(normalized) > 60:
        return None

    ranked: list[tuple[float, dict]] = []
    for alias, rows in index.items():
        if len(alias) < 4:
            continue
        resolved = _resolve_ambiguous_alias(alias, rows)
        if not resolved:
            continue
        score = SequenceMatcher(None, normalized, alias).ratio()
        if score >= 0.84:
            ranked.append((score, resolved))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best_row = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < 0.87 or best_score - second_score < 0.025:
        return None

    return _row_result(
        best_row,
        confidence=best_score,
        method="fuzzy_alias",
    )


def detect_taxonomy_terms(
    text: Any,
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
    *,
    dimensions: Iterable[str] | None = None,
    limit: int = 28,
) -> list[dict]:
    normalized = normalize_taxonomy_text(text)
    if not normalized:
        return []

    allowed_dimensions = set(dimensions) if dimensions is not None else None
    matches: dict[tuple[str, str], dict] = {}

    for alias, rows in _alias_index(entity_type, custom_aliases).items():
        if len(alias) < 3 or not _phrase_present(normalized, alias):
            continue
        resolved = _resolve_ambiguous_alias(alias, rows)
        if not resolved:
            continue
        if (
            allowed_dimensions is not None
            and resolved["dimension"] not in allowed_dimensions
        ):
            continue

        key = (
            str(resolved["dimension"]),
            str(resolved["canonical_term"]),
        )
        candidate = {
            **_row_result(
                resolved,
                confidence=0.94,
                method="text_alias",
            ),
            "_alias_length": len(alias),
        }
        current = matches.get(key)
        if current is None or candidate["_alias_length"] > current["_alias_length"]:
            matches[key] = candidate

    ranked = sorted(
        matches.values(),
        key=lambda item: item["_alias_length"],
        reverse=True,
    )[:limit]
    for item in ranked:
        item.pop("_alias_length", None)
    return ranked


def semantic_tags_for(
    entity_type: str,
    canonical_terms: Iterable[str],
) -> list[str]:
    wanted = set(canonical_terms)
    tags: list[str] = []
    for term in TERM_DEFINITIONS:
        if (
            term["entity_type"] == entity_type
            and term["canonical_term"] in wanted
        ):
            tags.extend(term.get("semantic_tags") or [])
    return list(dict.fromkeys(tags))


# ------------------------------------------------------------------
# Record normalization and search expansion
# ------------------------------------------------------------------
def _choose_primary_match(
    original_category: Any,
    detected: list[dict],
    entity_type: str,
    custom_aliases: Iterable[dict] | None,
) -> dict | None:
    direct = match_taxonomy(
        original_category,
        entity_type,
        custom_aliases,
    )
    if direct and direct.get("primary_eligible"):
        return direct
    for item in detected:
        if item.get("primary_eligible"):
            return item
    return None


def normalize_record_taxonomy(
    record: dict,
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
) -> dict:
    result = dict(record)
    category_field = "venue_type" if entity_type == "venue" else "category"
    original_category = result.get(category_field)
    existing_tags = _as_list(result.get("tags"))

    context = " ".join(
        [
            str(result.get("name") or ""),
            str(original_category or ""),
            str(result.get("description") or ""),
            " ".join(existing_tags),
        ]
    )
    detected = detect_taxonomy_terms(
        context,
        entity_type,
        custom_aliases,
    )
    primary = _choose_primary_match(
        original_category,
        detected,
        entity_type,
        custom_aliases,
    )

    canonical = (
        primary.get("canonical")
        if primary
        else str(original_category or "").strip() or None
    )
    term_labels = [str(item["canonical"]) for item in detected]
    dimension_tags = [
        f"{item['dimension_label']}: {item['canonical']}"
        for item in detected
    ]
    semantic_tags = semantic_tags_for(entity_type, term_labels)
    merged_tags = list(
        dict.fromkeys(
            [
                *existing_tags,
                *term_labels,
                *dimension_tags,
                *semantic_tags,
            ]
        )
    )

    if canonical:
        result[category_field] = canonical
    if entity_type in DOMAIN_LABELS:
        result["tags"] = merged_tags

    result["taxonomy_original_category"] = original_category
    result["taxonomy_canonical_category"] = canonical
    result["taxonomy_terms"] = term_labels
    result["taxonomy_matches"] = detected
    result["taxonomy_matched_aliases"] = [
        item["matched_alias"] for item in detected
    ]
    result["taxonomy_dimensions"] = {
        dimension: [
            item["canonical"]
            for item in detected
            if item["dimension"] == dimension
        ]
        for dimension in taxonomy_dimensions(entity_type)
    }
    if primary:
        result["taxonomy_category_match"] = primary
    return result


def annotate_candidate_taxonomy(
    row: dict,
    custom_aliases: Iterable[dict] | None = None,
) -> dict:
    entity_type = str(row.get("item_type") or "")
    if entity_type not in DOMAIN_LABELS:
        return {
            "category_nave": row.get("category") or "Não informado",
            "taxonomy_terms": [],
            "taxonomy_search_text": "",
            "taxonomy_dimensions": {},
        }

    normalized = normalize_record_taxonomy(
        {
            "name": row.get("name"),
            "category": row.get("category"),
            "venue_type": row.get("category"),
            "description": row.get("description"),
            "tags": row.get("tags"),
        },
        entity_type,
        custom_aliases,
    )
    canonical = (
        normalized.get("taxonomy_canonical_category")
        or row.get("category")
        or "Não informado"
    )
    matches = normalized.get("taxonomy_matches", [])
    aliases: list[str] = []
    for item in matches:
        aliases.extend(
            aliases_for_canonical(
                entity_type,
                item["canonical"],
                custom_aliases,
                item["dimension"],
            )
        )

    search_text = " ".join(
        [
            str(row.get("name") or ""),
            str(row.get("category") or ""),
            str(canonical or ""),
            str(row.get("description") or ""),
            str(row.get("supplier_name") or ""),
            str(row.get("location") or ""),
            " ".join(_as_list(row.get("tags"))),
            " ".join(item["canonical"] for item in matches),
            " ".join(item["dimension_label"] for item in matches),
            " ".join(aliases),
        ]
    )
    return {
        "category_nave": canonical,
        "taxonomy_terms": [item["canonical"] for item in matches],
        "taxonomy_search_text": search_text,
        "taxonomy_dimensions": normalized.get("taxonomy_dimensions", {}),
    }


# ------------------------------------------------------------------
# Gemini prompt context
# ------------------------------------------------------------------
def taxonomy_prompt_block(entity_type: str) -> str:
    dimension_lines: list[str] = []
    for dimension in taxonomy_dimensions(entity_type):
        options = taxonomy_terms_for_dimension(entity_type, dimension)
        preview = options[:28]
        dimension_lines.append(
            f"{DIMENSION_LABELS.get(dimension, dimension)}: "
            + ", ".join(preview)
            + ("..." if len(options) > len(preview) else "")
        )

    examples = {
        "activation": (
            "Exemplo: phopp, photopp, photo opportunity, selfie spot "
            "e espaço instagramável representam Photo-op. VR é uma "
            "tecnologia; quiz é uma mecânica; lançamento é formato ou "
            "objetivo conforme o contexto."
        ),
        "product": (
            "Exemplo: squeeze, tumbler e travel mug pertencem à família "
            "de copos, canecas e garrafas; backpack e tote bag pertencem "
            "às famílias de bolsas."
        ),
        "venue": (
            "Exemplo: warehouse e galpão descrevem tipo de espaço; "
            "rooftop, waterfront, luz natural e sem pilares também podem "
            "ser atributos do espaço."
        ),
    }
    return (
        "\n\nTAXONOMIA HIERÁRQUICA NAVE "
        f"(pesquisa pública atualizada em {RESEARCH_DATE}):\n"
        "Preserve o nome original. Não trate formato, mecânica, tecnologia, "
        "objetivo, serviço e atributo como se fossem o mesmo nível.\n- "
        + "\n- ".join(dimension_lines)
        + "\n"
        + examples.get(entity_type, "")
        + "\nNão force correspondências quando a fonte não permitir uma "
        "associação segura."
    )
