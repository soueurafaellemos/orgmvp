"""Detecção, agrupamento e backfill de duplicidades de locais da NAVE.

Este módulo corrige duas lacunas diferentes:

1. duplicidades antigas, criadas antes da fila de revisão, passam a ser
   verificadas e inseridas em ``knowledge_duplicate_candidates``;
2. a consulta pode apresentar uma única linha representativa para pares de
   alta confiança sem apagar ou unir registros antes da revisão administrativa.

A união definitiva continua acontecendo somente em "Revisar duplicidades".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, asdict
from datetime import datetime
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import json
import re
import unicodedata


@dataclass(frozen=True)
class VenueDuplicateCandidate:
    source_entity_id: str
    candidate_entity_id: str
    source_name: str
    candidate_name: str
    similarity_score: float
    match_method: str
    match_context: dict[str, Any]
    pair_key: str

    def as_review_row(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(
            {
                "entity_type": "venue",
                "status": "pending",
                "scan_origin": "existing_base_scan",
                "original_strategy": "review_existing",
            }
        )
        return data


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text in {"none", "null", "nan", "não informado", "nao informado"}:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _record_value(record: Mapping[str, Any], *keys: str) -> Any:
    normalized = {normalize_text(key).replace(" ", "_") for key in keys}
    for key, value in record.items():
        current = normalize_text(key).replace(" ", "_")
        if current in normalized:
            return value
    return None


def _name(record: Mapping[str, Any]) -> str:
    return str(
        _record_value(record, "name", "LOCAL", "local", "NOME", "nome")
        or ""
    ).strip()


def _identifier(record: Mapping[str, Any]) -> str:
    value = _record_value(record, "id", "ID", "venue_id", "entity_id")
    if value is None:
        # Suporte a testes e prévias ainda não salvas. Não deve ser usado para
        # inserir a revisão no banco antes de o registro receber UUID real.
        payload = json.dumps(dict(record), sort_keys=True, default=str)
        return "temporary-" + sha256(payload.encode("utf-8")).hexdigest()[:20]
    return str(value)


def _raw_data(record: Mapping[str, Any]) -> dict[str, Any]:
    raw = _record_value(record, "raw_data", "RAW_DATA")
    return raw if isinstance(raw, dict) else {}


def _lookup(record: Mapping[str, Any], *keys: str) -> Any:
    value = _record_value(record, *keys)
    if value not in (None, "", [], {}):
        return value
    raw = _raw_data(record)
    return _record_value(raw, *keys)


def normalize_name(value: Any) -> str:
    text = normalize_text(value)
    # Rótulos de renomeação não devem impedir o reconhecimento do local.
    text = re.sub(
        r"\b(?:atualmente|antigo|antiga|novo nome|nova marca|renomeado para)\b.*$",
        "",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def base_name(value: Any) -> str:
    raw = str(value or "")
    # "Allianz Parque (Nubank Parque)" mantém Allianz Parque como base.
    raw = re.sub(r"\([^)]*\)", " ", raw)
    return normalize_name(raw)


def _parenthetical_aliases(value: Any) -> set[str]:
    raw = str(value or "")
    return {
        normalize_name(match)
        for match in re.findall(r"\(([^)]*)\)", raw)
        if normalize_name(match)
    }


def _learned_aliases(record: Mapping[str, Any]) -> set[str]:
    raw = _raw_data(record)
    values = raw.get("identity_aliases")
    if not isinstance(values, list):
        values = []
    return {
        normalize_name(value)
        for value in values
        if normalize_name(value)
    }


def normalize_postal_code(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:8] if len(digits) >= 8 else digits


def normalize_address(value: Any) -> str:
    text = normalize_text(value)
    substitutions = {
        r"\bavenida\b": "av",
        r"\brua\b": "r",
        r"\brodovia\b": "rod",
        r"\bpraca\b": "pca",
        r"\bnumero\b": "",
    }
    for pattern, replacement in substitutions.items():
        text = re.sub(pattern, replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_domain(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, flags=re.I):
        text = "https://" + text
    try:
        hostname = (urlparse(text).hostname or "").lower()
    except ValueError:
        return ""
    return hostname.removeprefix("www.")


def normalize_instagram(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    match = re.search(r"instagram\.com/([^/?#]+)", text)
    if match:
        return normalize_text(match.group(1)).replace(" ", "")
    return normalize_text(text.lstrip("@")).replace(" ", "")


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _same_or_missing(left: str, right: str) -> bool:
    return not left or not right or left == right


def _pair_key(left_id: str, right_id: str) -> str:
    first, second = sorted((str(left_id), str(right_id)))
    return sha256(f"venue:{first}:{second}".encode("utf-8")).hexdigest()


def _completeness(record: Mapping[str, Any]) -> int:
    fields = (
        "name", "venue_type", "description", "address", "neighborhood",
        "city", "state", "postal_code", "website_url", "map_url",
        "standing_capacity", "seated_capacity", "auditorium_capacity",
        "source_image_url", "tags", "evidence",
    )
    score = 0
    for field in fields:
        value = _lookup(record, field, field.upper())
        if value not in (None, "", [], {}):
            score += 1
    return score


def _created_at_value(record: Mapping[str, Any]) -> float:
    raw = _lookup(record, "created_at", "CREATED_AT")
    if isinstance(raw, datetime):
        try:
            return raw.timestamp()
        except (OverflowError, OSError, ValueError):
            return float("inf")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return float("inf")


def preferred_primary(records: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Escolhe a ficha mais completa; em empate, preserva a mais antiga."""
    return sorted(
        records,
        key=lambda item: (-_completeness(item), _created_at_value(item), _identifier(item)),
    )[0]


