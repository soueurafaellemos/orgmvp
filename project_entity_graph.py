from __future__ import annotations

"""NAVE V28.6 — Canonical Project Entity Graph.

Materializa entidades canônicas de projeto a partir das estruturas já confiáveis do
workspace (proposta, custos e briefing) antes do Cross-Source Linker. O objetivo é
não depender de o mesmo nome ter sido extraído da mesma forma em todos os arquivos.

A camada é idempotente: cria/atualiza entidades canônicas e aliases, sem apagar
entidades/evidências existentes.
"""

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

CANONICAL_PROJECT_GRAPH_VERSION = "canonical-project-graph-v1"

_GENERIC_TITLES = {
    "brincadeiras", "ativacoes", "ativacoes e experiencias", "brindes", "press kit",
    "comunicacao", "jornada", "operacao", "cenografia", "ambientes", "conteudos",
    "materiais", "proposta", "conceito", "estrategia",
}

_SECTION_TYPE = {
    "scenography": "solution",
    "activations": "activation",
    "gifts": "gift",
    "journey_operation": "deliverable",
    "communication": "communication_asset",
    "content_agenda": "deliverable",
    "partners_sponsorship": "partner",
    "pr_esg_legacy": "deliverable",
    "strategy": "strategy",
}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        return [dict(data)]
    return []


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clip(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _project_entity(client: Any, project_id: str) -> dict[str, Any] | None:
    try:
        rows = _rows(
            client.table("knowledge_entities").select("*")
            .eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _canonical_title(row: Mapping[str, Any]) -> str:
    title = re.sub(r"\s+", " ", str(row.get("title") or row.get("name") or row.get("item_name") or "")).strip()
    if not title:
        return ""
    # Remove prefixes editoriais que aparecem em títulos derivados de slides.
    title = re.sub(r"^(?:apresenta|apresentamos|proposta|material visual)\s*[:\-–—]?\s*", "", title, flags=re.I)
    title = re.sub(r"^(?:brincadeiras|ativacoes|ativações|brindes)\s+", "", title, flags=re.I)
    title = _clip(title, 120)
    return title


def _item_type(row: Mapping[str, Any]) -> str:
    section = str(row.get("section_key") or row.get("inferred_section") or "")
    title_norm = _norm(row.get("title"))
    if "press kit" in title_norm or "presskit" in title_norm:
        return "presskit"
    return _SECTION_TYPE.get(section, "solution")


def _is_useful_name(name: str) -> bool:
    norm = _norm(name)
    if not norm or norm in _GENERIC_TITLES:
        return False
    tokens = [t for t in norm.split() if not t.isdigit()]
    return bool(tokens) and len(norm) >= 3


def _ensure_alias(client: Any, entity_id: str, alias: str, scope_id: str, confidence: float = 0.98) -> int:
    normalized = _norm(alias)
    if not normalized:
        return 0
    try:
        found = _rows(
            client.table("entity_aliases").select("id")
            .eq("entity_id", entity_id).eq("normalized_alias", normalized).eq("active", True).limit(1).execute()
        )
        if found:
            return 0
        client.table("entity_aliases").insert({
            "entity_id": entity_id,
            "alias": alias,
            "normalized_alias": normalized,
            "alias_type": "workspace_title",
            "scope_entity_id": scope_id,
            "confidence": confidence,
            "active": True,
        }).execute()
        return 1
    except Exception:
        return 0


def _ensure_canonical_entity(
    client: Any,
    *,
    project_entity_id: str,
    entity_type: str,
    name: str,
    attributes: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    normalized = _norm(name)
    if not normalized:
        return None, False
    try:
        found = _rows(
            client.table("knowledge_entities").select("*")
            .eq("scope_entity_id", project_entity_id)
            .eq("entity_kind", "canonical")
            .eq("entity_type", entity_type)
            .eq("normalized_name", normalized)
            .in_("status", ["active", "review_required"]).limit(1).execute()
        )
    except Exception:
        found = []
    payload_attrs = dict(attributes or {})
    payload_attrs.update({"canonicalized_by": CANONICAL_PROJECT_GRAPH_VERSION})
    if found:
        row = found[0]
        try:
            merged = dict(row.get("attributes") or {})
            merged.update(payload_attrs)
            client.table("knowledge_entities").update({
                "attributes": merged,
                "confidence": max(float(row.get("confidence") or 0.0), 0.96),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
        except Exception:
            pass
        return row, False
    try:
        rows = _rows(client.table("knowledge_entities").insert({
            "entity_type": entity_type,
            "canonical_name": name,
            "normalized_name": normalized,
            "entity_kind": "canonical",
            "scope_entity_id": project_entity_id,
            "attributes": payload_attrs,
            "status": "active",
            "confidence": 0.96,
        }).execute())
        return (rows[0] if rows else None), bool(rows)
    except Exception:
        return None, False


def _ensure_domain_entity(
    client: Any,
    *,
    project_entity_id: str,
    entity_type: str,
    name: str,
    domain_table: str,
    domain_id: str,
    attributes: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    if not domain_id or not _is_useful_name(name):
        return None, False
    try:
        found = _rows(
            client.table("knowledge_entities").select("*")
            .eq("domain_table", domain_table).eq("domain_id", domain_id).limit(1).execute()
        )
    except Exception:
        found = []
    if found:
        return found[0], False
    try:
        rows = _rows(client.table("knowledge_entities").insert({
            "entity_type": entity_type,
            "canonical_name": name,
            "normalized_name": _norm(name),
            "entity_kind": "project_instance",
            "scope_entity_id": project_entity_id,
            "domain_table": domain_table,
            "domain_id": domain_id,
            "attributes": dict(attributes or {}),
            "status": "active",
            "confidence": 0.98,
        }).execute())
        return (rows[0] if rows else None), bool(rows)
    except Exception:
        return None, False


def _load_workspace(client: Any, project_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    def load(table: str) -> list[dict[str, Any]]:
        try:
            return _rows(client.table(table).select("*").eq("project_id", project_id).execute())
        except Exception:
            return []
    return load("memory_items"), load("memory_cost_items"), load("memory_briefing_requirements")


def materialize_project_canonical_entities(client: Any, project_id: str) -> dict[str, Any]:
    """Cria sementes canônicas e instâncias de domínio sem apagar o grafo existente."""
    project = _project_entity(client, project_id)
    if not project:
        return {"status": "skipped_project_entity_missing", "project_id": project_id}
    scope_id = str(project["id"])
    items, costs, requirements = _load_workspace(client, project_id)
    counts = {
        "canonical_entities_created": 0,
        "domain_entities_created": 0,
        "aliases_added": 0,
        "memory_items_considered": 0,
        "cost_items_considered": 0,
        "requirements_considered": 0,
    }

    for row in items:
        name = _canonical_title(row)
        if not _is_useful_name(name):
            continue
        entity_type = _item_type(row)
        counts["memory_items_considered"] += 1
        canonical, created = _ensure_canonical_entity(
            client,
            project_entity_id=scope_id,
            entity_type=entity_type,
            name=name,
            attributes={
                "semantic_family": "project_solution",
                "section_key": row.get("section_key"),
                "workspace_item_id": row.get("id"),
            },
        )
        counts["canonical_entities_created"] += int(created)
        if canonical:
            counts["aliases_added"] += _ensure_alias(client, str(canonical["id"]), name, scope_id)
            summary = str(row.get("summary") or row.get("description") or "").strip()
            # Um alias curto derivado só é aceito quando começa com o próprio título.
            if summary and _norm(summary).startswith(_norm(name)) and len(summary) <= 180:
                counts["aliases_added"] += _ensure_alias(client, str(canonical["id"]), summary, scope_id, 0.88)

    for row in costs:
        name = _canonical_title(row)
        if not _is_useful_name(name):
            continue
        counts["cost_items_considered"] += 1
        _, created = _ensure_domain_entity(
            client,
            project_entity_id=scope_id,
            entity_type="financial_line_item",
            name=name,
            domain_table="memory_cost_items",
            domain_id=str(row.get("id") or ""),
            attributes={
                "description": row.get("description") or row.get("scope_description") or row.get("item_name"),
                "category": row.get("category"),
                "client_total": row.get("client_total"),
                "source": "workspace_cost_item",
            },
        )
        counts["domain_entities_created"] += int(created)

    for row in requirements:
        name = _canonical_title({"title": row.get("title") or row.get("description") or row.get("source_quote")})
        if not _is_useful_name(name):
            continue
        counts["requirements_considered"] += 1
        _, created = _ensure_domain_entity(
            client,
            project_entity_id=scope_id,
            entity_type="requirement",
            name=name,
            domain_table="memory_briefing_requirements",
            domain_id=str(row.get("id") or ""),
            attributes={
                "requirement_type": row.get("requirement_type"),
                "priority": row.get("priority"),
                "mandatory": row.get("is_mandatory"),
                "source": "workspace_briefing_requirement",
            },
        )
        counts["domain_entities_created"] += int(created)

    return {"status": "completed", "project_id": project_id, **counts}
