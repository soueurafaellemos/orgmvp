from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from supabase import Client
else:
    Client = Any

from project_identity import (
    AUTO_LINK_THRESHOLD,
    REVIEW_THRESHOLD,
    MatchResult,
    ProjectSignals,
    rank_project_matches,
    signals_from_mapping,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_non_blank(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if value in ([], {}, ()):
            continue
        return value
    return None


def _json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _raw_project_value(
    row: Mapping[str, Any],
    *keys: str,
) -> Any:
    raw_data = _json_mapping(row.get("raw_data"))
    for key in keys:
        value = raw_data.get(key)
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _project_row_for_matching(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """Adapta a estrutura real de ``projects`` ao motor de identidade.

    A tabela atual usa:

    - event_date
    - location_city / location_state
    - audience_quantity
    - budget_total_brl

    Campos complementares ainda podem existir dentro de ``raw_data``.
    """
    item = dict(row)
    item["project_id"] = item.get("id")

    item["event_start"] = _first_non_blank(
        item.get("event_date"),
        _raw_project_value(
            item,
            "event_start",
            "event_date_start",
            "start_date",
        ),
    )
    item["event_end"] = _first_non_blank(
        _raw_project_value(
            item,
            "event_end",
            "event_date_end",
            "end_date",
            "check_out",
            "checkout",
        ),
        item.get("event_date"),
    )

    item["city"] = _first_non_blank(
        item.get("location_city"),
        _raw_project_value(item, "city", "location_city"),
    )
    item["state"] = _first_non_blank(
        item.get("location_state"),
        _raw_project_value(item, "state", "location_state"),
    )
    item["audience_size"] = _first_non_blank(
        item.get("audience_quantity"),
        _raw_project_value(
            item,
            "audience_size",
            "audience_quantity",
            "participants",
            "pax",
        ),
    )
    item["budget_amount"] = _first_non_blank(
        item.get("budget_total_brl"),
        _raw_project_value(
            item,
            "budget_amount",
            "budget_total_brl",
            "budget",
            "estimated_budget",
        ),
    )
    item["venue_name"] = _first_non_blank(
        _raw_project_value(
            item,
            "venue_name",
            "venue",
            "location_name",
            "local",
            "hotel",
        ),
    )
    item["edition"] = _first_non_blank(
        item.get("edition"),
        _raw_project_value(item, "edition", "event_edition"),
    )
    item["reference_year"] = _first_non_blank(
        item.get("reference_year"),
        _raw_project_value(
            item,
            "reference_year",
            "event_year",
            "document_year",
        ),
    )
    item["keywords"] = _first_non_blank(
        item.get("keywords"),
        _raw_project_value(item, "keywords", "tags"),
        [],
    )
    return item


def fetch_project_signature_rows(
    client: Client,
    *,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    response = (
        client.table("project_signatures")
        .select("*")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(row) for row in (response.data or [])]


def fetch_projects_for_matching(
    client: Client,
    *,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    # Durante uma implantação incompleta, a tabela de assinaturas pode ainda
    # não existir. Nesse caso, o motor continua funcional usando projects.
    try:
        signature_rows = fetch_project_signature_rows(
            client,
            limit=limit,
        )
    except Exception:
        signature_rows = []

    if signature_rows:
        return signature_rows

    response = (
        client.table("projects")
        .select("*")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [
        _project_row_for_matching(row)
        for row in (response.data or [])
    ]


def project_signature_payload(
    *,
    project_id: str,
    signals: ProjectSignals,
    source_confidence: float = 1.0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "canonical_name": (
            signals.project_name
            or signals.event_name
            or "Projeto sem nome"
        ),
        "client_brand": signals.client_brand,
        "event_name": signals.event_name,
        "edition": signals.edition,
        "reference_year": signals.reference_year,
        "event_start": (
            signals.event_start.isoformat()
            if signals.event_start
            else None
        ),
        "event_end": (
            signals.event_end.isoformat()
            if signals.event_end
            else None
        ),
        "venue_name": signals.venue_name,
        "city": signals.city,
        "state": signals.state,
        "audience_size": signals.audience_size,
        "budget_amount": (
            str(signals.budget_amount)
            if signals.budget_amount is not None
            else None
        ),
        "keywords": list(signals.keywords),
        "signals": signals.to_payload(),
        "signature_version": 1,
        "source_confidence": round(
            max(0.0, min(1.0, source_confidence)),
            5,
        ),
        "metadata": dict(metadata or {}),
    }


def upsert_project_signature(
    client: Client,
    *,
    project_id: str,
    signals: ProjectSignals,
    source_confidence: float = 1.0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = project_signature_payload(
        project_id=project_id,
        signals=signals,
        source_confidence=source_confidence,
        metadata=metadata,
    )
    response = (
        client.table("project_signatures")
        .upsert(payload, on_conflict="project_id")
        .execute()
    )
    return dict(response.data[0]) if response.data else payload


def match_document_to_projects(
    client: Client,
    *,
    signals: ProjectSignals,
    limit: int = 5,
) -> list[MatchResult]:
    projects = fetch_projects_for_matching(client)
    return rank_project_matches(
        signals,
        projects,
        limit=limit,
    )


def register_ingestion_event(
    client: Client,
    *,
    event_type: str,
    project_id: str | None = None,
    import_id: str | None = None,
    source_file_id: str | None = None,
    project_file_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "event_type": event_type,
        "project_id": project_id,
        "import_id": import_id,
        "source_file_id": source_file_id,
        "project_file_id": project_file_id,
        "payload": dict(payload or {}),
    }
    response = (
        client.table("project_ingestion_events")
        .insert(row)
        .execute()
    )
    return dict(response.data[0]) if response.data else row


def create_match_candidate(
    client: Client,
    *,
    match: MatchResult,
    file_name: str,
    document_role: str,
    import_id: str | None = None,
    source_file_id: str | None = None,
    content_sha256: str | None = None,
    signals: ProjectSignals | None = None,
) -> dict[str, Any]:
    if not match.project_id:
        raise ValueError(
            "O candidato de associação precisa de project_id."
        )

    row = {
        "project_id": match.project_id,
        "import_id": import_id,
        "source_file_id": source_file_id,
        "content_sha256": content_sha256,
        "file_name": file_name,
        "document_role": document_role,
        "match_confidence": match.score,
        "match_method": "weighted_project_signature_v1",
        "match_reasons": match.reasons,
        "match_conflicts": match.conflicts,
        "document_signals": (
            signals.to_payload()
            if signals
            else {}
        ),
        "status": "pending",
        "last_seen_at": utc_now(),
    }
    response = (
        client.table("project_match_candidates")
        .upsert(
            row,
            on_conflict=(
                "project_id,source_file_id,content_sha256"
            ),
        )
        .execute()
    )
    return dict(response.data[0]) if response.data else row


def link_document_to_project(
    client: Client,
    *,
    project_id: str,
    file_name: str,
    document_role: str,
    match: MatchResult,
    import_id: str | None = None,
    source_file_id: str | None = None,
    project_file_id: str | None = None,
    content_sha256: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if match.decision != "auto_link":
        raise ValueError(
            "Somente associações automáticas aprovadas podem "
            "ser vinculadas sem confirmação humana."
        )

    row = {
        "project_id": project_id,
        "project_file_id": project_file_id,
        "import_id": import_id,
        "source_file_id": source_file_id,
        "content_sha256": content_sha256,
        "file_name": file_name,
        "document_role": document_role,
        "match_confidence": match.score,
        "match_decision": "auto_link",
        "match_method": "weighted_project_signature_v1",
        "match_reasons": match.reasons,
        "metadata": dict(metadata or {}),
        "is_current": True,
    }
    response = (
        client.table("project_document_links")
        .upsert(
            row,
            on_conflict=(
                "project_id,document_role,content_sha256"
            ),
        )
        .execute()
    )
    linked = dict(response.data[0]) if response.data else row

    register_ingestion_event(
        client,
        event_type="document_auto_linked",
        project_id=project_id,
        import_id=import_id,
        source_file_id=source_file_id,
        project_file_id=project_file_id,
        payload={
            "file_name": file_name,
            "document_role": document_role,
            "match": match.to_payload(),
        },
    )
    return linked


def enqueue_project_updates(
    client: Client,
    *,
    project_id: str,
    document_role: str,
    import_id: str | None = None,
    source_file_id: str | None = None,
    project_file_id: str | None = None,
) -> list[dict[str, Any]]:
    targets_by_role = {
        "briefing_original": [
            "overview",
            "briefing",
            "diagnostic",
        ],
        "final_presentation": [
            "strategy",
            "scenography_activations",
            "gifts_presskits",
            "suppliers_references",
            "diagnostic",
        ],
        "cost_sheet": [
            "budget_adherence",
            "cost_correlations",
            "diagnostic",
        ],
        "budget_study": [
            "overview",
            "budget_adherence",
            "diagnostic",
        ],
        "feedback": [
            "feedback_approvals",
            "diagnostic",
        ],
        "approval": [
            "feedback_approvals",
            "diagnostic",
        ],
        "closure_report": [
            "results_learnings",
            "diagnostic",
        ],
        "post_execution_report": [
            "results_learnings",
            "execution_evidence",
            "diagnostic",
        ],
    }
    targets = targets_by_role.get(
        document_role,
        ["documents"],
    )

    rows = []
    for target_area in targets:
        row = {
            "project_id": project_id,
            "import_id": import_id,
            "source_file_id": source_file_id,
            "project_file_id": project_file_id,
            "document_role": document_role,
            "target_area": target_area,
            "status": "pending",
            "priority": 100,
            "payload": {},
        }
        response = (
            client.table("project_update_jobs")
            .upsert(
                row,
                on_conflict=(
                    "project_id,source_file_id,"
                    "document_role,target_area,status"
                ),
            )
            .execute()
        )
        rows.append(
            dict(response.data[0])
            if response.data
            else row
        )
    return rows


def decide_project_association(
    client: Client,
    *,
    payload: Mapping[str, Any],
    file_name: str,
    document_role: str,
    source_file_id: str | None = None,
    import_id: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    signals = signals_from_mapping(
        payload,
        source_file=file_name,
        document_role=document_role,
    )
    matches = match_document_to_projects(
        client,
        signals=signals,
    )
    best = matches[0] if matches else None
    decision = best.decision if best else "unmatched"

    result = {
        "decision": decision,
        "signals": signals.to_payload(),
        "matches": [
            match.to_payload()
            for match in matches
        ],
        "automatic_threshold": AUTO_LINK_THRESHOLD,
        "review_threshold": REVIEW_THRESHOLD,
    }

    register_ingestion_event(
        client,
        event_type="project_match_evaluated",
        project_id=best.project_id if best else None,
        import_id=import_id,
        source_file_id=source_file_id,
        payload={
            "file_name": file_name,
            "document_role": document_role,
            **result,
        },
    )

    if best and best.decision == "review":
        create_match_candidate(
            client,
            match=best,
            file_name=file_name,
            document_role=document_role,
            import_id=import_id,
            source_file_id=source_file_id,
            content_sha256=content_sha256,
            signals=signals,
        )

    return result
