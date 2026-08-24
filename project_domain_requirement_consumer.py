from __future__ import annotations

"""NAVE V28.7.3B1.1 — requirements consumer adapter and governed router."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping, Sequence

from project_domain_consumer_canary import (
    CANARY_VERSION,
    ConsumerCanaryBlocked,
    ConsumerCanaryRead,
    best_effort_control_audit,
    elapsed_ms,
    fetch_active_canary,
    fetch_latest_a31_audit,
    stable_fingerprint,
    validate_active_preconditions,
    write_canary_audit,
)

DOMAIN_KEY = "requirements"
CONSUMER_KEY = "workspace.briefing.requirements_readonly"
CONSUMER_ADAPTER_VERSION = "V28.7.3B1.2.1"

VALID_REQUIREMENT_TYPES = {
    "objective",
    "deliverable",
    "mandatory",
    "restriction",
    "audience",
    "logistics",
    "budget",
    "kpi",
    "operation",
    "communication",
    "desirable",
    "context",
    "other",
    "deadline",
}
VALID_PRIORITIES = {"critical", "high", "medium", "low", "not_informed"}
DOMAIN_TRUTH_STATES = {"verified", "human_confirmed"}


@dataclass(frozen=True)
class RequirementConsumerRow:
    stable_key: str
    title: str
    description: str | None
    requirement_type: str
    mandatory: bool | None
    priority: str | None
    source_excerpt: str | None
    source_reference: str | None
    evidence_ref: str | None
    truth_status: str | None
    source_kind: str
    legacy_id: str | None = None
    adherence_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable_key": self.stable_key,
            "title": self.title,
            "description": self.description,
            "requirement_type": self.requirement_type,
            "mandatory": self.mandatory,
            "priority": self.priority,
            "source_excerpt": self.source_excerpt,
            "source_reference": self.source_reference,
            "evidence_ref": self.evidence_ref,
            "truth_status": self.truth_status,
            "source_kind": self.source_kind,
            "legacy_id": self.legacy_id,
            "adherence_status": self.adherence_status,
        }


def _text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _attribute_text(row: Mapping[str, Any], *keys: str) -> str | None:
    attributes = row.get("attributes")
    if not isinstance(attributes, Mapping):
        return None
    return _text(attributes, *keys)


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "t", "1", "yes", "sim"}:
        return True
    if text in {"false", "f", "0", "no", "nao", "não"}:
        return False
    return None


def adapt_legacy_requirements(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    adapted: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        legacy_id = _text(row, "id")
        title = _text(row, "title", "description") or ""
        requirement_type = (_text(row, "requirement_type") or "").casefold()
        priority = (_text(row, "priority") or "not_informed").casefold()
        item = RequirementConsumerRow(
            stable_key=legacy_id or f"legacy:{index}:{title}",
            title=title,
            description=_text(row, "description"),
            requirement_type=requirement_type,
            mandatory=_bool_or_none(row.get("mandatory")),
            priority=priority,
            source_excerpt=_text(row, "source_quote"),
            source_reference=_text(row, "source_reference"),
            evidence_ref=None,
            truth_status=None,
            source_kind="legacy",
            legacy_id=legacy_id,
            adherence_status=_text(row, "adherence_status") or "not_assessed",
        )
        adapted.append(item.to_dict())
    return adapted


def adapt_domain_requirements(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    adapted: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        raw_id = _text(row, "id", "requirement_id", "resolved_domain_id")
        title = _text(
            row,
            "requirement_name",
            "canonical_name",
            "name",
            "title",
            "observed_name",
            "requirement_text",
            "statement",
            "description",
            "observed_text",
        ) or ""
        description = _text(
            row,
            "description",
            "requirement_text",
            "statement",
            "observed_text",
        )
        requirement_type = (_text(row, "requirement_type", "semantic_role") or "").casefold()
        priority_raw = _text(row, "priority")
        priority = priority_raw.casefold() if priority_raw else None
        evidence_ref = _text(
            row,
            "evidence_unit_id",
            "source_evidence_id",
            "source_claim_id",
            "source_asset_id",
            "legacy_explanation_evidence_id",
        )
        truth_status = (_text(row, "truth_state", "verification_state") or "").casefold() or None
        item = RequirementConsumerRow(
            stable_key=raw_id or f"domain:{index}:{title}",
            title=title,
            description=description,
            requirement_type=requirement_type,
            mandatory=_bool_or_none(row.get("mandatory", row.get("is_mandatory"))),
            priority=priority,
            source_excerpt=(
                _text(
                    row,
                    "observed_text",
                    "source_quote",
                    "requirement_text",
                    "statement",
                )
                or _attribute_text(row, "source_quote")
            ),
            source_reference=(
                _text(row, "source_reference", "locator_text", "source_name")
                or _attribute_text(row, "source_reference")
            ),
            evidence_ref=(
                evidence_ref
                or _attribute_text(row, "source_observation_id")
            ),
            truth_status=truth_status,
            source_kind="domain",
            legacy_id=None,
            adherence_status=None,
        )
        adapted.append(item.to_dict())
    return adapted


def validate_requirement_contract(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_source: str,
) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows):
        stable_key = str(row.get("stable_key") or "").strip()
        if not stable_key:
            raise ConsumerCanaryBlocked("CONTRACT_STABLE_KEY_EMPTY", f"row={index}")
        if stable_key in seen:
            raise ConsumerCanaryBlocked("CONTRACT_STABLE_KEY_DUPLICATE", stable_key)
        seen.add(stable_key)

        title = str(row.get("title") or "").strip()
        if not title:
            raise ConsumerCanaryBlocked("CONTRACT_TITLE_EMPTY", f"row={index}")

        requirement_type = str(row.get("requirement_type") or "").casefold()
        if requirement_type not in VALID_REQUIREMENT_TYPES:
            raise ConsumerCanaryBlocked(
                "CONTRACT_REQUIREMENT_TYPE_INVALID",
                f"row={index}; type={requirement_type or 'missing'}",
            )

        source_kind = str(row.get("source_kind") or "")
        if source_kind != expected_source:
            raise ConsumerCanaryBlocked(
                "CONTRACT_SOURCE_KIND_INVALID",
                f"row={index}; expected={expected_source}; actual={source_kind}",
            )

        priority = row.get("priority")
        if priority not in (None, "") and str(priority).casefold() not in VALID_PRIORITIES:
            raise ConsumerCanaryBlocked(
                "CONTRACT_PRIORITY_INVALID",
                f"row={index}; priority={priority}",
            )

        mandatory = row.get("mandatory")
        if mandatory is not None and not isinstance(mandatory, bool):
            raise ConsumerCanaryBlocked("CONTRACT_MANDATORY_INVALID", f"row={index}")

        if expected_source == "domain":
            truth_status = str(row.get("truth_status") or "").casefold()
            if truth_status not in DOMAIN_TRUTH_STATES:
                raise ConsumerCanaryBlocked(
                    "CONTRACT_DOMAIN_TRUTH_INVALID",
                    f"row={index}; truth_status={truth_status or 'missing'}",
                )


def _legacy_result(
    *,
    project_id: str,
    rows: list[dict[str, Any]],
    served_source: str,
    fallback_used: bool,
    failure_code: str | None,
    failure_detail: str | None,
    canary_id: str | None,
    domain_row_count: int | None,
    domain_fingerprint: str | None,
) -> ConsumerCanaryRead:
    return ConsumerCanaryRead(
        project_id=project_id,
        domain_key=DOMAIN_KEY,
        consumer_key=CONSUMER_KEY,
        served_source=served_source,
        rows=rows,
        fallback_used=fallback_used,
        failure_code=failure_code,
        failure_detail=failure_detail,
        canary_id=canary_id,
        domain_row_count=domain_row_count,
        legacy_row_count=len(rows),
        contract_ok=True,
        domain_fingerprint=domain_fingerprint,
        legacy_fingerprint=stable_fingerprint(rows),
        consumer_adapter_version=CONSUMER_ADAPTER_VERSION,
    )


def read_requirement_consumer(
    client: Any,
    *,
    project_id: str,
    legacy_rows: Sequence[Mapping[str, Any]],
) -> ConsumerCanaryRead:
    """Serve requirements to the B1 consumer with explicit Legacy fallback.

    The global registry remains ``shadow_compare``. ``read_domain`` is reused only
    to materialize the governed Domain candidate; the B1 router decides whether
    this one consumer may receive it.
    """
    started = perf_counter()
    legacy_view = adapt_legacy_requirements(legacy_rows)
    legacy_fp = stable_fingerprint(legacy_view)
    try:
        validate_requirement_contract(legacy_view, expected_source="legacy")
        legacy_contract_ok = True
    except ConsumerCanaryBlocked:
        # Existing Legacy UI remains the fallback of record even when a stricter
        # B1 neutral contract would reject a row; the issue is captured in audit.
        legacy_contract_ok = False

    try:
        config = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=CONSUMER_KEY,
        )
    except Exception as exc:
        best_effort_control_audit(
            client,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=CONSUMER_KEY,
            rows=legacy_view,
            consumer_adapter_version=CONSUMER_ADAPTER_VERSION,
            contract_ok=legacy_contract_ok,
            legacy_fingerprint=legacy_fp,
            total_latency_ms=elapsed_ms(started),
            failure_code="CANARY_CONFIG_UNAVAILABLE",
            failure_detail=str(exc),
        )
        return _legacy_result(
            project_id=project_id,
            rows=legacy_view,
            served_source="legacy_control",
            fallback_used=False,
            failure_code="CANARY_CONFIG_UNAVAILABLE",
            failure_detail=str(exc),
            canary_id=None,
            domain_row_count=None,
            domain_fingerprint=None,
        )

    if not config:
        best_effort_control_audit(
            client,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=CONSUMER_KEY,
            rows=legacy_view,
            consumer_adapter_version=CONSUMER_ADAPTER_VERSION,
            contract_ok=legacy_contract_ok,
            legacy_fingerprint=legacy_fp,
            total_latency_ms=elapsed_ms(started),
        )
        return _legacy_result(
            project_id=project_id,
            rows=legacy_view,
            served_source="legacy_control",
            fallback_used=False,
            failure_code=None,
            failure_detail=None,
            canary_id=None,
            domain_row_count=None,
            domain_fingerprint=None,
        )

    canary_id = str(config.get("id") or "") or None
    expected_rows = config.get("expected_domain_row_count")
    domain_view: list[dict[str, Any]] = []
    domain_fp: str | None = None
    domain_latency: int | None = None
    reader_version: str | None = None

    try:
        from project_domain_reader import get_cutover_state, read_domain

        readiness = get_cutover_state(client, project_id, DOMAIN_KEY)
        a31 = fetch_latest_a31_audit(client, project_id=project_id, domain_key=DOMAIN_KEY)
        validate_active_preconditions(config=config, readiness=readiness, a31_audit=a31)

        domain_started = perf_counter()
        shadow = read_domain(
            client,
            project_id,
            DOMAIN_KEY,
            legacy_loader=lambda: list(legacy_rows),
            audit=False,
        )
        domain_latency = elapsed_ms(domain_started)
        reader_version = str(getattr(shadow, "reader_version", None) or config.get("approved_reader_version") or "") or None

        if str(shadow.read_mode) != "shadow_compare":
            raise ConsumerCanaryBlocked("RUNTIME_MODE_DRIFT", f"read_mode={shadow.read_mode}")
        if str(shadow.served_source) != "legacy":
            raise ConsumerCanaryBlocked(
                "RUNTIME_SHADOW_SOURCE_DRIFT",
                f"shadow served_source={shadow.served_source}",
            )

        domain_view = adapt_domain_requirements(shadow.domain_candidate)
        validate_requirement_contract(domain_view, expected_source="domain")

        try:
            expected_int = int(expected_rows)
        except (TypeError, ValueError):
            raise ConsumerCanaryBlocked("EXPECTED_ROW_COUNT_INVALID", str(expected_rows))
        if len(domain_view) != expected_int:
            raise ConsumerCanaryBlocked(
                "DOMAIN_ROW_COUNT_DRIFT",
                f"expected={expected_int}; actual={len(domain_view)}",
            )

        domain_fp = stable_fingerprint(domain_view)

        # Domain is returned only after the canary audit has been persisted.
        write_canary_audit(
            client,
            canary_id=canary_id,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=CONSUMER_KEY,
            served_source="domain",
            fallback_used=False,
            failure_code=None,
            failure_detail=None,
            domain_row_count=len(domain_view),
            legacy_row_count=len(legacy_view),
            expected_domain_row_count=expected_int,
            contract_ok=True,
            domain_fingerprint=domain_fp,
            legacy_fingerprint=legacy_fp,
            domain_latency_ms=domain_latency,
            legacy_latency_ms=None,
            total_latency_ms=elapsed_ms(started),
            reader_version=reader_version,
            consumer_adapter_version=CONSUMER_ADAPTER_VERSION,
            metadata={
                "canary_version": CANARY_VERSION,
                "registry_read_mode": readiness.get("read_mode"),
                "readiness_state": readiness.get("readiness_state"),
                "legacy_source": "workspace_snapshot",
            },
            strict=True,
        )

        return ConsumerCanaryRead(
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=CONSUMER_KEY,
            served_source="domain",
            rows=domain_view,
            fallback_used=False,
            canary_id=canary_id,
            domain_row_count=len(domain_view),
            legacy_row_count=len(legacy_view),
            contract_ok=True,
            domain_fingerprint=domain_fp,
            legacy_fingerprint=legacy_fp,
            consumer_adapter_version=CONSUMER_ADAPTER_VERSION,
        )

    except ConsumerCanaryBlocked as exc:
        failure_code = exc.code
        failure_detail = exc.detail
    except Exception as exc:  # runtime integration fail-closed boundary
        failure_code = "DOMAIN_RUNTIME_ERROR"
        failure_detail = str(exc)

    # A failed Domain attempt is explicit Legacy fallback; it is never represented
    # as a healthy Domain response.
    write_canary_audit(
        client,
        canary_id=canary_id,
        project_id=project_id,
        domain_key=DOMAIN_KEY,
        consumer_key=CONSUMER_KEY,
        served_source="legacy_fallback",
        fallback_used=True,
        failure_code=failure_code,
        failure_detail=failure_detail,
        domain_row_count=len(domain_view) if domain_view else None,
        legacy_row_count=len(legacy_view),
        expected_domain_row_count=int(expected_rows) if str(expected_rows).isdigit() else None,
        contract_ok=legacy_contract_ok,
        domain_fingerprint=domain_fp,
        legacy_fingerprint=legacy_fp,
        domain_latency_ms=domain_latency,
        legacy_latency_ms=None,
        total_latency_ms=elapsed_ms(started),
        reader_version=reader_version,
        consumer_adapter_version=CONSUMER_ADAPTER_VERSION,
        metadata={"canary_version": CANARY_VERSION, "legacy_source": "workspace_snapshot"},
        strict=False,
    )
    return _legacy_result(
        project_id=project_id,
        rows=legacy_view,
        served_source="legacy_fallback",
        fallback_used=True,
        failure_code=failure_code,
        failure_detail=failure_detail,
        canary_id=canary_id,
        domain_row_count=len(domain_view) if domain_view else None,
        domain_fingerprint=domain_fp,
    )
