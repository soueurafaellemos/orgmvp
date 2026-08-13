from __future__ import annotations

"""NAVE V28.7.1 — Domain Integrity & Provenance.

Esta versão endurece a Domain Normalization V28.7.0 sem antecipar os domínios
semânticos da V28.7.2. O fluxo passa a ser:

    strict read -> build bundle in memory -> validate -> transactional RPC -> promote

Regras de contrato:
- erro de leitura nunca vira lista vazia;
- occurrence != identity;
- evidence binding é locator-aware e many-to-many;
- execution != approval;
- outcome event stream é a única autoridade para status projetados;
- confidence, source authority e human review são dimensões distintas;
- memory_* permanece legacy_shadow; nenhum cutover é automático.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

DOMAIN_NORMALIZATION_VERSION = "V28.7.1"
DOMAIN_SCHEMA_VERSION = "28.7.1"
NORMALIZATION_RPC = "apply_project_domain_normalization_v2871"


class DomainReadError(RuntimeError):
    """Falha de leitura que NÃO pode ser interpretada como ausência de conhecimento."""


class DomainBundleError(RuntimeError):
    """Bundle não passa pelos gates antes do apply transacional."""


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _strict_rows(
    client: Any,
    table: str,
    *,
    equals: Mapping[str, Any] | None = None,
    columns: str = "*",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    try:
        query = client.table(table).select(columns)
        for key, value in (equals or {}).items():
            query = query.eq(key, value)
        if limit is not None:
            query = query.limit(limit)
        return _rows(query.execute())
    except Exception as exc:  # deliberately not swallowed
        raise DomainReadError(f"Falha lendo {table}: {exc}") from exc


def _strict_one(
    client: Any,
    table: str,
    *,
    equals: Mapping[str, Any] | None = None,
    columns: str = "*",
) -> dict[str, Any] | None:
    rows = _strict_rows(client, table, equals=equals, columns=columns, limit=1)
    return rows[0] if rows else None


def _strict_in_rows(
    client: Any,
    table: str,
    *,
    field: str,
    values: Sequence[Any],
    columns: str = "*",
    equals: Mapping[str, Any] | None = None,
    chunk_size: int = 80,
) -> list[dict[str, Any]]:
    clean_values = list(dict.fromkeys(v for v in values if v not in (None, "")))
    if not clean_values:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(clean_values), chunk_size):
        chunk = clean_values[start:start + chunk_size]
        try:
            query = client.table(table).select(columns).in_(field, chunk)
            for key, value in (equals or {}).items():
                query = query.eq(key, value)
            out.extend(_rows(query.execute()))
        except Exception as exc:
            raise DomainReadError(f"Falha lendo {table}.{field} em lote: {exc}") from exc
    return out


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


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _sha_json(value: Any) -> str:
    payload = json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()




def _dedicated_outcome_authority(row: Mapping[str, Any], base_authority: float) -> float:
    """Outcome tables are semantically more direct than a proposal item label.

    information_source refines the floor, but never turns legacy metadata into
    explicit human review. This prevents a low-confidence extraction from a
    proposal deck from outranking a dedicated outcome record.
    """
    source = _norm(row.get("information_source")).replace(" ", "_")
    floor = {
        "client_feedback": 0.95,
        "email": 0.90,
        "meeting": 0.88,
        "document": 0.85,
        "voe_team": 0.78,
        "other": 0.65,
        # Missing source metadata cannot manufacture source authority.
        "not_informed": 0.0,
    }.get(source, 0.0)
    return max(float(base_authority or 0.0), floor)

def _version_key(row: Mapping[str, Any]) -> str:
    return str(row.get("updated_at") or row.get("created_at") or "legacy-v1")


def _normalized_event_version_key(row: Mapping[str, Any]) -> str:
    # The transform version is part of event identity. If semantics are corrected
    # (e.g. V28.7.0 -> V28.7.1), a new event supersedes the old normalized event
    # instead of mutating append-only history in place.
    return f"{_version_key(row)}|{DOMAIN_NORMALIZATION_VERSION}"


def _confidence_from_legacy(level: Any) -> tuple[float, float, bool]:
    """Retorna model confidence, source authority, explicit human review.

    V28.7.1: rótulos legacy NÃO equivalem a review explícito dentro da NAVE.
    Mesmo client_confirmed/voe_confirmed ficam is_human_confirmed=False.
    """
    key = _norm(level).replace(" ", "_")
    # confidence_level is a LEGACY confidence label, not evidence of source
    # authority. Source authority is refined separately from information_source.
    if key == "client_confirmed":
        return 0.99, 0.70, False
    if key == "voe_confirmed":
        return 0.96, 0.65, False
    if key == "inferred":
        return 0.72, 0.40, False
    return 0.45, 0.30, False


# ---------------------------------------------------------------------------
# Legacy -> domain semantics that are safe in this phase
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

    # Strategy/Journey permanecem compatibilidade da V28.7.0 até a V28.7.2.
    # Não são promovidas aqui a novos domínios nem usadas como modelo universal.
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
    """Compat helper. Crucial: executed NEVER implies approved."""
    status = _norm(row.get("item_status"))
    proposal = {
        "proposto": "proposed",
        "opcao": "proposed",
        "recomendado": "proposed",
        "aprovado": "approved",
        "descartado": "rejected",
        "referencia": "unknown",
        "nao identificado": "unknown",
        "executado": "unknown",
    }.get(status, "unknown")
    execution = "executed" if status == "executado" else "not_confirmed"
    return proposal, execution


def _item_status_outcome(status: Any) -> tuple[str, str] | None:
    key = _norm(status)
    if key in {"proposto", "opcao", "recomendado"}:
        return "proposal_status", "proposed"
    if key == "aprovado":
        return "proposal_status", "approved"
    if key == "descartado":
        return "proposal_status", "rejected"
    if key == "executado":
        return "execution_status", "executed"
    return None


def _occurrence_semantics(status: Any) -> tuple[str, str]:
    """Classify an occurrence only from item-level semantics.

    A document's overall phase is contextual metadata; it cannot upgrade an
    ambiguous mention to proposal/execution/approval.
    """
    key = _norm(status)
    if key == "executado":
        return "execution", "execution"
    if key == "referencia":
        return "reference", "reference"
    if key in {"proposto", "opcao", "recomendado"}:
        return "proposal", "proposal"
    if key in {"aprovado", "descartado"}:
        return "approval", "mention"
    return "other", "mention"


def _solution_identity_key(row: Mapping[str, Any], solution_kind: str) -> str:
    name = _norm(row.get("title")) or _norm(row.get("item_type")) or "sem nome"
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


def _group_memory_items(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        kind = solution_kind_from_legacy(row)
        key = _solution_identity_key(row, kind)
        grouped.setdefault((key, kind), []).append(row)
    return [(key, kind, items) for (key, kind), items in grouped.items()]


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


def _merge_text(rows: Sequence[Mapping[str, Any]], key: str) -> str | None:
    values = [_clean(row.get(key)) for row in rows]
    values = [value for value in values if value]
    return max(values, key=len) if values else None


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


def _financial_document_kind(row: Mapping[str, Any]) -> str:
    text = _norm(" ".join(str(v or "") for v in (row.get("title"), row.get("file_name"), row.get("metadata"))))
    if "actual" in text or "realizado" in text or "fechamento" in text:
        return "actual_cost"
    if "supplier" in text or "fornecedor" in text or "cotacao" in text or "quotation" in text:
        return "supplier_quote"
    return "proposal_budget"


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
    return "client" if _norm(row.get("item_status")) == "client responsibility" else "unknown"


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
    return None


def _project_outcome_rows(memory_outcome: Mapping[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    commercial = _norm(memory_outcome.get("commercial_result")).replace(" ", "_")
    if commercial not in {"", "in_evaluation", "not_informed"}:
        rows.append(("commercial_result", commercial))

    proposal = _norm(memory_outcome.get("proposal_result")).replace(" ", "_")
    proposal_map = {
        "fully_approved": "approved",
        "partially_approved": "approved_with_changes",
        "not_approved": "rejected",
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


# ---------------------------------------------------------------------------
# Evidence binding
# ---------------------------------------------------------------------------


def _locator_sha(locator: Mapping[str, Any] | None) -> str:
    return _sha_json(dict(locator or {}))


def _evidence_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        asset_id = str(row.get("source_asset_id") or "")
        if asset_id:
            out.setdefault(asset_id, []).append(row)
    return out


def _best_evidence(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return dict(max(candidates, key=lambda r: float(r.get("extraction_confidence") or 0.0)))


def _conservative_evidence_match(
    candidates: Sequence[Mapping[str, Any]],
    *,
    text_hints: Sequence[Any] = (),
    locator_key: str | None = None,
    locator_value: int | str | None = None,
) -> dict[str, Any] | None:
    """Return evidence only when the binding is unambiguous.

    Provenance cannot be a fuzzy convenience. If a page/slide contains several
    fragment EvidenceUnits, we either find one uniquely supported by the object's
    own text or use a unique page/slide container unit. Otherwise we leave the
    domain object evidence-unbound and surface that gap to the debugger.
    """
    unique: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        row = dict(raw)
        key = str(row.get("id") or _sha_json(row))
        unique[key] = row
    rows = list(unique.values())
    if len(rows) == 1:
        return rows[0]
    if not rows:
        return None

    hints = [_norm(v) for v in text_hints if _norm(v) and len(_norm(v)) >= 4]
    if hints:
        matched = [
            row for row in rows
            if any(hint in _norm(row.get("content_text")) for hint in hints)
        ]
        if len(matched) == 1:
            return matched[0]

    if locator_key and locator_value not in (None, ""):
        containers: list[dict[str, Any]] = []
        for row in rows:
            locator = row.get("locator") if isinstance(row.get("locator"), Mapping) else {}
            if str(locator.get(locator_key) or "") != str(locator_value):
                continue
            # Container locators may include a harmless source/file key, but not
            # block/fragment/shape/cell coordinates that narrow to another object.
            fragment_keys = {
                "block", "block_index", "fragment", "fragment_index", "shape",
                "shape_index", "paragraph", "paragraph_index", "cell", "bbox",
            }
            if not fragment_keys.intersection(str(k) for k in locator.keys()):
                containers.append(row)
        if len(containers) == 1:
            return containers[0]

    return None


def _evidence_for_memory_item(
    row: Mapping[str, Any],
    *,
    document_by_id: Mapping[str, Mapping[str, Any]],
    asset_by_sha: Mapping[str, Mapping[str, Any]],
    evidence_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[str | None, dict[str, Any] | None]:
    doc = document_by_id.get(str(row.get("document_id") or ""))
    if not doc:
        return None, None
    asset = asset_by_sha.get(str(doc.get("content_sha256") or ""))
    if not asset:
        return None, None
    asset_id = str(asset.get("id") or "")
    page = int(row.get("source_page") or 0)
    if not asset_id or page <= 0:
        return asset_id or None, None
    mime = str(doc.get("mime_type") or "").casefold()
    preferred = "slide" if "presentation" in mime or str(doc.get("file_name") or "").lower().endswith(".pptx") else "page"
    rows = list(evidence_by_asset.get(asset_id) or [])
    exact = [
        ev for ev in rows
        if str(ev.get("unit_type") or "") == preferred
        and (
            int((ev.get("locator") or {}).get(preferred) or 0) == page
            or int(ev.get("ordinal") or 0) == page
        )
    ]
    match = _conservative_evidence_match(
        exact,
        text_hints=(row.get("title"), row.get("summary"), row.get("description")),
        locator_key=preferred,
        locator_value=page,
    )
    if match:
        return asset_id, match

    fallback = [
        ev for ev in rows
        if str(ev.get("unit_type") or "") in {"page", "slide"}
        and int(ev.get("ordinal") or 0) == page
    ]
    match = _conservative_evidence_match(
        fallback,
        text_hints=(row.get("title"), row.get("summary"), row.get("description")),
        locator_key=preferred,
        locator_value=page,
    )
    return asset_id, match


def _evidence_for_requirement(
    row: Mapping[str, Any],
    *,
    briefing_document_by_id: Mapping[str, Mapping[str, Any]],
    asset_by_sha: Mapping[str, Mapping[str, Any]],
    evidence_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[str | None, dict[str, Any] | None]:
    doc = briefing_document_by_id.get(str(row.get("briefing_document_id") or ""))
    if not doc:
        return None, None
    asset = asset_by_sha.get(str(doc.get("content_sha256") or ""))
    if not asset:
        return None, None
    asset_id = str(asset.get("id") or "")
    candidates = list(evidence_by_asset.get(asset_id) or [])

    quote = _norm(row.get("source_quote"))
    if quote:
        matches = [ev for ev in candidates if quote in _norm(ev.get("content_text"))]
        match = _conservative_evidence_match(matches, text_hints=(row.get("source_quote"), row.get("title")))
        if match:
            return asset_id, match
        # An exact quote that occurs in multiple evidence units is ambiguous; do
        # not silently select the highest-confidence extraction.

    ref = str(row.get("source_reference") or "")
    numbers = [int(v) for v in re.findall(r"\d+", ref)]
    if numbers:
        ordinal = numbers[0]
        ref_norm = _norm(ref)
        unit_types: set[str]
        if "slide" in ref_norm:
            unit_types = {"slide"}
        elif "pag" in ref_norm or "page" in ref_norm:
            unit_types = {"page"}
        elif "parag" in ref_norm:
            unit_types = {"paragraph"}
        else:
            unit_types = {"page", "slide", "paragraph"}
        matches = [ev for ev in candidates if str(ev.get("unit_type") or "") in unit_types and int(ev.get("ordinal") or 0) == ordinal]
        locator_key = "slide" if "slide" in unit_types and len(unit_types) == 1 else "page" if "page" in unit_types and len(unit_types) == 1 else "paragraph" if "paragraph" in unit_types and len(unit_types) == 1 else None
        match = _conservative_evidence_match(
            matches,
            text_hints=(row.get("source_quote"), row.get("title")),
            locator_key=locator_key,
            locator_value=ordinal if locator_key else None,
        )
        if match:
            return asset_id, match
    return asset_id, None


def _evidence_for_cost_item(
    row: Mapping[str, Any],
    *,
    cost_document_by_id: Mapping[str, Mapping[str, Any]],
    asset_by_sha: Mapping[str, Mapping[str, Any]],
    evidence_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[str | None, dict[str, Any] | None]:
    doc = cost_document_by_id.get(str(row.get("cost_document_id") or ""))
    if not doc:
        return None, None
    asset = asset_by_sha.get(str(doc.get("content_sha256") or ""))
    if not asset:
        return None, None
    asset_id = str(asset.get("id") or "")
    sheet = str(row.get("source_sheet") or "")
    source_row = int(row.get("source_row") or 0)
    matches = []
    for ev in evidence_by_asset.get(asset_id) or []:
        if str(ev.get("unit_type") or "") != "row":
            continue
        locator = ev.get("locator") if isinstance(ev.get("locator"), Mapping) else {}
        if str(locator.get("sheet") or "") == sheet and int(locator.get("row") or 0) == source_row:
            matches.append(ev)
    return asset_id, _best_evidence(matches)


def _evidence_link(
    *,
    project_id: str,
    object_entity_id: str,
    domain_table: str,
    domain_id: str,
    evidence_unit_id: str,
    link_role: str,
    context: Mapping[str, Any],
    binding_confidence: float,
) -> dict[str, Any]:
    context_dict = dict(context)
    return {
        "project_id": project_id,
        "object_entity_id": object_entity_id,
        "domain_table": domain_table,
        "domain_id": domain_id,
        "evidence_unit_id": evidence_unit_id,
        "link_role": link_role,
        "context": context_dict,
        "context_sha256": _sha_json(context_dict),
        "binding_confidence": binding_confidence,
    }


# ---------------------------------------------------------------------------
# Bundle build
# ---------------------------------------------------------------------------


def _existing_by(rows: Sequence[Mapping[str, Any]], key_fn: Any) -> dict[Any, dict[str, Any]]:
    out: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        if key not in (None, "", (None, None)):
            out[key] = dict(row)
    return out


def _read_project_inputs(client: Any, project_id: str) -> dict[str, Any]:
    """All reads are strict. Failure aborts BEFORE any domain write."""
    project = _strict_one(client, "projects", equals={"id": project_id})
    if not project:
        raise DomainReadError(f"Projeto {project_id} não encontrado")

    data: dict[str, Any] = {
        "project": project,
        "memory_items": _strict_rows(client, "memory_items", equals={"project_id": project_id}),
        "memory_documents": _strict_rows(client, "memory_documents", equals={"project_id": project_id}),
        "requirements": _strict_rows(client, "memory_briefing_requirements", equals={"project_id": project_id}),
        "briefing_documents": _strict_rows(client, "memory_briefing_documents", equals={"project_id": project_id}),
        "cost_documents": _strict_rows(client, "memory_cost_documents", equals={"project_id": project_id}),
        "cost_items": _strict_rows(client, "memory_cost_items", equals={"project_id": project_id}),
        "item_outcomes": _strict_rows(client, "memory_item_outcomes", equals={"project_id": project_id}),
        "project_outcomes": _strict_rows(client, "memory_project_outcomes", equals={"project_id": project_id}),
        "existing_solutions": _strict_rows(client, "project_solution_instances", equals={"project_id": project_id}),
        "existing_requirements": _strict_rows(client, "project_requirements", equals={"project_id": project_id}),
        "existing_financial_documents": _strict_rows(client, "financial_documents", equals={"project_id": project_id}),
        "existing_financial_line_items": _strict_rows(client, "financial_line_items", equals={"project_id": project_id}),
        "existing_occurrences": _strict_rows(client, "project_solution_occurrences", equals={"project_id": project_id}),
    }

    project_mirror = _strict_one(
        client,
        "knowledge_entities",
        equals={"domain_table": "projects", "domain_id": project_id},
    )
    data["project_mirror"] = project_mirror

    domain_entity_ids = [
        str(row.get("entity_id"))
        for name in ("existing_solutions", "existing_requirements", "existing_financial_line_items")
        for row in data[name]
        if row.get("entity_id")
    ]
    data["governance"] = _strict_in_rows(
        client,
        "domain_object_governance",
        field="entity_id",
        values=domain_entity_ids,
    ) if domain_entity_ids else []

    hashes = list(dict.fromkeys(
        str(row.get("content_sha256") or "")
        for name in ("memory_documents", "briefing_documents", "cost_documents")
        for row in data[name]
        if row.get("content_sha256")
    ))
    assets = _strict_in_rows(client, "source_assets", field="content_sha256", values=hashes) if hashes else []
    data["source_assets"] = assets
    asset_ids = [str(row.get("id")) for row in assets if row.get("id")]
    data["evidence_units"] = _strict_in_rows(
        client,
        "evidence_units",
        field="source_asset_id",
        values=asset_ids,
        equals={"is_current": True},
    ) if asset_ids else []
    return data


def _project_name(project: Mapping[str, Any], project_id: str) -> str:
    return (
        _clean(project.get("project_name"))
        or _clean(project.get("name"))
        or _clean(project.get("event_name"))
        or f"Projeto {project_id[:8]}"
    )


def _build_bundle(project_id: str, data: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    project = data["project"]
    project_mirror = data.get("project_mirror") or {}
    project_entity_id = str(project_mirror.get("id") or uuid4())
    project_name = _project_name(project, project_id)

    documents_by_id = _existing_by(data["memory_documents"], lambda r: str(r.get("id") or ""))
    briefing_docs_by_id = _existing_by(data["briefing_documents"], lambda r: str(r.get("id") or ""))
    cost_docs_by_id = _existing_by(data["cost_documents"], lambda r: str(r.get("id") or ""))
    asset_by_sha = _existing_by(data["source_assets"], lambda r: str(r.get("content_sha256") or ""))
    evidence_by_asset = _evidence_index(data["evidence_units"])

    existing_solutions = _existing_by(data["existing_solutions"], lambda r: str(r.get("identity_key") or ""))
    existing_requirements = _existing_by(
        data["existing_requirements"],
        lambda r: (str(r.get("legacy_source_table") or ""), str(r.get("legacy_source_id") or "")),
    )
    existing_fin_docs = _existing_by(
        data["existing_financial_documents"],
        lambda r: (str(r.get("legacy_source_table") or ""), str(r.get("legacy_source_id") or "")),
    )
    existing_lines = _existing_by(
        data["existing_financial_line_items"],
        lambda r: (str(r.get("legacy_source_table") or ""), str(r.get("legacy_source_id") or "")),
    )
    existing_occurrences = _existing_by(
        data["existing_occurrences"],
        lambda r: str(r.get("legacy_memory_item_id") or ""),
    )

    solutions: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    evidence_links: list[dict[str, Any]] = []
    solution_by_legacy_item: dict[str, dict[str, Any]] = {}

    for identity_key, kind, items in _group_memory_items(data["memory_items"]):
        existing = existing_solutions.get(identity_key) or {}
        domain_id = str(existing.get("id") or uuid4())
        entity_id = str(existing.get("entity_id") or uuid4())
        title = max((_clean(row.get("title")) for row in items if _clean(row.get("title"))), key=len, default="Solução")
        description = _merge_text(items, "description") or _merge_text(items, "summary")
        journey_stage = next((_clean(row.get("journey_stage")) for row in items if _clean(row.get("journey_stage"))), None)
        legacy_ids = [str(row.get("id")) for row in items if row.get("id")]
        roles: list[str] = []
        confidences: list[float] = []
        for row in items:
            roles.extend(contextual_roles_from_legacy(row, kind))
            value = _float(row.get("confidence"))
            if value is not None:
                confidences.append(value)
        confidence = max(confidences) if confidences else 0.92
        attrs = {
            "normalized_by": DOMAIN_NORMALIZATION_VERSION,
            "legacy_memory_item_ids": legacy_ids,
            "legacy_sections": list(dict.fromkeys(str(row.get("section_key") or "") for row in items if row.get("section_key"))),
            "legacy_item_types": list(dict.fromkeys(str(row.get("item_type") or "") for row in items if row.get("item_type"))),
            "source_pages": sorted({int(row.get("source_page")) for row in items if str(row.get("source_page") or "").isdigit()}),
            "tags": list(dict.fromkeys(str(tag) for row in items for tag in (row.get("tags") or []) if str(tag).strip())),
            "objectives": list(dict.fromkeys(str(v) for row in items for v in (row.get("objectives") or []) if str(v).strip())),
            "audiences": list(dict.fromkeys(str(v) for row in items for v in (row.get("audiences") or []) if str(v).strip())),
            "mechanics": list(dict.fromkeys(str(v) for row in items for v in (row.get("mechanics") or []) if str(v).strip())),
            "technologies": list(dict.fromkeys(str(v) for row in items for v in (row.get("technologies") or []) if str(v).strip())),
            "compatibility_note": "strategy/journey classification remains legacy_shadow until V28.7.2",
        }
        solution = {
            "id": domain_id,
            "entity_id": entity_id,
            "entity_type": _entity_type_for_solution(kind),
            "identity_key": identity_key,
            "solution_kind": kind,
            "name": title,
            "normalized_name": _norm(title),
            "description": description,
            "journey_stage": journey_stage,
            "roles": list(dict.fromkeys(roles)),
            "attributes": attrs,
            "confidence": confidence,
            "source_authority_score": 0.58,
            "legacy_source_ids": legacy_ids,
        }
        solutions.append(solution)
        for legacy_id in legacy_ids:
            solution_by_legacy_item[legacy_id] = solution

        for row in items:
            legacy_id = str(row.get("id") or "")
            if not legacy_id:
                continue
            asset_id, evidence = _evidence_for_memory_item(
                row,
                document_by_id=documents_by_id,
                asset_by_sha=asset_by_sha,
                evidence_by_asset=evidence_by_asset,
            )
            doc = documents_by_id.get(str(row.get("document_id") or "")) or {}
            doc_status = _norm(doc.get("document_status"))
            item_status = _norm(row.get("item_status"))
            # A post-event/executed document is context, not proof that every item
            # mentioned in it was executed. Occurrence semantics require item-level
            # evidence; dedicated outcomes remain the stronger status authority.
            phase, role = _occurrence_semantics(row.get("item_status"))
            existing_occ = existing_occurrences.get(legacy_id) or {}
            occurrence_id = str(existing_occ.get("id") or uuid4())
            locator = dict((evidence or {}).get("locator") or {})
            if not locator and row.get("source_page"):
                locator = {"source_page": int(row.get("source_page"))}
            occurrence = {
                "id": occurrence_id,
                "solution_instance_id": domain_id,
                "legacy_memory_item_id": legacy_id,
                "source_asset_id": asset_id,
                "evidence_unit_id": str((evidence or {}).get("id") or "") or None,
                "occurrence_phase": phase,
                "occurrence_role": role,
                "observed_name": _clean(row.get("title")),
                "observed_status": _clean(row.get("item_status")),
                "section_key": _clean(row.get("section_key")),
                "source_page": int(row.get("source_page") or 0) or None,
                "source_locator": locator,
                "confidence": _float(row.get("confidence")) or confidence,
                "attributes": {
                    "document_id": row.get("document_id"),
                    "page_id": row.get("page_id"),
                    "slide_title": row.get("slide_title"),
                    "source_document_status": doc_status or None,
                    "normalized_by": DOMAIN_NORMALIZATION_VERSION,
                },
            }
            occurrences.append(occurrence)
            if evidence and evidence.get("id"):
                evidence_links.append(_evidence_link(
                    project_id=project_id,
                    object_entity_id=entity_id,
                    domain_table="project_solution_instances",
                    domain_id=domain_id,
                    evidence_unit_id=str(evidence["id"]),
                    link_role="occurrence",
                    context={"occurrence_id": occurrence_id, "legacy_memory_item_id": legacy_id, "phase": phase},
                    binding_confidence=0.99,
                ))
            elif asset_id:
                warnings.append(f"Solução '{title}': source_asset localizado, mas occurrence {legacy_id[:8]} sem evidence_unit exata.")

    requirements: list[dict[str, Any]] = []
    for row in data["requirements"]:
        legacy_id = str(row.get("id") or "")
        if not legacy_id:
            continue
        existing = existing_requirements.get(("memory_briefing_requirements", legacy_id)) or {}
        domain_id = str(existing.get("id") or uuid4())
        entity_id = str(existing.get("entity_id") or uuid4())
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
        requirement = {
            "id": domain_id,
            "entity_id": entity_id,
            "requirement_type": str(row.get("requirement_type") or "context"),
            "title": title,
            "normalized_name": _norm(title),
            "description": _clean(row.get("description")),
            "priority": str(row.get("priority") or "not_informed"),
            "mandatory": bool(row.get("mandatory")),
            # Quantitative parsing is V28.7.2. Do not invent it here.
            "constraint_operator": existing.get("constraint_operator"),
            "constraint_value": existing.get("constraint_value"),
            "unit": existing.get("unit"),
            "status": _requirement_status(row),
            "confidence": confidence,
            "attributes": attrs,
            "legacy_source_id": legacy_id,
        }
        requirements.append(requirement)
        _asset_id, evidence = _evidence_for_requirement(
            row,
            briefing_document_by_id=briefing_docs_by_id,
            asset_by_sha=asset_by_sha,
            evidence_by_asset=evidence_by_asset,
        )
        if evidence and evidence.get("id"):
            evidence_links.append(_evidence_link(
                project_id=project_id,
                object_entity_id=entity_id,
                domain_table="project_requirements",
                domain_id=domain_id,
                evidence_unit_id=str(evidence["id"]),
                link_role="source",
                context={"legacy_requirement_id": legacy_id, "source_reference": row.get("source_reference")},
                binding_confidence=0.96,
            ))
        else:
            warnings.append(f"Requisito '{title}': sem evidence_unit exata; mantido em legacy_shadow sem provenance inventada.")

    financial_documents: list[dict[str, Any]] = []
    fin_doc_by_legacy: dict[str, dict[str, Any]] = {}
    for row in data["cost_documents"]:
        legacy_id = str(row.get("id") or "")
        if not legacy_id:
            continue
        existing = existing_fin_docs.get(("memory_cost_documents", legacy_id)) or {}
        domain_id = str(existing.get("id") or uuid4())
        asset = asset_by_sha.get(str(row.get("content_sha256") or "")) or {}
        doc = {
            "id": domain_id,
            "source_asset_id": str(asset.get("id") or "") or None,
            "document_kind": _financial_document_kind(row),
            "currency": str(row.get("currency") or "BRL"),
            "base_total": row.get("total_base"),
            "fees_total": row.get("fees_total"),
            "taxes_total": row.get("charges_total"),
            "client_total": row.get("client_total"),
            "actual_total": existing.get("actual_total"),
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
            "legacy_source_id": legacy_id,
        }
        financial_documents.append(doc)
        fin_doc_by_legacy[legacy_id] = doc
        if not doc["source_asset_id"]:
            warnings.append(f"Documento financeiro {legacy_id[:8]} sem source_asset correspondente por hash.")

    financial_line_items: list[dict[str, Any]] = []
    for row in data["cost_items"]:
        legacy_id = str(row.get("id") or "")
        legacy_doc_id = str(row.get("cost_document_id") or "")
        fin_doc = fin_doc_by_legacy.get(legacy_doc_id)
        if not legacy_id or not fin_doc:
            continue
        existing = existing_lines.get(("memory_cost_items", legacy_id)) or {}
        domain_id = str(existing.get("id") or uuid4())
        entity_id = str(existing.get("entity_id") or uuid4())
        name = _clean(row.get("item_name")) or "Linha financeira"
        _asset_id, evidence = _evidence_for_cost_item(
            row,
            cost_document_by_id=cost_docs_by_id,
            asset_by_sha=asset_by_sha,
            evidence_by_asset=evidence_by_asset,
        )
        attrs = {
            "normalized_by": DOMAIN_NORMALIZATION_VERSION,
            "source_sheet": row.get("source_sheet"),
            "source_row": row.get("source_row"),
            "billing_type": row.get("billing_type"),
            "estimate_type": row.get("estimate_type"),
            "legacy_item_status": row.get("item_status"),
            "raw_data": row.get("raw_data") or {},
        }
        line = {
            "id": domain_id,
            "entity_id": entity_id,
            "financial_document_id": fin_doc["id"],
            "source_evidence_id": str((evidence or {}).get("id") or "") or None,
            "line_code": row.get("item_code"),
            "category": row.get("category"),
            "subcategory": existing.get("subcategory"),
            "item_name": name,
            "normalized_name": _norm(name),
            "description": _clean(row.get("description")),
            "supplier_entity_id": existing.get("supplier_entity_id"),
            "quantity": row.get("quantity"),
            "period": row.get("period"),
            "unit": existing.get("unit"),
            "unit_value": row.get("unit_value"),
            "base_value": row.get("base_value"),
            "fees_value": row.get("fees_value"),
            "taxes_value": row.get("charges_value"),
            "total_value": row.get("client_total"),
            "cost_state": _cost_state(row),
            "paid_by": _paid_by(row),
            "flags": row.get("flags") or [],
            "attributes": attrs,
            "legacy_source_id": legacy_id,
        }
        financial_line_items.append(line)
        if evidence and evidence.get("id"):
            evidence_links.append(_evidence_link(
                project_id=project_id,
                object_entity_id=entity_id,
                domain_table="financial_line_items",
                domain_id=domain_id,
                evidence_unit_id=str(evidence["id"]),
                link_role="source",
                context={"legacy_cost_item_id": legacy_id, "sheet": row.get("source_sheet"), "row": row.get("source_row")},
                binding_confidence=1.0,
            ))
        else:
            warnings.append(f"Linha financeira '{name}' ({row.get('source_sheet')}:{row.get('source_row')}): sem evidence row exata.")

    outcomes: list[dict[str, Any]] = []

    # Status extracted on memory_items becomes an event; never direct status truth.
    for row in data["memory_items"]:
        legacy_id = str(row.get("id") or "")
        solution = solution_by_legacy_item.get(legacy_id)
        semantic = _item_status_outcome(row.get("item_status"))
        if not legacy_id or not solution or not semantic:
            continue
        outcome_type, outcome_status = semantic
        outcomes.append({
            "entity_id": solution["entity_id"],
            "outcome_type": outcome_type,
            "outcome_status": outcome_status,
            "outcome_at": None,
            "reason": _clean(row.get("evidence")),
            "source_claim_id": None,
            "source_evidence_id": next((
                occ.get("evidence_unit_id") for occ in occurrences
                if occ.get("legacy_memory_item_id") == legacy_id and occ.get("evidence_unit_id")
            ), None),
            "confidence": _float(row.get("confidence")) or 0.82,
            "authority_score": 0.58,
            "is_human_confirmed": False,
            "attributes": {"normalized_by": DOMAIN_NORMALIZATION_VERSION, "legacy_item_status": row.get("item_status")},
            "legacy_source_table": "memory_items",
            "legacy_source_id": legacy_id,
            "legacy_version_key": _normalized_event_version_key(row),
        })

    for row in data["item_outcomes"]:
        item_id = str(row.get("item_id") or "")
        solution = solution_by_legacy_item.get(item_id)
        semantic = _item_outcome_semantics(row.get("outcome_status"))
        if not solution or not semantic:
            continue
        outcome_type, outcome_status = semantic
        confidence, authority, human = _confidence_from_legacy(row.get("confidence_level"))
        authority = _dedicated_outcome_authority(row, authority)
        reason = _clean(row.get("decision_reason")) or _clean(row.get("feedback_summary")) or _clean(row.get("execution_notes"))
        outcomes.append({
            "entity_id": solution["entity_id"],
            "outcome_type": outcome_type,
            "outcome_status": outcome_status,
            "outcome_at": None,
            "reason": reason,
            "source_claim_id": None,
            "source_evidence_id": None,
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
            "legacy_version_key": _normalized_event_version_key(row),
        })

    memory_project_outcome = data["project_outcomes"][0] if data["project_outcomes"] else None
    if memory_project_outcome:
        confidence, authority, human = _confidence_from_legacy(memory_project_outcome.get("confidence_level"))
        authority = _dedicated_outcome_authority(memory_project_outcome, authority)
        for outcome_type, outcome_status in _project_outcome_rows(memory_project_outcome):
            reason_parts: list[str] = []
            if memory_project_outcome.get("result_context"):
                reason_parts.append(str(memory_project_outcome["result_context"]))
            reason_parts.extend(str(v) for v in (memory_project_outcome.get("result_reasons") or []) if str(v).strip())
            if outcome_type == "execution_status" and memory_project_outcome.get("execution_notes"):
                reason_parts.append(str(memory_project_outcome["execution_notes"]))
            event_date = memory_project_outcome.get("execution_date") if outcome_type == "execution_status" else memory_project_outcome.get("result_date")
            outcomes.append({
                "entity_id": project_entity_id,
                "outcome_type": outcome_type,
                "outcome_status": outcome_status,
                "outcome_at": f"{event_date}T12:00:00+00:00" if event_date else None,
                "reason": _clean(" | ".join(reason_parts)),
                "source_claim_id": None,
                "source_evidence_id": None,
                "confidence": confidence,
                "authority_score": authority,
                "is_human_confirmed": human,
                "attributes": {
                    "normalized_by": DOMAIN_NORMALIZATION_VERSION,
                    "process_type": memory_project_outcome.get("process_type"),
                    "information_source": memory_project_outcome.get("information_source"),
                    "contracting_client": memory_project_outcome.get("contracting_client"),
                },
                "legacy_source_table": "memory_project_outcomes",
                "legacy_source_id": project_id,
                "legacy_version_key": _normalized_event_version_key(memory_project_outcome),
            })

    bundle = {
        "version": DOMAIN_NORMALIZATION_VERSION,
        "schema_version": DOMAIN_SCHEMA_VERSION,
        "project_id": project_id,
        "project_entity_id": project_entity_id,
        "project_name": project_name,
        "project_normalized_name": _norm(project_name),
        "solutions": solutions,
        "requirements": requirements,
        "financial_documents": financial_documents,
        "financial_line_items": financial_line_items,
        "solution_occurrences": occurrences,
        "evidence_links": evidence_links,
        "outcomes": outcomes,
    }
    return bundle, list(dict.fromkeys(warnings))


def _validate_bundle(bundle: Mapping[str, Any], data: Mapping[str, Any]) -> None:
    errors: list[str] = []
    if len(bundle.get("requirements") or []) < len(data.get("requirements") or []):
        errors.append("requisitos normalizados ficaram abaixo do legado")
    if len(bundle.get("financial_documents") or []) < len(data.get("cost_documents") or []):
        errors.append("documentos financeiros normalizados ficaram abaixo do legado")
    if len(bundle.get("financial_line_items") or []) < len(data.get("cost_items") or []):
        errors.append("linhas financeiras normalizadas ficaram abaixo do legado")
    if len(bundle.get("solution_occurrences") or []) != len([r for r in data.get("memory_items") or [] if r.get("id")]):
        errors.append("cada memory_item com id precisa virar exatamente uma occurrence")

    solution_ids = {str(row.get("id")) for row in bundle.get("solutions") or []}
    if any(str(row.get("solution_instance_id")) not in solution_ids for row in bundle.get("solution_occurrences") or []):
        errors.append("há occurrence apontando para solution instance fora do bundle")

    # Regression gate: execution cannot manufacture proposal approval.
    for row in data.get("memory_items") or []:
        if _norm(row.get("item_status")) == "executado":
            proposal, execution = _proposal_execution_status(row)
            if proposal != "unknown" or execution != "executed":
                errors.append("executado não pode implicar aprovado")
                break

    if errors:
        raise DomainBundleError("; ".join(errors))


# ---------------------------------------------------------------------------
# Run / RPC
# ---------------------------------------------------------------------------


def _schema_error_kind(exc: Exception) -> str:
    """Classify schema-probe failures without turning every read error into "not installed"."""
    text = str(exc)
    folded = text.casefold()
    if "pgrst205" in folded or "could not find the table" in folded or "schema cache" in folded:
        return "schema_missing"
    return "schema_check_error"


def _domain_schema_available(client: Any) -> tuple[bool, str | None, str | None]:
    required = (
        "project_solution_instances",
        "project_requirements",
        "financial_documents",
        "financial_line_items",
        "entity_outcomes",
        "project_solution_occurrences",
        "domain_object_evidence",
        "domain_object_governance",
        "project_domain_migration_state",
    )
    try:
        for table in required:
            client.table(table).select("*").limit(1).execute()
        return True, None, None
    except Exception as exc:
        return False, _schema_error_kind(exc), str(exc)


def probe_domain_schema(client: Any) -> dict[str, Any]:
    """Public preflight used by orchestration before any downstream mutation."""
    available, failure_kind, error = _domain_schema_available(client)
    return {
        "available": bool(available),
        "status": "ready" if available else (failure_kind or "schema_check_error"),
        "error": error,
    }


def _start_run(client: Any, *, project_id: str, bundle: Mapping[str, Any]) -> str:
    run_id = str(uuid4())
    signature = _sha_json(bundle)
    payload = {
        "id": run_id,
        "analyzer_type": "domain_normalization",
        "scope_kind": "project",
        "pipeline_version": DOMAIN_NORMALIZATION_VERSION,
        "code_version": DOMAIN_NORMALIZATION_VERSION,
        "schema_version": DOMAIN_SCHEMA_VERSION,
        "input_signature": signature,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"project_id": project_id, "migration_mode": "legacy_shadow", "transactional_apply": True},
    }
    try:
        rows = _rows(client.table("intelligence_runs").insert(payload).execute())
    except Exception as exc:
        raise RuntimeError(f"Não foi possível abrir intelligence_run da normalização: {exc}") from exc
    if not rows:
        raise RuntimeError("Supabase não confirmou intelligence_run da normalização")
    return str(rows[0].get("id") or run_id)


def _mark_run_error(client: Any, run_id: str, exc: Exception) -> None:
    try:
        client.table("intelligence_runs").update({
            "status": "error",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "domain_normalization_error",
            "error_detail": str(exc)[:4000],
        }).eq("id", run_id).execute()
    except Exception:
        # This is observability-only and must not mask the original error.
        pass


def _rpc_result(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return dict(data)
    if isinstance(data, list) and data and isinstance(data[0], Mapping):
        return dict(data[0])
    return {}


# ---------------------------------------------------------------------------
# Status/debugger
# ---------------------------------------------------------------------------


def fetch_project_domain_status(client: Any, project_id: str) -> dict[str, Any]:
    available, failure_kind, error = _domain_schema_available(client)
    if not available:
        return {"status": failure_kind or "schema_check_error", "project_id": project_id, "error": error}
    try:
        status_rows = _strict_rows(client, "project_domain_integrity_status", equals={"project_id": project_id})
        status = status_rows[0] if status_rows else {}
        current_outcomes = _strict_rows(client, "entity_current_outcomes", equals={"project_id": project_id})
    except DomainReadError as exc:
        return {"status": "read_error", "project_id": project_id, "error": str(exc)}

    outcome_breakdown: dict[str, int] = {}
    for row in current_outcomes:
        key = str(row.get("outcome_type") or "other")
        outcome_breakdown[key] = outcome_breakdown.get(key, 0) + 1

    normalized = {
        "solution_instances": int(status.get("solution_instances") or 0),
        "solution_occurrences": int(status.get("solution_occurrences") or 0),
        "occurrences_with_evidence": int(status.get("occurrences_with_evidence") or 0),
        "requirements": int(status.get("requirements") or 0),
        "requirements_with_evidence": int(status.get("requirements_with_evidence") or 0),
        "financial_documents": int(status.get("financial_documents") or 0),
        "financial_line_items": int(status.get("financial_line_items") or 0),
        "financial_lines_with_evidence": int(status.get("financial_lines_with_evidence") or 0),
        "outcomes": int(status.get("current_outcomes") or 0),
        "evidence_links": int(status.get("evidence_links") or 0),
    }
    legacy = {
        "memory_items": int(status.get("legacy_memory_items") or 0),
        "requirements": int(status.get("legacy_requirements") or 0),
        "cost_documents": int(status.get("legacy_cost_documents") or 0),
        "cost_items": int(status.get("legacy_cost_items") or 0),
    }
    integrity = {
        "migration_mode": status.get("migration_mode") or "legacy_shadow",
        "domain_schema_version": status.get("domain_schema_version") or DOMAIN_SCHEMA_VERSION,
        "last_completed_run_id": status.get("last_completed_run_id"),
        "outcome_breakdown": outcome_breakdown,
        "occurrence_evidence_coverage": (
            normalized["occurrences_with_evidence"] / normalized["solution_occurrences"]
            if normalized["solution_occurrences"] else None
        ),
        "requirement_evidence_coverage": (
            normalized["requirements_with_evidence"] / normalized["requirements"]
            if normalized["requirements"] else None
        ),
        "financial_evidence_coverage": (
            normalized["financial_lines_with_evidence"] / normalized["financial_line_items"]
            if normalized["financial_line_items"] else None
        ),
    }
    return {"status": "ready", "project_id": project_id, "normalized": normalized, "legacy": legacy, "integrity": integrity}


@dataclass
class DomainNormalizationResult:
    project_id: str
    status: str
    solution_instances: int = 0
    solution_occurrences: int = 0
    requirements: int = 0
    financial_documents: int = 0
    financial_line_items: int = 0
    outcomes_created: int = 0
    evidence_links: int = 0
    warnings: list[str] | None = None
    parity: dict[str, Any] | None = None
    run_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "status": self.status,
            "solution_instances": self.solution_instances,
            "solution_occurrences": self.solution_occurrences,
            "requirements": self.requirements,
            "financial_documents": self.financial_documents,
            "financial_line_items": self.financial_line_items,
            "outcomes_created": self.outcomes_created,
            "evidence_links": self.evidence_links,
            "warnings": list(self.warnings or []),
            "parity": dict(self.parity or {}),
            "run_id": self.run_id,
        }


def sync_project_domain_normalization(client: Any, project_id: str) -> dict[str, Any]:
    """Normalize one project with strict reads and a single transactional apply."""
    available, failure_kind, error = _domain_schema_available(client)
    if not available:
        if failure_kind == "schema_missing":
            headline = "Domain Integrity V28.7.1 não está visível no Data API. Execute/revalide o SQL V28.7.1B e recarregue o schema do PostgREST."
        else:
            headline = "Não foi possível validar o schema de Domain Integrity. O erro não será tratado como banco vazio ou migration ausente."
        return DomainNormalizationResult(
            project_id=project_id,
            status=failure_kind or "schema_check_error",
            warnings=[headline, error or ""],
        ).as_dict()

    try:
        data = _read_project_inputs(client, project_id)
        bundle, warnings = _build_bundle(project_id, data)
        _validate_bundle(bundle, data)
    except Exception as exc:
        # No write occurred before this point.
        return DomainNormalizationResult(
            project_id=project_id,
            status="read_or_validation_error",
            warnings=[str(exc)],
        ).as_dict()

    run_id: str | None = None
    try:
        run_id = _start_run(client, project_id=project_id, bundle=bundle)
        response = client.rpc(NORMALIZATION_RPC, {
            "p_project_id": project_id,
            "p_run_id": run_id,
            "p_bundle": _json_safe(bundle),
        }).execute()
        applied = _rpc_result(response)
        if str(applied.get("status") or "") != "completed":
            raise RuntimeError(f"RPC não confirmou apply completo: {applied or 'resposta vazia'}")
    except Exception as exc:
        if run_id:
            _mark_run_error(client, run_id, exc)
        return DomainNormalizationResult(
            project_id=project_id,
            status="transaction_error",
            warnings=[*warnings, str(exc)],
            run_id=run_id,
        ).as_dict()

    status = fetch_project_domain_status(client, project_id)
    if status.get("status") != "ready":
        return DomainNormalizationResult(
            project_id=project_id,
            status="post_apply_read_error",
            warnings=[*warnings, str(status.get("error") or "falha ao validar geração promovida")],
            run_id=run_id,
        ).as_dict()

    normalized = status.get("normalized") or {}
    legacy = status.get("legacy") or {}
    integrity = status.get("integrity") or {}
    parity = {
        "solution_occurrence_reduction": max(0, int(legacy.get("memory_items") or 0) - int(normalized.get("solution_instances") or 0)),
        "occurrence_parity": int(normalized.get("solution_occurrences") or 0) == int(legacy.get("memory_items") or 0),
        "requirements_parity": int(normalized.get("requirements") or 0) >= int(legacy.get("requirements") or 0),
        "financial_documents_parity": int(normalized.get("financial_documents") or 0) >= int(legacy.get("cost_documents") or 0),
        "financial_line_items_parity": int(normalized.get("financial_line_items") or 0) >= int(legacy.get("cost_items") or 0),
        "legacy": legacy,
        "normalized": normalized,
        "integrity": integrity,
    }
    hard_fail = [
        key for key in ("occurrence_parity", "requirements_parity", "financial_documents_parity", "financial_line_items_parity")
        if parity.get(key) is False
    ]
    if hard_fail:
        # RPC committed a valid generation, but parity reveals an architectural regression.
        # We report it explicitly; migration mode remains legacy_shadow, so no cutover happens.
        warnings.append("Gate de paridade falhou após apply: " + ", ".join(hard_fail))

    return DomainNormalizationResult(
        project_id=project_id,
        status="completed_with_gate_warning" if hard_fail else "completed",
        solution_instances=int(normalized.get("solution_instances") or 0),
        solution_occurrences=int(normalized.get("solution_occurrences") or 0),
        requirements=int(normalized.get("requirements") or 0),
        financial_documents=int(normalized.get("financial_documents") or 0),
        financial_line_items=int(normalized.get("financial_line_items") or 0),
        outcomes_created=int((applied or {}).get("outcomes_inserted") or 0),
        evidence_links=int(normalized.get("evidence_links") or 0),
        warnings=warnings,
        parity=parity,
        run_id=run_id,
    ).as_dict()
