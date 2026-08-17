from __future__ import annotations

"""NAVE V28.7.2C0 — Evidence-led Requirement Semantic Observation collector.

Legacy requirements are recall hints, never provenance. Every observation produced by
this module is anchored to a current Evidence Unit. Short fragments can be classified
as scope/attribute/context instead of being promoted as Requirement truth.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from project_requirement_identity import normalize_requirement_text
from project_semantic_observations import _project_evidence, _source_role, _phase_role, _authority

C0_VERSION = "V28.7.2C0"

CHANNEL_TERMS = {
    "youtube", "instagram", "tiktok", "tik tok", "kwai", "facebook", "linkedin",
    "stories", "story", "reels", "reel", "feed", "shorts", "twitter", "x",
}
AUDIENCE_TERMS = {
    "publico alvo", "publico", "audiencia", "audience", "target audience", "criadores de conteudo",
    "content creators", "filmmakers", "fotografos", "photographers", "moda e lifestyle", "lifestyle",
}
PRODUCT_TERMS = {
    "foco do produto", "product focus", "captura em alta velocidade", "high speed capture",
    "camera", "cameras", "produto", "product", "feature", "recurso", "velocidade", "capture",
}
OBLIGATION_PATTERNS = (
    r"\bdeve(?:ra|m)?\b", r"\bprecisa(?:m)?\b", r"\bnecessari[oa]s?\b", r"\bobrigatori[oa]s?\b",
    r"\bmust\b", r"\bshould\b", r"\brequired\b", r"\bgarantir\b", r"\bensure\b",
    r"\bdesenvolver\b", r"\bdevelop\b", r"\bcriar\b", r"\bcreate\b", r"\bentregar\b", r"\bdeliver\b",
    r"\bobjetivo\s+(?:e|eh|é|de)\b", r"\bobjective\s+(?:is|to)\b",
)


@dataclass(frozen=True)
class RequirementSemanticObservation:
    id: str
    project_id: str
    source_asset_id: str
    evidence_unit_id: str
    observation_kind: str
    observed_name: str
    observed_type: str | None
    observed_status: str | None
    occurrence_phase: str
    occurrence_role: str
    domain_hint: str
    semantic_role: str
    assertion_mode: str
    attributes: dict[str, Any]
    source_authority_score: float
    model_confidence: float
    extraction_method: str
    observation_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_rows(client: Any, table: str, *, equals: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    q = client.table(table).select("*")
    for key, value in (equals or {}).items():
        q = q.eq(key, value)
    return _rows(q.execute())


def _read_in(client: Any, table: str, field: str, values: Sequence[Any]) -> list[dict[str, Any]]:
    clean = list(dict.fromkeys(v for v in values if v not in (None, "")))
    if not clean:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(clean), 80):
        out.extend(_rows(client.table(table).select("*").in_(field, clean[start:start + 80]).execute()))
    return out


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _token_overlap(left: Any, right: Any) -> float:
    a = {t for t in _norm(left).split() if len(t) >= 3}
    b = {t for t in _norm(right).split() if len(t) >= 3}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def _requirement_evidence_links(client: Any, project_id: str) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    links = _read_rows(client, "domain_object_evidence", equals={"project_id": project_id, "domain_table": "project_requirements"})
    evidence = _read_in(client, "evidence_units", "id", [row.get("evidence_unit_id") for row in links])
    current = {str(row.get("id")): dict(row) for row in evidence if row.get("is_current") is True and row.get("id")}
    out: dict[str, list[dict[str, Any]]] = {}
    linked_ids: set[str] = set()
    for link in links:
        eid = str(link.get("evidence_unit_id") or "")
        did = str(link.get("domain_id") or "")
        if eid in current and did:
            out.setdefault(did, []).append(current[eid])
            linked_ids.add(eid)
    return out, linked_ids


def _best_requirement_evidence(req: Mapping[str, Any], evidence_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, float, str]:
    attrs = req.get("attributes") if isinstance(req.get("attributes"), Mapping) else {}
    hints = [
        attrs.get("source_quote"), attrs.get("source_reference"), req.get("description"), req.get("title")
    ]
    hints = [str(v).strip() for v in hints if str(v or "").strip()]
    title = str(req.get("title") or "").strip()
    title_norm = _norm(title)
    best: tuple[float, int, dict[str, Any], str] | None = None
    for raw in evidence_rows:
        row = dict(raw)
        text = str(row.get("content_text") or "").strip()
        norm = _norm(text)
        if not norm:
            continue
        score = 0.0
        reason = ""
        for idx, hint in enumerate(hints):
            hnorm = _norm(hint)
            if len(hnorm) < 3:
                continue
            if hnorm == norm:
                cand, why = 1.0, "exact_evidence_text"
            elif len(hnorm) >= 8 and hnorm in norm:
                cand, why = (0.99 if idx == 0 else 0.95), "evidence_contains_requirement_hint"
            else:
                overlap = _token_overlap(hnorm, norm)
                cand, why = (0.60 + 0.30 * overlap if overlap >= 0.55 else 0.0), "token_overlap"
            if cand > score:
                score, reason = cand, why
        if title_norm and len(title_norm) >= 4 and title_norm in norm:
            score = max(score, 0.88 if len(title_norm.split()) > 1 else 0.78)
            reason = reason or "title_in_evidence"
        if score < 0.78:
            continue
        item = (score, -len(text), row, reason)
        if best is None or item[:2] > best[:2]:
            best = item
    if not best:
        return None, 0.0, "no_unambiguous_evidence"
    return best[2], float(best[0]), best[3]


def _is_channel_title(title: str) -> bool:
    norm = _norm(title)
    return norm in CHANNEL_TERMS or any(norm == _norm(v) for v in CHANNEL_TERMS)


def _classify(req: Mapping[str, Any], evidence_text: str) -> tuple[str, str, str]:
    title = str(req.get("title") or "").strip()
    title_norm = _norm(title)
    text_norm = _norm(evidence_text)
    req_type = _norm(req.get("requirement_type")).replace(" ", "_")

    if _is_channel_title(title):
        if re.search(r"\b(plataform|platform|canal|channel|ativacao|activation|conteudo|content|social)\w*\b", text_norm):
            return "scope_signal", "channel_scope", "scope"
        return "scope_signal", "channel_scope", "scope"

    if title_norm in {_norm(v) for v in AUDIENCE_TERMS} or req_type in {"audience", "publico", "publico_alvo", "context", "contexto"}:
        return "context_signal", "audience_context", "context"

    if title_norm in {_norm(v) for v in PRODUCT_TERMS} or (
        len(title_norm.split()) <= 5 and re.search(r"\b(produto|product|camera|feature|recurso|capture|captura|velocidade)\b", text_norm)
    ):
        return "attribute_signal", "product_attribute", "attribute"

    if re.search(r"\b(budget|orcamento|verba|investimento|prazo|deadline|quantidade|participantes|attendees)\b", text_norm):
        if re.search(r"\b\d+[\d\s\.,]*\b", evidence_text):
            return "constraint_candidate", "constraint_candidate", "constraint"

    obligation = any(re.search(pattern, text_norm) for pattern in OBLIGATION_PATTERNS)
    substantive = len(title_norm.split()) >= 3 or len(_norm(req.get("description")).split()) >= 5
    if obligation or bool(req.get("mandatory")) or substantive:
        return "requirement_candidate", "requirement_candidate", "requirement"
    return "requirement_mention", "requirement_mention", "reference"


def _make_observation(
    *, project_id: str, requirement: Mapping[str, Any], evidence: Mapping[str, Any],
    semantic_role: str, occurrence_role: str, confidence: float, match_reason: str,
    source_role: str, primary: bool,
) -> RequirementSemanticObservation:
    title = str(requirement.get("title") or "Requisito").strip()
    source_asset_id = str(evidence.get("source_asset_id") or "")
    evidence_id = str(evidence.get("id") or "")
    identity = {
        "project_id": project_id,
        "evidence_unit_id": evidence_id,
        "domain_hint": "requirement",
        "semantic_role": semantic_role,
        "legacy_requirement_id": str(requirement.get("legacy_source_id") or requirement.get("id") or ""),
        "observed_name": _norm(title),
    }
    ohash = _hash(identity)
    oid = str(uuid5(NAMESPACE_URL, "nave:requirement-observation:" + ohash))
    phase, _source_occurrence_role = _phase_role(source_role)
    attrs = {
        "normalized_by": C0_VERSION,
        "legacy_requirement_id": str(requirement.get("legacy_source_id") or "") or None,
        "requirement_id": str(requirement.get("id") or "") or None,
        "requirement_entity_id": str(requirement.get("entity_id") or "") or None,
        "legacy_requirement_type": requirement.get("requirement_type"),
        "source_reference": (requirement.get("attributes") or {}).get("source_reference") if isinstance(requirement.get("attributes"), Mapping) else None,
        "match_reason": match_reason,
        "evidence_text": str(evidence.get("content_text") or "")[:1600],
    }
    role_map = {
        "requirement": "mention",
        "scope": "reference",
        "attribute": "reference",
        "constraint": "reference",
        "context": "reference",
        "reference": "reference",
    }
    return RequirementSemanticObservation(
        id=oid,
        project_id=project_id,
        source_asset_id=source_asset_id,
        evidence_unit_id=evidence_id,
        observation_kind="requirement_signal",
        observed_name=title,
        observed_type=str(requirement.get("requirement_type") or "requirement"),
        observed_status=None,
        occurrence_phase=phase,
        occurrence_role=role_map.get(occurrence_role, "reference"),
        domain_hint="requirement",
        semantic_role=semantic_role,
        assertion_mode="source_explicit",
        attributes=attrs,
        source_authority_score=_authority(source_role, primary=primary),
        model_confidence=max(0.0, min(1.0, confidence)),
        extraction_method="requirement_legacy_recall+current_evidence",
        observation_hash=ohash,
    )


def collect_project_requirement_observations(client: Any, project_id: str) -> dict[str, Any]:
    source = _project_evidence(client, project_id)
    requirements = _read_rows(client, "project_requirements", equals={"project_id": project_id})
    direct_by_requirement, _linked_evidence_ids = _requirement_evidence_links(client, project_id)

    # Provenance recovery stays source-local whenever the legacy requirement still
    # carries its briefing document lineage. This prevents a short fragment such as
    # a platform name from binding to an unrelated proposal/report occurrence merely
    # because the same token appears elsewhere in the project.
    briefing_docs = _read_rows(client, "memory_briefing_documents", equals={"project_id": project_id})
    asset_by_sha = {str(row.get("content_sha256") or ""): dict(row) for row in (source.get("assets") or []) if row.get("content_sha256")}
    briefing_asset_by_id: dict[str, str] = {}
    for row in briefing_docs:
        asset = asset_by_sha.get(str(row.get("content_sha256") or "")) or {}
        if row.get("id") and asset.get("id"):
            briefing_asset_by_id[str(row["id"])] = str(asset["id"])
    observations: list[RequirementSemanticObservation] = []
    diagnostics: list[dict[str, Any]] = []

    for req in requirements:
        req_id = str(req.get("id") or "")
        evidences = direct_by_requirement.get(req_id) or []
        evidence: dict[str, Any] | None = None
        score = 0.0
        match_reason = ""
        already_bound = False
        if evidences:
            evidence = min((dict(row) for row in evidences), key=lambda row: len(str(row.get("content_text") or "")))
            score = 0.99
            match_reason = "existing_current_domain_evidence"
            already_bound = True
        else:
            attrs = req.get("attributes") if isinstance(req.get("attributes"), Mapping) else {}
            briefing_doc_id = str(attrs.get("legacy_briefing_document_id") or "")
            source_asset_id = briefing_asset_by_id.get(briefing_doc_id)
            candidates = (source.get("evidence_by_asset") or {}).get(source_asset_id, []) if source_asset_id else (source.get("evidence") or [])
            evidence, score, match_reason = _best_requirement_evidence(req, candidates)
            if source_asset_id:
                match_reason = (match_reason + "+same_source") if evidence else "no_unambiguous_same_source_evidence"

        if not evidence:
            diagnostics.append({
                "requirement_id": req_id,
                "title": req.get("title"),
                "classification": "unresolved",
                "evidence_found": False,
                "match_reason": match_reason,
            })
            continue

        if already_bound:
            semantic_role, occurrence_role = "requirement_mention", "requirement"
        else:
            _candidate_kind, semantic_role, occurrence_role = _classify(req, str(evidence.get("content_text") or ""))

        source_role, primary = _source_role(str(evidence.get("source_asset_id") or ""), source)
        observation = _make_observation(
            project_id=project_id,
            requirement=req,
            evidence=evidence,
            semantic_role=semantic_role,
            occurrence_role=occurrence_role,
            confidence=score,
            match_reason=match_reason,
            source_role=source_role,
            primary=primary,
        )
        observations.append(observation)
        diagnostics.append({
            "requirement_id": req_id,
            "legacy_requirement_id": req.get("legacy_source_id"),
            "title": req.get("title"),
            "classification": semantic_role,
            "evidence_found": True,
            "evidence_unit_id": evidence.get("id"),
            "source_role": source_role,
            "match_score": score,
            "match_reason": match_reason,
        })

    deduped = {row.observation_hash: row for row in observations}
    return {
        "project_id": project_id,
        "observations": [row.to_dict() for row in deduped.values()],
        "diagnostics": diagnostics,
        "source_snapshot": source,
        "counts": {
            "requirements": len(requirements),
            "observations": len(deduped),
            "evidence_bound_before_c0": sum(1 for row in diagnostics if row.get("match_reason") == "existing_current_domain_evidence"),
            "recovered_evidence_candidates": sum(1 for row in diagnostics if row.get("evidence_found") and row.get("match_reason") != "existing_current_domain_evidence"),
            "unresolved": sum(1 for row in diagnostics if not row.get("evidence_found")),
        },
    }
