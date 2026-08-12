from __future__ import annotations

"""NAVE Intelligence — Cross-Source Linker v1.

Runs after the File Analyst has persisted the individual sources of a project. It
resolves entity identity, links project solutions to cost lines, recognizes explicit
execution evidence in post-event reports and surfaces ambiguous cross-source facts as
reviewable findings instead of silently inventing conclusions.

This layer is intentionally conservative. It does not replace the Project Analyst V2;
it creates a connected, auditable graph for that analyst to reason over.
"""

import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence

from entity_resolution import (
    AUTO_MERGE_THRESHOLD,
    REVIEW_THRESHOLD,
    MatchResult,
    ResolutionEntity,
    entity_match_score,
    normalize_text,
    records_from_rows,
    resolve_entities,
)

CROSS_SOURCE_LINKER_VERSION = "cross-source-linker-v1"
CROSS_SOURCE_SCHEMA_VERSION = "1"
CROSS_SOURCE_PROMPT_VERSION = "deterministic-2026-08-12.v1"

_LINKABLE_COST_SOURCE_TYPES = {
    "activation", "solution", "venue", "venue_space", "product", "gift",
    "presskit", "deliverable", "communication_asset", "technology",
}
_EXECUTABLE_TYPES = {
    "activation", "solution", "venue", "venue_space", "product", "gift",
    "presskit", "deliverable", "communication_asset", "technology", "concept",
}
_STOP = {
    "a", "as", "o", "os", "um", "uma", "de", "da", "das", "do", "dos", "e", "em", "no", "na",
    "para", "por", "com", "sem", "the", "and", "of", "for", "in", "on", "with", "to",
    "ativacao", "activation", "gift", "brinde", "press", "kit", "item", "locacao", "servico", "servicos",
}
_DIRECT_PAY_FAMILIES: dict[str, set[str]] = {
    "scenography": {"cenografia", "cenografico", "cenografica", "scenography", "infraestrutura", "estrutura", "casa", "stand", "booth", "portico", "paredes", "cobertura", "frontao"},
    "venue": {"local", "venue", "espaco", "locacao", "sala"},
    "food_beverage": {"alimentacao", "bebida", "bebidas", "catering", "a b", "food", "beverage"},
    "artistic": {"artistico", "artista", "talent", "show", "atracao"},
}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        return [dict(data)]
    return []


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    return str(value)


def _sha(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return normalize_text(value)


def _tokens(value: Any) -> set[str]:
    return {token for token in _norm(value).split() if len(token) > 1 and token not in _STOP}


def _select_in(client: Any, table: str, column: str, values: Sequence[str], columns: str = "*") -> list[dict[str, Any]]:
    values = [str(v) for v in values if str(v).strip()]
    if not values:
        return []
    result: list[dict[str, Any]] = []
    for start in range(0, len(values), 150):
        chunk = values[start:start + 150]
        try:
            result.extend(_rows(client.table(table).select(columns).in_(column, chunk).execute()))
        except Exception:
            for value in chunk:
                try:
                    result.extend(_rows(client.table(table).select(columns).eq(column, value).execute()))
                except Exception:
                    continue
    return result


def _project_entity(client: Any, project_id: str) -> dict[str, Any] | None:
    try:
        rows = _rows(
            client.table("knowledge_entities").select("*")
            .eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _start_run(client: Any, project_entity_id: str, project_id: str) -> dict[str, Any] | None:
    payload = {
        "analyzer_type": "cross_source_linker",
        "scope_kind": "project",
        "scope_entity_id": project_entity_id,
        "pipeline_version": CROSS_SOURCE_LINKER_VERSION,
        "code_version": "28.2.2",
        "prompt_version": CROSS_SOURCE_PROMPT_VERSION,
        "schema_version": CROSS_SOURCE_SCHEMA_VERSION,
        "input_signature": _sha(f"{project_id}|{CROSS_SOURCE_LINKER_VERSION}"),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"project_id": project_id},
    }
    try:
        rows = _rows(client.table("intelligence_runs").insert(payload).execute())
        return rows[0] if rows else None
    except Exception:
        return None


def _finish_run(client: Any, run: Mapping[str, Any] | None, started: float, status: str, counts: Mapping[str, Any], error: str | None = None) -> None:
    if not run or not run.get("id"):
        return
    payload = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "latency_ms": int((time.monotonic() - started) * 1000),
        "output_signature": _sha(json.dumps(_safe(counts), sort_keys=True, ensure_ascii=False)),
        "error_detail": error,
        "metadata": {"counts": _safe(counts), "version": CROSS_SOURCE_LINKER_VERSION},
    }
    try:
        client.table("intelligence_runs").update(payload).eq("id", run["id"]).execute()
    except Exception:
        pass


