from types import SimpleNamespace

from project_requirement_human_response_adjudication_contract import (
    build_human_adjudication_queue,
    build_human_adjudication_package,
    DECISION_CONFIRM_RESPONSE,
    DECISION_PARTIAL_RESPONSE,
    DECISION_REJECT_MATCH,
    DECISION_DEFER,
)


def projection(rows, project_id="p1"):
    return SimpleNamespace(
        project_id=project_id,
        status="PASS_READ_ONLY_PROJECTION_WITH_REVIEW",
        total_requirements=len(rows),
        requirement_rows=rows,
    )


def review_row(req_id, status, *, evidence_id="e1", title="Requirement"):
    return {
        "requirement_id": req_id,
        "title": title,
        "requirement_type": "deliverable",
        "mandatory": True,
        "priority": "critical",
        "truth_status": "verified",
        "current_response_contract_status": "no_verified_response",
        "projected_response_status": status,
        "projected_reason": "reason",
        "review_origin": "recall",
        "current_response_evidence_count": 0,
        "current_response_evidence": [],
        "recall_evidence_id": evidence_id,
        "recall_evidence_source": "proposal.pdf",
        "recall_evidence_locator": "page 10",
        "recall_candidate_text": "candidate evidence",
        "recall_gate_class": "HIGH_CONFIDENCE_REVIEW_CANDIDATE",
        "recall_obligation_atom_coverage": 1.0,
        "recall_title_anchor_coverage": 0.5,
        "recall_requirement_atoms": "a | b",
        "recall_shared_atoms": "a | b",
        "recall_missing_atoms": "",
        "recall_missing_hard_atoms": "",
    }


def test_queue_contains_only_review_statuses():
    rows = [
        review_row("r1", "response_review_high_confidence"),
        review_row("r2", "response_review_partial"),
        review_row("r3", "verified_response"),
        review_row("r4", "no_safely_verified_response"),
        review_row("r5", "false_positive_excluded"),
    ]
    q = build_human_adjudication_queue(project_id="p1", projection=projection(rows))
    assert q.queue_count == 2
    assert q.high_confidence_count == 1
    assert q.partial_count == 1
    assert q.context_no_safe_response_count == 1
    assert q.context_false_positive_excluded_count == 1


def test_candidate_id_is_stable():
    row = review_row("r1", "response_review_high_confidence")
    q1 = build_human_adjudication_queue(project_id="p1", projection=projection([row]))
    q2 = build_human_adjudication_queue(project_id="p1", projection=projection([row]))
    assert q1.queue_rows[0]["candidate_id"] == q2.queue_rows[0]["candidate_id"]


def test_nothing_is_decided_by_default():
    q = build_human_adjudication_queue(
        project_id="p1",
        projection=projection([review_row("r1", "response_review_high_confidence")]),
    )
    package = build_human_adjudication_package(
        queue=q,
        reviewer="R",
        edited_rows=[{**q.queue_rows[0], "decision": "", "human_rationale": ""}],
        adjudicated_at_utc="2026-08-28T12:00:00+00:00",
    )
    assert package.package_status == "EMPTY_DRAFT"
    assert package.explicitly_decided_count == 0
    assert len(package.decision_rows) == 1
    assert package.decision_rows[0]["decision_explicit"] is False


def test_confirm_requires_reviewer_and_rationale():
    q = build_human_adjudication_queue(
        project_id="p1",
        projection=projection([review_row("r1", "response_review_high_confidence")]),
    )
    package = build_human_adjudication_package(
        queue=q,
        reviewer="",
        edited_rows=[{**q.queue_rows[0], "decision": DECISION_CONFIRM_RESPONSE, "human_rationale": "ok"}],
    )
    assert package.package_status == "INVALID_DRAFT"
    assert len(package.validation_errors) == 2


def test_complete_package_never_applies_truth_effect():
    q = build_human_adjudication_queue(
        project_id="p1",
        projection=projection([
            review_row("r1", "response_review_high_confidence"),
            review_row("r2", "response_review_partial", evidence_id="e2"),
        ]),
    )
    package = build_human_adjudication_package(
        queue=q,
        reviewer="Reviewer",
        edited_rows=[
            {**q.queue_rows[0], "decision": DECISION_CONFIRM_RESPONSE, "human_rationale": "Evidence answers the requirement."},
            {**q.queue_rows[1], "decision": DECISION_PARTIAL_RESPONSE, "human_rationale": "Only part is covered."},
        ],
        adjudicated_at_utc="2026-08-28T12:00:00+00:00",
    )
    assert package.package_status == "COMPLETE_REVIEW_PACKAGE"
    assert package.confirmed_count == 1
    assert package.partial_count == 1
    assert all(row["truth_effect_applied"] is False for row in package.decision_rows)
    assert all(row["persistence_performed"] is False for row in package.decision_rows)


def test_defer_is_valid_explicit_decision_without_rationale():
    q = build_human_adjudication_queue(
        project_id="p1",
        projection=projection([review_row("r1", "response_review_high_confidence")]),
    )
    package = build_human_adjudication_package(
        queue=q,
        reviewer="Reviewer",
        edited_rows=[{**q.queue_rows[0], "decision": DECISION_DEFER, "human_rationale": ""}],
    )
    assert package.package_status == "COMPLETE_REVIEW_PACKAGE"
    assert package.deferred_count == 1


def test_reject_is_decisive_and_requires_rationale():
    q = build_human_adjudication_queue(
        project_id="p1",
        projection=projection([review_row("r1", "response_review_high_confidence")]),
    )
    package = build_human_adjudication_package(
        queue=q,
        reviewer="Reviewer",
        edited_rows=[{**q.queue_rows[0], "decision": DECISION_REJECT_MATCH, "human_rationale": "Mismatch"}],
    )
    assert package.package_status == "COMPLETE_REVIEW_PACKAGE"
    assert package.rejected_count == 1


def test_project_mismatch_blocks_queue():
    try:
        build_human_adjudication_queue(
            project_id="p1",
            projection=projection([], project_id="p2"),
        )
    except ValueError:
        return
    assert False, "expected project mismatch ValueError"
