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

CANONICAL_PROJECT_GRAPH_VERSION = "canonical-project-graph-v1.2"

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


def _is_useful_name(name: str, *, entity_type: str | None = None) -> bool:
    norm = _norm(name)
    if not norm:
        return False
    # Alguns rótulos são genéricos como headings, mas são entidades de contêiner
    # legítimas quando o tipo já foi resolvido pelo workspace. Press Kit é o caso
    # mais importante: sem ele a NAVE nunca consegue modelar contains/part_of.
    if norm in _GENERIC_TITLES and not (entity_type == "presskit" and norm in {"press kit", "presskit"}):
        return False
    tokens = [t for t in norm.split() if not t.isdigit()]
    return bool(tokens) and len(norm) >= 3


def _alias_variants(name: str) -> list[str]:
    """Gera poucas variantes conservadoras para nomes editoriais do workspace.

    O objetivo não é criar sinônimos criativos; é remover apenas prefixos estruturais
    que frequentemente aparecem em apresentação/planilha, como ``Oficina de`` ou
    ``Ativação -``. Variantes genéricas continuam bloqueadas por ``_is_useful_name``.
    """
    clean = re.sub(r"\s+", " ", str(name or "")).strip()
    values = [clean] if clean else []
    patterns = (
        r"^(?:oficina(?:\s+de)?|workshop)\s+(.+)$",
        r"^(?:ativacao|ativação|activation)\s*[-:–—]?\s*(.+)$",
        r"^(?:brincadeira|experiencia|experiência)\s*[-:–—]?\s*(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, clean, flags=re.I)
        if match:
            candidate = re.sub(r"\s+", " ", match.group(1)).strip()
            if _is_useful_name(candidate):
                values.append(candidate)
    return list(dict.fromkeys(v for v in values if _is_useful_name(v)))


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
            "alias_type": "other",
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
    canonical_entity_id: str | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    if not domain_id or not _is_useful_name(name, entity_type=entity_type):
        return None, False
    try:
        found = _rows(
            client.table("knowledge_entities").select("*")
            .eq("domain_table", domain_table).eq("domain_id", domain_id).limit(1).execute()
        )
    except Exception:
        found = []
    merged_attrs = dict(attributes or {})
    if found:
        row = found[0]
        try:
            prior_attrs = dict(row.get("attributes") or {})
            prior_attrs.update(merged_attrs)
            payload: dict[str, Any] = {
                "attributes": prior_attrs,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if canonical_entity_id:
                payload.update({
                    "canonical_entity_id": canonical_entity_id,
                    "status": "merged",
                    "confidence": max(float(row.get("confidence") or 0.0), 0.98),
                })
            client.table("knowledge_entities").update(payload).eq("id", row["id"]).execute()
            row = {**row, **payload}
        except Exception:
            pass
        return row, False
    try:
        payload = {
            "entity_type": entity_type,
            "canonical_name": name,
            "normalized_name": _norm(name),
            "entity_kind": "project_instance",
            "scope_entity_id": project_entity_id,
            "domain_table": domain_table,
            "domain_id": domain_id,
            "attributes": merged_attrs,
            "status": "merged" if canonical_entity_id else "active",
            "confidence": 0.99 if canonical_entity_id else 0.98,
        }
        if canonical_entity_id:
            payload["canonical_entity_id"] = canonical_entity_id
        rows = _rows(client.table("knowledge_entities").insert(payload).execute())
        return (rows[0] if rows else None), bool(rows)
    except Exception:
        return None, False

def _load_workspace(client: Any, project_id: str) -> dict[str, list[dict[str, Any]]]:
    def load(table: str) -> list[dict[str, Any]]:
        try:
            return _rows(client.table(table).select("*").eq("project_id", project_id).execute())
        except Exception:
            return []
    return {
        "items": load("memory_items"),
        "costs": load("memory_cost_items"),
        "requirements": load("memory_briefing_requirements"),
        "outcomes": load("memory_item_outcomes"),
        "cost_links": load("memory_cost_links"),
        "briefing_links": load("memory_briefing_links"),
    }

def materialize_project_canonical_entities(client: Any, project_id: str) -> dict[str, Any]:
    """Cria canônicos + ocorrências estruturadas sem apagar o grafo existente.

    V28.6.2 trata as tabelas confiáveis do workspace como registros de ocorrência.
    Assim, uma solução da proposta e o seu outcome pós-evento deixam de depender de
    fuzzy matching para saber que pertencem ao mesmo canônico.
    """
    project = _project_entity(client, project_id)
    if not project:
        return {"status": "skipped_project_entity_missing", "project_id": project_id}
    scope_id = str(project["id"])
    ws = _load_workspace(client, project_id)
    items = ws["items"]
    costs = ws["costs"]
    requirements = ws["requirements"]
    outcomes = ws["outcomes"]

    counts = {
        "canonical_entities_created": 0,
        "domain_entities_created": 0,
        "aliases_added": 0,
        "memory_items_considered": 0,
        "cost_items_considered": 0,
        "requirements_considered": 0,
        "proposal_occurrences_linked": 0,
        "execution_occurrences_linked": 0,
        "structured_cost_links_available": len(ws["cost_links"]),
        "structured_briefing_links_available": len(ws["briefing_links"]),
    }

    canonical_by_item_id: dict[str, dict[str, Any]] = {}
    item_by_id = {str(row.get("id") or ""): row for row in items if row.get("id")}

    # Proposta: cada memory_item cria o canônico e também uma ocorrência de domínio
    # explicitamente ligada a ele. Isso remove a dependência de o File Analyst ter
    # escolhido exatamente o mesmo nome/tipo para a ocorrência do slide.
    for row in items:
        name = _canonical_title(row)
        entity_type = _item_type(row)
        if not _is_useful_name(name, entity_type=entity_type):
            continue
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
                "workspace_summary": row.get("summary") or row.get("description"),
                "workspace_source_text": row.get("source_text") or row.get("content_text"),
            },
        )
        counts["canonical_entities_created"] += int(created)
        if not canonical:
            continue
        item_id = str(row.get("id") or "")
        canonical_by_item_id[item_id] = canonical
        for alias in _alias_variants(name):
            counts["aliases_added"] += _ensure_alias(client, str(canonical["id"]), alias, scope_id)
        summary = str(row.get("summary") or row.get("description") or "").strip()
        if summary and _norm(summary).startswith(_norm(name)) and len(summary) <= 180:
            counts["aliases_added"] += _ensure_alias(client, str(canonical["id"]), summary, scope_id, 0.88)

        occurrence, _ = _ensure_domain_entity(
            client,
            project_entity_id=scope_id,
            entity_type=entity_type,
            name=name,
            domain_table="memory_items",
            domain_id=item_id,
            canonical_entity_id=str(canonical["id"]),
            attributes={
                "occurrence_role": "proposal",
                "section_key": row.get("section_key"),
                "status": row.get("status"),
                "summary": row.get("summary") or row.get("description"),
                "source": "workspace_memory_item",
            },
        )
        counts["domain_entities_created"] += int(bool(occurrence))
        counts["proposal_occurrences_linked"] += int(bool(occurrence))

    # Linhas financeiras e requisitos são ocorrências relacionáveis, mas não são a
    # mesma identidade da solução; por isso não recebem canonical_entity_id.
    for row in costs:
        name = _canonical_title(row)
        if not _is_useful_name(name, entity_type="financial_line_item"):
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
                "occurrence_role": "cost",
            },
        )
        counts["domain_entities_created"] += int(created)

    for row in requirements:
        name = _canonical_title({"title": row.get("title") or row.get("description") or row.get("source_quote")})
        if not _is_useful_name(name, entity_type="requirement"):
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
                "occurrence_role": "briefing",
            },
        )
        counts["domain_entities_created"] += int(created)

    # Pós-evento: memory_item_outcomes já possuem item_id. Este vínculo é muito mais
    # forte do que tentar reconhecer novamente o nome em texto. Registramos uma
    # ocorrência de execução da MESMA entidade canônica.
    for row in outcomes:
        item_id = str(row.get("item_id") or "")
        canonical = canonical_by_item_id.get(item_id)
        item = item_by_id.get(item_id) or {}
        outcome_id = str(row.get("id") or "")
        if not canonical or not outcome_id:
            continue
        name = str(canonical.get("canonical_name") or _canonical_title(item)).strip()
        entity_type = str(canonical.get("entity_type") or _item_type(item))
        occurrence, _ = _ensure_domain_entity(
            client,
            project_entity_id=scope_id,
            entity_type=entity_type,
            name=name,
            domain_table="memory_item_outcomes",
            domain_id=outcome_id,
            canonical_entity_id=str(canonical["id"]),
            attributes={
                "occurrence_role": "execution",
                "outcome_status": row.get("outcome_status"),
                "feedback_summary": row.get("feedback_summary"),
                "decision_reason": row.get("decision_reason"),
                "information_source": row.get("information_source"),
                "confidence_level": row.get("confidence_level"),
                "source_item_id": item_id,
                "source": "workspace_item_outcome",
            },
        )
        counts["domain_entities_created"] += int(bool(occurrence))
        counts["execution_occurrences_linked"] += int(bool(occurrence))

    return {"status": "completed", "project_id": project_id, **counts}

