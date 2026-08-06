from __future__ import annotations

import json
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
            "galpões",
            "galpoes",
            "fábrica",
            "fabrica",
            "fábricas",
            "fabricas",
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
            "centros de convenções",
            "centros de convencoes",
            "pavilhão",
            "pavilhao",
            "pavilhões",
            "pavilhoes",
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
            "espaços de eventos",
            "espacos de eventos",
            "casa de eventos",
            "casas de eventos",
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
            "teatro / auditório",
            "teatro / auditorio",
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
            "resorts",
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
            "pubs",
            "boteco",
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
            "galerias",
            "galeria de arte",
            "galerias de arte",
            "museu",
            "museus",
            "centro cultural",
            "espaço cultural",
            "espaco cultural",
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
            "arena",
            "arenas",
            "arena esportiva",
            "arenas esportivas",
            "arena estádio",
            "arena estadio",
            "arena / estádio",
            "arena / estadio",
            "arena/estádio",
            "arena/estadio",
            "estádio arena",
            "estadio arena",
            "estádio / arena",
            "estadio / arena",
            "estádio e arena",
            "estadio e arena",
            "arena e estádio",
            "arena e estadio",
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

_TYPE_BY_NORMALIZED: dict[str, VenueTypeDefinition] = {}
for definition in VENUE_TYPE_DEFINITIONS:
    for term in (
        definition.code,
        definition.label,
        *definition.aliases,
    ):
        normalized_term = normalize_text(term)
        if normalized_term:
            _TYPE_BY_NORMALIZED[normalized_term] = definition


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
    """Retorna o rótulo canônico para aliases explícitos e seguros."""
    normalized = normalize_text(value)
    if not normalized:
        return None
    definition = _TYPE_BY_NORMALIZED.get(normalized)
    return definition.label if definition else None


def display_venue_type(value: Any) -> str:
    canonical = normalize_venue_type(value)
    if canonical:
        return canonical
    return UNDEFINED_VENUE_TYPE


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
    """Valores vazios, genéricos ou não reconhecidos são não definidos."""
    return normalize_venue_type(value) is None


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def original_type_candidates(record: dict[str, Any]) -> list[str]:
    """Lê campos explícitos de categoria, sem inferir pelo nome."""
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
        "grupo_local",
        "GRUPO_LOCAL",
    ):
        value = record.get(key)
        if value is not None and str(value).strip():
            candidates.append(str(value).strip())

    raw_data = _json_dict(record.get("raw_data"))
    for key in (
        "venue_type",
        "category",
        "tipo_local_padronizado",
        "tipo_local",
        "categoria",
        "CATEGORIA",
        "TIPO_LOCAL_PADRONIZADO",
        "TIPO_LOCAL",
        "grupo_local",
        "GRUPO_LOCAL",
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
    """Classifica somente por campos explícitos com alias reconhecido."""
    for candidate in original_type_candidates(record):
        canonical = normalize_venue_type(candidate)
        if canonical:
            return canonical
    return None


def _record_canonical_type(record: dict[str, Any]) -> str | None:
    return (
        normalize_venue_type(record.get("venue_type"))
        or safe_type_from_record(record)
    )


def venue_identity_name(value: Any) -> str:
    """
    Normaliza o nome usado para identificar repetições.

    Remove apenas um complemento final entre parênteses. Assim:
    - Allianz Parque
    - Allianz Parque (Nubank Parque)

    entram no mesmo grupo, mas Parque Mirante continua independente.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    return normalize_text(text)


def _record_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return value

    raw_data = _json_dict(record.get("raw_data"))
    for key in keys:
        value = raw_data.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _location_compatible(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    """
    Evita esconder locais homônimos em cidades ou estados diferentes.

    Campo ausente funciona como desconhecido, não como divergência.
    """
    field_groups = (
        ("state", "estado", "ESTADO"),
        ("city", "cidade", "CIDADE"),
        ("postal_code", "cep", "CEP"),
    )
    for keys in field_groups:
        left = normalize_text(_record_value(first, *keys))
        right = normalize_text(_record_value(second, *keys))
        if left and right and left != right:
            return False
    return True


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and normalize_text(value) not in {
            "nao informado",
            "sem informacao",
            "none",
            "null",
        }
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _record_completeness(record: dict[str, Any]) -> int:
    fields = (
        "venue_type",
        "description",
        "address",
        "neighborhood",
        "city",
        "state",
        "postal_code",
        "website_url",
        "source_image_url",
        "standing_capacity",
        "seated_capacity",
        "auditorium_capacity",
        "total_area_sqm",
        "parking",
        "accessibility",
        "loading_access",
        "kitchen_or_catering",
        "audiovisual",
        "infrastructure",
        "tags",
    )
    score = sum(_is_present(record.get(field)) for field in fields)
    score += min(len(_json_dict(record.get("raw_data"))), 10)
    if _record_canonical_type(record):
        score += 3
    return score


def deduplicate_venue_records(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Exibe somente uma linha para repetições fortes do mesmo local.

    A função não apaga nem une registros. A união definitiva continua
    exclusivamente na tela Revisar duplicidades.
    """
    clusters: list[list[dict[str, Any]]] = []
    standalone: list[dict[str, Any]] = []

    for record in records:
        identity = venue_identity_name(record.get("name"))
        if not identity:
            standalone.append(record)
            continue

        destination: list[dict[str, Any]] | None = None
        for cluster in clusters:
            cluster_identity = venue_identity_name(cluster[0].get("name"))
            if cluster_identity != identity:
                continue
            if any(_location_compatible(record, item) for item in cluster):
                destination = cluster
                break

        if destination is None:
            clusters.append([record])
        else:
            destination.append(record)

    representatives: list[dict[str, Any]] = []
    for cluster in clusters:
        representative = max(
            cluster,
            key=_record_completeness,
        )
        representatives.append(representative)

    result = representatives + standalone
    return sorted(
        result,
        key=lambda record: str(record.get("name") or "").casefold(),
    )


def filter_records_by_type(
    records: Iterable[dict[str, Any]],
    selected_type: str,
) -> list[dict[str, Any]]:
    """
    Filtra pelo tipo canônico e remove repetições fortes somente da exibição.
    """
    records = list(records)

    if selected_type == ALL_VENUE_TYPES:
        filtered = records
    elif selected_type == UNDEFINED_VENUE_TYPE:
        filtered = [
            record
            for record in records
            if _record_canonical_type(record) is None
        ]
    else:
        canonical_selected = normalize_venue_type(selected_type)
        if not canonical_selected:
            return []
        filtered = [
            record
            for record in records
            if _record_canonical_type(record) == canonical_selected
        ]

    return deduplicate_venue_records(filtered)