def compare_venues(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> VenueDuplicateCandidate | None:
    """Compara dois locais e devolve candidato apenas com evidência suficiente.

    Um endereço igual, sozinho, não é suficiente: isso protege espaços internos
    independentes, como Parque Mirante dentro do complexo Allianz Parque.
    """
    left_id = _identifier(left)
    right_id = _identifier(right)
    if left_id == right_id:
        return None

    left_name = _name(left)
    right_name = _name(right)
    name_a = normalize_name(left_name)
    name_b = normalize_name(right_name)
    base_a = base_name(left_name)
    base_b = base_name(right_name)
    aliases_a = _parenthetical_aliases(left_name) | _learned_aliases(left)
    aliases_b = _parenthetical_aliases(right_name) | _learned_aliases(right)

    city_a = normalize_text(_lookup(left, "city", "CIDADE"))
    city_b = normalize_text(_lookup(right, "city", "CIDADE"))
    state_a = normalize_text(_lookup(left, "state", "ESTADO", "uf", "UF"))
    state_b = normalize_text(_lookup(right, "state", "ESTADO", "uf", "UF"))
    address_a = normalize_address(_lookup(left, "address", "ENDERECO", "ENDEREÇO"))
    address_b = normalize_address(_lookup(right, "address", "ENDERECO", "ENDEREÇO"))
    postal_a = normalize_postal_code(_lookup(left, "postal_code", "CEP"))
    postal_b = normalize_postal_code(_lookup(right, "postal_code", "CEP"))
    domain_a = normalize_domain(_lookup(left, "website_url", "SITE", "SITE_ORIGINAL"))
    domain_b = normalize_domain(_lookup(right, "website_url", "SITE", "SITE_ORIGINAL"))
    instagram_a = normalize_instagram(_lookup(left, "instagram_url", "INSTAGRAM"))
    instagram_b = normalize_instagram(_lookup(right, "instagram_url", "INSTAGRAM"))

    exact_name = bool(name_a and name_a == name_b)
    exact_base_name = bool(base_a and base_a == base_b)
    alias_cross_match = bool(
        base_a and base_b and (
            base_a in aliases_b
            or base_b in aliases_a
            or name_a in aliases_b
            or name_b in aliases_a
            or bool(aliases_a & aliases_b)
        )
    )
    token_set_equal = bool(
        name_a
        and name_b
        and set(name_a.split()) == set(name_b.split())
    )
    name_similarity = max(
        _similarity(name_a, name_b),
        _similarity(base_a, base_b),
    )
    same_city = bool(city_a and city_a == city_b)
    same_state = bool(state_a and state_a == state_b)
    same_address = bool(address_a and address_a == address_b)
    same_postal = bool(postal_a and postal_a == postal_b)
    same_domain = bool(domain_a and domain_a == domain_b)
    same_instagram = bool(instagram_a and instagram_a == instagram_b)

    # Nomes idênticos em cidades/estados incompatíveis precisam de revisão mais
    # conservadora, pois redes e hotéis podem repetir nomes.
    location_compatible = _same_or_missing(city_a, city_b) and _same_or_missing(state_a, state_b)

    score = 0.0
    method = ""

    if exact_name and location_compatible:
        score = 1.0
        method = "exact_normalized_name"
    elif token_set_equal and location_compatible:
        score = 0.99
        method = "same_name_tokens"
    elif exact_base_name and location_compatible:
        score = 0.98
        method = "same_base_name"
    elif alias_cross_match and location_compatible:
        score = 0.97
        method = "semantic_alias"
    elif same_instagram and name_similarity >= 0.45 and location_compatible:
        score = 0.97
        method = "same_instagram"
    elif same_domain and name_similarity >= 0.50 and location_compatible:
        score = 0.96
        method = "same_official_domain"
    elif same_address and name_similarity >= 0.65 and location_compatible:
        score = 0.95
        method = "same_address_and_similar_name"
    elif same_postal and same_address and name_similarity >= 0.58 and location_compatible:
        score = 0.94
        method = "same_postal_address_and_similar_name"
    elif name_similarity >= 0.92 and location_compatible:
        score = 0.92
        method = "high_name_similarity"
    elif exact_name:
        score = 0.82
        method = "same_name_conflicting_location"
    else:
        return None

    # Proteção de local principal x subespaço: compartilhar endereço/CEP sem
    # nome, domínio ou perfil social compatível não cria duplicidade.
    if (
        method in {"same_address_and_similar_name", "same_postal_address_and_similar_name"}
        and not (same_domain or same_instagram or exact_base_name or alias_cross_match)
        and name_similarity < 0.72
    ):
        return None

    context = {
        "name_similarity": round(name_similarity, 5),
        "exact_name": exact_name,
        "exact_base_name": exact_base_name,
        "alias_cross_match": alias_cross_match,
        "token_set_equal": token_set_equal,
        "learned_aliases_left": sorted(_learned_aliases(left)),
        "learned_aliases_right": sorted(_learned_aliases(right)),
        "same_city": same_city,
        "same_state": same_state,
        "same_address": same_address,
        "same_postal_code": same_postal,
        "same_official_domain": same_domain,
        "same_instagram": same_instagram,
        "left_address": _lookup(left, "address", "ENDERECO", "ENDEREÇO"),
        "right_address": _lookup(right, "address", "ENDERECO", "ENDEREÇO"),
        "left_website": _lookup(left, "website_url", "SITE", "SITE_ORIGINAL"),
        "right_website": _lookup(right, "website_url", "SITE", "SITE_ORIGINAL"),
        "left_type": _lookup(left, "venue_type", "TIPO_LOCAL_PADRONIZADO", "CATEGORIA"),
        "right_type": _lookup(right, "venue_type", "TIPO_LOCAL_PADRONIZADO", "CATEGORIA"),
    }

    primary = preferred_primary([left, right])
    duplicate = right if _identifier(primary) == left_id else left

    return VenueDuplicateCandidate(
        source_entity_id=_identifier(duplicate),
        candidate_entity_id=_identifier(primary),
        source_name=_name(duplicate),
        candidate_name=_name(primary),
        similarity_score=round(score, 5),
        match_method=method,
        match_context=context,
        pair_key=_pair_key(left_id, right_id),
    )


def find_existing_venue_duplicates(
    records: Iterable[Mapping[str, Any]],
    *,
    minimum_score: float = 0.82,
) -> list[VenueDuplicateCandidate]:
    venues = [dict(item) for item in records]
    results: list[VenueDuplicateCandidate] = []
    seen: set[str] = set()

    # Bloqueios simples reduzem comparações sem perder pares relevantes.
    buckets: dict[str, set[int]] = defaultdict(set)
    for index, venue in enumerate(venues):
        name = normalize_name(_name(venue))
        base = base_name(_name(venue))
        city = normalize_text(_lookup(venue, "city", "CIDADE"))
        postal = normalize_postal_code(_lookup(venue, "postal_code", "CEP"))
        domain = normalize_domain(_lookup(venue, "website_url", "SITE", "SITE_ORIGINAL"))
        instagram = normalize_instagram(_lookup(venue, "instagram_url", "INSTAGRAM"))

        keys = {
            f"name:{name}",
            f"base:{base}",
            f"prefix:{' '.join(base.split()[:2])}:{city}",
        }
        if postal:
            keys.add(f"postal:{postal}")
        if domain:
            keys.add(f"domain:{domain}")
        if instagram:
            keys.add(f"instagram:{instagram}")

        for key in {key for key in keys if not key.endswith(":") and key.split(":", 1)[-1]}:
            buckets[key].add(index)

    compared: set[tuple[int, int]] = set()
    for indices in buckets.values():
        ordered = sorted(indices)
        for position, left_index in enumerate(ordered):
            for right_index in ordered[position + 1 :]:
                pair = (left_index, right_index)
                if pair in compared:
                    continue
                compared.add(pair)
                candidate = compare_venues(venues[left_index], venues[right_index])
                if not candidate or candidate.similarity_score < minimum_score:
                    continue
                if candidate.pair_key in seen:
                    continue
                seen.add(candidate.pair_key)
                results.append(candidate)

    return sorted(
        results,
        key=lambda item: (-item.similarity_score, item.source_name, item.candidate_name),
    )


class _DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def collapse_duplicate_display_rows(
    records: Iterable[Mapping[str, Any]],
    *,
    candidates: Sequence[VenueDuplicateCandidate] | None = None,
    minimum_score: float = 0.94,
) -> list[dict[str, Any]]:
    """Agrupa duplicidades fortes apenas na visualização da consulta.

    Nenhum registro é apagado. A linha principal recebe:
    ``_duplicate_record_count``, ``_duplicate_record_ids`` e
    ``_duplicate_review_pending``.
    """
    venues = [dict(item) for item in records]
    by_id = {_identifier(item): item for item in venues}
    candidates = list(candidates or find_existing_venue_duplicates(venues))

    groups = _DisjointSet()
    for candidate in candidates:
        if candidate.similarity_score >= minimum_score:
            groups.union(candidate.source_entity_id, candidate.candidate_entity_id)

    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for identifier, venue in by_id.items():
        components[groups.find(identifier)].append(venue)

    output: list[dict[str, Any]] = []
    for items in components.values():
        primary = dict(preferred_primary(items))
        ids = sorted(_identifier(item) for item in items)
        primary["_duplicate_record_count"] = len(items)
        primary["_duplicate_record_ids"] = ids
        primary["_duplicate_review_pending"] = len(items) > 1
        primary["_duplicate_names"] = sorted({_name(item) for item in items if _name(item)})
        output.append(primary)

    return sorted(output, key=lambda item: normalize_name(_name(item)))


def _existing_pair_keys(client: Any) -> set[str]:
    response = (
        client.table("knowledge_duplicate_candidates")
        .select("pair_key")
        .eq("entity_type", "venue")
        .execute()
    )
    return {
        str(row.get("pair_key"))
        for row in (getattr(response, "data", None) or [])
        if row.get("pair_key")
    }


def fetch_all_venues(client: Any, *, page_size: int = 1000) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    start = 0
    while True:
        response = (
            client.table("venues")
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = list(getattr(response, "data", None) or [])
        records.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return records


def queue_existing_venue_duplicates(
    client: Any,
    *,
    records: Iterable[Mapping[str, Any]] | None = None,
    minimum_score: float = 0.82,
) -> dict[str, Any]:
    """Escaneia a base existente e cria revisões idempotentes.

    Pares já resolvidos como ``different`` ou ``merged`` não são recriados,
    porque ``pair_key`` é único independentemente do status.
    """
    venue_records = list(records) if records is not None else fetch_all_venues(client)
    candidates = find_existing_venue_duplicates(
        venue_records,
        minimum_score=minimum_score,
    )
    existing_keys = _existing_pair_keys(client)
    new_rows = [
        candidate.as_review_row()
        for candidate in candidates
        if candidate.pair_key not in existing_keys
        and not candidate.source_entity_id.startswith("temporary-")
        and not candidate.candidate_entity_id.startswith("temporary-")
    ]

    inserted = 0
    errors: list[str] = []
    for row in new_rows:
        try:
            client.table("knowledge_duplicate_candidates").insert(row).execute()
            inserted += 1
        except Exception as exc:  # o restante do lote continua sendo processado
            errors.append(f"{row['source_name']} × {row['candidate_name']}: {exc}")

    return {
        "venues_scanned": len(venue_records),
        "candidates_found": len(candidates),
        "already_registered": len(candidates) - len(new_rows),
        "inserted": inserted,
        "errors": errors,
    }
