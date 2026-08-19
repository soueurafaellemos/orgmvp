from __future__ import annotations

"""NAVE V28.7.3A — Domain Read Path abstraction.

The reader deliberately separates read-mode from semantic readiness.
V28.7.3A installs the abstraction and registry only; it does not promote any
project/domain to ``domain_primary``.

Core invariants:
- an empty, ready Domain result is valid truth and never triggers fallback;
- a technical Domain read error never triggers silent legacy fallback;
- ``domain_primary`` is allowed only for ``ready`` / ``ready_with_findings``;
- shadow mode can compare Domain with a legacy loader while still serving legacy;
- Domain and Legacy rows are never concatenated into one silent mixed result.
"""

from dataclasses import dataclass, asdict
from typing import Any, Callable, Mapping, Sequence

READ_PATH_VERSION = "V28.7.3A2"
READ_SCHEMA_VERSION = "28.7.3a"
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
READ_MODES = ("legacy_primary", "shadow_compare", "domain_primary")
READY_STATES = ("ready", "ready_with_findings")


class DomainReadError(RuntimeError):
    """Base error for fail-closed read-path failures."""


class DomainReadBlocked(DomainReadError):
    """Raised when a domain is asked to serve primary before readiness."""


class LegacyLoaderRequired(DomainReadError):
    """Raised when a legacy-serving mode has no explicit legacy adapter."""


@dataclass(frozen=True)
class DomainReadResult:
    project_id: str
    domain_key: str
    read_mode: str
    readiness_state: str
    served_source: str
    data: list[dict[str, Any]]
    domain_candidate: list[dict[str, Any]]
    legacy_candidate: list[dict[str, Any]] | None
    fallback_used: bool
    comparison_status: str | None
    governed_findings: list[dict[str, Any]]
    reader_version: str = READ_PATH_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_rows(
    client: Any,
    table: str,
    *,
    equals: Mapping[str, Any] | None = None,
    columns: str = "*",
) -> list[dict[str, Any]]:
    query = client.table(table).select(columns)
    for key, value in (equals or {}).items():
        query = query.eq(key, value)
    return _rows(query.execute())


def _active_rows(client: Any, table: str, project_id: str, lifecycle_field: str = "lifecycle_status") -> list[dict[str, Any]]:
    query = client.table(table).select("*").eq("project_id", project_id)
    query = query.eq(lifecycle_field, "active")
    return _rows(query.execute())


def probe_domain_read_schema(client: Any) -> dict[str, Any]:
    try:
        client.table("project_domain_read_state").select("project_id,domain_key,read_mode,readiness_state").limit(1).execute()
        client.table("project_domain_cutover_readiness").select("project_id,domain_key,read_mode,readiness_state").limit(1).execute()
        return {"available": True, "status": "ready", "schema_version": READ_SCHEMA_VERSION}
    except Exception as exc:  # pragma: no cover - runtime integration path
        text = str(exc)
        missing = "PGRST205" in text or "does not exist" in text.lower() or "schema cache" in text.lower()
        return {
            "available": False,
            "status": "schema_missing" if missing else "schema_check_error",
            "schema_version": READ_SCHEMA_VERSION,
            "error": text,
        }


def get_cutover_state(client: Any, project_id: str, domain_key: str) -> dict[str, Any]:
    if domain_key not in SUPPORTED_DOMAIN_KEYS:
        raise ValueError(f"Unsupported NAVE domain_key: {domain_key}")
    rows = _rows(
        client.table("project_domain_cutover_readiness")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_key", domain_key)
        .limit(1)
        .execute()
    )
    if not rows:
        # Fail safe for a project created before the registry or before trigger refresh.
        return {
            "project_id": project_id,
            "domain_key": domain_key,
            "read_mode": "legacy_primary",
            "readiness_state": "not_ready",
            "hard_blockers": ["READ_STATE_MISSING"],
            "governed_findings": [],
        }
    return rows[0]


def _read_domain_rows(client: Any, project_id: str, domain_key: str) -> list[dict[str, Any]]:
    if domain_key == "context":
        return _active_rows(client, "project_context_elements", project_id)

    if domain_key == "requirements":
        rows = _read_rows(client, "project_requirement_truth_status", equals={"project_id": project_id})
        return [row for row in rows if row.get("truth_state") in {"verified", "human_confirmed"}]

    if domain_key == "solutions":
        return _read_rows(client, "project_solution_instances", equals={"project_id": project_id})

    if domain_key == "outcomes":
        return _read_rows(client, "entity_current_outcomes", equals={"project_id": project_id})

    if domain_key == "strategy":
        return _active_rows(client, "project_strategy_elements", project_id)

    if domain_key == "creative":
        platforms = _active_rows(client, "project_creative_platforms", project_id)
        elements = _active_rows(client, "project_creative_elements", project_id)
        return [dict(row, _domain_object_type="creative_platform") for row in platforms] + [
            dict(row, _domain_object_type="creative_element") for row in elements
        ]

    if domain_key == "experience":
        return _active_rows(client, "project_experience_architectures", project_id)

    if domain_key == "journey":
        return _active_rows(client, "project_journey_moments", project_id)

    raise ValueError(f"Unsupported NAVE domain_key: {domain_key}")