def _load_snapshot(client: Any, project_entity: Mapping[str, Any]) -> dict[str, Any]:
    project_entity_id = str(project_entity["id"])
    contexts = _rows(
        client.table("source_asset_contexts").select("source_asset_id,context_role,is_primary_source")
        .eq("context_entity_id", project_entity_id).execute()
    )
    asset_roles: dict[str, set[str]] = defaultdict(set)
    for row in contexts:
        asset_roles[str(row.get("source_asset_id"))].add(str(row.get("context_role") or ""))
    asset_ids = list(asset_roles)
    evidence = _select_in(client, "evidence_units", "source_asset_id", asset_ids, "id,source_asset_id,unit_type,ordinal,locator,content_text,content_json,extraction_confidence,is_current")
    evidence = [row for row in evidence if row.get("is_current") is not False]
    evidence_by_id = {str(row["id"]): row for row in evidence if row.get("id")}
    evidence_ids = list(evidence_by_id)
    mentions = _select_in(client, "entity_mentions", "evidence_unit_id", evidence_ids, "id,evidence_unit_id,entity_id,mention_text,confidence")
    mentioned_entity_ids = {str(row.get("entity_id")) for row in mentions if row.get("entity_id")}
    scoped_entities = _rows(
        client.table("knowledge_entities").select("*").eq("scope_entity_id", project_entity_id).execute()
    )
    entity_ids = mentioned_entity_ids | {str(row.get("id")) for row in scoped_entities if row.get("id")} | {project_entity_id}
    entities = _select_in(client, "knowledge_entities", "id", list(entity_ids), "*")
    entities_by_id = {str(row["id"]): row for row in entities if row.get("id")}
    aliases = _select_in(client, "entity_aliases", "entity_id", list(entity_ids), "entity_id,alias,normalized_alias,active")
    aliases_by_entity: dict[str, list[str]] = defaultdict(list)
    for row in aliases:
        if row.get("active") is False:
            continue
        aliases_by_entity[str(row.get("entity_id"))].append(str(row.get("alias") or ""))
    mentions_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    roles_by_entity: dict[str, set[str]] = defaultdict(set)
    evidence_ids_by_entity: dict[str, list[str]] = defaultdict(list)
    for mention in mentions:
        entity_id = str(mention.get("entity_id") or "")
        evidence_id = str(mention.get("evidence_unit_id") or "")
        if not entity_id or not evidence_id:
            continue
        mentions_by_entity[entity_id].append(mention)
        evidence_ids_by_entity[entity_id].append(evidence_id)
        ev = evidence_by_id.get(evidence_id) or {}
        roles_by_entity[entity_id].update(asset_roles.get(str(ev.get("source_asset_id") or ""), set()))
    return {
        "asset_roles": asset_roles,
        "evidence": evidence,
        "evidence_by_id": evidence_by_id,
        "entities": entities,
        "entities_by_id": entities_by_id,
        "aliases_by_entity": aliases_by_entity,
        "mentions_by_entity": mentions_by_entity,
        "roles_by_entity": roles_by_entity,
        "evidence_ids_by_entity": evidence_ids_by_entity,
        "project_entity_id": project_entity_id,
    }


def _ensure_alias(client: Any, canonical_id: str, alias: str, scope_entity_id: str | None, confidence: float) -> None:
    normalized = _norm(alias)
    if not normalized:
        return
    try:
        existing = _rows(
            client.table("entity_aliases").select("id")
            .eq("entity_id", canonical_id).eq("normalized_alias", normalized).eq("active", True).limit(1).execute()
        )
        if existing:
            return
        client.table("entity_aliases").insert({
            "entity_id": canonical_id,
            "alias": alias,
            "normalized_alias": normalized,
            "alias_type": "name",
            "scope_entity_id": scope_entity_id,
            "confidence": confidence,
            "active": True,
        }).execute()
    except Exception:
        pass


