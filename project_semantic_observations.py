from __future__ import annotations

"""NAVE V28.7.2A — Evidence -> Semantic Observation collector.

Observations are intentionally pre-ontological. They preserve what a source appears to
say before the NAVE commits to a Project Domain identity. They are never current truth.
"""

from dataclasses import dataclass, asdict
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from project_domain_identity import normalize_name, similarity

OBSERVATION_VERSION = "V28.7.2A"


@dataclass(frozen=True)
class SemanticObservation:
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


def _read_rows(client: Any, table: str, *, equals: Mapping[str, Any] | None = None, columns: str = "*") -> list[dict[str, Any]]:
    query = client.table(table).select(columns)
    for key, value in (equals or {}).items():
        query = query.eq(key, value)
    return _rows(query.execute())


def _read_in(client: Any, table: str, field: str, values: Sequence[Any], *, columns: str = "*") -> list[dict[str, Any]]:
    clean = list(dict.fromkeys(v for v in values if v not in (None, "")))
    if not clean:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(clean), 80):
        out.extend(_rows(client.table(table).select(columns).in_(field, clean[start:start + 80]).execute()))
    return out


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _authority(source_role: Any, *, primary: bool = False) -> float:
    role = _norm(source_role).replace(" ", "_")
    base = {
        "post_execution_report": 0.94,
        "post_event_report": 0.94,
        "closure_report": 0.94,
        "report": 0.92,
        "feedback": 0.90,
        "feedback_approval": 0.90,
        "budget": 0.88,
        "budget_sheet": 0.88,
        "preliminary_budget": 0.86,
        "cost": 0.88,
        "cost_sheet": 0.88,
        "detailed_costs": 0.88,
        "proposal": 0.82,
        "proposal_presentation": 0.82,
        "final_presentation": 0.84,
        "briefing": 0.86,
        "briefing_original": 0.86,
    }.get(role, 0.72)
    return min(0.98, base + (0.02 if primary else 0.0))


def _phase_role(source_role: Any) -> tuple[str, str]:
    role = _norm(source_role).replace(" ", "_")
    if role in {"post_execution_report", "post_event_report", "closure_report", "report"}:
        return "post_event", "result"
    if role in {"proposal", "creative_proposal", "commercial_proposal", "proposal_presentation", "final_presentation"}:
        return "proposal", "proposal"
    if role in {"budget", "cost", "financial", "estimate", "budget_sheet", "preliminary_budget", "cost_sheet", "detailed_costs"}:
        return "reference", "budget_reference"
    if role in {"briefing", "briefing_original"}:
        return "briefing", "mention"
    if role in {"feedback", "feedback_approval"}:
        return "feedback", "feedback_context"
    return "reference", "reference"


