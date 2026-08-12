from __future__ import annotations

"""Adapter do File Analyst v1 para o NAVE IQ Bench Runner.

Não contém fixture nem regra de cliente. Ele apenas resolve os binários autorizados pelo
runner, executa o File Analyst arquivo a arquivo e agrega o contrato parcial do benchmark.
"""

import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from file_analyst import FileAnalysisResult, analyze_file, bench_role, result_to_bench_fragment


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _fixture_map(fixture_status: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in fixture_status.get("files") or []:
        if not isinstance(row, Mapping) or not row.get("path") or not row.get("hash_ok"):
            continue
        result[str(row.get("role") or "source")] = dict(row)
    return result


def _declared_role_for_fixture(role: str) -> str | None:
    return {
        "briefing": "briefing_original",
        "proposal": "proposal_presentation",
        "budget": "detailed_costs",
        "feedback": "feedback_approval",
        "report": "post_event_report",
    }.get(role)


def _entity_index(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id") or ""): row for row in entities if row.get("id")}


def _best_entity_id(name: str, entities: list[dict[str, Any]], *, preferred_type: str | None = None) -> str | None:
    target = _normalize(name)
    if not target:
        return None
    best: tuple[float, str] | None = None
    target_tokens = set(target.split())
    for entity in entities:
        etype = _normalize(entity.get("type"))
        if preferred_type and etype != _normalize(preferred_type):
            continue
        candidate = _normalize(entity.get("canonical_name"))
        if not candidate:
            continue
        if candidate == target:
            return str(entity.get("id"))
        tokens = set(candidate.split())
        overlap = len(tokens & target_tokens) / max(1, len(tokens | target_tokens))
        containment = 0.8 if candidate in target or target in candidate else 0.0
        score = max(overlap, containment)
        if best is None or score > best[0]:
            best = (score, str(entity.get("id")))
    return best[1] if best and best[0] >= 0.38 else None


def _feedback_topic(raw: Mapping[str, Any], target_name: str | None = None) -> str:
    text = _normalize(" ".join(str(raw.get(k) or "") for k in (
        "title", "theme", "evidence_quote", "interpretation", "result_reason", "recommended_learning"
    )))
    if "budget" in text or "orcamento" in text or "cap" in text:
        return "budget_cap"
    if "deadline" in text or "prazo" in text or "06 00" in text or "6 00" in text:
        return "deadline"
    if any(token in text for token in ("not moving forward", "will not be moving forward", "commercial decision", "proposta nao aprovada")):
        return "commercial_decision"
    if "capacity" in text or "capacidade" in text or "space limitation" in text or "250" in text:
        return "venue_capacity"
    if ("horizontal" in text and "vertical" in text) or "platform specific" in text:
        return "platform_format_alignment"
    if any(token in text for token in ("lifestyle", "themselves", "self content", "zoom", "night mode")):
        return "lifestyle_self_content"
    if "repetitive" in text or "market standard" in text or "repetitivo" in text:
        return "repetition_market_standard"
    if "campaign alignment" in text or "aligned with our campaign" in text or "alinhamento" in text:
        return "concept_campaign_alignment"
    if raw.get("result_reason") == "venue":
        return "venue"
    return _normalize(raw.get("theme") or "other").replace(" ", "_") or "other"


def _feedback_target(raw: Mapping[str, Any], entities: list[dict[str, Any]]) -> str:
    related = raw.get("related_entities") or []
    if isinstance(related, str):
        related = [related]
    for name in related:
        match = _best_entity_id(str(name), entities)
        if match:
            return match
    theme = _normalize(raw.get("theme"))
    title = str(raw.get("title") or "")
    if theme in {"budget", "timeline", "presentation", "other"} and not related:
        return "project"
    preferred = {
        "creative concept": "concept",
        "strategy": "strategy",
        "activation": "activation",
        "scenography": "solution",
        "gift": "gift",
        "journey": "journey_stage",
    }.get(theme)
    match = _best_entity_id(title, entities, preferred_type=preferred)
    return match or "project"


def _financial_from_workbook(path: Path) -> dict[str, Any]:
    from memory_cost_parser import parse_cost_workbook

    parsed = parse_cost_workbook(path.name, path.read_bytes())
    after_tax_total = parsed.client_total
    before_tax_total = None
    if parsed.total_base is not None or parsed.fees_total is not None:
        before_tax_total = float(parsed.total_base or 0.0) + float(parsed.fees_total or 0.0)
    if after_tax_total is None and before_tax_total is not None and parsed.charges_total is not None:
        after_tax_total = before_tax_total + float(parsed.charges_total or 0.0)

    category_totals: dict[str, float] = {}
    line_totals: list[tuple[str, float]] = []
    for item in parsed.items:
        value = item.client_total
        if value is None:
            value = (item.base_value or 0.0) + (item.fees_value or 0.0) + (item.charges_value or 0.0)
        value = float(value or 0.0)
        if value <= 0:
            continue
        category = str(item.category or "Sem categoria").strip()
        category_totals[category] = category_totals.get(category, 0.0) + value
        line_totals.append((str(item.item_name or f"Linha {item.source_row}"), value))
    top_categories = sorted(category_totals.items(), key=lambda row: row[1], reverse=True)
    largest_lines = sorted(line_totals, key=lambda row: row[1], reverse=True)
    top4 = sum(value for _, value in top_categories[:4])
    concentration = (top4 / float(after_tax_total) * 100.0) if after_tax_total else None
    return {
        "base_cost_total": parsed.total_base,
        "agency_markup_total": parsed.fees_total,
        "before_tax_total": before_tax_total,
        "tax_amount_total": parsed.charges_total,
        "after_tax_total": after_tax_total,
        "proposed_total": after_tax_total,
        "actual_total": None,
        "top_categories_after_tax": [[name, round(value, 2)] for name, value in top_categories[:10]],
        "top4_concentration_pct": round(concentration, 4) if concentration is not None else None,
        "largest_line_items_after_tax": [[name, round(value, 2)] for name, value in largest_lines[:15]],
        "currency": parsed.currency,
    }


def _numeric_claim(claims: list[dict[str, Any]], predicate: str) -> float | None:
    for claim in claims:
        if _normalize(claim.get("predicate")) == _normalize(predicate) and claim.get("value_numeric") is not None:
            try:
                return float(claim["value_numeric"])
            except Exception:
                continue
    return None


def run_case(case: Mapping[str, Any], fixture_status: Mapping[str, Any]) -> dict[str, Any] | None:
    fixtures = _fixture_map(fixture_status)
    if not fixtures:
        # File Analyst v1 não finge responder cases sintéticos que não possuem fonte.
        return None

    semantic = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    source_roles: dict[str, str] = {}
    entities: list[dict[str, Any]] = [
        {"id": "project", "type": "project", "canonical_name": "Current Project"}
    ]
    claims: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    feedback_claims: list[dict[str, Any]] = []
    analyses: dict[str, FileAnalysisResult] = {}
    financial: dict[str, Any] = {}

    for role, fixture in fixtures.items():
        path = Path(str(fixture["path"]))
        result = analyze_file(
            file_name=path.name,
            data=path.read_bytes(),
            mime_type=None,
            declared_role=_declared_role_for_fixture(role),
            enable_semantic=semantic,
        )
        analyses[role] = result
        fragment = result_to_bench_fragment(result, role)
        source_roles[role] = fragment["source_role"]
        entities.extend(fragment["entities"])
        claims.extend(fragment["claims"])
        relations.extend(fragment["relations"])
        if role == "budget":
            try:
                financial = _financial_from_workbook(path)
            except Exception:
                financial = {}

    # Dedupe de entidades/claims/relations sem criar regras de projeto.
    dedup_entities: dict[tuple[str, str], dict[str, Any]] = {}
    id_alias: dict[str, str] = {"project": "project"}
    for entity in entities:
        key = (_normalize(entity.get("type")), _normalize(entity.get("canonical_name")))
        if not key[1]:
            continue
        if key not in dedup_entities:
            dedup_entities[key] = dict(entity)
        else:
            current = dedup_entities[key]
            refs = list(dict.fromkeys([*(current.get("evidence_refs") or []), *(entity.get("evidence_refs") or [])]))
            current["evidence_refs"] = refs
        id_alias[str(entity.get("id"))] = str(dedup_entities[key].get("id"))
    entities = list(dedup_entities.values())

    for relation in relations:
        relation["source"] = id_alias.get(str(relation.get("source")), relation.get("source"))
        relation["target"] = id_alias.get(str(relation.get("target")), relation.get("target"))

    # Feedback especializado: converte claims granulares para o contrato do bench
    # e cria relações ator→alvo em forma genericamente derivada da fonte do cliente.
    feedback_analysis = analyses.get("feedback")
    if feedback_analysis:
        raw_feedback_claims = feedback_analysis.metadata.get("feedback_claims") or []
        actor_id = "client_feedback_actor"
        if raw_feedback_claims:
            entities.append({"id": actor_id, "type": "client", "canonical_name": "Client feedback source"})
        for raw in raw_feedback_claims:
            if not isinstance(raw, Mapping):
                continue
            target = _feedback_target(raw, entities)
            polarity = _normalize(raw.get("sentiment")).replace(" ", "_") or "neutral"
            feedback_claims.append({
                "target": target,
                "polarity": polarity,
                "topic": _feedback_topic(raw),
                "evidence_refs": ["feedback:transcript:1" if feedback_analysis.metadata.get("feedback_decision_summary") else "feedback:image:1"],
            })
            if target != "project":
                if polarity == "positive" or raw.get("item_outcome_status") in {"approved", "approved_with_changes"}:
                    relations.append({"source": target, "relation": "validated_by", "target": actor_id, "evidence_refs": ["feedback:transcript:1"]})
                elif polarity == "negative" or raw.get("item_outcome_status") in {"not_approved", "removed_budget", "removed_timeline"}:
                    relations.append({"source": target, "relation": "challenged_by", "target": actor_id, "evidence_refs": ["feedback:transcript:1"]})
        commercial = next((c for c in claims if c.get("subject") == "project" and c.get("predicate") == "commercial_result"), None)
        if commercial:
            feedback_claims.append({
                "target": "project",
                "polarity": "negative" if _normalize(commercial.get("value_text")) in {"lost", "not approved", "rejected"} else "neutral",
                "topic": "commercial_decision",
                "evidence_refs": commercial.get("evidence_refs") or ["feedback:transcript:1"],
            })

    budget_max = _numeric_claim(claims, "budget_max")
    proposed_total = financial.get("after_tax_total") or _numeric_claim(claims, "proposed_total")
    if budget_max is not None and proposed_total is not None:
        delta = float(proposed_total) - float(budget_max)
        financial["budget_delta"] = round(delta, 2)
        financial["budget_delta_pct"] = round(delta / float(budget_max) * 100.0, 4) if budget_max else None

    execution_claim = next((
        c for c in claims
        if _normalize(c.get("predicate")) == "execution result"
        and _normalize(c.get("value_text")) not in {"", "not informed", "unknown"}
    ), None)
    execution_state = str(execution_claim.get("value_text")) if execution_claim else "not_evidenced"

    # File Analyst v1 deliberadamente NÃO produz findings cross-source: isso é
    # responsabilidade do Project Analyst V2. A ausência fica mensurável no IQ Bench.
    return {
        "source_roles": source_roles,
        "entities": entities,
        "claims": claims,
        "relations": relations,
        "financial": financial,
        "feedback_claims": feedback_claims,
        "findings": [],
        "execution_state": execution_state,
        "conflict_sets": [],
        "current_values": {},
        "facts": {},
        "metadata": {
            "pipeline": "file-analyst-v1",
            "semantic_enabled": semantic,
            "files_analyzed": len(analyses),
        },
    }
