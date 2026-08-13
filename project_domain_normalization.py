from __future__ import annotations

"""NAVE V28.7.0 — Domain Normalization Foundation.

Esta camada faz a ponte idempotente entre as estruturas legadas ``memory_*`` e os
objetos de domínio aprovados no Data Model da NAVE. Ela NÃO substitui a UI nem o
Relation Graph nesta versão; prepara o source of truth correto para o próximo
cutover.

Princípios:
- Project Solution Instance é uma solução contextual do projeto, não uma ocorrência;
- ocorrências/duplicatas exatas de ``memory_items`` são consolidadas por identidade;
- requirement, financial line item e outcome são objetos independentes;
- knowledge_entities espelha cada objeto normalizado 1:1;
- sync é monotônico: atualiza/adiciona, nunca apaga automaticamente.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

DOMAIN_NORMALIZATION_VERSION = "V28.7.0"


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _safe_rows(
    client: Any,
    table: str,
    *,
    equals: Mapping[str, Any] | None = None,
    columns: str = "*",
) -> list[dict[str, Any]]:
    try:
        query = client.table(table).select(columns)
        for key, value in (equals or {}).items():
            query = query.eq(key, value)
        return _rows(query.execute())
    except Exception:
        return []


def _safe_one(
    client: Any,
    table: str,
    *,
    equals: Mapping[str, Any] | None = None,
    columns: str = "*",
) -> dict[str, Any] | None:
    rows = _safe_rows(client, table, equals=equals, columns=columns)
    return rows[0] if rows else None


def _norm(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _confidence_from_legacy(level: Any) -> tuple[float, float, bool]:
    key = _norm(level).replace(" ", "_")
    if key == "client_confirmed":
        return 1.0, 1.0, True
    if key == "voe_confirmed":
        return 0.98, 0.95, True
    if key == "inferred":
        return 0.72, 0.55, False
    return 0.45, 0.35, False


def _version_key(row: Mapping[str, Any]) -> str:
    return str(row.get("updated_at") or row.get("created_at") or "legacy-v1")


# ---------------------------------------------------------------------------
# Project entity mirror
# ---------------------------------------------------------------------------


def _ensure_project_entity(client: Any, project_id: str) -> dict[str, Any] | None:
    found = _safe_one(
        client,
        "knowledge_entities",
        equals={"domain_table": "projects", "domain_id": project_id},
    )
    if found:
        return found

    project = _safe_one(client, "projects", equals={"id": project_id}) or {}
    name = (
        _clean(project.get("project_name"))
        or _clean(project.get("name"))
        or _clean(project.get("event_name"))
        or f"Projeto {project_id[:8]}"
    )
    try:
        rows = _rows(
            client.table("knowledge_entities").insert({
                "entity_type": "project",
                "canonical_name": name,
                "normalized_name": _norm(name),
                "entity_kind": "project_instance",
                "domain_table": "projects",
                "domain_id": project_id,
                "attributes": {"normalized_by": DOMAIN_NORMALIZATION_VERSION},
                "status": "active",
                "confidence": 1.0,
            }).execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _entity_type_for_solution(solution_kind: str) -> str:
    mapping = {
        "concept": "concept",
        "strategy": "strategy",
        "activation": "activation",
        "gift": "gift",
        "presskit": "presskit",
        "communication": "communication_asset",
        "content": "deliverable",
        "audiovisual": "deliverable",
        "deliverable": "deliverable",
        "venue_selection": "solution",
        "scenography": "solution",
        "journey": "solution",
        "operation": "solution",
        "staffing": "solution",
        "f&b": "solution",
        "logistics": "solution",
        "technology": "technology",
    }
    return mapping.get(solution_kind, "solution")


def _ensure_domain_entity(
    client: Any,
    *,
    domain_table: str,
    domain_id: str,
    project_entity_id: str,
    entity_type: str,
    name: str,
    attributes: Mapping[str, Any],
    confidence: float | None,
) -> dict[str, Any]:
    existing = _safe_one(
        client,
        "knowledge_entities",
        equals={"domain_table": domain_table, "domain_id": domain_id},
    )
    payload = {
        "entity_type": entity_type,
        "canonical_name": name,
        "normalized_name": _norm(name),
        "entity_kind": "project_instance",
        "scope_entity_id": project_entity_id,
        "domain_table": domain_table,
        "domain_id": domain_id,
        "attributes": dict(attributes),
        "status": "active",
        "confidence": confidence,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing:
        merged = dict(existing.get("attributes") or {})
        merged.update(payload["attributes"])
        payload["attributes"] = merged
        client.table("knowledge_entities").update(payload).eq("id", existing["id"]).execute()
        return {**existing, **payload}

    payload["id"] = str(uuid4())
    rows = _rows(client.table("knowledge_entities").insert(payload).execute())
    if not rows:
        raise RuntimeError(f"não foi possível criar mirror de {domain_table}:{domain_id}")
    return rows[0]


# ---------------------------------------------------------------------------
# Project Solution Instance normalization
# ---------------------------------------------------------------------------


def solution_kind_from_legacy(row: Mapping[str, Any]) -> str:
    section = _norm(row.get("section_key"))
    title = _norm(row.get("title"))
    item_type = _norm(row.get("item_type"))
    body = _norm(" ".join(str(v or "") for v in (row.get("summary"), row.get("description"))))
    combined = " ".join((title, item_type, body))

    if "press kit" in combined or "presskit" in combined or "seeding" in combined:
        return "presskit"
    if re.search(r"\b(oficina|workshop|atividade|brincadeira|game|jogo|experiencia)\b", combined):
        return "activation"
    if "mascote" in combined:
        return "activation"

    mapping = {
        "strategy": "strategy",
        "scenography": "scenography",
        "activations": "activation",
        "gifts": "gift",
        "journey operation": "journey",
        "journey_operation": "journey",
        "communication": "communication",
        "content agenda": "content",
        "content_agenda": "content",
        "partners sponsorship": "other",
        "partners_sponsorship": "other",
        "pr esg legacy": "other",
        "pr_esg_legacy": "other",
    }
    return mapping.get(section, "other")


def contextual_roles_from_legacy(row: Mapping[str, Any], solution_kind: str) -> list[str]:
    roles: list[str] = []
    section = _norm(row.get("section_key"))
    combined = _norm(" ".join(str(v or "") for v in (row.get("title"), row.get("summary"), row.get("description"))))
    if solution_kind:
        roles.append(solution_kind)
    if "oficina" in combined or "workshop" in combined:
        roles.append("workshop")
    if "press kit" in combined or "presskit" in combined or "seeding" in combined:
        roles.append("presskit_context")
    if section in {"journey operation", "journey_operation"}:
        roles.append("journey_operation")
    return list(dict.fromkeys(role for role in roles if role))


def _proposal_execution_status(row: Mapping[str, Any]) -> tuple[str, str]:
    status = _norm(row.get("item_status"))
    proposal = {
        "proposto": "proposed",
        "opcao": "proposed",
        "recomendado": "proposed",
        "aprovado": "approved",
        "descartado": "rejected",
        "referencia": "unknown",
        "nao identificado": "unknown",
    }.get(status, "unknown")
    execution = "executed" if status == "executado" else "not_confirmed"
    if status == "executado" and proposal == "unknown":
        proposal = "approved"
    return proposal, execution


def _solution_identity_key(row: Mapping[str, Any], solution_kind: str) -> str:
    name = _norm(row.get("title")) or _norm(row.get("item_type")) or "sem nome"
    # O kind participa apenas para evitar colapsar conceitos diferentes com o mesmo
    # heading. O papel contextual NÃO vira nova identidade.
    family = {
        "gift": "physical",
        "presskit": "container",
        "activation": "experience",
        "strategy": "strategy",
        "concept": "strategy",
        "communication": "communication",
        "content": "content",
        "scenography": "space",
    }.get(solution_kind, solution_kind or "other")
    return f"{family}:{name}"


def _merge_text(rows: Sequence[Mapping[str, Any]], key: str) -> str | None:
    values = [_clean(row.get(key)) for row in rows]
    values = [value for value in values if value]
    if not values:
        return None
    # Preferimos a descrição mais rica sem concatenar chunks quase duplicados.
    return max(values, key=len)


def _group_memory_items(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        kind = solution_kind_from_legacy(row)
        key = _solution_identity_key(row, kind)
        grouped.setdefault((key, kind), []).append(row)
    return [(key, kind, items) for (key, kind), items in grouped.items()]


def _sync_solution_instances(
    client: Any,
    *,
    project_id: str,
    project_entity_id: str,
    legacy_rows: Sequence[Mapping[str, Any]],
) -> tuple[int, dict[str, dict[str, Any]]]:
    synced = 0
    by_legacy_id: dict[str, dict[str, Any]] = {}
    for identity_key, kind, items in _group_memory_items(legacy_rows):
        title = max((_clean(row.get("title")) for row in items if _clean(row.get("title"))), key=len, default="Solução")
        description = _merge_text(items, "description") or _merge_text(items, "summary")
        journey_stage = next((_clean(row.get("journey_stage")) for row in items if _clean(row.get("journey_stage"))), None)
        legacy_ids = [str(row.get("id")) for row in items if row.get("id")]
        roles: list[str] = []
        proposal_status = "unknown"
        execution_status = "not_confirmed"
        confidence_values: list[float] = []
        for row in items:
            roles.extend(contextual_roles_from_legacy(row, kind))
            proposal, execution = _proposal_execution_status(row)
            if proposal in {"approved", "approved_with_changes"}:
                proposal_status = proposal
            elif proposal_status == "unknown" and proposal != "unknown":
                proposal_status = proposal
            if execution == "executed":
                execution_status = "executed"
            value = _float(row.get("confidence"))
            if value is not None:
                confidence_values.append(value)
        confidence = max(confidence_values) if confidence_values else 0.92
        attrs = {
            "normalized_by": DOMAIN_NORMALIZATION_VERSION,
            "legacy_memory_item_ids": legacy_ids,
            "legacy_sections": list(dict.fromkeys(str(row.get("section_key") or "") for row in items if row.get("section_key"))),
            "legacy_item_types": list(dict.fromkeys(str(row.get("item_type") or "") for row in items if row.get("item_type"))),
            "source_pages": sorted({int(row.get("source_page")) for row in items if str(row.get("source_page") or "").isdigit()}),
            "tags": list(dict.fromkeys(tag for row in items for tag in (row.get("tags") or []) if str(tag).strip())),
            "objectives": list(dict.fromkeys(v for row in items for v in (row.get("objectives") or []) if str(v).strip())),
            "audiences": list(dict.fromkeys(v for row in items for v in (row.get("audiences") or []) if str(v).strip())),
            "mechanics": list(dict.fromkeys(v for row in items for v in (row.get("mechanics") or []) if str(v).strip())),
            "technologies": list(dict.fromkeys(v for row in items for v in (row.get("technologies") or []) if str(v).strip())),
        }
        existing = _safe_one(
            client,
            "project_solution_instances",
            equals={"project_id": project_id, "identity_key": identity_key},
        )
        domain_id = str(existing.get("id")) if existing else str(uuid4())
        entity = _ensure_domain_entity(
            client,
            domain_table="project_solution_instances",
            domain_id=domain_id,
            project_entity_id=project_entity_id,
            entity_type=_entity_type_for_solution(kind),
            name=title,
            attributes={**attrs, "solution_kind": kind, "identity_key": identity_key},
            confidence=confidence,
        )
        payload = {
            "id": domain_id,
            "project_id": project_id,
            "entity_id": entity["id"],
            "identity_key": identity_key,
            "solution_kind": kind,
            "name": title,
            "description": description,
            "journey_stage": journey_stage,
            "roles": list(dict.fromkeys(roles)),
            "proposal_status": proposal_status,
            "execution_status": execution_status,
            "attributes": attrs,
            "confidence": confidence,
            "legacy_source_table": "memory_items",
            "legacy_source_ids": legacy_ids,
        }
        if existing:
            client.table("project_solution_instances").update(payload).eq("id", domain_id).execute()
        else:
            client.table("project_solution_instances").insert(payload).execute()
        normalized = {**(existing or {}), **payload}
        for legacy_id in legacy_ids:
            by_legacy_id[legacy_id] = normalized
        synced += 1
    return synced, by_legacy_id


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


def _requirement_status(row: Mapping[str, Any]) -> str:
    adherence = _norm(row.get("adherence_status"))
    mapping = {
        "fulfilled": "fulfilled",
        "partially fulfilled": "partially_fulfilled",
        "not fulfilled": "not_fulfilled",
        "removed budget": "cancelled",
        "removed timeline": "cancelled",
        "not applicable": "cancelled",
    }
    return mapping.get(adherence, "active")


def _sync_requirements(client: Any, *, project_id: str, project_entity_id: str, legacy_rows: Sequence[Mapping[str, Any]]) -> int:
    synced = 0
    for row in legacy_rows:
        legacy_id = str(row.get("id") or "")
        if not legacy_id:
            continue
        existing = _safe_one(
            client,
            "project_requirements",
            equals={"legacy_source_table": "memory_briefing_requirements", "legacy_source_id": legacy_id},
        )
        domain_id = str(existing.get("id")) if existing else str(uuid4())
        title = _clean(row.get("title")) or "Requisito"
        confidence = 0.97 if row.get("mandatory") else 0.92
        attrs = {
            "normalized_by": DOMAIN_NORMALIZATION_VERSION,
            "legacy_briefing_document_id": row.get("briefing_document_id"),
            "source_reference": row.get("source_reference"),
            "source_quote": row.get("source_quote"),
            "tags": row.get("tags") or [],
            "sort_order": row.get("sort_order"),
            "adherence_status": row.get("adherence_status"),
            "adherence_evidence": row.get("adherence_evidence"),
            "adherence_notes": row.get("adherence_notes"),
        }
        entity = _ensure_domain_entity(
            client,
            domain_table="project_requirements",
            domain_id=domain_id,
            project_entity_id=project_entity_id,
            entity_type="requirement",
            name=title,
            attributes=attrs,
            confidence=confidence,
        )
        payload = {
            "id": domain_id,
            "project_id": project_id,
            "entity_id": entity["id"],
            "requirement_type": str(row.get("requirement_type") or "context"),
            "title": title,
            "description": _clean(row.get("description")),
            "priority": str(row.get("priority") or "not_informed"),
            "mandatory": bool(row.get("mandatory")),
            "status": _requirement_status(row),
            "confidence": confidence,
            "attributes": attrs,
            "legacy_source_table": "memory_briefing_requirements",
            "legacy_source_id": legacy_id,
        }
        if existing:
            client.table("project_requirements").update(payload).eq("id", domain_id).execute()
        else:
            client.table("project_requirements").insert(payload).execute()
        synced += 1
    return synced


# ---------------------------------------------------------------------------
# Financial normalization
# ---------------------------------------------------------------------------


def _financial_document_kind(row: Mapping[str, Any]) -> str:
    text = _norm(" ".join(str(v or "") for v in (row.get("title"), row.get("file_name"), row.get("metadata"))))
    if "actual" in text or "realizado" in text or "fechamento" in text:
        return "actual_cost"
    if "supplier" in text or "fornecedor" in text or "cotacao" in text or "quotation" in text:
        return "supplier_quote"
    return "proposal_budget"


def _sync_financial_documents(client: Any, *, project_id: str, legacy_rows: Sequence[Mapping[str, Any]]) -> tuple[int, dict[str, dict[str, Any]]]:
    synced = 0
    mapping: dict[str, dict[str, Any]] = {}
    for row in legacy_rows:
        legacy_id = str(row.get("id") or "")
        if not legacy_id:
            continue
        existing = _safe_one(
            client,
            "financial_documents",
            equals={"legacy_source_table": "memory_cost_documents", "legacy_source_id": legacy_id},
        )
        domain_id = str(existing.get("id")) if existing else str(uuid4())
        payload = {
            "id": domain_id,
            "project_id": project_id,
            "document_kind": _financial_document_kind(row),
            "currency": str(row.get("currency") or "BRL"),
            "base_total": row.get("total_base"),
            "fees_total": row.get("fees_total"),
            "taxes_total": row.get("charges_total"),
            "client_total": row.get("client_total"),
            "status": str(row.get("extraction_status") or "structured"),
            "metadata": {
                "normalized_by": DOMAIN_NORMALIZATION_VERSION,
                "title": row.get("title"),
                "file_name": row.get("file_name"),
                "sheet_name": row.get("sheet_name"),
                "header_row": row.get("header_row"),
                "content_sha256": row.get("content_sha256"),
                "macros_present": row.get("macros_present"),
                "legacy_metadata": row.get("metadata") or {},
            },
            "legacy_source_table": "memory_cost_documents",
            "legacy_source_id": legacy_id,
        }
        if existing:
            client.table("financial_documents").update(payload).eq("id", domain_id).execute()
        else:
            client.table("financial_documents").insert(payload).execute()
        normalized = {**(existing or {}), **payload}
        mapping[legacy_id] = normalized
        synced += 1
    return synced, mapping


def _cost_state(row: Mapping[str, Any]) -> str:
    item_status = _norm(row.get("item_status"))
    estimate_type = _norm(row.get("estimate_type"))
    if item_status == "optional":
        return "optional"
    if item_status in {"pending", "reserve"} or estimate_type in {"reserve", "waiting supplier"}:
        return "pending"
    if estimate_type == "quoted":
        return "quoted"
    return "budgeted"


def _paid_by(row: Mapping[str, Any]) -> str:
    if _norm(row.get("item_status")) == "client responsibility":
        return "client"
    return "unknown"


def _sync_financial_line_items(
    client: Any,
    *,
    project_id: str,
    project_entity_id: str,
    legacy_rows: Sequence[Mapping[str, Any]],
    documents_by_legacy: Mapping[str, Mapping[str, Any]],
) -> int:
    synced = 0
    for row in legacy_rows:
        legacy_id = str(row.get("id") or "")
        legacy_doc_id = str(row.get("cost_document_id") or "")
        financial_doc = documents_by_legacy.get(legacy_doc_id)
        if not legacy_id or not financial_doc:
            continue
        existing = _safe_one(
            client,
            "financial_line_items",
            equals={"legacy_source_table": "memory_cost_items", "legacy_source_id": legacy_id},
        )
        domain_id = str(existing.get("id")) if existing else str(uuid4())
        name = _clean(row.get("item_name")) or "Linha financeira"
        attrs = {
            "normalized_by": DOMAIN_NORMALIZATION_VERSION,
            "source_sheet": row.get("source_sheet"),
            "source_row": row.get("source_row"),
            "billing_type": row.get("billing_type"),
            "estimate_type": row.get("estimate_type"),
            "legacy_item_status": row.get("item_status"),
            "raw_data": row.get("raw_data") or {},
        }
        entity = _ensure_domain_entity(
            client,
            domain_table="financial_line_items",
            domain_id=domain_id,
            project_entity_id=project_entity_id,
            entity_type="financial_line_item",
            name=name,
            attributes={**attrs, "category": row.get("category")},
            confidence=0.99,
        )
        payload = {
            "id": domain_id,
            "financial_document_id": financial_doc["id"],
            "project_id": project_id,
            "entity_id": entity["id"],
            "line_code": row.get("item_code"),
            "category": row.get("category"),
            "item_name": name,
            "description": _clean(row.get("description")),
            "quantity": row.get("quantity"),
            "period": row.get("period"),
            "unit_value": row.get("unit_value"),
            "base_value": row.get("base_value"),
            "fees_value": row.get("fees_value"),
            "taxes_value": row.get("charges_value"),
            "total_value": row.get("client_total"),
            "cost_state": _cost_state(row),
            "paid_by": _paid_by(row),
            "flags": row.get("flags") or [],
            "attributes": attrs,
            "legacy_source_table": "memory_cost_items",
            "legacy_source_id": legacy_id,
        }
        if existing:
            client.table("financial_line_items").update(payload).eq("id", domain_id).execute()
        else:
            client.table("financial_line_items").insert(payload).execute()
        synced += 1
    return synced


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


def _item_outcome_semantics(status: Any) -> tuple[str, str] | None:
    key = _norm(status).replace(" ", "_")
    if key in {"approved", "approved_with_changes", "not_approved", "replaced", "removed_budget", "removed_timeline"}:
        mapped = {
            "approved": "approved",
            "approved_with_changes": "approved_with_changes",
            "not_approved": "rejected",
            "replaced": "replaced",
            "removed_budget": "removed",
            "removed_timeline": "removed",
        }[key]
        return "proposal_status", mapped
    if key in {"executed", "not_executed"}:
        return "execution_status", key
    if key == "unknown":
        return "solution_status", "unknown"
    return None


def _insert_outcome_if_missing(client: Any, payload: Mapping[str, Any]) -> bool:
    lookup = {
        "legacy_source_table": payload.get("legacy_source_table"),
        "legacy_source_id": payload.get("legacy_source_id"),
        "outcome_type": payload.get("outcome_type"),
        "legacy_version_key": payload.get("legacy_version_key"),
    }
    if all(lookup.values()) and _safe_one(client, "entity_outcomes", equals=lookup, columns="id"):
        return False
    client.table("entity_outcomes").insert(dict(payload)).execute()
    return True


def _sync_item_outcomes(
    client: Any,
    *,
    project_id: str,
    legacy_rows: Sequence[Mapping[str, Any]],
    solution_by_legacy_item_id: Mapping[str, Mapping[str, Any]],
) -> int:
    created = 0
    for row in legacy_rows:
        item_id = str(row.get("item_id") or "")
        solution = solution_by_legacy_item_id.get(item_id)
        semantic = _item_outcome_semantics(row.get("outcome_status"))
        if not solution or not semantic:
            continue
        outcome_type, outcome_status = semantic
        confidence, authority, human = _confidence_from_legacy(row.get("confidence_level"))
        reason = _clean(row.get("decision_reason")) or _clean(row.get("feedback_summary")) or _clean(row.get("execution_notes"))
        payload = {
            "entity_id": solution["entity_id"],
            "project_id": project_id,
            "outcome_type": outcome_type,
            "outcome_status": outcome_status,
            "reason": reason,
            "confidence": confidence,
            "authority_score": authority,
            "is_human_confirmed": human,
            "attributes": {
                "normalized_by": DOMAIN_NORMALIZATION_VERSION,
                "information_source": row.get("information_source"),
                "legacy_confidence_level": row.get("confidence_level"),
            },
            "legacy_source_table": "memory_item_outcomes",
            "legacy_source_id": item_id,
            "legacy_version_key": _version_key(row),
        }
        created += int(_insert_outcome_if_missing(client, payload))
        update: dict[str, Any] = {}
        if outcome_type == "proposal_status":
            update["proposal_status"] = outcome_status
        elif outcome_type == "execution_status":
            update["execution_status"] = outcome_status
        if update:
            client.table("project_solution_instances").update(update).eq("id", solution["id"]).execute()
    return created


def _project_outcome_rows(memory_outcome: Mapping[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    commercial = _norm(memory_outcome.get("commercial_result")).replace(" ", "_")
    if commercial not in {"", "in_evaluation", "not_informed"}:
        rows.append(("commercial_result", commercial))

    proposal = _norm(memory_outcome.get("proposal_result")).replace(" ", "_")
    proposal_map = {
        "fully_approved": "approved",
        "partially_approved": "approved_with_changes",
        "not_approved": "not_approved",
        "no_feedback": "unknown",
    }
    if proposal in proposal_map:
        rows.append(("proposal_status", proposal_map[proposal]))

    execution = _norm(memory_outcome.get("execution_result")).replace(" ", "_")
    execution_map = {
        "executed": "executed",
        "partially_executed": "partial",
        "not_executed": "not_executed",
        "in_progress": "planned",
        "not_applicable": "not_applicable",
    }
    if execution in execution_map:
        rows.append(("execution_status", execution_map[execution]))
    return rows


def _sync_project_outcomes(client: Any, *, project_id: str, project_entity_id: str, memory_outcome: Mapping[str, Any] | None) -> int:
    if not memory_outcome:
        return 0
    confidence, authority, human = _confidence_from_legacy(memory_outcome.get("confidence_level"))
    created = 0
    for outcome_type, outcome_status in _project_outcome_rows(memory_outcome):
        reason_parts: list[str] = []
        if memory_outcome.get("result_context"):
            reason_parts.append(str(memory_outcome["result_context"]))
        if memory_outcome.get("result_reasons"):
            reason_parts.extend(str(v) for v in (memory_outcome.get("result_reasons") or []) if str(v).strip())
        if outcome_type == "execution_status" and memory_outcome.get("execution_notes"):
            reason_parts.append(str(memory_outcome["execution_notes"]))
        event_date = memory_outcome.get("execution_date") if outcome_type == "execution_status" else memory_outcome.get("result_date")
        payload = {
            "entity_id": project_entity_id,
            "project_id": project_id,
            "outcome_type": outcome_type,
            "outcome_status": outcome_status,
            "outcome_at": f"{event_date}T12:00:00+00:00" if event_date else None,
            "reason": _clean(" | ".join(reason_parts)),
            "confidence": confidence,
            "authority_score": authority,
            "is_human_confirmed": human,
            "attributes": {
                "normalized_by": DOMAIN_NORMALIZATION_VERSION,
                "process_type": memory_outcome.get("process_type"),
                "information_source": memory_outcome.get("information_source"),
                "contracting_client": memory_outcome.get("contracting_client"),
            },
            "legacy_source_table": "memory_project_outcomes",
            "legacy_source_id": project_id,
            "legacy_version_key": _version_key(memory_outcome),
        }
        created += int(_insert_outcome_if_missing(client, payload))
    return created


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class DomainNormalizationResult:
    project_id: str
    status: str
    solution_instances: int = 0
    requirements: int = 0
    financial_documents: int = 0
    financial_line_items: int = 0
    outcomes_created: int = 0
    warnings: list[str] | None = None
    parity: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "status": self.status,
            "solution_instances": self.solution_instances,
            "requirements": self.requirements,
            "financial_documents": self.financial_documents,
            "financial_line_items": self.financial_line_items,
            "outcomes_created": self.outcomes_created,
            "warnings": list(self.warnings or []),
            "parity": dict(self.parity or {}),
        }


def _domain_schema_available(client: Any) -> tuple[bool, str | None]:
    try:
        client.table("project_solution_instances").select("id").limit(1).execute()
        client.table("project_requirements").select("id").limit(1).execute()
        client.table("financial_documents").select("id").limit(1).execute()
        client.table("financial_line_items").select("id").limit(1).execute()
        client.table("entity_outcomes").select("id").limit(1).execute()
        return True, None
    except Exception as exc:
        return False, str(exc)


def fetch_project_domain_status(client: Any, project_id: str) -> dict[str, Any]:
    available, error = _domain_schema_available(client)
    if not available:
        return {"status": "schema_missing", "project_id": project_id, "error": error}
    normalized = {
        "solution_instances": len(_safe_rows(client, "project_solution_instances", equals={"project_id": project_id}, columns="id")),
        "requirements": len(_safe_rows(client, "project_requirements", equals={"project_id": project_id}, columns="id")),
        "financial_documents": len(_safe_rows(client, "financial_documents", equals={"project_id": project_id}, columns="id")),
        "financial_line_items": len(_safe_rows(client, "financial_line_items", equals={"project_id": project_id}, columns="id")),
        "outcomes": len(_safe_rows(client, "entity_outcomes", equals={"project_id": project_id}, columns="id")),
    }
    legacy = {
        "memory_items": len(_safe_rows(client, "memory_items", equals={"project_id": project_id}, columns="id")),
        "requirements": len(_safe_rows(client, "memory_briefing_requirements", equals={"project_id": project_id}, columns="id")),
        "cost_documents": len(_safe_rows(client, "memory_cost_documents", equals={"project_id": project_id}, columns="id")),
        "cost_items": len(_safe_rows(client, "memory_cost_items", equals={"project_id": project_id}, columns="id")),
        "item_outcomes": len(_safe_rows(client, "memory_item_outcomes", equals={"project_id": project_id}, columns="item_id")),
    }
    return {"status": "ready", "project_id": project_id, "normalized": normalized, "legacy": legacy}


def sync_project_domain_normalization(client: Any, project_id: str) -> dict[str, Any]:
    """Backfill/dual-write idempotente para um único projeto.

    A função é deliberadamente monotônica: não apaga objetos normalizados se uma
    estrutura legacy desaparecer. Isso protege conhecimento já promovido durante a
    migração e mantém o mesmo princípio de Knowledge Monotonicity do reprocessamento.
    """
    available, error = _domain_schema_available(client)
    if not available:
        return DomainNormalizationResult(
            project_id=project_id,
            status="schema_missing",
            warnings=[
                "Domain Normalization ainda não está instalada no banco. Execute NAVE_V28_7_0_DOMAIN_NORMALIZATION_FOUNDATION.sql antes de normalizar o projeto.",
                error or "",
            ],
        ).as_dict()

    warnings: list[str] = []
    project_entity = _ensure_project_entity(client, project_id)
    if not project_entity:
        return DomainNormalizationResult(
            project_id=project_id,
            status="project_entity_missing",
            warnings=["Não foi possível localizar/criar o mirror do projeto em knowledge_entities."],
        ).as_dict()

    legacy_items = _safe_rows(client, "memory_items", equals={"project_id": project_id})
    legacy_requirements = _safe_rows(client, "memory_briefing_requirements", equals={"project_id": project_id})
    legacy_cost_documents = _safe_rows(client, "memory_cost_documents", equals={"project_id": project_id})
    legacy_cost_items = _safe_rows(client, "memory_cost_items", equals={"project_id": project_id})
    legacy_item_outcomes = _safe_rows(client, "memory_item_outcomes", equals={"project_id": project_id})
    legacy_project_outcome = _safe_one(client, "memory_project_outcomes", equals={"project_id": project_id})

    try:
        solution_count, solution_map = _sync_solution_instances(
            client,
            project_id=project_id,
            project_entity_id=str(project_entity["id"]),
            legacy_rows=legacy_items,
        )
        requirement_count = _sync_requirements(
            client,
            project_id=project_id,
            project_entity_id=str(project_entity["id"]),
            legacy_rows=legacy_requirements,
        )
        financial_document_count, document_map = _sync_financial_documents(
            client,
            project_id=project_id,
            legacy_rows=legacy_cost_documents,
        )
        financial_line_count = _sync_financial_line_items(
            client,
            project_id=project_id,
            project_entity_id=str(project_entity["id"]),
            legacy_rows=legacy_cost_items,
            documents_by_legacy=document_map,
        )
        outcomes_created = _sync_item_outcomes(
            client,
            project_id=project_id,
            legacy_rows=legacy_item_outcomes,
            solution_by_legacy_item_id=solution_map,
        )
        outcomes_created += _sync_project_outcomes(
            client,
            project_id=project_id,
            project_entity_id=str(project_entity["id"]),
            memory_outcome=legacy_project_outcome,
        )
    except Exception as exc:
        warnings.append(str(exc))
        status = fetch_project_domain_status(client, project_id)
        return DomainNormalizationResult(
            project_id=project_id,
            status="partial_error",
            warnings=warnings,
            parity=status,
        ).as_dict()

    status = fetch_project_domain_status(client, project_id)
    normalized = status.get("normalized") or {}
    legacy = status.get("legacy") or {}
    # Soluções não precisam ter paridade 1:1: exatamente o contrário. Uma solution
    # instance pode consolidar várias ocorrências memory_items.
    parity = {
        "solution_occurrence_reduction": max(0, int(legacy.get("memory_items") or 0) - int(normalized.get("solution_instances") or 0)),
        "requirements_parity": int(normalized.get("requirements") or 0) >= int(legacy.get("requirements") or 0),
        "financial_documents_parity": int(normalized.get("financial_documents") or 0) >= int(legacy.get("cost_documents") or 0),
        "financial_line_items_parity": int(normalized.get("financial_line_items") or 0) >= int(legacy.get("cost_items") or 0),
        "legacy": legacy,
        "normalized": normalized,
    }

    return DomainNormalizationResult(
        project_id=project_id,
        status="completed",
        solution_instances=solution_count,
        requirements=requirement_count,
        financial_documents=financial_document_count,
        financial_line_items=financial_line_count,
        outcomes_created=outcomes_created,
        warnings=warnings,
        parity=parity,
    ).as_dict()
