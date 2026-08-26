from __future__ import annotations

"""NAVE V28.7.3B2.3 — Matrix requirement identity consumer canary.

This consumer changes ONLY the requirement identity used to derive the "Briefing"
column of the integrated project matrix. The Unified snapshot, gaps, findings,
recommendations and persisted intelligence remain Legacy.

Global project_domain_cutover_readiness.read_mode stays shadow_compare.
"""

from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping, Sequence

from project_domain_consumer_canary import (
    CANARY_VERSION,
    ConsumerCanaryBlocked,
    elapsed_ms,
    fetch_active_canary,
    fetch_latest_a31_audit,
    stable_fingerprint,
    validate_active_preconditions,
    write_canary_audit,
)
from project_requirement_compatibility import load_requirement_compatibility

DOMAIN_KEY = "requirements"
MATRIX_CONSUMER_KEY = "workspace.intelligence.matrix.requirements_readonly"
BRIEFING_CONSUMER_KEY = "workspace.briefing.requirements_readonly"
MATRIX_ADAPTER_VERSION = "V28.7.3B2.3"
CURRENT_TRUTH_STATES = {"verified", "human_confirmed"}


@dataclass(frozen=True)
class MatrixCanaryRoute:
    intelligence: dict[str, Any]
    served_source: str
    fallback_used: bool
    failure_code: str | None = None
    failure_detail: str | None = None
    canary_id: str | None = None
    consumer_adapter_version: str = MATRIX_ADAPTER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "served_source": self.served_source,
            "fallback_used": self.fallback_used,
            "failure_code": self.failure_code,
            "failure_detail": self.failure_detail,
            "canary_id": self.canary_id,
            "consumer_adapter_version": self.consumer_adapter_version,
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


def _active_link(row: Mapping[str, Any]) -> bool:
    return (_text(row, "link_status") or "suggested").casefold() != "rejected"


