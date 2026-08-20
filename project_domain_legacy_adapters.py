from __future__ import annotations

"""NAVE V28.7.3A3 — comparator-side Legacy semantic adapters.

These adapters make the legacy side explicit for semantic shadow comparison.
They are intentionally *not* production view-model adapters yet. They preserve
legacy rows, add comparator metadata, and fail closed on technical read errors.

Important invariants:
- a technical read error is never converted into an empty legacy candidate;
- rows are scoped by project_id;
- no project name, Golden fixture, client or campaign is hardcoded;
- the adapters never mutate legacy data, Domain data, readiness or read_mode.
"""

from collections.abc import Iterable, Mapping
from typing import Any

LEGACY_ADAPTER_VERSION = "V28.7.3A3"
SUPPORTED_DOMAIN_KEYS = (
    "context",
    "requirements",
    "solutions",
    "outcomes",
    "strategy",
    "creative",
    "experience",
    "journey",
)


class LegacyAdapterError(RuntimeError):
    """Fail-closed legacy read failure."""


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_project_rows(client: Any, table_name: str, project_id: str) -> list[dict[str, Any]]:
    try:
        return _rows(
            client.table(table_name)
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )
    except Exception as exc:  # runtime integration path
        raise LegacyAdapterError(
            f"Legacy adapter failed reading {table_name!r} for project {project_id}: {exc}"
        ) from exc


