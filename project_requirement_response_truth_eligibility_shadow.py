from __future__ import annotations

"""NAVE V28.7.3B2.14 — Response Truth Eligibility & Provenance Shadow.

READ ONLY.

This phase does NOT persist Response Truth. It classifies every Current Requirement
into an explicit future-promotion eligibility class and proves the provenance contract
that would be required by a later write phase.

Core rule:
- governed B2.7.1 `verified_response` is evidence-backed contract verification;
- machine `recommend_confirm` is NEVER Truth and NEVER Human Review;
- a machine-confirm row may become only an explicit HUMAN-CONFIRMATION CANDIDATE;
- partial/reject/visual/defer/no-safe/false-positive rows are not truth-eligible.
"""

from collections import Counter
from typing import Any, Mapping

from project_domain_reader import get_cutover_state
from project_intelligence_pipeline import requirement_reconciliation_contract
from project_requirement_auto_adjudication_completeness import (
    run_semantic_hardened_adjudication as run_b21222,
)
from project_requirement_identity_supersession_verify import verify_supersession

VERSION = "V28.7.3B2.14"
SOURCE_VERSION = "V28.7.3B2.12.2.2"
PROMOTION_VERSION = "V28.7.2C0.2.4H3.1.3P1"

PROJECTS = {
    "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136": "Festivalzinho Chambinho",
    "01415104-72f2-4b8e-aeca-2dd24c231a7d": "Lançamento Jovi X300",
}

ELIGIBLE_CONTRACT = "eligible_contract_verified"
ELIGIBLE_HUMAN = "eligible_human_confirmation_only"
NOT_PARTIAL = "not_eligible_partial"
NOT_REJECT = "not_eligible_reject"
NOT_VISUAL = "not_eligible_visual_review"
NOT_DEFER = "not_eligible_defer"
NOT_NO_SAFE = "not_eligible_no_safe_response"
NOT_FALSE_POSITIVE = "not_eligible_false_positive_excluded"
BLOCKED = "blocked_unclassified"

ELIGIBILITY_ORDER = (
    ELIGIBLE_CONTRACT,
    ELIGIBLE_HUMAN,
    NOT_PARTIAL,
    NOT_REJECT,
    NOT_VISUAL,
    NOT_DEFER,
    NOT_NO_SAFE,
    NOT_FALSE_POSITIVE,
    BLOCKED,
)


def project_options() -> list[dict[str, str]]:
    return [{"project_id": pid, "label": label} for pid, label in PROJECTS.items()]


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _latest_completed_supersession_run(client: Any, project_id: str) -> dict[str, Any] | None:
    rows = _rows(
        client.table("intelligence_runs")
        .select("*")
        .eq("analyzer_type", "project_requirement_identity_supersession")
        .order("started_at", desc=True)
        .limit(100)
        .execute()
    )
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        if str(metadata.get("project_id") or "") != str(project_id):
            continue
        if str(row.get("status") or "") != "completed":
            continue
        return row
    return None