def _project_evidence(client: Any, project_id: str) -> dict[str, Any]:
    project_files = _read_rows(client, "project_files", equals={"project_id": project_id})
    memory_docs = _read_rows(client, "memory_documents", equals={"project_id": project_id})
    hashes = [str(row.get("content_sha256") or "") for row in project_files + memory_docs if row.get("content_sha256")]
    assets = _read_in(client, "source_assets", "content_sha256", hashes)
    asset_by_sha = {str(row.get("content_sha256") or ""): dict(row) for row in assets if row.get("content_sha256")}
    asset_ids = [str(row.get("id")) for row in assets if row.get("id")]
    contexts = _read_in(client, "source_asset_contexts", "source_asset_id", asset_ids)
    project_entities = _read_rows(client, "knowledge_entities", equals={"domain_table": "projects", "domain_id": project_id})
    project_entity_id = str((project_entities[0] if project_entities else {}).get("id") or "")
    if project_entity_id:
        project_contexts = [row for row in contexts if str(row.get("context_entity_id") or "") == project_entity_id]
        # If the current project mirror has no explicit source contexts yet, fall back
        # to the asset role rather than borrowing a different project's context.
        contexts = project_contexts
    evidence = [row for row in _read_in(client, "evidence_units", "source_asset_id", asset_ids) if row.get("is_current") is True]

    context_by_asset: dict[str, dict[str, Any]] = {}
    for row in contexts:
        aid = str(row.get("source_asset_id") or "")
        if not aid:
            continue
        previous = context_by_asset.get(aid)
        if previous is None or bool(row.get("is_primary_source")):
            context_by_asset[aid] = dict(row)

    asset_by_id = {str(row.get("id")): dict(row) for row in assets if row.get("id")}
    evidence_by_asset: dict[str, list[dict[str, Any]]] = {}
    for row in evidence:
        evidence_by_asset.setdefault(str(row.get("source_asset_id") or ""), []).append(row)

    project_file_asset: dict[str, str] = {}
    for row in project_files:
        sha = str(row.get("content_sha256") or "")
        asset = asset_by_sha.get(sha) or {}
        if row.get("id") and asset.get("id"):
            project_file_asset[str(row["id"])] = str(asset["id"])

    return {
        "project_files": project_files,
        "assets": assets,
        "asset_by_id": asset_by_id,
        "context_by_asset": context_by_asset,
        "evidence": evidence,
        "evidence_by_asset": evidence_by_asset,
        "project_file_asset": project_file_asset,
    }


def _source_role(asset_id: str, data: Mapping[str, Any]) -> tuple[str, bool]:
    context = (data.get("context_by_asset") or {}).get(asset_id) or {}
    asset = (data.get("asset_by_id") or {}).get(asset_id) or {}
    role = str(context.get("context_role") or asset.get("source_role") or "reference")
    return role, bool(context.get("is_primary_source"))


def _best_evidence(rows: Sequence[Mapping[str, Any]], hints: Iterable[Any]) -> dict[str, Any] | None:
    normalized = [_norm(v) for v in hints if _norm(v)]
    if not normalized:
        return None
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for raw in rows:
        text = str(raw.get("content_text") or "")
        norm = _norm(text)
        if not norm:
            continue
        score = 0.0
        for hint in normalized:
            if hint == norm:
                score = max(score, 1.0)
            elif hint in norm:
                score = max(score, 0.94)
            else:
                score = max(score, similarity(hint, norm) * 0.75)
        if score >= 0.62:
            scored.append((score, len(text), dict(raw)))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][2]


def _make_observation(
    *, project_id: str, evidence: Mapping[str, Any], kind: str, name: str,
    observed_type: str | None, observed_status: str | None = None, phase: str, role: str, source_role: str,
    primary_source: bool, confidence: float, extraction_method: str, attributes: Mapping[str, Any] | None = None,
) -> SemanticObservation:
    source_asset_id = str(evidence.get("source_asset_id") or "")
    evidence_id = str(evidence.get("id") or "")
    identity = {
        "project_id": project_id,
        "source_asset_id": source_asset_id,
        "evidence_unit_id": evidence_id,
        "observation_kind": kind,
        "observed_name": _norm(name),
        "observed_type": _norm(observed_type),
        "observed_status": _norm(observed_status),
        "occurrence_phase": phase,
        "occurrence_role": role,
    }
    observation_hash = _hash(identity)
    observation_id = str(uuid5(NAMESPACE_URL, "nave:semantic-observation:" + observation_hash))
    attrs = dict(attributes or {})
    attrs.setdefault("source_role", source_role)
    attrs.setdefault("normalized_by", OBSERVATION_VERSION)
    return SemanticObservation(
        id=observation_id,
        project_id=project_id,
        source_asset_id=source_asset_id,
        evidence_unit_id=evidence_id,
        observation_kind=kind,
        observed_name=str(name).strip(),
        observed_type=observed_type,
        observed_status=observed_status,
        occurrence_phase=phase,
        occurrence_role=role,
        attributes=attrs,
        source_authority_score=_authority(source_role, primary=primary_source),
        model_confidence=max(0.0, min(1.0, confidence)),
        extraction_method=extraction_method,
        observation_hash=observation_hash,
    )