def _read_project(client: Any, project_id: str) -> dict[str, Any]:
    try:
        rows = _rows(
            client.table("projects")
            .select("*")
            .eq("id", project_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # runtime integration path
        raise LegacyAdapterError(
            f"Legacy adapter failed reading 'projects' for project {project_id}: {exc}"
        ) from exc
    return rows[0] if rows else {"id": project_id}


def build_legacy_domain_snapshot(client: Any, project_id: str) -> dict[str, Any]:
    """Read all legacy sources needed by the eight semantic domains once."""
    return {
        "project": _read_project(client, project_id),
        "briefing_documents": _read_project_rows(client, "memory_briefing_documents", project_id),
        "briefing_requirements": _read_project_rows(client, "memory_briefing_requirements", project_id),
        "memory_documents": _read_project_rows(client, "memory_documents", project_id),
        "memory_items": _read_project_rows(client, "memory_items", project_id),
        "project_outcomes": _read_project_rows(client, "memory_project_outcomes", project_id),
        "item_outcomes": _read_project_rows(client, "memory_item_outcomes", project_id),
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        parts = []
        for key, item in value.items():
            if key in {"id", "project_id", "created_at", "updated_at"}:
                continue
            rendered = _text(item)
            if rendered:
                parts.append(f"{key}: {rendered}")
        return " | ".join(parts)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return "; ".join(filter(None, (_text(item) for item in value)))
    return str(value).strip()


def _join_fields(row: Mapping[str, Any], *fields: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for field in fields:
        rendered = _text(row.get(field))
        key = rendered.casefold()
        if rendered and key not in seen:
            seen.add(key)
            parts.append(rendered)
    return " | ".join(parts)


def _legacy_human_confirmed(_row: Mapping[str, Any]) -> bool:
    """Legacy labels are never treated as explicit Human Review.

    confidence_level/information_source/item_status are preserved as provenance,
    but V28.7.1D established that they cannot manufacture human confirmation.
    Explicit review lives outside the legacy tables and is governed by Domain.
    """
    return False


def _candidate(
    *,
    project_id: str,
    domain_key: str,
    source_table: str,
    row: Mapping[str, Any],
    role: str,
    semantic_text: str,
    human_confirmed: bool = False,
    synthetic_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(row)
    result.update(
        {
            "project_id": project_id,
            "_legacy_adapter_version": LEGACY_ADAPTER_VERSION,
            "_legacy_domain_key": domain_key,
            "_legacy_source_table": source_table,
            "_legacy_source_id": str(row.get("id") or synthetic_id or ""),
            "_legacy_role": role,
            "_legacy_text": semantic_text.strip(),
            "_legacy_human_confirmed": bool(human_confirmed),
        }
    )
    if extra:
        result.update(dict(extra))
    return result


def _memory_item_text(row: Mapping[str, Any]) -> str:
    return _join_fields(
        row,
        "title",
        "summary",
        "description",
        "item_type",
        "tags",
        "objectives",
        "audiences",
        "mechanics",
        "technologies",
        "journey_stage",
        "evidence",
    )


def _briefing_requirement_text(row: Mapping[str, Any]) -> str:
    return _join_fields(
        row,
        "title",
        "description",
        "source_quote",
        "source_reference",
        "requirement_type",
        "tags",
    )


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        text = str(row.get("_legacy_text") or "").strip()
        key = (
            str(row.get("_legacy_source_table") or ""),
            str(row.get("_legacy_role") or ""),
            " ".join(text.casefold().split()),
        )
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _context_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    project = snapshot.get("project") or {}
    project_text = _join_fields(project, "client_brand", "event_name", "project_name", "name")
    if project_text:
        rows.append(
            _candidate(
                project_id=project_id,
                domain_key="context",
                source_table="projects",
                row=project,
                role="project_identity_context",
                semantic_text=project_text,
            )
        )

    for req in snapshot.get("briefing_requirements") or []:
        req_type = str(req.get("requirement_type") or "").casefold()
        if req_type in {"audience", "context"}:
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="context",
                    source_table="memory_briefing_requirements",
                    row=req,
                    role=req_type or "context",
                    semantic_text=_briefing_requirement_text(req),
                )
            )

    # Legacy memory items often preserve audiences even when no standalone
    # legacy context row exists. Keep each audience as a provenance-preserving
    # synthetic observation rather than silently losing it.
    for item in snapshot.get("memory_items") or []:
        audiences = item.get("audiences") or []
        if isinstance(audiences, str):
            audiences = [audiences]
        for index, audience in enumerate(audiences):
            audience_text = _text(audience)
            if not audience_text:
                continue
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="context",
                    source_table="memory_items",
                    row=item,
                    role="audience_context",
                    semantic_text=audience_text,
                    synthetic_id=f"{item.get('id') or 'item'}:audience:{index}",
                )
            )
    return _dedupe(rows)


def _requirement_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    # Deliberately preserve *all* legacy briefing requirement rows. A3 must be
    # able to prove that rows corrected by the Evidence-first model are legacy
    # recall rather than deleting them before comparison.
    return _dedupe(
        [
            _candidate(
                project_id=project_id,
                domain_key="requirements",
                source_table="memory_briefing_requirements",
                row=req,
                role=str(req.get("requirement_type") or "legacy_requirement"),
                semantic_text=_briefing_requirement_text(req),
            )
            for req in (snapshot.get("briefing_requirements") or [])
        ]
    )


def _solution_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    accepted_sections = {"scenography", "activations", "gifts", "communication"}
    rows = []
    for item in snapshot.get("memory_items") or []:
        section = str(item.get("section_key") or "").casefold()
        if section not in accepted_sections:
            continue
        rows.append(
            _candidate(
                project_id=project_id,
                domain_key="solutions",
                source_table="memory_items",
                row=item,
                role=section,
                semantic_text=_memory_item_text(item),
                human_confirmed=False,
            )
        )
    return _dedupe(rows)


def _project_outcome_semantics(outcome: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Map legacy project outcome fields to the Domain event vocabulary.

    This mirrors the established V28.7.1D normalization semantics so A3 compares
    meaning, not incompatible field names (proposal_result vs proposal_status).
    """
    result: list[tuple[str, str]] = []

    process = str(outcome.get("process_type") or "").strip().casefold()
    if process and process not in {"not_informed", "unknown"}:
        result.append(("process_type", process))

    commercial = str(outcome.get("commercial_result") or "").strip().casefold()
    if commercial and commercial not in {"in_evaluation", "not_informed", "unknown"}:
        result.append(("commercial_result", commercial))

    proposal = str(outcome.get("proposal_result") or "").strip().casefold()
    proposal_map = {
        "fully_approved": "approved",
        "partially_approved": "approved_with_changes",
        "not_approved": "rejected",
        "no_feedback": "unknown",
    }
    if proposal in proposal_map:
        result.append(("proposal_status", proposal_map[proposal]))

    execution = str(outcome.get("execution_result") or "").strip().casefold()
    execution_map = {
        "executed": "executed",
        "partially_executed": "partial",
        "not_executed": "not_executed",
        "in_progress": "planned",
        "not_applicable": "not_applicable",
    }
    if execution in execution_map:
        result.append(("execution_status", execution_map[execution]))

    return result


def _item_outcome_semantics(row: Mapping[str, Any]) -> tuple[str, str] | None:
    raw = str(row.get("outcome_status") or row.get("status") or "").strip().casefold()
    proposal = {
        "approved": "approved",
        "approved_with_changes": "approved_with_changes",
        "not_approved": "rejected",
        "replaced": "replaced",
        "removed_budget": "cancelled",
        "removed_timeline": "cancelled",
    }
    if raw in proposal:
        return "proposal_status", proposal[raw]
    execution = {
        "executed": "executed",
        "not_executed": "not_executed",
    }
    if raw in execution:
        return "execution_status", execution[raw]
    return None


def _outcome_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for outcome in snapshot.get("project_outcomes") or []:
        for dimension, value in _project_outcome_semantics(outcome):
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="outcomes",
                    source_table="memory_project_outcomes",
                    row=outcome,
                    role="project_outcome",
                    semantic_text=f"{dimension}: {value}",
                    # Legacy confidence/source labels are provenance only; they
                    # are not explicit Human Review under V28.7.1D.
                    human_confirmed=_legacy_human_confirmed(outcome),
                    synthetic_id=f"{outcome.get('id') or project_id}:{dimension}",
                    extra={
                        "_legacy_outcome_dimension": dimension,
                        "_legacy_outcome_value": value,
                    },
                )
            )

    for item_outcome in snapshot.get("item_outcomes") or []:
        semantic = _item_outcome_semantics(item_outcome)
        if not semantic:
            continue
        dimension, value = semantic
        text = _join_fields(
            item_outcome,
            "outcome_status",
            "status",
            "decision_reason",
            "feedback_summary",
            "execution_notes",
            "reason",
            "notes",
        )
        rows.append(
            _candidate(
                project_id=project_id,
                domain_key="outcomes",
                source_table="memory_item_outcomes",
                row=item_outcome,
                role="item_outcome",
                semantic_text=f"{dimension}: {value}" + (f" | {text}" if text else ""),
                human_confirmed=False,
                extra={
                    "_legacy_outcome_dimension": dimension,
                    "_legacy_outcome_value": value,
                },
            )
        )
    return _dedupe(rows)


def _strategy_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for req in snapshot.get("briefing_requirements") or []:
        if str(req.get("requirement_type") or "").casefold() != "objective":
            continue
        rows.append(
            _candidate(
                project_id=project_id,
                domain_key="strategy",
                source_table="memory_briefing_requirements",
                row=req,
                role="objective",
                semantic_text=_briefing_requirement_text(req),
            )
        )
    for item in snapshot.get("memory_items") or []:
        if str(item.get("section_key") or "").casefold() != "strategy":
            continue
        rows.append(
            _candidate(
                project_id=project_id,
                domain_key="strategy",
                source_table="memory_items",
                row=item,
                role="strategy_item",
                semantic_text=_memory_item_text(item),
                human_confirmed=False,
            )
        )
    for doc in snapshot.get("memory_documents") or []:
        summary = str(doc.get("strategic_summary") or "").strip()
        if summary:
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="strategy",
                    source_table="memory_documents",
                    row=doc,
                    role="strategic_summary_container",
                    semantic_text=summary,
                )
            )
    return _dedupe(rows)


def _creative_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in snapshot.get("memory_documents") or []:
        concept = str(doc.get("creative_concept") or "").strip()
        if concept:
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="creative",
                    source_table="memory_documents",
                    row=doc,
                    role="creative_concept_container",
                    semantic_text=concept,
                )
            )

    creative_markers = (
        "conceito",
        "concept",
        "creative",
        "criativ",
        "plataforma",
        "campanha",
        "kv",
        "key visual",
        "identidade visual",
    )
    for item in snapshot.get("memory_items") or []:
        text = _memory_item_text(item)
        folded = text.casefold()
        if any(marker in folded for marker in creative_markers):
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="creative",
                    source_table="memory_items",
                    row=item,
                    role="creative_item",
                    semantic_text=text,
                    human_confirmed=False,
                )
            )
    return _dedupe(rows)


def _experience_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    markers = (
        "experien",
        "hands-on",
        "hands on",
        "lab",
        "jornada",
        "imers",
        "área de exposição",
        "area de exposicao",
    )
    for item in snapshot.get("memory_items") or []:
        section = str(item.get("section_key") or "").casefold()
        text = _memory_item_text(item)
        folded = text.casefold()
        if section in {"activations", "scenography"} and any(marker in folded for marker in markers):
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="experience",
                    source_table="memory_items",
                    row=item,
                    role="experience_candidate",
                    semantic_text=text,
                    human_confirmed=False,
                )
            )
    return _dedupe(rows)


def _journey_rows(snapshot: Mapping[str, Any], project_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in snapshot.get("memory_items") or []:
        section = str(item.get("section_key") or "").casefold()
        stage = str(item.get("journey_stage") or "").strip()
        if stage:
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="journey",
                    source_table="memory_items",
                    row=item,
                    role="journey_stage",
                    semantic_text=stage,
                    synthetic_id=f"{item.get('id') or 'item'}:journey_stage",
                )
            )
        if section == "journey_operation":
            rows.append(
                _candidate(
                    project_id=project_id,
                    domain_key="journey",
                    source_table="memory_items",
                    row=item,
                    role="journey_operation_item",
                    semantic_text=_memory_item_text(item),
                    human_confirmed=False,
                )
            )
    return _dedupe(rows)


_ADAPTERS = {
    "context": _context_rows,
    "requirements": _requirement_rows,
    "solutions": _solution_rows,
    "outcomes": _outcome_rows,
    "strategy": _strategy_rows,
    "creative": _creative_rows,
    "experience": _experience_rows,
    "journey": _journey_rows,
}


def legacy_rows_for_domain(
    snapshot: Mapping[str, Any],
    project_id: str,
    domain_key: str,
) -> list[dict[str, Any]]:
    if domain_key not in SUPPORTED_DOMAIN_KEYS:
        raise ValueError(f"Unsupported legacy semantic domain: {domain_key}")
    return _ADAPTERS[domain_key](snapshot, project_id)
