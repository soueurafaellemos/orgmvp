from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable


UNDEFINED_VENUE_TYPE = "Tipo não definido"
ALL_VENUE_TYPES = "Todos"


@dataclass(frozen=True)
class VenueTypeDefinition:
    code: str
    label: str
    group: str
    aliases: tuple[str, ...]


VENUE_TYPE_DEFINITIONS: tuple[VenueTypeDefinition, ...] = (
    VenueTypeDefinition(
        code="industrial",
        label="Galpão / Fábrica",
        group="Industrial",
        aliases=(
            "galpão",
            "galpao",
            "fábrica",
            "fabrica",
            "galpão industrial",
            "galpao industrial",
            "galpão / fábrica",
            "galpao / fabrica",
            "warehouse",
            "industrial venue",
        ),
    ),
    VenueTypeDefinition(
        code="convencoes_pavilhoes",
        label="Centro de Convenções / Pavilhão",
        group="Convenções",
        aliases=(
            "centro de convenções",
            "centro de convencoes",
            "pavilhão",
            "pavilhao",
            "centro de convenções/ pavilhão",
            "centro de convencoes/ pavilhao",
            "centro de convenções / pavilhão",
            "centro de convencoes / pavilhao",
            "convention center",
            "convention centre",
            "exhibition hall",
            "exhibition pavilion",
        ),
    ),
    VenueTypeDefinition(
        code="espacos_eventos",
        label="Espaço de Eventos",
        group="Hospitalidade e eventos",
        aliases=(
            "espaço de eventos",
            "espaco de eventos",
            "casa de eventos",
            "event venue",
            "event space",
        ),
    ),
    VenueTypeDefinition(
        code="casas_show",
        label="Casas de Show",
        group="Entretenimento",
        aliases=(
            "casa de show",
            "casas de show",
            "show house",
            "music venue",
            "concert venue",
        ),
    ),
    VenueTypeDefinition(
        code="teatros_auditorios",
        label="Teatros / Auditórios",
        group="Cultural e conteúdo",
        aliases=(
            "teatro",
            "teatros",
            "auditório",
            "auditorio",
            "auditórios",
            "auditorios",
            "teatros / auditórios",
            "teatros / auditorios",
            "theater",
            "theatre",
            "auditorium",
        ),
    ),
    VenueTypeDefinition(
        code="hoteis",
        label="Hotéis",
        group="Hospitalidade",
        aliases=(
            "hotel",
            "hotéis",
            "hoteis",
            "resort",
            "hotel ballroom",
        ),
    ),
    VenueTypeDefinition(
        code="bares",
        label="Bares",
        group="Gastronomia e hospitalidade",
        aliases=(
            "bar",
            "bares",
            "pub",
            "rooftop bar",
        ),
    ),
    VenueTypeDefinition(
        code="restaurantes",
        label="Restaurantes",
        group="Gastronomia e hospitalidade",
        aliases=(
            "restaurante",
            "restaurantes",
            "restaurant",
            "dining venue",
        ),
    ),
    VenueTypeDefinition(
        code="galerias_arte",
        label="Galerias de Arte",
        group="Cultural",
        aliases=(
            "galeria",
            "galeria de arte",
            "galerias de arte",
            "museu",
            "centro cultural",
            "art gallery",
            "museum",
            "cultural center",
            "cultural centre",
        ),
    ),
    VenueTypeDefinition(
        code="estadios",
        label="Estádios",
        group="Esportivo",
        aliases=(
            "estádio",
            "estadio",
            "estádios",
            "estadios",
            "arena esportiva",
            "sports arena",
            "stadium",
        ),
    ),
)


def normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_TYPE_BY_LABEL = {
    definition.label: definition
    for definition in VENUE_TYPE_DEFINITIONS
}
_TYPE_BY_NORMALIZED = {
    normalize_text(term): definition
    for definition in VENUE_TYPE_DEFINITIONS
    for term in (definition.label, *definition.aliases)
}


def venue_type_options(*, include_all: bool = False) -> list[str]:
    options = [
        definition.label
        for definition in VENUE_TYPE_DEFINITIONS
    ]
    options.append(UNDEFINED_VENUE_TYPE)
    if include_all:
        options.insert(0, ALL_VENUE_TYPES)
    return options


def normalize_venue_type(value: Any) -> str | None:
    """Return a canonical label only when the match is explicit and safe."""
    normalized = normalize_text(value)
    if not normalized:
        return None
    definition = _TYPE_BY_NORMALIZED.get(normalized)
    return definition.label if definition else None


def display_venue_type(value: Any) -> str:
    canonical = normalize_venue_type(value)
    if canonical:
        return canonical
    text = str(value or "").strip()
    return text or UNDEFINED_VENUE_TYPE


def venue_group(value: Any) -> str:
    canonical = normalize_venue_type(value)
    if not canonical:
        return "Sem definição"
    return _TYPE_BY_LABEL[canonical].group


def venue_type_code(value: Any) -> str | None:
    canonical = normalize_venue_type(value)
    if not canonical:
        return None
    return _TYPE_BY_LABEL[canonical].code


def is_undefined_venue_type(value: Any) -> bool:
    return not str(value or "").strip()


def original_type_candidates(record: dict[str, Any]) -> list[str]:
    """Read only explicit category fields; never infer from name/description."""
    candidates: list[str] = []

    for key in (
        "venue_type",
        "category",
        "tipo_local_padronizado",
        "tipo_local",
        "categoria",
        "CATEGORIA",
        "TIPO_LOCAL_PADRONIZADO",
        "TIPO_LOCAL",
    ):
        value = record.get(key)
        if value is not None and str(value).strip():
            candidates.append(str(value).strip())

    raw_data = record.get("raw_data")
    if isinstance(raw_data, dict):
        for key in (
            "venue_type",
            "category",
            "tipo_local_padronizado",
            "tipo_local",
            "categoria",
            "CATEGORIA",
            "TIPO_LOCAL_PADRONIZADO",
            "TIPO_LOCAL",
        ):
            value = raw_data.get(key)
            if value is not None and str(value).strip():
                candidates.append(str(value).strip())

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = normalize_text(candidate)
        if key and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def safe_type_from_record(record: dict[str, Any]) -> str | None:
    """Classify only from explicit category fields with an exact alias match."""
    for candidate in original_type_candidates(record):
        canonical = normalize_venue_type(candidate)
        if canonical:
            return canonical
    return None


def filter_records_by_type(
    records: Iterable[dict[str, Any]],
    selected_type: str,
) -> list[dict[str, Any]]:
    records = list(records)
    if selected_type == ALL_VENUE_TYPES:
        return records
    if selected_type == UNDEFINED_VENUE_TYPE:
        return [
            record
            for record in records
            if is_undefined_venue_type(record.get("venue_type"))
        ]
    return [
        record
        for record in records
        if normalize_venue_type(record.get("venue_type")) == selected_type
    ]
