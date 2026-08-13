from __future__ import annotations

"""NAVE Intelligence — Entity Resolution v1.

Pure matching layer used by the Cross-Source Linker. The resolver never relies on
client/project-specific vocabulary. It scores identity using names, aliases, scope,
type compatibility and light contextual attributes, returning either:
- AUTO_MERGE: identity is strong enough to canonicalize;
- REVIEW: plausible identity, but human/semantic review should decide;
- DISTINCT: insufficient evidence that the records are the same thing.

The database adapter persists merges non-destructively through canonical_entity_id.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence

ENTITY_RESOLVER_VERSION = "entity-resolution-v2.0"
AUTO_MERGE_THRESHOLD = 0.91
REVIEW_THRESHOLD = 0.74

_STOPWORDS = {
    "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "da", "das", "do", "dos",
    "e", "em", "no", "na", "nos", "nas", "para", "por", "com", "sem",
    "the", "a", "an", "and", "of", "for", "in", "on", "with", "without", "to",
}

_GENERIC_BY_TYPE = {
    "activation": {"ativacao", "activation", "experiencia", "experience", "oficina", "workshop"},
    "solution": {"solucao", "solution", "experiencia", "experience"},
    "gift": {"gift", "brinde", "brindes"},
    "presskit": {"press", "kit", "presskit"},
    "venue": {"venue", "local", "espaco", "space"},
    "deliverable": {"entregavel", "deliverable"},
    "concept": {"conceito", "concept"},
    "strategy": {"estrategia", "strategy"},
}

_GLOBAL_CANONICAL_TYPES = {
    "client", "brand", "supplier", "venue", "venue_space", "product", "platform",
    "technology", "location", "person", "partner",
}
_ENTITY_FAMILY = {
    "activation": "project_solution",
    "solution": "project_solution",
    "deliverable": "project_solution",
    "gift": "project_solution",
    "presskit": "project_solution",
    "communication_asset": "project_solution",
    "technology": "project_solution",
    "concept": "strategy",
    "strategy": "strategy",
    "venue": "place",
    "venue_space": "place",
}

_GENERIC_NAMES = {
    "ativacao", "ativacoes", "activation", "experiencia", "experiencias",
    "brincadeira", "brincadeiras", "oficina", "oficinas", "brinde", "brindes",
    "conteudo", "conteudos", "material", "materiais", "comunicacao",
    "cenografia", "ambiente", "ambientes", "jornada", "operacao",
}

def entity_family(entity_type: str) -> str:
    return _ENTITY_FAMILY.get(str(entity_type or ""), str(entity_type or ""))

def compatible_entity_types(left_type: str, right_type: str) -> bool:
    if left_type == right_type:
        return True
    pair = frozenset((str(left_type or ""), str(right_type or "")))
    compatible_pairs = {
        frozenset(("activation", "solution")),
        frozenset(("activation", "deliverable")),
        frozenset(("solution", "deliverable")),
        frozenset(("gift", "presskit")),
        frozenset(("communication_asset", "deliverable")),
        frozenset(("venue", "venue_space")),
        frozenset(("concept", "strategy")),
    }
    return pair in compatible_pairs

def _distinctive_alias(value: str, entity_type: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or normalized in _GENERIC_NAMES:
        return False
    toks = _tokens(normalized, entity_type=entity_type)
    if not toks:
        return False
    if len(toks) >= 2:
        return True
    token = toks[0]
    return len(token) >= 5 and token not in _GENERIC_NAMES



@dataclass(frozen=True)
class ResolutionEntity:
    id: str
    entity_type: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    entity_kind: str = "project_instance"
    scope_entity_id: str | None = None
    domain_table: str | None = None
    domain_id: str | None = None
    confidence: float = 0.75
    mention_count: int = 0
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchResult:
    left_id: str
    right_id: str
    score: float
    decision: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ResolutionCluster:
    canonical_id: str
    member_ids: tuple[str, ...]
    aliases_to_add: tuple[str, ...]
    confidence: float


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any, *, entity_type: str | None = None) -> list[str]:
    generic = _GENERIC_BY_TYPE.get(str(entity_type or ""), set())
    return [
        token for token in normalize_text(value).split()
        if token and token not in _STOPWORDS and token not in generic
        and not token.isdigit()
    ]


def _aliases(entity: ResolutionEntity) -> set[str]:
    values = {normalize_text(entity.canonical_name)}
    values.update(normalize_text(v) for v in entity.aliases if normalize_text(v))
    return {v for v in values if v}


def _initialism(tokens: Sequence[str]) -> str:
    return "".join(token[0] for token in tokens if token)


def _attribute_bonus(left: ResolutionEntity, right: ResolutionEntity) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []
    for key in ("platform", "brand", "product", "category", "journey_stage"):
        lv = normalize_text(left.attributes.get(key))
        rv = normalize_text(right.attributes.get(key))
        if lv and rv:
            if lv == rv:
                bonus += 0.025
                reasons.append(f"contexto {key} coincide")
            else:
                # Explicit contradictory context is meaningful for project-scoped solutions.
                bonus -= 0.08
                reasons.append(f"contexto {key} diverge")
    return max(-0.20, min(0.08, bonus)), reasons


def entity_match_score(left: ResolutionEntity, right: ResolutionEntity) -> MatchResult:
    reasons: list[str] = []
    if left.id == right.id:
        return MatchResult(left.id, right.id, 1.0, "AUTO_MERGE", ("mesmo registro",))
    if left.entity_type != right.entity_type and not compatible_entity_types(left.entity_type, right.entity_type):
        return MatchResult(left.id, right.id, 0.0, "DISTINCT", ("tipos/famílias de entidade incompatíveis",))
    cross_type = left.entity_type != right.entity_type
    if cross_type:
        reasons.append(f"tipos compatíveis na família {entity_family(left.entity_type)}")
    if left.scope_entity_id and right.scope_entity_id and left.scope_entity_id != right.scope_entity_id:
        # Project instances from different projects are never merged by this project resolver.
        if left.entity_type not in _GLOBAL_CANONICAL_TYPES:
            return MatchResult(left.id, right.id, 0.0, "DISTINCT", ("instâncias pertencem a projetos diferentes",))

    left_aliases = _aliases(left)
    right_aliases = _aliases(right)
    exact = {
        value for value in (left_aliases & right_aliases)
        if re.search(r"[a-z]", value) and len(value) >= 3
        and _distinctive_alias(value, left.entity_type)
    }
    if exact:
        score = 0.995 if not cross_type else 0.985
        exact_reasons = list(reasons) + ["nome/alias normalizado idêntico e distintivo"]
        return MatchResult(left.id, right.id, score, "AUTO_MERGE", tuple(exact_reasons))

    best = 0.0
    best_pair: tuple[str, str] | None = None
    for a in left_aliases:
        for b in right_aliases:
            if not a or not b:
                continue
            # Whole-name containment is a strong alias signal even when the short
            # name contains words normally treated as stopwords (e.g. "ON TOUR").
            short_raw, long_raw = (a, b) if len(a) <= len(b) else (b, a)
            raw_phrase = bool(
                len(short_raw) >= 5
                and re.search(r"[a-z]", short_raw)
                and re.search(rf"(?:^|\s){re.escape(short_raw)}(?:$|\s)", long_raw)
            )
            ta = _tokens(a, entity_type=left.entity_type)
            tb = _tokens(b, entity_type=right.entity_type)
            if not ta or not tb:
                continue
            sa, sb = set(ta), set(tb)
            inter = sa & sb
            jaccard = len(inter) / max(1, len(sa | sb))
            overlap = len(inter) / max(1, min(len(sa), len(sb)))
            seq = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
            phrase = 0.0
            short, long = (" ".join(ta), " ".join(tb)) if len(ta) <= len(tb) else (" ".join(tb), " ".join(ta))
            if len(short) >= 5 and re.search(rf"(?:^|\s){re.escape(short)}(?:$|\s)", long):
                phrase = 1.0
            acronym = 0.0
            ia, ib = _initialism(ta), _initialism(tb)
            if len(ia) >= 2 and (a == ib or b == ia or ia == ib):
                acronym = 1.0

            score = 0.32 * jaccard + 0.34 * overlap + 0.22 * seq + 0.10 * phrase + 0.08 * acronym
            if raw_phrase:
                raw_tokens = [t for t in short_raw.split() if t]
                # Multi-token aliases are auto-merge candidates. A single distinctive
                # token is strong for venues/brands but only review-level for generic
                # project solutions/activations.
                if len(raw_tokens) >= 2:
                    score = max(score, 0.95)
                elif left.entity_type in _GLOBAL_CANONICAL_TYPES and len(short_raw) >= 8:
                    score = max(score, 0.93)
                elif entity_family(left.entity_type) == "project_solution" and _distinctive_alias(short_raw, left.entity_type):
                    score = max(score, 0.93)
                else:
                    score = max(score, 0.82)
            elif phrase and len(set(ta)) >= 2:
                score = max(score, 0.94)
            elif overlap == 1.0 and min(len(sa), len(sb)) >= 2 and seq >= 0.62:
                score = max(score, 0.90)
            if score > best:
                best = score
                best_pair = (a, b)

    bonus, attr_reasons = _attribute_bonus(left, right)
    best = max(0.0, min(1.0, best + bonus))
    if cross_type and best < 0.97:
        best = max(0.0, best - 0.025)
    reasons.extend(attr_reasons)
    if best_pair:
        reasons.append(f"similaridade nominal entre '{best_pair[0]}' e '{best_pair[1]}'")

    # Domain-linked canonical records deserve a slight advantage when the names already match strongly.
    if best >= 0.84 and (left.domain_id or right.domain_id):
        best = min(1.0, best + 0.025)
        reasons.append("uma das entidades está ligada a cadastro canônico")

    if best >= AUTO_MERGE_THRESHOLD:
        decision = "AUTO_MERGE"
    elif best >= REVIEW_THRESHOLD:
        decision = "REVIEW"
    else:
        decision = "DISTINCT"
    return MatchResult(left.id, right.id, round(best, 4), decision, tuple(reasons or ["sinais insuficientes"]))


def choose_canonical(entities: Sequence[ResolutionEntity]) -> ResolutionEntity:
    def key(entity: ResolutionEntity) -> tuple[int, int, int, float, int]:
        return (
            1 if entity.entity_kind == "canonical" else 0,
            1 if entity.domain_id and entity.domain_table else 0,
            int(entity.mention_count or 0),
            float(entity.confidence or 0.0),
            min(len(_tokens(entity.canonical_name, entity_type=entity.entity_type)), 8),
        )
    return max(entities, key=key)


def resolve_entities(entities: Sequence[ResolutionEntity]) -> tuple[list[ResolutionCluster], list[MatchResult]]:
    """Return auto-merge clusters and review candidates without mutating storage."""
    by_id = {entity.id: entity for entity in entities}
    parent = {entity.id: entity.id for entity in entities}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    reviews: list[MatchResult] = []
    for i, left in enumerate(entities):
        for right in entities[i + 1:]:
            match = entity_match_score(left, right)
            if match.decision == "AUTO_MERGE":
                union(left.id, right.id)
            elif match.decision == "REVIEW":
                reviews.append(match)

    groups: dict[str, list[ResolutionEntity]] = {}
    for entity in entities:
        groups.setdefault(find(entity.id), []).append(entity)

    clusters: list[ResolutionCluster] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        canonical = choose_canonical(members)
        aliases: list[str] = []
        for member in members:
            if member.id == canonical.id:
                aliases.extend(member.aliases)
                continue
            aliases.append(member.canonical_name)
            aliases.extend(member.aliases)
        aliases = [v for v in dict.fromkeys(v.strip() for v in aliases if v.strip()) if normalize_text(v) != normalize_text(canonical.canonical_name)]
        pair_scores = [
            entity_match_score(canonical, member).score
            for member in members if member.id != canonical.id
        ]
        clusters.append(ResolutionCluster(
            canonical_id=canonical.id,
            member_ids=tuple(member.id for member in members),
            aliases_to_add=tuple(aliases[:40]),
            confidence=round(min(pair_scores) if pair_scores else 1.0, 4),
        ))
    return clusters, sorted(reviews, key=lambda row: row.score, reverse=True)


def records_from_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    aliases_by_entity: Mapping[str, Sequence[str]] | None = None,
    mention_counts: Mapping[str, int] | None = None,
) -> list[ResolutionEntity]:
    aliases_by_entity = aliases_by_entity or {}
    mention_counts = mention_counts or {}
    result: list[ResolutionEntity] = []
    for row in rows:
        entity_id = str(row.get("id") or "").strip()
        if not entity_id:
            continue
        attrs = row.get("attributes") if isinstance(row.get("attributes"), Mapping) else {}
        result.append(ResolutionEntity(
            id=entity_id,
            entity_type=str(row.get("entity_type") or ""),
            canonical_name=str(row.get("canonical_name") or ""),
            aliases=tuple(str(v) for v in aliases_by_entity.get(entity_id, []) if str(v).strip()),
            entity_kind=str(row.get("entity_kind") or "project_instance"),
            scope_entity_id=str(row.get("scope_entity_id") or "") or None,
            domain_table=str(row.get("domain_table") or "") or None,
            domain_id=str(row.get("domain_id") or "") or None,
            confidence=float(row.get("confidence") or 0.0),
            mention_count=int(mention_counts.get(entity_id, 0)),
            attributes=dict(attrs),
        ))
    return result