def classify_response_truth_eligibility(
    projection_row: Mapping[str, Any],
    recommendation_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    p = dict(projection_row)
    r = dict(recommendation_row or {})

    rid = str(p.get("requirement_id") or "")
    current_status = str(p.get("current_response_contract_status") or "")
    projected_status = str(p.get("projected_response_status") or "")
    evidence = list(p.get("current_response_evidence") or [])
    machine = str(r.get("machine_recommendation") or "")
    machine_conf = r.get("machine_confidence")
    evidence_id = str(r.get("evidence_id") or "")

    base = {
        "requirement_id": rid,
        "requirement_title": p.get("title"),
        "requirement_truth_status": p.get("requirement_truth_status"),
        "current_response_contract_status": current_status,
        "projected_response_status": projected_status,
        "machine_recommendation": machine or None,
        "machine_confidence": machine_conf,
        "evidence_id": evidence_id or None,
        "evidence_locator": r.get("evidence_locator"),
        "evidence_source": r.get("evidence_source"),
        "human_review_created": False,
        "truth_effect_applied": False,
        "persistence_performed": False,
        "requires_explicit_human_decision": False,
        "future_truth_target_state": None,
        "provenance_contract": None,
        "eligibility_class": BLOCKED,
        "eligibility_reason": "unclassified response state",
    }

    if current_status == "verified_response" and projected_status == "verified_response":
        valid_evidence = bool(evidence) and all(
            str(item.get("verdict") or "") == "verified_response"
            and str(item.get("entailment_status") or "").startswith("SUPPORTED_")
            and bool(item.get("evidence_id"))
            for item in evidence
            if isinstance(item, Mapping)
        )
        if valid_evidence:
            base.update({
                "eligibility_class": ELIGIBLE_CONTRACT,
                "eligibility_reason": (
                    "already verified by governed response contract with explicit supporting evidence"
                ),
                "future_truth_target_state": "verified_response",
                "provenance_contract": "governed_response_contract+evidence",
            })
        else:
            base["eligibility_reason"] = (
                "verified_response contract row lacks complete governed evidence provenance"
            )
        return base

    if machine:
        machine_guard_ok = (
            r.get("human_review_created") is False
            and r.get("truth_effect_applied") is False
            and r.get("persistence_performed") is False
        )
        if not machine_guard_ok:
            base["eligibility_reason"] = (
                "machine recommendation violates no-truth/no-persistence provenance contract"
            )
            return base

        if machine == "recommend_confirm":
            confirm_ok = (
                projected_status == "response_review_high_confidence"
                and bool(evidence_id)
                and str(r.get("requirement_truth_status_at_review") or "")
                    in {"verified", "human_confirmed"}
                and not bool(r.get("completeness_guard_applied"))
            )
            if confirm_ok:
                base.update({
                    "eligibility_class": ELIGIBLE_HUMAN,
                    "eligibility_reason": (
                        "machine evidence is strong enough to request explicit human confirmation; "
                        "machine output alone remains non-Truth"
                    ),
                    "requires_explicit_human_decision": True,
                    "future_truth_target_state": "human_confirmed_response",
                    "provenance_contract": (
                        "explicit_human_decision+candidate_snapshot+evidence+machine_recommendation"
                    ),
                })
            else:
                base["eligibility_reason"] = (
                    "recommend_confirm lacks one or more hard provenance/eligibility guards"
                )
            return base

        mapping = {
            "recommend_partial": (
                NOT_PARTIAL,
                "partial obligation coverage cannot support Response Truth",
            ),
            "recommend_reject": (
                NOT_REJECT,
                "machine recommendation rejects truth promotion",
            ),
            "recommend_visual_review": (
                NOT_VISUAL,
                "visual/structured evidence requires separate review before any truth eligibility",
            ),
            "recommend_defer": (
                NOT_DEFER,
                "candidate is deferred and cannot support truth promotion",
            ),
        }
        if machine in mapping:
            cls, reason = mapping[machine]
            base.update({
                "eligibility_class": cls,
                "eligibility_reason": reason,
            })
            return base

        base["eligibility_reason"] = f"unknown machine recommendation: {machine}"
        return base

    if projected_status == "no_safely_verified_response":
        base.update({
            "eligibility_class": NOT_NO_SAFE,
            "eligibility_reason": "no response evidence is safe enough for truth promotion",
        })
        return base

    if projected_status == "false_positive_excluded":
        base.update({
            "eligibility_class": NOT_FALSE_POSITIVE,
            "eligibility_reason": "false-positive response evidence is explicitly excluded",
        })
        return base

    if projected_status in {"response_review_high_confidence", "response_review_partial"}:
        base["eligibility_reason"] = "review candidate has no machine adjudication recommendation"
        return base

    base["eligibility_reason"] = (
        f"unsupported response state: {projected_status or current_status or 'empty'}"
    )
    return base


def build_response_truth_eligibility_shadow(
    *,
    project_id: str,
    projection: Mapping[str, Any],
    read_mode: str,
    pipeline_contract: Mapping[str, Any],
    supersession_verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    projection_rows = [
        dict(row) for row in (projection.get("projection_rows") or [])
        if isinstance(row, Mapping)
    ]
    recommendation_rows = [
        dict(row) for row in (projection.get("recommendation_rows") or [])
        if isinstance(row, Mapping)
    ]

    rec_by_id = {
        str(row.get("requirement_id") or ""): row
        for row in recommendation_rows
        if row.get("requirement_id")
    }

    eligibility_rows = [
        classify_response_truth_eligibility(
            row,
            rec_by_id.get(str(row.get("requirement_id") or "")),
        )
        for row in projection_rows
    ]

    ids = [str(row.get("requirement_id") or "") for row in eligibility_rows]
    counts = Counter(str(row.get("eligibility_class") or BLOCKED) for row in eligibility_rows)

    contract_rows = [row for row in eligibility_rows if row["eligibility_class"] == ELIGIBLE_CONTRACT]
    human_rows = [row for row in eligibility_rows if row["eligibility_class"] == ELIGIBLE_HUMAN]
    blocked_rows = [row for row in eligibility_rows if row["eligibility_class"] == BLOCKED]
    machine_rows = [row for row in eligibility_rows if row.get("machine_recommendation")]

    supersession_ok = True
    if supersession_verification is not None:
        supersession_ok = (
            supersession_verification.get("status") == "PASS_POST_TRANSACTION_VERIFICATION"
            and supersession_verification.get("all_checks_pass") is True
            and supersession_verification.get("response_truth_changed") is False
        )

    checks = {
        "source_projection_version_is_b21222": (
            str(projection.get("version") or "") == SOURCE_VERSION
        ),
        "project_matches": str(projection.get("project_id") or "") == str(project_id),
        "source_truth_unchanged": projection.get("truth_changed") is False,
        "source_human_review_not_created": projection.get("human_review_created") is False,
        "source_persistence_not_performed": projection.get("persistence_performed") is False,
        "source_cutover_not_approved": projection.get("cutover_approved") is False,
        "requirements_still_shadow_compare": str(read_mode or "") == "shadow_compare",
        "normal_pipeline_still_h31": (
            pipeline_contract.get("normal_pipeline_uses_h31") is True
            and str(pipeline_contract.get("promotion_version") or "") == PROMOTION_VERSION
        ),
        "semantic_unknown_count_zero": int(projection.get("semantic_unknown_count") or 0) == 0,
        "canonical_collision_count_zero": int(
            projection.get("canonical_identity_collision_count") or 0
        ) == 0,
        "one_projection_row_per_current_requirement": (
            len(projection_rows)
            == int(projection.get("current_requirement_count_before_semantic_gate") or 0)
            == len(set(ids))
            and "" not in ids
        ),
        "every_current_requirement_classified": len(eligibility_rows) == len(projection_rows),
        "no_blocked_unclassified_rows": not blocked_rows,
        "every_recommendation_maps_to_current_requirement": set(rec_by_id).issubset(set(ids)),
        "all_machine_rows_remain_non_truth": all(
            row.get("truth_effect_applied") is False
            and row.get("persistence_performed") is False
            and row.get("human_review_created") is False
            for row in machine_rows
        ),
        "contract_verified_rows_have_governed_evidence": all(
            row.get("provenance_contract") == "governed_response_contract+evidence"
            and row.get("future_truth_target_state") == "verified_response"
            and row.get("requires_explicit_human_decision") is False
            for row in contract_rows
        ),
        "machine_confirm_rows_require_explicit_human_decision": all(
            row.get("provenance_contract")
            == "explicit_human_decision+candidate_snapshot+evidence+machine_recommendation"
            and row.get("future_truth_target_state") == "human_confirmed_response"
            and row.get("requires_explicit_human_decision") is True
            for row in human_rows
        ),
        "no_machine_row_is_auto_promoted": all(
            row.get("future_truth_target_state") != "verified_response"
            for row in machine_rows
        ),
        "supersession_verifier_still_passes_when_applicable": supersession_ok,
    }

    failed = [key for key, value in checks.items() if not value]
    count_map = {key: int(counts.get(key, 0)) for key in ELIGIBILITY_ORDER}

    return {
        "version": VERSION,
        "project_id": project_id,
        "project_label": PROJECTS.get(project_id),
        "status": (
            "PASS_RESPONSE_TRUTH_ELIGIBILITY_SHADOW"
            if not failed
            else "BLOCKED_RESPONSE_TRUTH_ELIGIBILITY_SHADOW"
        ),
        "all_checks_pass": not failed,
        "failed_checks": failed,
        "checks": checks,
        "current_requirement_count": len(projection_rows),
        "recommendation_queue_count": len(recommendation_rows),
        "eligibility_counts": count_map,
        "contract_verified_count": len(contract_rows),
        "human_confirmation_candidate_count": len(human_rows),
        "blocked_count": len(blocked_rows),
        "eligibility_rows": eligibility_rows,
        "response_truth_changed": False,
        "human_review_created": False,
        "persistence_performed": False,
        "writes_performed": False,
        "cutover_approved": False,
        "machine_recommendation_is_truth": False,
    }


def run_response_truth_eligibility_shadow(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    project_id = str(project_id or "")
    if project_id not in PROJECTS:
        raise ValueError(f"B2.14 unsupported Golden project: {project_id}")

    state = get_cutover_state(client, project_id, "requirements")
    pipeline_contract = requirement_reconciliation_contract()
    projection = run_b21222(client, project_id=project_id).to_dict()

    supersession_verification = None
    if _latest_completed_supersession_run(client, project_id) is not None:
        supersession_verification = verify_supersession(client, project_id=project_id)

    return build_response_truth_eligibility_shadow(
        project_id=project_id,
        projection=projection,
        read_mode=str(state.get("read_mode") or ""),
        pipeline_contract=pipeline_contract,
        supersession_verification=supersession_verification,
    )
