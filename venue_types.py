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


def _candidate_values(value: Any) -> list[str]:
    """Transforma campos escalares/listas em candidatos textuais úteis."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_candidate_values(item))
        return result
    text = str(value).strip()
    if not text:
        return []
    # Tags/categorias vindas de planilhas costumam usar ; | ou quebra de linha.
    parts = [part.strip() for part in re.split(r"[;|\n]+", text) if part.strip()]
    return parts or [text]


_EXPLICIT_TYPE_KEYS = (
    "category",
    "tipo_local_padronizado",
    "tipo_local",
    "categoria",
    "CATEGORIA",
    "TIPO_LOCAL_PADRONIZADO",
    "TIPO_LOCAL",
    "grupo_local",
    "GRUPO_LOCAL",
)

_SOURCE_TYPE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("vol_02", "galpoes_e_fabricas", "galpões_e_fábricas"), "Galpão / Fábrica"),
    (("vol_03", "convencoes_e_pavilhoes", "convenções_e_pavilhões"), "Centro de Convenções / Pavilhão"),
    (("vol_04a", "vol_04b", "vol_04c", "espacos_de_eventos", "espaços_de_eventos"), "Espaço de Eventos"),
    (("vol_05", "casas_de_show"), "Casas de Show"),
    (("vol_06", "teatros_e_auditorios", "teatros_e_auditórios"), "Teatros / Auditórios"),
    (("vol_07", "hoteis", "hotéis"), "Hotéis"),
    (("vol_08", "bares"), "Bares"),
    (("vol_09", "restaurantes"), "Restaurantes"),
    (("vol_10", "galerias_de_arte"), "Galerias de Arte"),
    (("vol_11", "estadios", "estádios"), "Estádios"),
)


def original_type_candidates(record: dict[str, Any]) -> list[str]:
    """
    Lê primeiro as categorias específicas preservadas pelo upload.

    Isso é intencional: extratores legados podiam reduzir ``BARES`` e
    ``RESTAURANTES`` ao mesmo ``Restaurante / bar`` ou ``CASAS DE SHOW`` e
    ``TEATROS`` ao genérico ``Auditório / teatro``. A categoria original é
    semanticamente mais precisa que esse valor legado.
    """
    candidates: list[str] = []
    raw_data = _json_dict(record.get("raw_data"))

    for container in (record, raw_data):
        for key in _EXPLICIT_TYPE_KEYS:
            candidates.extend(_candidate_values(container.get(key)))
        # A importação tabular da base-mestra preserva a categoria também nas
        # tags. Elas são uma evidência explícita, não uma inferência por nome.
        candidates.extend(_candidate_values(container.get("tags")))
        candidates.extend(_candidate_values(container.get("TAGS")))

    # O venue_type atual vem por último quando ele não é canônico. Assim um
    # valor legado genérico nunca sobrepõe uma categoria específica preservada.
    candidates.extend(_candidate_values(record.get("venue_type")))
    candidates.extend(_candidate_values(raw_data.get("venue_type")))

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = normalize_text(candidate)
        if key and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _source_type(record: dict[str, Any]) -> str | None:
    """Recupera tipologia pelo volume visual/origem, quando inequívoco."""
    raw_data = _json_dict(record.get("raw_data"))
    source_values: list[str] = []
    for container in (record, raw_data):
        for key in (
            "source_file",
            "document_name",
            "arquivo_visual",
            "ARQUIVO_VISUAL",
            "volume_visual_previsto",
            "VOLUME_VISUAL_PREVISTO",
            "arquivo_visual_previsto",
            "ARQUIVO_VISUAL_PREVISTO",
        ):
            value = container.get(key)
            if value is not None and str(value).strip():
                source_values.append(str(value))
    haystack = normalize_text(" ".join(source_values)).replace(" ", "_")
    if not haystack:
        return None
    for patterns, label in _SOURCE_TYPE_RULES:
        for pattern in patterns:
            normalized_pattern = normalize_text(pattern).replace(" ", "_")
            if normalized_pattern and normalized_pattern in haystack:
                return label
    return None


def _high_confidence_text_type(record: dict[str, Any]) -> str | None:
    """
    Último fallback para nomes inequivocamente tipológicos.

    Evita termos ambíguos como ``arena`` ou ``bar`` isoladamente. O objetivo
    não é adivinhar, apenas recuperar casos óbvios que chegaram sem categoria.
    """
    raw_data = _json_dict(record.get("raw_data"))
    values = [
        record.get("name"),
        record.get("description"),
        raw_data.get("LOCAL"),
        raw_data.get("DESCRICAO_NAVE"),
        raw_data.get("descricao_nave"),
    ]
    text = normalize_text(" ".join(str(value or "") for value in values))
    if not text:
        return None

    rules: tuple[tuple[tuple[str, ...], str], ...] = (
        (("centro de convencoes", "convention center", "pavilhao de exposicoes"), "Centro de Convenções / Pavilhão"),
        (("galpao ", "galpao de ", "fabrica ", "estudio quanta"), "Galpão / Fábrica"),
        (("casa de show", "music venue", "concert venue"), "Casas de Show"),
        (("teatro ", " teatro", "auditorio ", " auditorio"), "Teatros / Auditórios"),
        (("hotel ", " hotel", "resort ", " resort"), "Hotéis"),
        (("restaurante ", " restaurante"), "Restaurantes"),
        (("galeria de arte", "pinacoteca", "museu ", " museu", "centro cultural"), "Galerias de Arte"),
        (("estadio ", " estadio", "stadium"), "Estádios"),
    )
    padded = f" {text} "
    for terms, label in rules:
        if any(term in padded for term in terms):
            return label
    return None


def venue_type_suggestion(record: dict[str, Any]) -> dict[str, Any] | None:
    """Retorna uma sugestão auditável de alta confiança para o cadastro."""
    current = normalize_venue_type(record.get("venue_type"))
    if current:
        return {
            "label": current,
            "confidence": 1.0,
            "source": "venue_type_canonical",
            "evidence": str(record.get("venue_type") or current),
        }

    for candidate in original_type_candidates(record):
        canonical = normalize_venue_type(candidate)
        if canonical:
            return {
                "label": canonical,
                "confidence": 0.99,
                "source": "explicit_category_or_tag",
                "evidence": candidate,
            }

    source_type = _source_type(record)
    if source_type:
        return {
            "label": source_type,
            "confidence": 0.98,
            "source": "source_volume",
            "evidence": str(record.get("source_file") or record.get("document_name") or "volume visual"),
        }

    text_type = _high_confidence_text_type(record)
    if text_type:
        return {
            "label": text_type,
            "confidence": 0.92,
            "source": "high_confidence_text",
            "evidence": str(record.get("name") or ""),
        }
    return None


def safe_type_from_record(record: dict[str, Any]) -> str | None:
    """Classifica apenas quando há uma evidência local de alta confiança."""
    suggestion = venue_type_suggestion(record)
    if not suggestion:
        return None
    if float(suggestion.get("confidence") or 0) < 0.9:
        return None
    return str(suggestion["label"])

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