def _persist_entity_resolution(client: Any, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    entities = [
        row for row in snapshot["entities"]
        if str(row.get("entity_type") or "") != "project"
        and str(row.get("status") or "active") in {"active", "review_required"}
    ]
    records = records_from_rows(
        entities,
        aliases_by_entity=snapshot["aliases_by_entity"],
        mention_counts={entity_id: len(rows) for entity_id, rows in snapshot["mentions_by_entity"].items()},
    )
    clusters, reviews = resolve_entities(records)
    merged = 0
    aliases_added = 0
    for cluster in clusters:
        canonical = snapshot["entities_by_id"].get(cluster.canonical_id) or {}
        scope_id = str(canonical.get("scope_entity_id") or "") or None
        for member_id in cluster.member_ids:
            if member_id == cluster.canonical_id:
                continue
            try:
                client.table("knowledge_entities").update({
                    "canonical_entity_id": cluster.canonical_id,
                    "status": "merged",
                    "confidence": max(float((snapshot["entities_by_id"].get(member_id) or {}).get("confidence") or 0.0), cluster.confidence),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", member_id).execute()
                merged += 1
            except Exception:
                continue
        for alias in cluster.aliases_to_add:
            before = len(snapshot["aliases_by_entity"].get(cluster.canonical_id, []))
            _ensure_alias(client, cluster.canonical_id, alias, scope_id, cluster.confidence)
            aliases_added += 1 if before == 0 or _norm(alias) not in {_norm(v) for v in snapshot["aliases_by_entity"].get(cluster.canonical_id, [])} else 0
    return {"clusters": clusters, "reviews": reviews, "merged": merged, "aliases_added": aliases_added}


def _canonical_map(entities: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    rows = {str(row.get("id")): row for row in entities if row.get("id")}
    result: dict[str, str] = {}
    for entity_id in rows:
        seen: set[str] = set()
        current = entity_id
        while current in rows and current not in seen:
            seen.add(current)
            parent = str(rows[current].get("canonical_entity_id") or "")
            if not parent:
                break
            current = parent
        result[entity_id] = current
    return result


def cost_link_score(source: ResolutionEntity, line: ResolutionEntity) -> tuple[float, list[str]]:
    if source.entity_type not in _LINKABLE_COST_SOURCE_TYPES or line.entity_type != "financial_line_item":
        return 0.0, ["tipos não elegíveis para costed_by"]
    source_tokens = _tokens(" ".join((source.canonical_name, *source.aliases)))
    attrs = line.attributes or {}
    target_text = " ".join(str(v or "") for v in (
        line.canonical_name, attrs.get("description"), attrs.get("category")
    ))
    target_tokens = _tokens(target_text)
    if not source_tokens or not target_tokens:
        return 0.0, ["texto insuficiente"]
    overlap = source_tokens & target_tokens
    containment = len(overlap) / max(1, len(source_tokens))
    jaccard = len(overlap) / max(1, len(source_tokens | target_tokens))
    seq = SequenceMatcher(None, " ".join(sorted(source_tokens)), " ".join(sorted(target_tokens))).ratio()
    score = 0.58 * containment + 0.18 * jaccard + 0.18 * seq
    reasons: list[str] = []
    if containment == 1.0 and len(source_tokens) >= 1:
        score = max(score, 0.93 if len(source_tokens) >= 2 else 0.86)
        reasons.append("todos os termos significativos da solução aparecem na linha financeira")
    category = _norm(attrs.get("category"))
    category_boost = {
        "activation": ("ativacao",),
        "gift": ("brinde", "gift"),
        "presskit": ("press kit", "press"),
        "venue": ("local", "locacao", "venue"),
        "venue_space": ("local", "locacao", "venue"),
        "technology": ("tecnologia", "av", "audiovisual"),
    }.get(source.entity_type, ())
    if category_boost and any(token in category for token in category_boost):
        score += 0.05
        reasons.append("categoria financeira coerente com o tipo da entidade")
    return round(min(1.0, score), 4), reasons or ["similaridade lexical/contextual"]


def _relation_hash(source_id: str, relation_type: str, target_id: str, scope_id: str, kind: str) -> str:
    return _sha(json.dumps({"source": source_id, "relation": relation_type, "target": target_id, "scope": scope_id, "kind": kind}, sort_keys=True))


def _persist_relation(
    client: Any,
    *,
    source_id: str,
    relation_type: str,
    target_id: str,
    scope_id: str,
    confidence: float,
    run_id: str | None,
    evidence_ids: Sequence[str] = (),
    relation_kind: str = "inference",
    status: str = "active",
    attributes: Mapping[str, Any] | None = None,
) -> bool:
    if not source_id or not target_id or source_id == target_id:
        return False
    relation_hash = _relation_hash(source_id, relation_type, target_id, scope_id, relation_kind)
    try:
        existing = _rows(client.table("knowledge_relations").select("id,confidence,status").eq("relation_hash", relation_hash).limit(1).execute())
        if existing:
            client.table("knowledge_relations").update({
                "confidence": max(float(existing[0].get("confidence") or 0.0), confidence),
                "strength": max(float(existing[0].get("confidence") or 0.0), confidence),
                "status": status,
                "attributes": _safe(attributes or {}),
                "intelligence_run_id": run_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", existing[0]["id"]).execute()
            relation_id = str(existing[0]["id"])
        else:
            rows = _rows(client.table("knowledge_relations").insert({
                "source_entity_id": source_id,
                "relation_type": relation_type,
                "target_entity_id": target_id,
                "scope_entity_id": scope_id,
                "relation_kind": relation_kind,
                "strength": confidence,
                "confidence": confidence,
                "status": status,
                "attributes": _safe(attributes or {}),
                "intelligence_run_id": run_id,
                "relation_hash": relation_hash,
            }).execute())
            if not rows:
                return False
            relation_id = str(rows[0]["id"])
        for evidence_id in dict.fromkeys(str(v) for v in evidence_ids if str(v)):
            try:
                client.table("relation_evidence").insert({
                    "relation_id": relation_id,
                    "evidence_unit_id": evidence_id,
                    "support_type": "supports",
                    "evidence_weight": 1.0,
                }).execute()
            except Exception:
                pass
        return True
    except Exception:
        return False


def _persist_text_claim(
    client: Any,
    *,
    subject_id: str,
    predicate: str,
    value_text: str,
    scope_id: str,
    confidence: float,
    authority_score: float,
    run_id: str | None,
    evidence_ids: Sequence[str],
    claim_kind: str = "inference",
) -> bool:
    payload_key = {"subject": subject_id, "predicate": predicate, "value_text": value_text, "scope": scope_id, "kind": claim_kind}
    claim_hash = _sha(json.dumps(payload_key, sort_keys=True, ensure_ascii=False))
    try:
        existing = _rows(client.table("knowledge_claims").select("id,model_confidence").eq("claim_hash", claim_hash).limit(1).execute())
        if existing:
            claim_id = str(existing[0]["id"])
            client.table("knowledge_claims").update({
                "model_confidence": max(float(existing[0].get("model_confidence") or 0.0), confidence),
                "authority_score": authority_score,
                "intelligence_run_id": run_id,
            }).eq("id", claim_id).execute()
        else:
            rows = _rows(client.table("knowledge_claims").insert({
                "subject_entity_id": subject_id,
                "predicate": predicate,
                "value_type": "text",
                "value_text": value_text,
                "claim_kind": claim_kind,
                "scope_entity_id": scope_id,
                "model_confidence": confidence,
                "authority_score": authority_score,
                "status": "active",
                "intelligence_run_id": run_id,
                "claim_hash": claim_hash,
            }).execute())
            if not rows:
                return False
            claim_id = str(rows[0]["id"])
        for evidence_id in dict.fromkeys(str(v) for v in evidence_ids if str(v)):
            try:
                client.table("claim_evidence").insert({
                    "claim_id": claim_id,
                    "evidence_unit_id": evidence_id,
                    "support_type": "supports",
                    "evidence_weight": 1.0,
                }).execute()
            except Exception:
                pass
        return True
    except Exception:
        return False


def _persist_finding(
    client: Any,
    *,
    run_id: str | None,
    scope_id: str,
    finding_type: str,
    title: str,
    statement: str,
    finding_kind: str,
    importance: str,
    confidence: float,
    evidence_ids: Sequence[str] = (),
    entity_ids: Sequence[str] = (),
    recommended_action: str | None = None,
) -> bool:
    if not run_id:
        return False
    try:
        rows = _rows(client.table("intelligence_findings").insert({
            "intelligence_run_id": run_id,
            "analyzer_type": "cross_source_linker",
            "scope_entity_id": scope_id,
            "finding_type": finding_type,
            "title": title,
            "statement": statement,
            "finding_kind": finding_kind,
            "importance": importance,
            "confidence": confidence,
            "impact_domains": ["entity_resolution", "cross_source_reasoning"],
            "recommended_action": recommended_action,
            "status": "active",
        }).execute())
        if not rows:
            return False
        finding_id = str(rows[0]["id"])
        for evidence_id in dict.fromkeys(str(v) for v in evidence_ids if str(v)):
            try:
                client.table("finding_evidence").insert({
                    "finding_id": finding_id,
                    "evidence_unit_id": evidence_id,
                    "evidence_role": "support",
                }).execute()
            except Exception:
                pass
        for entity_id in dict.fromkeys(str(v) for v in entity_ids if str(v)):
            try:
                client.table("finding_entities").insert({
                    "finding_id": finding_id,
                    "entity_id": entity_id,
                    "role": "subject",
                }).execute()
            except Exception:
                pass
        return True
    except Exception:
        return False


def _canonical_resolution_entity(row: Mapping[str, Any], aliases: Sequence[str], mention_count: int) -> ResolutionEntity:
    attrs = row.get("attributes") if isinstance(row.get("attributes"), Mapping) else {}
    return ResolutionEntity(
        id=str(row.get("id")),
        entity_type=str(row.get("entity_type") or ""),
        canonical_name=str(row.get("canonical_name") or ""),
        aliases=tuple(str(v) for v in aliases if str(v).strip()),
        entity_kind=str(row.get("entity_kind") or "project_instance"),
        scope_entity_id=str(row.get("scope_entity_id") or "") or None,
        domain_table=str(row.get("domain_table") or "") or None,
        domain_id=str(row.get("domain_id") or "") or None,
        confidence=float(row.get("confidence") or 0.0),
        mention_count=mention_count,
        attributes=dict(attrs),
    )


def _link_costs(client: Any, snapshot: Mapping[str, Any], run_id: str | None) -> tuple[int, list[dict[str, Any]]]:
    canonical = _canonical_map(snapshot["entities"])
    rows_by_root: dict[str, dict[str, Any]] = {}
    roles_by_root: dict[str, set[str]] = defaultdict(set)
    evidence_by_root: dict[str, list[str]] = defaultdict(list)
    aliases_by_root: dict[str, list[str]] = defaultdict(list)
    for row in snapshot["entities"]:
        entity_id = str(row.get("id") or "")
        if not entity_id:
            continue
        root = canonical.get(entity_id, entity_id)
        root_row = snapshot["entities_by_id"].get(root) or row
        rows_by_root[root] = root_row
        roles_by_root[root].update(snapshot["roles_by_entity"].get(entity_id, set()))
        evidence_by_root[root].extend(snapshot["evidence_ids_by_entity"].get(entity_id, []))
        aliases_by_root[root].append(str(row.get("canonical_name") or ""))
        aliases_by_root[root].extend(snapshot["aliases_by_entity"].get(entity_id, []))

    sources: list[ResolutionEntity] = []
    lines: list[ResolutionEntity] = []
    for root, row in rows_by_root.items():
        entity = _canonical_resolution_entity(row, aliases_by_root[root], len(evidence_by_root[root]))
        if entity.entity_type == "financial_line_item":
            lines.append(entity)
        elif entity.entity_type in _LINKABLE_COST_SOURCE_TYPES and roles_by_root[root] & {"proposal_presentation", "final_presentation", "post_event_report", "briefing_original"}:
            sources.append(entity)

    linked = 0
    review_candidates: list[dict[str, Any]] = []
    for source in sources:
        scored: list[tuple[float, ResolutionEntity, list[str]]] = []
        for line in lines:
            score, reasons = cost_link_score(source, line)
            if score >= 0.68:
                scored.append((score, line, reasons))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            continue
        best_score, best_line, reasons = scored[0]
        # Avoid auto-linking ambiguous twins with virtually equal scores.
        second = scored[1][0] if len(scored) > 1 else 0.0
        evidence = list(dict.fromkeys(evidence_by_root[source.id] + evidence_by_root[best_line.id]))[:10]
        if best_score >= 0.86 and best_score - second >= 0.06:
            if _persist_relation(
                client,
                source_id=source.id,
                relation_type="costed_by",
                target_id=best_line.id,
                scope_id=snapshot["project_entity_id"],
                confidence=best_score,
                run_id=run_id,
                evidence_ids=evidence,
                relation_kind="inference",
                attributes={"method": "cross_source_cost_link_v1", "reasons": reasons},
            ):
                linked += 1
        elif best_score >= 0.74:
            review_candidates.append({"source": source, "target": best_line, "score": best_score, "evidence": evidence, "reasons": reasons})
    return linked, review_candidates


def _explicit_client_paid_relations(client: Any, snapshot: Mapping[str, Any], run_id: str | None, project_entity: Mapping[str, Any]) -> int:
    brand_name = str((project_entity.get("attributes") or {}).get("client_brand") or "").strip()
    if not brand_name:
        return 0
    normalized = _norm(brand_name)
    brand_rows = _rows(client.table("knowledge_entities").select("*").eq("entity_type", "brand").eq("normalized_name", normalized).limit(2).execute())
    if brand_rows:
        brand = brand_rows[0]
    else:
        inserted = _rows(client.table("knowledge_entities").insert({
            "entity_type": "brand",
            "canonical_name": brand_name,
            "normalized_name": normalized,
            "entity_kind": "canonical",
            "attributes": {"created_by": CROSS_SOURCE_LINKER_VERSION},
            "status": "active",
            "confidence": 0.88,
        }).execute())
        if not inserted:
            return 0
        brand = inserted[0]
    count = 0
    for row in snapshot["entities"]:
        if str(row.get("entity_type") or "") != "financial_line_item":
            continue
        attrs = row.get("attributes") if isinstance(row.get("attributes"), Mapping) else {}
        if str(attrs.get("item_status") or "") != "client_responsibility":
            continue
        entity_id = str(row.get("id") or "")
        if _persist_relation(
            client,
            source_id=entity_id,
            relation_type="paid_by_client",
            target_id=str(brand["id"]),
            scope_id=snapshot["project_entity_id"],
            confidence=0.99,
            run_id=run_id,
            evidence_ids=snapshot["evidence_ids_by_entity"].get(entity_id, [])[:5],
            relation_kind="fact",
            attributes={"method": "explicit_item_status_client_responsibility"},
        ):
            count += 1
    return count


def _direct_pay_review_candidates(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    briefing_evidence = [
        row for row in snapshot["evidence"]
        if "briefing_original" in snapshot["asset_roles"].get(str(row.get("source_asset_id") or ""), set())
        and row.get("content_text")
    ]
    direct_rows: list[dict[str, Any]] = []
    for row in briefing_evidence:
        text = str(row.get("content_text") or "")
        norm = _norm(text)
        direct_signal = any(signal in norm for signal in (
            "pagamento direto", "pago diretamente", "pagar diretamente",
            "pagamento sera realizado diretamente", "responsabilidade cliente",
        )) or bool(re.search(r"\bpag(?:ar|am|arem|ue|uem)?\w*\b.{0,90}\b(?:diretamente|forma direta)\b", norm))
        if direct_signal:
            families = [family for family, terms in _DIRECT_PAY_FAMILIES.items() if any(term in norm for term in terms)]
            direct_rows.append({"evidence": row, "families": families, "text": text})
    if not direct_rows:
        return []

    candidates: list[dict[str, Any]] = []
    for entity in snapshot["entities"]:
        if str(entity.get("entity_type") or "") != "financial_line_item":
            continue
        attrs = entity.get("attributes") if isinstance(entity.get("attributes"), Mapping) else {}
        if str(attrs.get("item_status") or "") == "client_responsibility":
            continue
        line_text = _norm(" ".join(str(v or "") for v in (entity.get("canonical_name"), attrs.get("description"), attrs.get("category"))))
        value = float(attrs.get("client_total") or 0.0)
        if value <= 0:
            continue
        for brief in direct_rows:
            score = 0.0
            matched_family = None
            for family in brief["families"]:
                terms = _DIRECT_PAY_FAMILIES[family]
                hits = sum(1 for term in terms if term in line_text)
                if hits:
                    local = min(0.92, 0.70 + hits * 0.06)
                    if local > score:
                        score = local
                        matched_family = family
            if score >= 0.74:
                candidates.append({
                    "line": entity,
                    "brief_evidence": brief["evidence"],
                    "score": score,
                    "family": matched_family,
                    "value": value,
                })
    candidates.sort(key=lambda row: (row["score"], row["value"]), reverse=True)
    return candidates


def _execution_evidence(client: Any, snapshot: Mapping[str, Any], run_id: str | None, project_entity: Mapping[str, Any]) -> int:
    canonical = _canonical_map(snapshot["entities"])
    roots: dict[str, dict[str, Any]] = {}
    roles: dict[str, set[str]] = defaultdict(set)
    evidences: dict[str, list[str]] = defaultdict(list)
    for row in snapshot["entities"]:
        entity_id = str(row.get("id") or "")
        if not entity_id:
            continue
        root = canonical.get(entity_id, entity_id)
        roots[root] = snapshot["entities_by_id"].get(root) or row
        roles[root].update(snapshot["roles_by_entity"].get(entity_id, set()))
        for ev_id in snapshot["evidence_ids_by_entity"].get(entity_id, []):
            ev = snapshot["evidence_by_id"].get(ev_id) or {}
            if "post_event_report" in snapshot["asset_roles"].get(str(ev.get("source_asset_id") or ""), set()):
                evidences[root].append(ev_id)
    count = 0
    for root, row in roots.items():
        if str(row.get("entity_type") or "") not in _EXECUTABLE_TYPES:
            continue
        if "post_event_report" not in roles[root] or not evidences[root]:
            continue
        if _persist_text_claim(
            client,
            subject_id=root,
            predicate="execution_result",
            value_text="executed",
            scope_id=snapshot["project_entity_id"],
            confidence=0.93,
            authority_score=0.96,
            run_id=run_id,
            evidence_ids=evidences[root][:8],
            claim_kind="inference",
        ):
            count += 1

    report_units = [
        row for row in snapshot["evidence"]
        if "post_event_report" in snapshot["asset_roles"].get(str(row.get("source_asset_id") or ""), set())
        and row.get("content_text")
    ]
    strong_markers = 0
    project_evidence: list[str] = []
    for row in report_units:
        norm = _norm(row.get("content_text"))
        if any(marker in norm for marker in (
            "presentes no evento", "produzidas", "distribuidas", "sobras", "fotos", "after movie", "realizado", "executado"
        )):
            strong_markers += 1
            project_evidence.append(str(row.get("id")))
    if strong_markers >= 2:
        if _persist_text_claim(
            client,
            subject_id=str(project_entity["id"]),
            predicate="execution_result",
            value_text="executed",
            scope_id=snapshot["project_entity_id"],
            confidence=0.97,
            authority_score=0.98,
            run_id=run_id,
            evidence_ids=project_evidence[:10],
            claim_kind="fact",
        ):
            count += 1
    return count


def _project_numeric_claims(client: Any, project_entity_id: str) -> tuple[dict[str, float], dict[str, list[str]]]:
    try:
        claims = _rows(
            client.table("knowledge_claims").select("id,predicate,value_numeric,model_confidence,authority_score,status")
            .eq("subject_entity_id", project_entity_id).eq("status", "active").execute()
        )
    except Exception:
        return {}, {}
    values: dict[str, tuple[float, float, str]] = {}
    claim_ids: dict[str, str] = {}
    for row in claims:
        if row.get("value_numeric") is None:
            continue
        pred = str(row.get("predicate") or "")
        authority = float(row.get("authority_score") or 0.0)
        confidence = float(row.get("model_confidence") or 0.0)
        score = authority * 0.65 + confidence * 0.35
        if pred not in values or score > values[pred][1]:
            values[pred] = (float(row["value_numeric"]), score, str(row.get("id")))
            claim_ids[pred] = str(row.get("id"))
    evidence_by_pred: dict[str, list[str]] = defaultdict(list)
    if claim_ids:
        rows = _select_in(client, "claim_evidence", "claim_id", list(claim_ids.values()), "claim_id,evidence_unit_id,support_type")
        pred_by_claim = {claim_id: pred for pred, claim_id in claim_ids.items()}
        for row in rows:
            pred = pred_by_claim.get(str(row.get("claim_id") or ""))
            if pred and str(row.get("support_type") or "supports") in {"supports", "partially_supports"}:
                evidence_by_pred[pred].append(str(row.get("evidence_unit_id")))
    return {pred: val[0] for pred, val in values.items()}, dict(evidence_by_pred)


def run_project_cross_source_intelligence(client: Any, project_id: str) -> dict[str, Any]:
    """Resolve + link one project's Intelligence Graph after all source files were analyzed."""
    try:
        from intelligence_graph_db import foundation_available
        if not foundation_available(client):
            return {"status": "skipped_foundation_missing", "project_id": project_id}
    except Exception:
        return {"status": "skipped_foundation_missing", "project_id": project_id}

    project = _project_entity(client, project_id)
    if not project:
        return {"status": "skipped_project_entity_missing", "project_id": project_id}
    started = time.monotonic()
    run = _start_run(client, str(project["id"]), project_id)
    run_id = str(run.get("id")) if run and run.get("id") else None
    counts: dict[str, Any] = {
        "entities_merged": 0,
        "resolution_reviews": 0,
        "cost_links": 0,
        "cost_link_reviews": 0,
        "paid_by_client_links": 0,
        "execution_claims": 0,
        "findings": 0,
    }
    try:
        snapshot = _load_snapshot(client, project)
        resolution = _persist_entity_resolution(client, snapshot)
        counts["entities_merged"] = int(resolution["merged"])
        counts["resolution_reviews"] = len(resolution["reviews"])

        for review in resolution["reviews"][:30]:
            left = snapshot["entities_by_id"].get(review.left_id) or {}
            right = snapshot["entities_by_id"].get(review.right_id) or {}
            evidence_ids = list(dict.fromkeys(
                snapshot["evidence_ids_by_entity"].get(review.left_id, []) + snapshot["evidence_ids_by_entity"].get(review.right_id, [])
            ))[:8]
            if _persist_finding(
                client,
                run_id=run_id,
                scope_id=snapshot["project_entity_id"],
                finding_type="entity_resolution_review",
                title="Possível identidade entre entidades requer revisão",
                statement=(
                    f"A NAVE encontrou {review.score:.0%} de evidência de identidade entre "
                    f"'{left.get('canonical_name')}' e '{right.get('canonical_name')}', mas não fez merge automático."
                ),
                finding_kind="unknown",
                importance="medium",
                confidence=review.score,
                evidence_ids=evidence_ids,
                entity_ids=[review.left_id, review.right_id],
                recommended_action="Confirmar se os dois registros representam a mesma entidade antes de usar a relação em decisões automáticas.",
            ):
                counts["findings"] += 1

        # Refresh to include canonical_entity_id updates.
        snapshot = _load_snapshot(client, project)
        cost_links, cost_reviews = _link_costs(client, snapshot, run_id)
        counts["cost_links"] = cost_links
        counts["cost_link_reviews"] = len(cost_reviews)
        for review in cost_reviews[:30]:
            source = review["source"]
            target = review["target"]
            if _persist_finding(
                client,
                run_id=run_id,
                scope_id=snapshot["project_entity_id"],
                finding_type="cost_link_review",
                title="Possível vínculo entre solução e linha de custo",
                statement=f"'{source.canonical_name}' pode estar relacionado à linha financeira '{target.canonical_name}' ({review['score']:.0%}), mas o vínculo ainda é ambíguo.",
                finding_kind="unknown",
                importance="low",
                confidence=review["score"],
                evidence_ids=review["evidence"],
                entity_ids=[source.id, target.id],
                recommended_action="Revisar o vínculo se ele for necessário para análise financeira da solução.",
            ):
                counts["findings"] += 1

        counts["paid_by_client_links"] = _explicit_client_paid_relations(client, snapshot, run_id, project)
        direct_candidates = _direct_pay_review_candidates(snapshot)
        if direct_candidates:
            top = direct_candidates[0]
            line = top["line"]
            line_id = str(line.get("id") or "")
            evidence_ids = [str(top["brief_evidence"].get("id") or "")] + snapshot["evidence_ids_by_entity"].get(line_id, [])[:4]
            if _persist_finding(
                client,
                run_id=run_id,
                scope_id=snapshot["project_entity_id"],
                finding_type="direct_client_payment_scope_review",
                title="Escopo de pagamento direto pode alterar a leitura do budget",
                statement=(
                    "O briefing contém orientação de pagamento direto pelo cliente e existe uma linha financeira relevante potencialmente relacionada. "
                    "A NAVE não descontou esse valor automaticamente do orçamento porque a responsabilidade não está explicitamente comprovada na própria linha."
                ),
                finding_kind="unknown",
                importance="high",
                confidence=float(top["score"]),
                evidence_ids=[v for v in evidence_ids if v],
                entity_ids=[line_id],
                recommended_action="Confirmar quais linhas estão fora do envelope da agência antes de concluir aderência ou estouro de budget.",
            ):
                counts["findings"] += 1

        counts["execution_claims"] = _execution_evidence(client, snapshot, run_id, project)

        values, claim_evidence = _project_numeric_claims(client, str(project["id"]))
        budget = values.get("budget_max")
        proposed = values.get("proposed_total")
        if budget and proposed and proposed > budget:
            refs = list(dict.fromkeys(claim_evidence.get("budget_max", []) + claim_evidence.get("proposed_total", [])))
            if direct_candidates or counts["paid_by_client_links"]:
                statement = (
                    f"O total proposto ({proposed:,.2f}) é superior ao budget nominal ({budget:,.2f}), mas há evidência de itens/responsabilidades pagas diretamente pelo cliente. "
                    "A aderência líquida ao envelope não deve ser concluída sem reconciliar o escopo financeiro."
                )
                kind, importance, confidence = "unknown", "high", 0.94
                action = "Separar total bruto, itens pagos diretamente pelo cliente e envelope efetivo da agência."
            else:
                statement = f"O total proposto ({proposed:,.2f}) supera o budget máximo identificado ({budget:,.2f})."
                kind, importance, confidence = "risk", "high", 0.97
                action = "Revisar os principais drivers de custo e a aderência ao teto do briefing."
            if _persist_finding(
                client,
                run_id=run_id,
                scope_id=snapshot["project_entity_id"],
                finding_type="budget_adherence_cross_source",
                title="Aderência financeira entre briefing e proposta",
                statement=statement,
                finding_kind=kind,
                importance=importance,
                confidence=confidence,
                evidence_ids=refs[:10],
                entity_ids=[str(project["id"])],
                recommended_action=action,
            ):
                counts["findings"] += 1

        status = "completed"
        _finish_run(client, run, started, status, counts)
        return {"status": status, "project_id": project_id, "run_id": run_id, **counts}
    except Exception as exc:
        _finish_run(client, run, started, "error", counts, str(exc))
        return {"status": "error", "project_id": project_id, "run_id": run_id, "error": str(exc), **counts}