def _current_domain_ids(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for row in rows:
        truth = (_text(row, "truth_state", "verification_state") or "").casefold()
        requirement_id = _text(row, "id", "requirement_id", "resolved_domain_id")
        if requirement_id and truth in CURRENT_TRUTH_STATES:
            result.add(requirement_id)
    return result


def _unique_matrix_rows(matrix: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(matrix):
        row = dict(raw)
        item_id = _text(row, "item_id")
        if not item_id:
            raise ConsumerCanaryBlocked(
                "MATRIX_ITEM_ID_MISSING",
                f"row={index}",
            )
        if item_id in indexed:
            raise ConsumerCanaryBlocked(
                "MATRIX_ITEM_ID_DUPLICATE",
                item_id,
            )
        if "Briefing" not in row:
            raise ConsumerCanaryBlocked(
                "MATRIX_BRIEFING_COLUMN_MISSING",
                item_id,
            )
        indexed[item_id] = row
    return indexed


def _link_state(row: Mapping[str, Any]) -> str:
    return (_text(row, "adherence_status") or "not_assessed").casefold()


def _matrix_briefing_label(link_rows: Sequence[Mapping[str, Any]]) -> str:
    """Same business semantics currently used by build_project_intelligence.

    The state comes from the relationship, not from Requirement Truth.
    """
    from project_workspace_intelligence import POSITIVE_ADHERENCE

    values = [_link_state(row) for row in link_rows]
    if any(value == "not_fulfilled" for value in values):
        return "Não cumprida"
    if any(value in POSITIVE_ADHERENCE for value in values):
        return "Com evidência de aderência"
    if link_rows:
        return "Relacionada, ainda não avaliada"
    return "Sem demanda relacionada"


def build_domain_matrix_overlay(
    *,
    snapshot: Mapping[str, Any],
    legacy_intelligence: Mapping[str, Any],
    compatibility: Any,
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    expected_domain_rows: int,
    expected_matrix_rows: int | None = None,
    expected_active_links: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a copy where only matrix[*]["Briefing"] is Domain-ID-derived.

    Every active Legacy link must be represented in the governed compatibility
    report. No lexical resolution is allowed.
    """
    if not bool(getattr(compatibility, "pass_data_bridge", False)):
        raise ConsumerCanaryBlocked(
            "COMPATIBILITY_NOT_PASS_DATA_BRIDGE",
            "B2.1 compatibility is not PASS_DATA_BRIDGE.",
        )

    domain_ids = _current_domain_ids(domain_requirement_rows)
    if len(domain_ids) != int(expected_domain_rows):
        raise ConsumerCanaryBlocked(
            "DOMAIN_ROW_COUNT_DRIFT",
            f"expected={expected_domain_rows}; actual={len(domain_ids)}",
        )

    matrix = list(legacy_intelligence.get("matrix") or [])
    indexed = _unique_matrix_rows(matrix)
    if expected_matrix_rows is not None and len(indexed) != int(expected_matrix_rows):
        raise ConsumerCanaryBlocked(
            "MATRIX_ROW_COUNT_DRIFT",
            f"expected={expected_matrix_rows}; actual={len(indexed)}",
        )

    active_snapshot_links = [
        dict(row)
        for row in (snapshot.get("briefing_links") or [])
        if isinstance(row, Mapping) and _active_link(row)
    ]
    resolved_by_link = {
        str(row.legacy_link_id): row
        for row in getattr(compatibility, "links", ())
    }

    active_ids = {
        str(row.get("id") or "")
        for row in active_snapshot_links
        if row.get("id")
    }
    resolved_ids = set(resolved_by_link)

    if "" in active_ids or len(active_ids) != len(active_snapshot_links):
        raise ConsumerCanaryBlocked(
            "ACTIVE_LINK_ID_INVALID",
            "One or more active Legacy links have a missing/duplicate id.",
        )
    if active_ids != resolved_ids:
        missing = sorted(active_ids - resolved_ids)
        extra = sorted(resolved_ids - active_ids)
        raise ConsumerCanaryBlocked(
            "ACTIVE_LINK_RUNTIME_DRIFT",
            f"snapshot_only={missing}; compatibility_only={extra}",
        )
    if expected_active_links is not None and len(active_ids) != int(expected_active_links):
        raise ConsumerCanaryBlocked(
            "ACTIVE_LINK_COUNT_DRIFT",
            f"expected={expected_active_links}; actual={len(active_ids)}",
        )

    links_by_matrix_item: dict[str, list[dict[str, Any]]] = {
        item_id: [] for item_id in indexed
    }
    non_matrix_active_links = 0

    for link in active_snapshot_links:
        link_id = str(link.get("id"))
        resolved = resolved_by_link[link_id]
        domain_requirement_id = str(resolved.domain_requirement_id or "")
        if domain_requirement_id not in domain_ids:
            raise ConsumerCanaryBlocked(
                "ACTIVE_LINK_DOMAIN_REQUIREMENT_NOT_CURRENT",
                f"link={link_id}; domain_requirement_id={domain_requirement_id}",
            )

        memory_item_id = str(link.get("memory_item_id") or "")
        if not memory_item_id:
            raise ConsumerCanaryBlocked(
                "ACTIVE_LINK_MEMORY_ITEM_MISSING",
                link_id,
            )

        if memory_item_id not in links_by_matrix_item:
            non_matrix_active_links += 1
            continue

        translated = dict(link)
        translated["legacy_requirement_id"] = str(resolved.legacy_requirement_id)
        translated["requirement_id"] = domain_requirement_id
        translated["_identity_source"] = "current_domain_via_b2_1_bridge"
        links_by_matrix_item[memory_item_id].append(translated)

    overlay_matrix: list[dict[str, Any]] = []
    briefing_drifts: list[dict[str, Any]] = []

    for raw in matrix:
        row = dict(raw)
        item_id = str(row.get("item_id"))
        legacy_label = str(row.get("Briefing") or "")
        domain_label = _matrix_briefing_label(links_by_matrix_item.get(item_id, []))

        if legacy_label != domain_label:
            briefing_drifts.append({
                "item_id": item_id,
                "item_title": row.get("Item apresentado"),
                "legacy_briefing": legacy_label,
                "domain_briefing": domain_label,
            })
        row["Briefing"] = domain_label
        overlay_matrix.append(row)

    # B2.3 is identity-only. Any business-label change means fail closed.
    if briefing_drifts:
        raise ConsumerCanaryBlocked(
            "MATRIX_BRIEFING_SEMANTIC_DRIFT",
            str(briefing_drifts[:5]),
        )

    routed = deepcopy(dict(legacy_intelligence))
    routed["matrix"] = overlay_matrix
    routed["_matrix_requirement_canary"] = {
        "version": MATRIX_ADAPTER_VERSION,
        "served_source": "domain",
        "identity_source": "current_domain_via_b2_1_bridge",
        "overlay_fields": ["Briefing"],
        "domain_requirement_count": len(domain_ids),
        "matrix_row_count": len(overlay_matrix),
        "active_link_count": len(active_snapshot_links),
        "matrix_active_link_count": sum(len(v) for v in links_by_matrix_item.values()),
        "non_matrix_active_link_count": non_matrix_active_links,
        "semantic_drift_count": 0,
        "persisted_intelligence_source": "legacy",
        "unified_source": "legacy",
    }
    return routed, routed["_matrix_requirement_canary"]


def _legacy_route(
    intelligence: Mapping[str, Any],
    *,
    served_source: str,
    fallback_used: bool,
    failure_code: str | None = None,
    failure_detail: str | None = None,
    canary_id: str | None = None,
) -> MatrixCanaryRoute:
    result = deepcopy(dict(intelligence))
    result["_matrix_requirement_canary"] = {
        "version": MATRIX_ADAPTER_VERSION,
        "served_source": served_source,
        "fallback_used": bool(fallback_used),
        "failure_code": failure_code,
        "persisted_intelligence_source": "legacy",
        "unified_source": "legacy",
    }
    return MatrixCanaryRoute(
        intelligence=result,
        served_source=served_source,
        fallback_used=fallback_used,
        failure_code=failure_code,
        failure_detail=failure_detail,
        canary_id=canary_id,
    )


def route_matrix_requirement_consumer(
    client: Any,
    *,
    project_id: str,
    snapshot: Mapping[str, Any],
    legacy_intelligence: Mapping[str, Any],
) -> MatrixCanaryRoute:
    """Governed matrix-only consumer router with explicit Legacy fail-closed."""
    started = perf_counter()
    legacy_matrix = [dict(row) for row in (legacy_intelligence.get("matrix") or [])]
    legacy_fp = stable_fingerprint(legacy_matrix)
    legacy_requirement_count = len(snapshot.get("briefing_requirements") or [])

    # Only projects already admitted to the B1 requirements canary participate
    # in B2.3 controls/canaries. Everything else stays untouched/noiseless.
    try:
        briefing_canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=BRIEFING_CONSUMER_KEY,
        )
    except Exception:
        return _legacy_route(
            legacy_intelligence,
            served_source="legacy_control",
            fallback_used=False,
        )

    if not briefing_canary:
        return _legacy_route(
            legacy_intelligence,
            served_source="legacy_control",
            fallback_used=False,
        )

    try:
        config = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=MATRIX_CONSUMER_KEY,
        )
    except Exception as exc:
        write_canary_audit(
            client,
            canary_id=None,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=MATRIX_CONSUMER_KEY,
            served_source="legacy_control",
            fallback_used=False,
            failure_code="MATRIX_CANARY_CONFIG_UNAVAILABLE",
            failure_detail=str(exc),
            domain_row_count=None,
            legacy_row_count=legacy_requirement_count,
            expected_domain_row_count=None,
            contract_ok=True,
            domain_fingerprint=None,
            legacy_fingerprint=legacy_fp,
            domain_latency_ms=None,
            legacy_latency_ms=None,
            total_latency_ms=elapsed_ms(started),
            reader_version=None,
            consumer_adapter_version=MATRIX_ADAPTER_VERSION,
            metadata={
                "canary_version": CANARY_VERSION,
                "matrix_rows": len(legacy_matrix),
                "control": True,
            },
            strict=False,
        )
        return _legacy_route(
            legacy_intelligence,
            served_source="legacy_control",
            fallback_used=False,
            failure_code="MATRIX_CANARY_CONFIG_UNAVAILABLE",
            failure_detail=str(exc),
        )

    if not config:
        write_canary_audit(
            client,
            canary_id=None,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=MATRIX_CONSUMER_KEY,
            served_source="legacy_control",
            fallback_used=False,
            failure_code=None,
            failure_detail=None,
            domain_row_count=None,
            legacy_row_count=legacy_requirement_count,
            expected_domain_row_count=None,
            contract_ok=True,
            domain_fingerprint=None,
            legacy_fingerprint=legacy_fp,
            domain_latency_ms=None,
            legacy_latency_ms=None,
            total_latency_ms=elapsed_ms(started),
            reader_version=None,
            consumer_adapter_version=MATRIX_ADAPTER_VERSION,
            metadata={
                "canary_version": CANARY_VERSION,
                "matrix_rows": len(legacy_matrix),
                "active_links": sum(
                    1 for row in (snapshot.get("briefing_links") or [])
                    if isinstance(row, Mapping) and _active_link(row)
                ),
                "control": True,
            },
            strict=False,
        )
        return _legacy_route(
            legacy_intelligence,
            served_source="legacy_control",
            fallback_used=False,
        )

    canary_id = str(config.get("id") or "") or None
    expected_rows_raw = config.get("expected_domain_row_count")
    metadata = config.get("metadata") if isinstance(config.get("metadata"), Mapping) else {}
    expected_matrix_rows = metadata.get("expected_matrix_rows")
    expected_active_links = metadata.get("expected_active_links")

    try:
        expected_rows = int(expected_rows_raw)
    except (TypeError, ValueError):
        expected_rows = -1

    domain_fp: str | None = None
    domain_latency: int | None = None
    reader_version: str | None = None
    domain_rows: list[dict[str, Any]] = []

    try:
        if expected_rows < 0:
            raise ConsumerCanaryBlocked(
                "EXPECTED_ROW_COUNT_INVALID",
                str(expected_rows_raw),
            )

        from project_domain_reader import get_cutover_state, read_domain

        readiness = get_cutover_state(client, project_id, DOMAIN_KEY)
        a31 = fetch_latest_a31_audit(
            client,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
        )
        validate_active_preconditions(
            config=config,
            readiness=readiness,
            a31_audit=a31,
        )

        domain_started = perf_counter()
        shadow = read_domain(
            client,
            project_id,
            DOMAIN_KEY,
            legacy_loader=lambda: list(snapshot.get("briefing_requirements") or []),
            audit=False,
        )
        domain_latency = elapsed_ms(domain_started)
        reader_version = (
            str(getattr(shadow, "reader_version", None)
                or config.get("approved_reader_version") or "")
            or None
        )

        if str(shadow.read_mode) != "shadow_compare":
            raise ConsumerCanaryBlocked(
                "RUNTIME_MODE_DRIFT",
                f"read_mode={shadow.read_mode}",
            )
        if str(shadow.served_source) != "legacy":
            raise ConsumerCanaryBlocked(
                "RUNTIME_SHADOW_SOURCE_DRIFT",
                f"served_source={shadow.served_source}",
            )

        domain_rows = [
            dict(row)
            for row in (shadow.domain_candidate or [])
            if isinstance(row, Mapping)
        ]
        compatibility = load_requirement_compatibility(
            client,
            project_id=project_id,
        )

        routed, overlay_meta = build_domain_matrix_overlay(
            snapshot=snapshot,
            legacy_intelligence=legacy_intelligence,
            compatibility=compatibility,
            domain_requirement_rows=domain_rows,
            expected_domain_rows=expected_rows,
            expected_matrix_rows=(
                int(expected_matrix_rows)
                if expected_matrix_rows not in (None, "")
                else None
            ),
            expected_active_links=(
                int(expected_active_links)
                if expected_active_links not in (None, "")
                else None
            ),
        )

        domain_matrix = list(routed.get("matrix") or [])
        domain_fp = stable_fingerprint(domain_matrix)

        # Persist audit BEFORE exposing Domain identity to the real matrix.
        write_canary_audit(
            client,
            canary_id=canary_id,
            project_id=project_id,
            domain_key=DOMAIN_KEY,
            consumer_key=MATRIX_CONSUMER_KEY,
            served_source="domain",
            fallback_used=False,
            failure_code=None,
            failure_detail=None,
            domain_row_count=expected_rows,
            legacy_row_count=legacy_requirement_count,
            expected_domain_row_count=expected_rows,
            contract_ok=True,
            domain_fingerprint=domain_fp,
            legacy_fingerprint=legacy_fp,
            domain_latency_ms=domain_latency,
            legacy_latency_ms=None,
            total_latency_ms=elapsed_ms(started),
            reader_version=reader_version,
            consumer_adapter_version=MATRIX_ADAPTER_VERSION,
            metadata={
                "canary_version": CANARY_VERSION,
                "registry_read_mode": readiness.get("read_mode"),
                "readiness_state": readiness.get("readiness_state"),
                **overlay_meta,
            },
            strict=True,
        )

        return MatrixCanaryRoute(
            intelligence=routed,
            served_source="domain",
            fallback_used=False,
            canary_id=canary_id,
        )

    except ConsumerCanaryBlocked as exc:
        failure_code = exc.code
        failure_detail = exc.detail
    except Exception as exc:
        failure_code = "MATRIX_DOMAIN_RUNTIME_ERROR"
        failure_detail = str(exc)

    write_canary_audit(
        client,
        canary_id=canary_id,
        project_id=project_id,
        domain_key=DOMAIN_KEY,
        consumer_key=MATRIX_CONSUMER_KEY,
        served_source="legacy_fallback",
        fallback_used=True,
        failure_code=failure_code,
        failure_detail=failure_detail,
        domain_row_count=(
            len(_current_domain_ids(domain_rows))
            if domain_rows else None
        ),
        legacy_row_count=legacy_requirement_count,
        expected_domain_row_count=expected_rows if expected_rows >= 0 else None,
        contract_ok=True,
        domain_fingerprint=domain_fp,
        legacy_fingerprint=legacy_fp,
        domain_latency_ms=domain_latency,
        legacy_latency_ms=None,
        total_latency_ms=elapsed_ms(started),
        reader_version=reader_version,
        consumer_adapter_version=MATRIX_ADAPTER_VERSION,
        metadata={
            "canary_version": CANARY_VERSION,
            "matrix_rows": len(legacy_matrix),
            "persisted_intelligence_source": "legacy",
            "unified_source": "legacy",
        },
        strict=False,
    )
    return _legacy_route(
        legacy_intelligence,
        served_source="legacy_fallback",
        fallback_used=True,
        failure_code=failure_code,
        failure_detail=failure_detail,
        canary_id=canary_id,
    )
