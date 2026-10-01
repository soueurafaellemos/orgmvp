from __future__ import annotations

"""NAVE V28.7.3B2.13 — Post-Supersession Response Projection Integrity Shadow.

READ ONLY / shadow only.

Purpose
-------
Prove that a real Requirement identity supersession changes only identity cardinality /
lineage, while preserving downstream response semantics for the surviving Current
Requirement set.

The module compares:
1. a user-supplied, previously approved B2.12.2.2 pre-supersession baseline JSON;
2. a fresh live B2.12.2.2 projection over the current database state;
3. the independently verified B2.12.5.4 supersession lineage, when one exists.

Nothing here creates Human Review, changes Requirement Truth, Response Truth, Evidence,
read_mode, canaries, domain_primary, or cutover.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from project_domain_reader import get_cutover_state
from project_intelligence_pipeline import requirement_reconciliation_contract
from project_requirement_auto_adjudication_completeness import (
    run_semantic_hardened_adjudication as run_b21222,
)
from project_requirement_identity_supersession_verify import verify_supersession

VERSION = "V28.7.3B2.13"
BASELINE_VERSION = "V28.7.3B2.12.2.2"
SUPERSESSION_WRITER_VERSION = "V28.7.3B2.12.5.4"
PROMOTION_VERSION = "V28.7.2C0.2.4H3.1.3P1"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def _hash(value: Any) -> str:
    payload = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _by_id(rows: Sequence[Mapping[str, Any]], key: str = "requirement_id") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        rid = str(row.get(key) or "")
        if rid:
            out[rid] = row
    return out


def _identity_free_projection_signature(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Response-semantic signature used only to prove duplicate identities were semantically equivalent.

    Deliberately excludes identity/business/provenance fields where the two duplicate
    Requirement identities legitimately differed before supersession.
    """
    if not row:
        return None
    keep = (
        "canonical_obligation_text",
        "current_response_contract_status",
        "projected_response_status",
        "projected_reason",
        "review_origin",
        "current_response_evidence_count",
        "current_response_evidence",
        "recall_gate_class",
        "recall_obligation_atom_coverage",
        "recall_title_anchor_coverage",
        "recall_requirement_atoms",
        "recall_shared_atoms",
        "recall_missing_atoms",
        "recall_missing_hard_atoms",
        "recall_evidence_id",
        "recall_evidence_source",
        "recall_evidence_locator",
        "recall_candidate_text",
    )
    return {k: _canonical(row.get(k)) for k in keep}