def _comparison_status(domain_rows: Sequence[Mapping[str, Any]], legacy_rows: Sequence[Mapping[str, Any]]) -> str:
    # 7.3A intentionally avoids pretending row-count parity is semantic parity.
    # This status is only a coarse observability signal until domain-specific
    # comparators are wired in 7.3B.
    if len(domain_rows) == len(legacy_rows):
        return "row_count_equal_not_semantic_proof"
    if not domain_rows and legacy_rows:
        return "domain_empty_legacy_nonempty_requires_semantic_review"
    if domain_rows and not legacy_rows:
        return "domain_only"
    if not domain_rows and not legacy_rows:
        return "both_empty"
    return "row_count_diff_not_semantic_failure"


def _audit_read(
    client: Any,
    result: DomainReadResult,
    *,
    request_scope: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    try:
        audit_metadata = {"governed_findings_count": len(result.governed_findings)}
        audit_metadata.update(dict(metadata or {}))
        client.table("project_domain_read_audit").insert({
            "project_id": result.project_id,
            "domain_key": result.domain_key,
            "read_mode": result.read_mode,
            "readiness_state": result.readiness_state,
            "served_source": result.served_source,
            "domain_row_count": len(result.domain_candidate),
            "legacy_row_count": None if result.legacy_candidate is None else len(result.legacy_candidate),
            "fallback_used": result.fallback_used,
            "comparison_status": result.comparison_status,
            "reader_version": result.reader_version,
            "request_scope": request_scope,
            "metadata": audit_metadata,
        }).execute()
    except Exception:
        # Observability must never alter read semantics. A missing/broken audit
        # sink is intentionally non-fatal; the Domain read itself stays fail-closed.
        return


def read_domain(
    client: Any,
    project_id: str,
    domain_key: str,
    *,
    legacy_loader: Callable[[], Sequence[Mapping[str, Any]]] | None = None,
    audit: bool = False,
    audit_scope: str | None = None,
    audit_metadata: Mapping[str, Any] | None = None,
) -> DomainReadResult:
    """Read one project/domain according to the cutover registry.

    ``legacy_loader`` is explicit during migration so the central reader owns the
    selection policy without guessing legacy table semantics. 7.3B will replace
    page-level legacy reads with dedicated adapters.
    """
    state = get_cutover_state(client, project_id, domain_key)
    read_mode = str(state.get("read_mode") or "legacy_primary")
    readiness_state = str(state.get("readiness_state") or "not_ready")
    findings = [dict(x) for x in (state.get("governed_findings") or []) if isinstance(x, Mapping)]

    if read_mode not in READ_MODES:
        raise DomainReadBlocked(f"Invalid read_mode {read_mode!r} for {project_id}/{domain_key}")

    # Domain is always evaluated in shadow/domain modes. Technical errors propagate;
    # they are never converted into silent legacy fallback.
    domain_rows: list[dict[str, Any]] = []
    if read_mode in {"shadow_compare", "domain_primary"}:
        domain_rows = _read_domain_rows(client, project_id, domain_key)

    if read_mode == "domain_primary":
        if readiness_state not in READY_STATES:
            raise DomainReadBlocked(
                f"Domain primary blocked for {project_id}/{domain_key}: readiness={readiness_state}"
            )
        result = DomainReadResult(
            project_id=project_id,
            domain_key=domain_key,
            read_mode=read_mode,
            readiness_state=readiness_state,
            served_source="domain",
            data=domain_rows,
            domain_candidate=domain_rows,
            legacy_candidate=None,
            fallback_used=False,
            comparison_status=None,
            governed_findings=findings,
        )
        if audit:
            _audit_read(
                client,
                result,
                request_scope=audit_scope,
                metadata=audit_metadata,
            )
        return result

    if legacy_loader is None:
        raise LegacyLoaderRequired(
            f"{read_mode} requires an explicit legacy loader for {project_id}/{domain_key}"
        )

    legacy_rows = [dict(row) for row in legacy_loader() if isinstance(row, Mapping)]

    if read_mode == "legacy_primary":
        result = DomainReadResult(
            project_id=project_id,
            domain_key=domain_key,
            read_mode=read_mode,
            readiness_state=readiness_state,
            served_source="legacy",
            data=legacy_rows,
            domain_candidate=[],
            legacy_candidate=legacy_rows,
            fallback_used=False,
            comparison_status=None,
            governed_findings=findings,
        )
    else:
        result = DomainReadResult(
            project_id=project_id,
            domain_key=domain_key,
            read_mode=read_mode,
            readiness_state=readiness_state,
            served_source="legacy",
            data=legacy_rows,
            domain_candidate=domain_rows,
            legacy_candidate=legacy_rows,
            fallback_used=False,
            comparison_status=_comparison_status(domain_rows, legacy_rows),
            governed_findings=findings,
        )

    if audit:
        _audit_read(
            client,
            result,
            request_scope=audit_scope,
            metadata=audit_metadata,
        )
    return result
