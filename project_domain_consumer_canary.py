from __future__ import annotations

"""NAVE V28.7.3B1 — consumer-scoped Domain Primary canary primitives.

This module owns only canary configuration, runtime guards and observability.
It does not alter Truth, readiness or the global domain read_mode.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from time import perf_counter
from typing import Any, Mapping, Sequence

CANARY_VERSION = "V28.7.3B1"
CANARY_TABLE = "project_domain_consumer_canary"
CANARY_AUDIT_TABLE = "project_domain_consumer_canary_audit"
A31_SCOPE = "v28.7.3a3_1_semantic_scope_compare"
READY_STATES = {"ready", "ready_with_findings"}


class ConsumerCanaryError(RuntimeError):
    """Base exception for governed consumer-canary failures."""


class ConsumerCanaryBlocked(ConsumerCanaryError):
    """A precondition/contract failed; the consumer must fall back to Legacy."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = str(code)
        self.detail = str(detail)


@dataclass(frozen=True)
class ConsumerCanaryRead:
    project_id: str
    domain_key: str
    consumer_key: str
    served_source: str
    rows: list[dict[str, Any]]
    fallback_used: bool
    failure_code: str | None = None
    failure_detail: str | None = None
    canary_id: str | None = None
    domain_row_count: int | None = None
    legacy_row_count: int | None = None
    contract_ok: bool = True
    domain_fingerprint: str | None = None
    legacy_fingerprint: str | None = None
    consumer_adapter_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def stable_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        _json_safe(list(rows)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def elapsed_ms(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))


