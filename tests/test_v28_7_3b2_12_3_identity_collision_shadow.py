from project_requirement_identity_collision_shadow import (
    build_identity_collision_shadow_from_rows,
)


CANON = (
    "Utilizar os conceitos apresentados para viabilizar parcerias de co-investimento "
    "(patrocínio e compartilhamento de verba), além de impulsionar conteúdo orgânico "
    "e pago com KOLs durante o lançamento."
)


def _row(
    rid,
    title,
    *,
    source,
    confidence=1.0,
    truth_state="verified",
    origin=None,
    legacy_source_id=None,
    mandatory=True,
    requirement_type="budget",
):
    attrs = {}
    if origin:
        attrs["origin"] = origin
    return {
        "id": rid,
        "title": title,
        "truth_state": truth_state,
        "semantic_role_current": "requirement_candidate",
        "canonical_obligation_text": CANON,
        "canonical_obligation_source": source,
        "canonical_obligation_confidence": confidence,
        "attributes": attrs,
        "legacy_source_id": legacy_source_id,
        "mandatory": mandatory,
        "requirement_type": requirement_type,
        "priority": "critical" if mandatory else "high",
    }


def test_no_collision_is_pass():
    report = build_identity_collision_shadow_from_rows(
        project_id="p",
        eligible_rows=[
            _row(
                "r1",
                "Obrigação única",
                source="semantic_observation.source_atom",
                origin="evidence_led_v2872c0_2",
            )
        ],
        occurrence_rows=[],
    )
    assert report.collision_count == 0
    assert report.status == "PASS_NO_CANONICAL_IDENTITY_COLLISIONS"


def test_jovi_shape_prefers_evidence_led_full_identity_without_merging():
    legacy = _row(
        "legacy",
        (
            "Utilizar os conceitos apresentados para viabilizar parcerias de "
            "co-investimento (patrocínio e compartilhamento de verba), além de "
            "impulsionar conteúdo orgânico e pago com KOLs dura"
        ),
        source="current_evidence.source_clause",
        confidence=0.995,
        legacy_source_id="legacy-source",
        mandatory=False,
        requirement_type="deliverable",
    )
    evidence_led = _row(
        "evidence",
        CANON,
        source="semantic_observation.source_atom",
        confidence=1.0,
        origin="evidence_led_v2872c0_2",
        mandatory=True,
        requirement_type="budget",
    )
    occurrences = [
        {
            "requirement_id": "legacy",
            "legacy_requirement_id": "legacy-source",
            "lifecycle_status": "active",
        },
        {
            "requirement_id": "evidence",
            "legacy_requirement_id": None,
            "lifecycle_status": "active",
        },
    ]
    report = build_identity_collision_shadow_from_rows(
        project_id="p",
        eligible_rows=[legacy, evidence_led],
        occurrence_rows=occurrences,
        raw_requirement_rows=[legacy, evidence_led],
    )
    assert report.collision_count == 1
    assert report.ready_collision_count == 1
    plan = report.plans[0]
    assert plan.resolution_status == "ready_for_transactional_resolution"
    assert plan.proposed_survivor_id == "evidence"
    assert plan.proposed_superseded_ids == ("legacy",)
    assert "mandatory" in plan.metadata_conflicts
    assert "requirement_type" in plan.metadata_conflicts
    assert plan.auto_merge_performed is False
    assert plan.persistence_performed is False


def test_human_confirmed_identity_has_absolute_shadow_precedence():
    machine = _row(
        "machine",
        CANON,
        source="semantic_observation.source_atom",
        origin="evidence_led_v2872c0_2",
    )
    human = _row(
        "human",
        CANON,
        source="current_evidence.source_clause",
        truth_state="human_confirmed",
        legacy_source_id="legacy-human",
    )
    report = build_identity_collision_shadow_from_rows(
        project_id="p",
        eligible_rows=[machine, human],
        occurrence_rows=[],
        raw_requirement_rows=[machine, human],
    )
    assert report.plans[0].proposed_survivor_id == "human"
    assert report.plans[0].resolution_status == "ready_for_transactional_resolution"


def test_two_human_confirmed_identities_require_review():
    a = _row("a", CANON, source="semantic_observation.source_atom", truth_state="human_confirmed")
    b = _row("b", CANON, source="semantic_observation.source_atom", truth_state="human_confirmed")
    report = build_identity_collision_shadow_from_rows(
        project_id="p",
        eligible_rows=[a, b],
        occurrence_rows=[],
        raw_requirement_rows=[a, b],
    )
    assert report.review_required_count == 1
    assert report.plans[0].proposed_survivor_id is None
    assert report.plans[0].resolution_status == "review_required_multiple_human_confirmed_identities"


def test_equal_machine_provenance_requires_review():
    a = _row(
        "a",
        CANON,
        source="semantic_observation.source_atom",
        origin="evidence_led_v2872c0_2",
    )
    b = _row(
        "b",
        CANON,
        source="semantic_observation.source_atom",
        origin="evidence_led_v2872c0_2",
    )
    report = build_identity_collision_shadow_from_rows(
        project_id="p",
        eligible_rows=[a, b],
        occurrence_rows=[],
        raw_requirement_rows=[a, b],
    )
    assert report.review_required_count == 1
    assert report.plans[0].resolution_status == "review_required_insufficient_provenance_margin"
    assert report.plans[0].auto_merge_performed is False


def test_semantically_ineligible_collision_is_blocked():
    a = _row("a", CANON, source="semantic_observation.source_atom")
    b = _row("b", CANON, source="semantic_observation.source_atom")
    b["semantic_role_current"] = "platform_scope"
    report = build_identity_collision_shadow_from_rows(
        project_id="p",
        eligible_rows=[a, b],
        occurrence_rows=[],
        raw_requirement_rows=[a, b],
    )
    assert report.blocked_collision_count == 1
    assert report.plans[0].resolution_status == "blocked_non_exact_or_semantically_ineligible_collision"