def _normalized_execution_status(value: Any) -> str | None:
    norm = _norm(value)
    if not norm:
        return None
    if norm in {"executed", "executado", "executada", "realizado", "realizada", "completed", "concluido", "concluida"}:
        return "executed"
    if norm in {"partial", "parcial", "partially executed", "executado parcialmente", "executada parcialmente"}:
        return "partial"
    if norm in {"not executed", "nao executado", "nao executada", "cancelled", "canceled", "cancelado", "cancelada"}:
        return "not_executed"
    if norm in {"planned", "planejado", "planejada"}:
        return "planned"
    return None


def _item_is_solution(raw: Mapping[str, Any]) -> bool:
    item_type = _norm(raw.get("item_type") or raw.get("type") or raw.get("category"))
    return item_type in {
        "ativacao", "activation", "solucao", "solution", "experiencia", "experience",
        "oficina", "workshop", "mecanica", "mechanic",
    }


SOLUTION_MENTION_ENTITY_TYPES = {
    "activation", "solution", "deliverable", "gift", "presskit",
    "communication_asset", "technology",
}


def _file_analyst_mention_candidates(
    mentions: Sequence[Mapping[str, Any]],
    entities: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert File Analyst mentions into pre-domain signals, never domain truth.

    We deliberately exclude strategy/concept/journey/product/financial entities here: those
    belong to other semantic domains or are too ambiguous to auto-create Solution Instances.
    """
    out: list[dict[str, Any]] = []
    for mention in mentions:
        # Consume only File Analyst source-level mentions. V28.6/cross-source graph
        # projections must not become an implicit input to the new Domain Reconciler.
        if _norm(mention.get("mention_role")).replace(" ", "_") != "file_analyst_entity":
            continue
        entity = entities.get(str(mention.get("entity_id") or "")) or {}
        entity_type = _norm(entity.get("entity_type")).replace(" ", "_")
        if entity_type not in SOLUTION_MENTION_ENTITY_TYPES:
            continue
        name = str(mention.get("mention_text") or entity.get("canonical_name") or "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "observed_type": entity_type,
            "evidence_unit_id": str(mention.get("evidence_unit_id") or ""),
            "confidence": float(mention.get("confidence") or entity.get("confidence") or 0.70),
            "entity_id": str(entity.get("id") or ""),
            "entity_type": entity_type,
            "mention_role": mention.get("mention_role"),
        })
    return out


def _report_candidates(reports: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for report in reports:
        report_file_id = str(report.get("report_file_id") or "")
        for raw in report.get("activation_results") or []:
            if isinstance(raw, Mapping) and str(raw.get("name") or "").strip():
                out.append({
                    "kind": "solution_candidate",
                    "name": str(raw.get("name")).strip(),
                    "observed_type": "activation",
                    "observed_status": _normalized_execution_status(raw.get("status") or raw.get("outcome_status")),
                    "evidence_hint": raw.get("evidence"),
                    "report_file_id": report_file_id,
                    "raw": dict(raw),
                })
        for raw in report.get("item_results") or []:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("item_name") or raw.get("name") or "").strip()
            if name:
                is_solution = _item_is_solution(raw)
                out.append({
                    "kind": "solution_candidate" if is_solution else "material_mention",
                    "name": name,
                    "observed_type": "activation" if is_solution else "material",
                    "observed_status": _normalized_execution_status(raw.get("outcome_status") or raw.get("status")) if is_solution else None,
                    "evidence_hint": raw.get("evidence"),
                    "report_file_id": report_file_id,
                    "raw": dict(raw),
                })
    return out

def collect_project_semantic_observations(client: Any, project_id: str) -> dict[str, Any]:
    source = _project_evidence(client, project_id)
    reports = _read_rows(client, "project_report_analyses", equals={"project_id": project_id})
    financial_lines = _read_rows(client, "financial_line_items", equals={"project_id": project_id})
    evidence_by_id = {str(row.get("id")): dict(row) for row in source["evidence"] if row.get("id")}

    observations: list[SemanticObservation] = []
    report_solution_names: list[str] = []
    for candidate in _report_candidates(reports):
        asset_id = source["project_file_asset"].get(candidate["report_file_id"], "")
        evidence = _best_evidence(
            source["evidence_by_asset"].get(asset_id) or [],
            [candidate.get("evidence_hint"), candidate.get("name")],
        )
        if not evidence:
            continue  # fail closed: structured JSON without atomic evidence is not a semantic observation
        source_role, primary = _source_role(str(evidence.get("source_asset_id") or ""), source)
        kind = str(candidate["kind"])
        observed_status = candidate.get("observed_status")
        if kind == "solution_candidate":
            phase = "execution"
            role = "execution" if observed_status == "executed" else "result"
            report_solution_names.append(str(candidate["name"]))
        else:
            phase, role = "post_event", "result"
        observations.append(_make_observation(
            project_id=project_id,
            evidence=evidence,
            kind=kind,
            name=str(candidate["name"]),
            observed_type=candidate.get("observed_type"),
            observed_status=observed_status,
            phase=phase,
            role=role,
            source_role=source_role,
            primary_source=primary,
            confidence=0.98 if kind == "solution_candidate" else 0.96,
            extraction_method="project_report_analysis+evidence_binding",
            attributes={"report_file_id": candidate.get("report_file_id"), "report_payload": candidate.get("raw") or {}},
        ))

    # File Analyst entities are only local extraction signals here. Their existing
    # knowledge_entity identity is NOT adopted as Project Domain identity. This gives
    # proposal-only projects an evidence-led path without making memory_items authoritative.
    evidence_ids = list(evidence_by_id)
    mentions = _read_in(client, "entity_mentions", "evidence_unit_id", evidence_ids)
    entity_rows = _read_in(client, "knowledge_entities", "id", [row.get("entity_id") for row in mentions])
    entity_by_id = {str(row.get("id")): dict(row) for row in entity_rows if row.get("id")}
    for candidate in _file_analyst_mention_candidates(mentions, entity_by_id):
        evidence = evidence_by_id.get(str(candidate.get("evidence_unit_id") or ""))
        if not evidence:
            continue
        source_role, primary = _source_role(str(evidence.get("source_asset_id") or ""), source)
        phase, role = _phase_role(source_role)
        # Post-event File Analyst mentions prove mention, not execution. Only structured
        # report results with an explicit normalized status may create execution truth.
        observations.append(_make_observation(
            project_id=project_id,
            evidence=evidence,
            kind="solution_mention",
            name=str(candidate.get("name") or ""),
            observed_type=str(candidate.get("observed_type") or "solution"),
            observed_status=None,
            phase=phase,
            role=role,
            source_role=source_role,
            primary_source=primary,
            confidence=max(0.0, min(1.0, float(candidate.get("confidence") or 0.70))),
            extraction_method="file_analyst_entity_mention+evidence_binding",
            attributes={
                "file_analyst_signal_only": True,
                "file_analyst_entity_id": candidate.get("entity_id"),
                "file_analyst_entity_type": candidate.get("entity_type"),
                "mention_role": candidate.get("mention_role"),
            },
        ))

    # Corroborate execution candidates across proposal/briefing/budget Evidence. This
    # creates additional observations, not extra identities.
    for name in list(dict.fromkeys(report_solution_names)):
        name_norm = _norm(name)
        if not name_norm:
            continue
        for evidence in source["evidence"]:
            text = _norm(evidence.get("content_text"))
            if not text or name_norm not in text:
                continue
            aid = str(evidence.get("source_asset_id") or "")
            source_role, primary = _source_role(aid, source)
            phase, role = _phase_role(source_role)
            if phase == "post_event":
                continue
            observations.append(_make_observation(
                project_id=project_id,
                evidence=evidence,
                kind="solution_mention",
                name=name,
                observed_type="activation",
                phase=phase,
                role=role,
                source_role=source_role,
                primary_source=primary,
                confidence=0.94,
                extraction_method="cross_source_exact_name_evidence",
                attributes={"corroborates_execution_name": True},
            ))

        # Financial lines can corroborate even when the line description adds a prefix.
        for line in financial_lines:
            evidence_id = str(line.get("source_evidence_id") or "")
            evidence = evidence_by_id.get(evidence_id)
            if not evidence:
                continue
            if similarity(name, line.get("item_name")) < 0.84:
                continue
            aid = str(evidence.get("source_asset_id") or "")
            source_role, primary = _source_role(aid, source)
            observations.append(_make_observation(
                project_id=project_id,
                evidence=evidence,
                kind="solution_mention",
                name=name,
                observed_type="activation",
                phase="reference",
                role="budget_reference",
                source_role=source_role,
                primary_source=primary,
                confidence=0.92,
                extraction_method="financial_line_corroboration",
                attributes={"financial_line_item_id": str(line.get("id") or ""), "financial_item_name": line.get("item_name")},
            ))

    deduped = {obs.observation_hash: obs for obs in observations}
    return {
        "project_id": project_id,
        "observations": [obs.to_dict() for obs in deduped.values()],
        "report_solution_names": list(dict.fromkeys(report_solution_names)),
        "diagnostics": {
            "reports": len(reports),
            "project_evidence_units": len(source["evidence"]),
            "observations": len(deduped),
        },
        "source_snapshot": source,
    }


def _evidence_for_requirement(client: Any, project_id: str, requirements: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    links = _read_rows(client, "domain_object_evidence", equals={"project_id": project_id, "domain_table": "project_requirements"})
    evidence = _read_in(client, "evidence_units", "id", [row.get("evidence_unit_id") for row in links])
    current = {str(row.get("id")): dict(row) for row in evidence if row.get("is_current") is True and row.get("id")}
    out: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        eid = str(link.get("evidence_unit_id") or "")
        did = str(link.get("domain_id") or "")
        if eid in current and did:
            out.setdefault(did, []).append(current[eid])
    return out


def _stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _parse_localized_number(raw: str, *, suffix: str | None = None) -> float | None:
    token = str(raw or "").strip().replace(" ", "")
    if not token or not re.fullmatch(r"[0-9][0-9\.,]*", token):
        return None
    suffix_norm = _norm(suffix or "")
    try:
        if "." in token and "," in token:
            # Last separator is the decimal separator; the other is thousands.
            if token.rfind(",") > token.rfind("."):
                number = token.replace(".", "").replace(",", ".")
            else:
                number = token.replace(",", "")
        elif "," in token:
            left, right = token.rsplit(",", 1)
            if suffix_norm and len(right) <= 2:
                number = left.replace(",", "") + "." + right
            elif len(right) == 3 and left:
                number = token.replace(",", "")
            else:
                number = left.replace(",", "") + "." + right
        elif "." in token:
            left, right = token.rsplit(".", 1)
            if suffix_norm and len(right) <= 2:
                number = left.replace(".", "") + "." + right
            elif len(right) == 3 and left:
                number = token.replace(".", "")
            elif token.count(".") > 1:
                number = token.replace(".", "")
            else:
                number = token
        else:
            number = token
        value = float(number)
    except (TypeError, ValueError):
        return None
    if suffix_norm.startswith("milh"):
        value *= 1_000_000
    elif suffix_norm == "mil":
        value *= 1_000
    return value


def _money_number(text: str) -> float | None:
    raw_text = unicodedata.normalize("NFKC", str(text or "")).casefold().replace("\u00a0", " ")
    # Prefer explicitly-currency-scoped values. This handles both Brazilian and
    # US-formatted numbers that may coexist in legacy normalized descriptions.
    money_pattern = re.compile(
        r"r\$\s*([0-9][0-9\.,]*)\s*(milh(?:ão|ões|ao|oes)|mil)?\b",
        flags=re.I,
    )
    for match in money_pattern.finditer(raw_text):
        value = _parse_localized_number(match.group(1), suffix=match.group(2))
        if value is not None:
            return value

    suffix_pattern = re.compile(
        r"\b([0-9]+(?:[\.,][0-9]+)?)\s*(milh(?:ão|ões|ao|oes)|mil)\b",
        flags=re.I,
    )
    for match in suffix_pattern.finditer(raw_text):
        value = _parse_localized_number(match.group(1), suffix=match.group(2))
        if value is not None:
            return value
    return None


def _audience_range(text: str) -> tuple[float, float] | None:
    raw_text = unicodedata.normalize("NFKC", str(text or "")).casefold().replace("\u00a0", " ")
    # Preserve punctuation here: `_norm` intentionally removes dashes, which are
    # semantically meaningful for ranges such as 6–8 mil.
    raw_text = "".join(
        ch for ch in unicodedata.normalize("NFKD", raw_text)
        if not unicodedata.combining(ch)
    )
    pattern = re.compile(
        r"(?:entre\s+)?"
        r"([0-9]+(?:[\.,][0-9]+)?)\s*(mil)?\s*"
        r"(?:a|e|ate|[-–—])\s*"
        r"([0-9]+(?:[\.,][0-9]+)?)\s*(mil)?\b",
        flags=re.I,
    )
    candidates: list[tuple[int, float, float]] = []
    for match in pattern.finditer(raw_text):
        left = _parse_localized_number(match.group(1))
        right = _parse_localized_number(match.group(3))
        if left is None or right is None:
            continue
        left_mil = bool(match.group(2))
        right_mil = bool(match.group(4))
        has_mil = left_mil or right_mil
        if has_mil:
            # "6–8 mil" conventionally scopes the suffix to the range.
            if left < 1000:
                left *= 1000
            if right < 1000:
                right *= 1000
        elif max(left, right) < 1000:
            # Avoid interpreting age ranges (e.g. 30–45) as event audience.
            continue
        candidates.append((1 if has_mil else 0, min(left, right), max(left, right)))
    if not candidates:
        return None
    # Prefer explicitly-thousands-qualified ranges over generic large-number ranges.
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    _priority, low, high = candidates[0]
    return low, high

def collect_project_context_and_constraints(client: Any, project_id: str) -> dict[str, Any]:
    project_rows = _read_rows(client, "projects", equals={"id": project_id})
    project = project_rows[0] if project_rows else {}
    project_name = str(project.get("project_name") or project.get("name") or "").strip()
    event_name = str(project.get("event_name") or "").strip()
    requirements = _read_rows(client, "project_requirements", equals={"project_id": project_id})
    evidence_by_requirement = _evidence_for_requirement(client, project_id, requirements)
    context_elements: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []

    for req in requirements:
        req_id = str(req.get("id") or "")
        req_entity_id = str(req.get("entity_id") or "")
        if not req_id or not req_entity_id:
            continue
        evidences = evidence_by_requirement.get(req_id) or []
        evidence = min(evidences, key=lambda row: len(str(row.get("content_text") or "")), default=None)
        if not evidence:
            continue
        title = str(req.get("title") or "Requisito").strip()
        description = str(req.get("description") or "").strip()
        evidence_text = str(evidence.get("content_text") or "").strip()
        # Evidence comes first so legacy display formatting cannot override the
        # value/range explicitly present in the source.
        text = " ".join(v for v in (evidence_text, title, description) if v)
        norm = _norm(text)
        evidence_id = str(evidence.get("id") or "")

        context_type: str | None = None
        if re.search(r"\b(objetivo|objective|finalidade)\b", norm):
            context_type = "objective"
        elif re.search(r"\b(publico|audiencia|audience|target)\b", norm):
            context_type = "audience_context"
        elif re.search(r"\b(prazo|deadline|data limite|cronograma)\b", norm):
            context_type = "deadline_context"
        elif re.search(r"\b(praca|cidade|localizacao|geografia|geography)\b", norm):
            context_type = "geography"
        if context_type:
            context_key = _hash({"project": project_id, "type": context_type, "requirement": req_id})
            context_elements.append({
                "id": _stable_uuid("nave:context:" + context_key),
                "entity_id": _stable_uuid("nave:context-entity:" + context_key),
                "context_key": context_key,
                "context_type": context_type,
                "title": title,
                "statement": evidence_text or description,
                "source_evidence_id": evidence_id,
                "source_claim_id": req.get("source_claim_id"),
                "scope": {"requirement_id": req_id},
                "attributes": {"derived_from_requirement": True, "normalized_by": OBSERVATION_VERSION},
                "confidence": float(req.get("confidence") or 0.90),
                "authority_score": 0.86,
            })

        if re.search(r"\b(budget|orcamento|investimento|verba)\b", norm):
            value = _money_number(text)
            if value is not None:
                # A numeric value alone proves a budget amount, not its comparison semantics.
                # Stay fail-closed unless the source language establishes the operator.
                operator = "unspecified"
                if re.search(r"\b(ate|teto|maximo|limite|nao ultrapassar|nao exceder)\b", norm):
                    operator = "<="
                elif re.search(r"\b(minimo|ao menos|pelo menos)\b", norm):
                    operator = ">="
                elif re.search(r"\b(envelope|verba disponivel|budget disponivel|orcamento disponivel)\b", norm):
                    operator = "envelope"
                elif re.search(r"\b(exatamente|valor exato)\b", norm):
                    operator = "="
                constraint_hash = _hash({"project": project_id, "requirement": req_id, "type": "budget", "value": value, "operator": operator, "evidence": evidence_id})
                constraints.append({
                    "id": _stable_uuid("nave:constraint:" + constraint_hash),
                    "requirement_id": req_id,
                    "requirement_entity_id": req_entity_id,
                    "constraint_type": "budget",
                    "operator": operator,
                    "value_numeric": value,
                    "value_min": None,
                    "value_max": None,
                    "value_text": None,
                    "value_json": {},
                    "unit": None,
                    "currency": "BRL",
                    "scope_type": "project",
                    "scope_entity_id": None,
                    "scope_json": {
                        "project_name": project_name or None,
                        "event_name": event_name or None,
                        "source_text": evidence_text[:1200],
                    },
                    "source_evidence_id": evidence_id,
                    "confidence": 0.97,
                    "authority_score": 0.86,
                    "constraint_hash": constraint_hash,
                })

        if re.search(r"\b(publico|audiencia|pessoas|participantes|convidados)\b", norm):
            audience = _audience_range(text)
            if audience:
                low, high = audience
                constraint_hash = _hash({"project": project_id, "requirement": req_id, "type": "expected_attendees", "min": low, "max": high, "evidence": evidence_id})
                constraints.append({
                    "id": _stable_uuid("nave:constraint:" + constraint_hash),
                    "requirement_id": req_id,
                    "requirement_entity_id": req_entity_id,
                    "constraint_type": "expected_attendees",
                    "operator": "between",
                    "value_numeric": None,
                    "value_min": low,
                    "value_max": high,
                    "value_text": None,
                    "value_json": {},
                    "unit": "people",
                    "currency": None,
                    "scope_type": "event",
                    "scope_entity_id": None,
                    "scope_json": {
                        "event_name": event_name or project_name or None,
                        "project_name": project_name or None,
                        "source_text": evidence_text[:1200],
                    },
                    "source_evidence_id": evidence_id,
                    "confidence": 0.97,
                    "authority_score": 0.86,
                    "constraint_hash": constraint_hash,
                })

    return {"context_elements": context_elements, "requirement_constraints": constraints}