def fetch_active_canary(
    client: Any,
    *,
    project_id: str,
    domain_key: str,
    consumer_key: str,
) -> dict[str, Any] | None:
    response = (
        client.table(CANARY_TABLE)
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_key", domain_key)
        .eq("consumer_key", consumer_key)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    rows = _rows(response)
    return rows[0] if rows else None


def fetch_latest_a31_audit(
    client: Any,
    *,
    project_id: str,
    domain_key: str,
) -> dict[str, Any] | None:
    response = (
        client.table("project_domain_read_audit")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_key", domain_key)
        .eq("request_scope", A31_SCOPE)
        .order("read_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = _rows(response)
    return rows[0] if rows else None


def validate_active_preconditions(
    *,
    config: Mapping[str, Any],
    readiness: Mapping[str, Any],
    a31_audit: Mapping[str, Any] | None,
) -> None:
    if str(config.get("status") or "") != "active":
        raise ConsumerCanaryBlocked("CANARY_NOT_ACTIVE", "Consumer canary is not active.")

    if str(config.get("fallback_policy") or "") != "legacy_fail_closed":
        raise ConsumerCanaryBlocked(
            "INVALID_FALLBACK_POLICY",
            "B1 requires fallback_policy=legacy_fail_closed.",
        )

    if str(readiness.get("read_mode") or "") != "shadow_compare":
        raise ConsumerCanaryBlocked(
            "REGISTRY_MODE_DRIFT",
            "Global registry must remain shadow_compare during B1.",
        )

    readiness_state = str(readiness.get("readiness_state") or "")
    if readiness_state not in READY_STATES:
        raise ConsumerCanaryBlocked(
            "READINESS_NOT_READY",
            f"readiness_state={readiness_state or 'missing'}",
        )

    if readiness.get("semantic_gate_ok") is not True:
        raise ConsumerCanaryBlocked("SEMANTIC_GATE_DRIFT", "semantic_gate_ok is not true.")

    if readiness.get("current_evidence_ok") is not True:
        raise ConsumerCanaryBlocked("CURRENT_EVIDENCE_DRIFT", "current_evidence_ok is not true.")

    findings = readiness.get("governed_findings") or []
    if isinstance(findings, Mapping):
        findings = [findings]
    if findings:
        raise ConsumerCanaryBlocked(
            "GOVERNED_FINDING_PRESENT",
            "The target project/domain has a governed finding pending.",
        )

    try:
        expected = int(config.get("expected_domain_row_count"))
        registry_rows = int(readiness.get("domain_row_count"))
    except (TypeError, ValueError):
        raise ConsumerCanaryBlocked(
            "ROW_COUNT_CONTRACT_MISSING",
            "Expected/current Domain row count is missing.",
        )
    if expected != registry_rows:
        raise ConsumerCanaryBlocked(
            "REGISTRY_ROW_COUNT_DRIFT",
            f"expected={expected}; registry={registry_rows}",
        )

    if not a31_audit:
        raise ConsumerCanaryBlocked("A31_AUDIT_MISSING", "Latest A3.1.1 proof is missing.")

    if str(a31_audit.get("comparison_status") or "") != "semantic_pass":
        raise ConsumerCanaryBlocked(
            "A31_NOT_PASS",
            f"comparison_status={a31_audit.get('comparison_status')}",
        )

    if str(a31_audit.get("read_mode") or "") != "shadow_compare":
        raise ConsumerCanaryBlocked("A31_MODE_DRIFT", "Latest A3.1.1 audit is not shadow_compare.")

    if str(a31_audit.get("served_source") or "") != "legacy":
        raise ConsumerCanaryBlocked(
            "A31_SERVED_SOURCE_DRIFT",
            "A3.1.1 proof must have served Legacy while comparing Domain.",
        )

    try:
        audit_domain_rows = int(a31_audit.get("domain_row_count"))
    except (TypeError, ValueError):
        raise ConsumerCanaryBlocked("A31_ROW_COUNT_MISSING", "A3.1.1 Domain row count is missing.")
    if audit_domain_rows != expected:
        raise ConsumerCanaryBlocked(
            "A31_ROW_COUNT_DRIFT",
            f"expected={expected}; a31={audit_domain_rows}",
        )

    metadata = a31_audit.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise ConsumerCanaryBlocked("A31_METADATA_INVALID", "A3.1.1 metadata is not an object.")

    try:
        semantic_conflicts = int(metadata.get("semantic_conflicts") or 0)
        review_required = int(metadata.get("review_required") or 0)
    except (TypeError, ValueError):
        raise ConsumerCanaryBlocked("A31_COUNTER_INVALID", "A3.1.1 counters are invalid.")
    if semantic_conflicts != 0:
        raise ConsumerCanaryBlocked("A31_SEMANTIC_CONFLICT", "A3.1.1 has semantic conflicts.")
    if review_required != 0:
        raise ConsumerCanaryBlocked("A31_REVIEW_REQUIRED", "A3.1.1 still requires semantic review.")

    version_checks = {
        "comparator_version": config.get("approved_comparator_version"),
        "semantic_scope_version": config.get("approved_semantic_scope_version"),
        "legacy_adapter_version": config.get("approved_legacy_adapter_version"),
    }
    for metadata_key, approved in version_checks.items():
        if not approved:
            raise ConsumerCanaryBlocked(
                "APPROVED_VERSION_MISSING",
                f"Config is missing {metadata_key} approval.",
            )
        actual = metadata.get(metadata_key)
        if str(actual or "") != str(approved):
            raise ConsumerCanaryBlocked(
                "A31_VERSION_DRIFT",
                f"{metadata_key}: approved={approved}; actual={actual}",
            )

    approved_reader = str(config.get("approved_reader_version") or "")
    if not approved_reader:
        raise ConsumerCanaryBlocked("APPROVED_READER_MISSING", "Approved reader version is missing.")
    if str(a31_audit.get("reader_version") or "") != approved_reader:
        raise ConsumerCanaryBlocked(
            "READER_VERSION_DRIFT",
            f"approved={approved_reader}; actual={a31_audit.get('reader_version')}",
        )


def write_canary_audit(
    client: Any,
    *,
    canary_id: str | None,
    project_id: str,
    domain_key: str,
    consumer_key: str,
    served_source: str,
    fallback_used: bool,
    failure_code: str | None,
    failure_detail: str | None,
    domain_row_count: int | None,
    legacy_row_count: int | None,
    expected_domain_row_count: int | None,
    contract_ok: bool,
    domain_fingerprint: str | None,
    legacy_fingerprint: str | None,
    domain_latency_ms: int | None,
    legacy_latency_ms: int | None,
    total_latency_ms: int | None,
    reader_version: str | None,
    consumer_adapter_version: str,
    metadata: Mapping[str, Any] | None = None,
    strict: bool = False,
) -> None:
    payload = {
        "canary_id": canary_id,
        "project_id": project_id,
        "domain_key": domain_key,
        "consumer_key": consumer_key,
        "served_source": served_source,
        "fallback_used": bool(fallback_used),
        "failure_code": failure_code,
        "failure_detail": failure_detail,
        "domain_row_count": domain_row_count,
        "legacy_row_count": legacy_row_count,
        "expected_domain_row_count": expected_domain_row_count,
        "contract_ok": bool(contract_ok),
        "domain_fingerprint": domain_fingerprint,
        "legacy_fingerprint": legacy_fingerprint,
        "domain_latency_ms": domain_latency_ms,
        "legacy_latency_ms": legacy_latency_ms,
        "total_latency_ms": total_latency_ms,
        "reader_version": reader_version,
        "consumer_adapter_version": consumer_adapter_version,
        "metadata": _json_safe(dict(metadata or {})),
    }
    try:
        client.table(CANARY_AUDIT_TABLE).insert(payload).execute()
    except Exception as exc:
        if strict:
            raise ConsumerCanaryBlocked(
                "CANARY_AUDIT_WRITE_FAILED",
                f"Domain cannot be served without B1 audit persistence: {exc}",
            ) from exc


def best_effort_control_audit(
    client: Any,
    *,
    project_id: str,
    domain_key: str,
    consumer_key: str,
    rows: Sequence[Mapping[str, Any]],
    consumer_adapter_version: str,
    contract_ok: bool,
    legacy_fingerprint: str,
    total_latency_ms: int,
    failure_code: str | None = None,
    failure_detail: str | None = None,
) -> None:
    write_canary_audit(
        client,
        canary_id=None,
        project_id=project_id,
        domain_key=domain_key,
        consumer_key=consumer_key,
        served_source="legacy_control",
        fallback_used=False,
        failure_code=failure_code,
        failure_detail=failure_detail,
        domain_row_count=None,
        legacy_row_count=len(rows),
        expected_domain_row_count=None,
        contract_ok=contract_ok,
        domain_fingerprint=None,
        legacy_fingerprint=legacy_fingerprint,
        domain_latency_ms=None,
        legacy_latency_ms=None,
        total_latency_ms=total_latency_ms,
        reader_version=None,
        consumer_adapter_version=consumer_adapter_version,
        metadata={"canary_version": CANARY_VERSION, "control": True},
        strict=False,
    )