def _identity_free_recommendation_signature(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    keep = (
        "canonical_obligation_text",
        "current_response_contract_status",
        "projected_response_status",
        "projected_reason",
        "review_origin",
        "current_response_evidence_count",
        "current_response_evidence",
        "evidence_id",
        "evidence_source",
        "evidence_locator",
        "evidence_text",
        "recall_gate_class",
        "obligation_atom_coverage",
        "title_anchor_coverage",
        "requirement_atoms",
        "shared_atoms",
        "missing_atoms",
        "missing_hard_atoms",
        "machine_recommendation",
        "machine_confidence",
        "machine_rule_id",
        "machine_rationale",
        "completeness_scope",
        "completeness_guard_applied",
    )
    return {k: _canonical(row.get(k)) for k in keep}


def _count_recommendations(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "recommend_confirm": 0,
        "recommend_partial": 0,
        "recommend_reject": 0,
        "recommend_visual_review": 0,
        "recommend_defer": 0,
    }
    for row in rows:
        key = str(row.get("machine_recommendation") or "recommend_defer")
        out[key] = out.get(key, 0) + 1
    return out


def _current_identity_ids(payload: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in (
        "projection_rows",
        "recommendation_rows",
        "semantic_excluded_rows",
    ):
        for row in payload.get(key) or []:
            rid = str((row or {}).get("requirement_id") or (row or {}).get("id") or "")
            if rid:
                ids.add(rid)
    for row in payload.get("canonical_identity_collision_rows") or []:
        for rid in (row or {}).get("requirement_ids") or []:
            if rid:
                ids.add(str(rid))
    return ids


def _latest_completed_supersession_run(client: Any, project_id: str) -> dict[str, Any] | None:
    runs = _rows(
        client.table("intelligence_runs")
        .select("*")
        .eq("analyzer_type", "project_requirement_identity_supersession")
        .order("started_at", desc=True)
        .limit(100)
        .execute()
    )
    for row in runs:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        if str(metadata.get("project_id") or "") != str(project_id):
            continue
        if str(row.get("status") or "") != "completed":
            continue
        return row
    return None


def _baseline_contract_checks(baseline: Mapping[str, Any], project_id: str) -> dict[str, bool]:
    return {
        "baseline_version_is_b21222": str(baseline.get("version") or "") == BASELINE_VERSION,
        "baseline_project_matches": str(baseline.get("project_id") or "") == str(project_id),
        "baseline_truth_unchanged": baseline.get("truth_changed") is False,
        "baseline_human_review_not_created": baseline.get("human_review_created") is False,
        "baseline_persistence_not_performed": baseline.get("persistence_performed") is False,
        "baseline_cutover_not_approved": baseline.get("cutover_approved") is False,
    }


def _same_id_row_mismatches(
    baseline_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
    *,
    ignored_ids: set[str],
) -> list[dict[str, Any]]:
    baseline = _by_id(baseline_rows)
    current = _by_id(current_rows)
    mismatches: list[dict[str, Any]] = []
    for rid in sorted((set(baseline) & set(current)) - set(ignored_ids)):
        if _canonical(baseline[rid]) != _canonical(current[rid]):
            mismatches.append({
                "requirement_id": rid,
                "baseline_sha256": _hash(baseline[rid]),
                "current_sha256": _hash(current[rid]),
                "reason": "same Requirement identity changed downstream row",
            })
    return mismatches


def compare_response_projection_integrity(
    *,
    project_id: str,
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    supersession_verification: Mapping[str, Any] | None,
    supersession_run: Mapping[str, Any] | None,
    read_mode: str,
    pipeline_contract: Mapping[str, Any],
) -> dict[str, Any]:
    baseline_projection = _by_id(baseline.get("projection_rows") or [])
    current_projection = _by_id(current.get("projection_rows") or [])
    baseline_recommendation = _by_id(baseline.get("recommendation_rows") or [])
    current_recommendation = _by_id(current.get("recommendation_rows") or [])

    baseline_ids = set(baseline_projection)
    current_ids = set(current_projection)

    common_checks = _baseline_contract_checks(baseline, project_id)
    common_checks.update({
        "current_truth_unchanged": current.get("truth_changed") is False,
        "current_human_review_not_created": current.get("human_review_created") is False,
        "current_persistence_not_performed": current.get("persistence_performed") is False,
        "current_cutover_not_approved": current.get("cutover_approved") is False,
        "requirements_still_shadow_compare": str(read_mode or "") == "shadow_compare",
        "normal_pipeline_still_h31": (
            pipeline_contract.get("normal_pipeline_uses_h31") is True
            and str(pipeline_contract.get("promotion_version") or "") == PROMOTION_VERSION
        ),
        "semantic_unknown_count_zero": int(current.get("semantic_unknown_count") or 0) == 0,
    })

    mismatch_rows: list[dict[str, Any]] = []
    mode = "CONTROL_NO_SUPERSESSION"

    if supersession_run is None:
        control_projection_mismatch = _same_id_row_mismatches(
            baseline.get("projection_rows") or [],
            current.get("projection_rows") or [],
            ignored_ids=set(),
        )
        control_recommendation_mismatch = _same_id_row_mismatches(
            baseline.get("recommendation_rows") or [],
            current.get("recommendation_rows") or [],
            ignored_ids=set(),
        )
        mismatch_rows.extend(control_projection_mismatch)
        mismatch_rows.extend(control_recommendation_mismatch)

        checks = {
            **common_checks,
            "control_projection_identity_set_unchanged": baseline_ids == current_ids,
            "control_recommendation_identity_set_unchanged": (
                set(baseline_recommendation) == set(current_recommendation)
            ),
            "control_projection_rows_unchanged": not control_projection_mismatch,
            "control_recommendation_rows_unchanged": not control_recommendation_mismatch,
            "control_current_count_unchanged": int(
                baseline.get("current_requirement_count_before_semantic_gate") or 0
            ) == int(current.get("current_requirement_count_before_semantic_gate") or 0),
            "control_collision_count_unchanged": int(
                baseline.get("canonical_identity_collision_count") or 0
            ) == int(current.get("canonical_identity_collision_count") or 0),
            "control_queue_count_unchanged": int(baseline.get("queue_count") or 0)
                == int(current.get("queue_count") or 0),
            "control_recommendation_distribution_unchanged": (
                _count_recommendations(baseline.get("recommendation_rows") or [])
                == _count_recommendations(current.get("recommendation_rows") or [])
            ),
        }

        failed = [key for key, value in checks.items() if not value]
        return {
            "version": VERSION,
            "project_id": project_id,
            "mode": mode,
            "status": "PASS_CONTROL_NO_DOWNSTREAM_DRIFT" if not failed
                else "BLOCKED_RESPONSE_IMPACT_SHADOW",
            "all_checks_pass": not failed,
            "failed_checks": failed,
            "checks": checks,
            "baseline": {
                "version": baseline.get("version"),
                "current_requirement_count": baseline.get(
                    "current_requirement_count_before_semantic_gate"
                ),
                "queue_count": baseline.get("queue_count"),
                "collision_count": baseline.get("canonical_identity_collision_count"),
                "projection_sha256": _hash(baseline.get("projection_rows") or []),
                "recommendation_sha256": _hash(baseline.get("recommendation_rows") or []),
            },
            "current": {
                "version": current.get("version"),
                "current_requirement_count": current.get(
                    "current_requirement_count_before_semantic_gate"
                ),
                "queue_count": current.get("queue_count"),
                "collision_count": current.get("canonical_identity_collision_count"),
                "projection_sha256": _hash(current.get("projection_rows") or []),
                "recommendation_sha256": _hash(current.get("recommendation_rows") or []),
            },
            "mismatch_rows": mismatch_rows,
            "response_truth_changed": False,
            "human_review_created": False,
            "persistence_performed": False,
            "writes_performed": False,
            "cutover_approved": False,
        }

    mode = "POST_SUPERSESSION"
    verification = dict(supersession_verification or {})
    run_metadata = (
        dict(supersession_run.get("metadata") or {})
        if isinstance(supersession_run.get("metadata"), Mapping)
        else {}
    )

    survivor_id = str(
        verification.get("survivor_requirement_id")
        or run_metadata.get("survivor_requirement_id")
        or ""
    )
    old_ids = {
        str(v)
        for v in (
            verification.get("superseded_requirement_ids")
            or run_metadata.get("superseded_requirement_ids")
            or []
        )
        if v
    }

    expected_current_ids = baseline_ids - old_ids
    old_rec_ids = old_ids & set(baseline_recommendation)
    expected_recommendation_ids = set(baseline_recommendation) - old_rec_ids

    same_projection_mismatches = _same_id_row_mismatches(
        baseline.get("projection_rows") or [],
        current.get("projection_rows") or [],
        ignored_ids=old_ids,
    )
    same_recommendation_mismatches = _same_id_row_mismatches(
        baseline.get("recommendation_rows") or [],
        current.get("recommendation_rows") or [],
        ignored_ids=old_ids,
    )
    mismatch_rows.extend(same_projection_mismatches)
    mismatch_rows.extend(same_recommendation_mismatches)

    baseline_survivor_projection = baseline_projection.get(survivor_id)
    baseline_survivor_recommendation = baseline_recommendation.get(survivor_id)
    duplicate_projection_equivalent = all(
        _identity_free_projection_signature(baseline_projection.get(old_id))
        == _identity_free_projection_signature(baseline_survivor_projection)
        for old_id in old_ids
    ) if old_ids and baseline_survivor_projection else False

    duplicate_recommendation_equivalent = True
    for old_id in old_ids:
        old_rec = baseline_recommendation.get(old_id)
        survivor_rec = baseline_survivor_recommendation
        if (old_rec is None) != (survivor_rec is None):
            duplicate_recommendation_equivalent = False
            break
        if old_rec is not None and (
            _identity_free_recommendation_signature(old_rec)
            != _identity_free_recommendation_signature(survivor_rec)
        ):
            duplicate_recommendation_equivalent = False
            break

    baseline_collision_covers = False
    for row in baseline.get("canonical_identity_collision_rows") or []:
        ids = {str(v) for v in (row or {}).get("requirement_ids") or [] if v}
        if survivor_id and old_ids and ({survivor_id} | old_ids).issubset(ids):
            baseline_collision_covers = True
            break

    baseline_dist = _count_recommendations(baseline.get("recommendation_rows") or [])
    expected_dist = dict(baseline_dist)
    for rid in old_rec_ids:
        cls = str(baseline_recommendation[rid].get("machine_recommendation") or "recommend_defer")
        expected_dist[cls] = expected_dist.get(cls, 0) - 1
    current_dist = _count_recommendations(current.get("recommendation_rows") or [])

    current_facing_ids = _current_identity_ids(current)

    checks = {
        **common_checks,
        "completed_supersession_run_is_b21254": (
            str(supersession_run.get("status") or "") == "completed"
            and str(supersession_run.get("pipeline_version") or "") == SUPERSESSION_WRITER_VERSION
        ),
        "post_transaction_verifier_passed": (
            verification.get("status") == "PASS_POST_TRANSACTION_VERIFICATION"
            and verification.get("all_checks_pass") is True
        ),
        "supersession_has_survivor": bool(survivor_id),
        "supersession_has_old_identities": bool(old_ids),
        "baseline_contains_survivor": survivor_id in baseline_ids,
        "baseline_contains_all_superseded_identities": old_ids.issubset(baseline_ids),
        "baseline_collision_explains_supersession": baseline_collision_covers,
        "duplicate_projection_response_semantics_equivalent_before_supersession": (
            duplicate_projection_equivalent
        ),
        "duplicate_recommendation_semantics_equivalent_before_supersession": (
            duplicate_recommendation_equivalent
        ),
        "current_projection_contains_survivor": survivor_id in current_ids,
        "current_projection_excludes_all_superseded_identities": not bool(current_ids & old_ids),
        "current_facing_outputs_exclude_all_superseded_identities": not bool(
            current_facing_ids & old_ids
        ),
        "current_projection_identity_set_is_baseline_minus_superseded": (
            current_ids == expected_current_ids
        ),
        "current_recommendation_identity_set_is_baseline_minus_superseded": (
            set(current_recommendation) == expected_recommendation_ids
        ),
        "all_surviving_projection_rows_semantically_unchanged": not same_projection_mismatches,
        "all_surviving_recommendation_rows_semantically_unchanged": not same_recommendation_mismatches,
        "current_count_delta_exactly_matches_supersession": (
            int(current.get("current_requirement_count_before_semantic_gate") or 0)
            == int(baseline.get("current_requirement_count_before_semantic_gate") or 0)
               - len(old_ids)
        ),
        "queue_delta_exactly_matches_removed_duplicate_review_rows": (
            int(current.get("queue_count") or 0)
            == int(baseline.get("queue_count") or 0) - len(old_rec_ids)
        ),
        "recommendation_distribution_delta_exact": current_dist == expected_dist,
        "canonical_collision_count_zero_after_supersession": int(
            current.get("canonical_identity_collision_count") or 0
        ) == 0,
        "historical_lineage_and_evidence_preserved_by_verifier": all([
            verification.get("checks", {}).get("governance_lineage_complete") is True,
            verification.get("checks", {}).get("knowledge_entity_lineage_complete") is True,
            verification.get("checks", {}).get("historical_evidence_count_preserved") is True,
            verification.get("checks", {}).get(
                "historical_semantic_observation_count_preserved"
            ) is True,
            verification.get("checks", {}).get(
                "all_legacy_aliases_uniquely_resolve_to_survivor"
            ) is True,
        ]),
        "response_truth_remains_unchanged": (
            verification.get("response_truth_changed") is False
        ),
    }

    failed = [key for key, value in checks.items() if not value]

    return {
        "version": VERSION,
        "project_id": project_id,
        "mode": mode,
        "status": "PASS_POST_SUPERSESSION_RESPONSE_INTEGRITY" if not failed
            else "BLOCKED_RESPONSE_IMPACT_SHADOW",
        "all_checks_pass": not failed,
        "failed_checks": failed,
        "checks": checks,
        "supersession": {
            "run_id": supersession_run.get("id"),
            "writer_version": supersession_run.get("pipeline_version"),
            "survivor_requirement_id": survivor_id,
            "superseded_requirement_ids": sorted(old_ids),
        },
        "baseline": {
            "version": baseline.get("version"),
            "current_requirement_count": baseline.get(
                "current_requirement_count_before_semantic_gate"
            ),
            "queue_count": baseline.get("queue_count"),
            "collision_count": baseline.get("canonical_identity_collision_count"),
            "recommendation_distribution": baseline_dist,
            "projection_sha256": _hash(baseline.get("projection_rows") or []),
            "recommendation_sha256": _hash(baseline.get("recommendation_rows") or []),
        },
        "current": {
            "version": current.get("version"),
            "status": current.get("status"),
            "current_requirement_count": current.get(
                "current_requirement_count_before_semantic_gate"
            ),
            "semantic_eligible_requirement_count": current.get(
                "semantic_eligible_requirement_count"
            ),
            "queue_count": current.get("queue_count"),
            "collision_count": current.get("canonical_identity_collision_count"),
            "recommendation_distribution": current_dist,
            "projection_sha256": _hash(current.get("projection_rows") or []),
            "recommendation_sha256": _hash(current.get("recommendation_rows") or []),
        },
        "expected_after_supersession": {
            "current_requirement_count": int(
                baseline.get("current_requirement_count_before_semantic_gate") or 0
            ) - len(old_ids),
            "queue_count": int(baseline.get("queue_count") or 0) - len(old_rec_ids),
            "recommendation_distribution": expected_dist,
        },
        "mismatch_rows": mismatch_rows,
        "post_transaction_verification": verification,
        "response_truth_changed": False,
        "human_review_created": False,
        "persistence_performed": False,
        "writes_performed": False,
        "cutover_approved": False,
    }


def run_response_truth_impact_shadow(
    client: Any,
    *,
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(baseline.get("project_id") or "")
    if not project_id:
        raise ValueError("B2.13 requires baseline.project_id")

    state = get_cutover_state(client, project_id, "requirements")
    pipeline_contract = requirement_reconciliation_contract()

    current_obj = run_b21222(
        client,
        project_id=project_id,
    )
    current = current_obj.to_dict()

    supersession_run = _latest_completed_supersession_run(client, project_id)
    supersession_verification = None
    if supersession_run is not None:
        supersession_verification = verify_supersession(
            client,
            project_id=project_id,
        )

    return compare_response_projection_integrity(
        project_id=project_id,
        baseline=baseline,
        current=current,
        supersession_verification=supersession_verification,
        supersession_run=supersession_run,
        read_mode=str(state.get("read_mode") or ""),
        pipeline_contract=pipeline_contract,
    )
