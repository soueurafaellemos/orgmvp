from types import SimpleNamespace

from project_requirement_auto_adjudication_completeness import (
    _completeness_scope,
    _evidence_proves_completeness,
    apply_completeness_guard,
)


def _base(rows):
    return SimpleNamespace(
        project_id="p1",
        status="PASS_SEMANTIC_HARDENING_READY",
        current_requirement_count_before_semantic_gate=2,
        semantic_eligible_requirement_count=2,
        semantic_excluded_no_domain_count=0,
        semantic_unknown_count=0,
        canonical_identity_collision_count=0,
        recommendation_rows=tuple(rows),
        semantic_excluded_rows=tuple(),
        canonical_identity_collision_rows=tuple(),
        projection_rows=tuple(),
    )


def _confirm(title, evidence, cid="old"):
    return {
        "project_id": "p1",
        "requirement_id": title[:8],
        "requirement_title": title,
        "canonical_obligation_text": title,
        "evidence_text": evidence,
        "candidate_id": cid,
        "machine_recommendation": "recommend_confirm",
        "machine_confidence": 0.94,
        "machine_rule_id": "high_confidence_full_obligation",
        "machine_rationale": "base confirm",
    }


def test_materials_open_set_quantifier_is_detected():
    scope = _completeness_scope(
        "Criar convite, STD, Reminder e todo o material proposto no projeto."
    )
    assert scope == "materials"


def test_named_assets_do_not_prove_all_materials():
    assert _evidence_proves_completeness(
        "materials",
        "Save the Date. Online invitation. Reminder.",
    ) is False


def test_explicit_all_materials_can_prove_completeness():
    assert _evidence_proves_completeness(
        "materials",
        "All proposed materials are included: Save the Date, Online invitation and Reminder.",
    ) is True


def test_false_confirm_is_downgraded_to_partial():
    base = _base([
        _confirm(
            "Materiais Gráficos: convite, STD, Reminder e todo o material proposto no projeto.",
            "Save the Date. Online invitation. Reminder.",
        ),
        _confirm(
            "O local deve contemplar: Espaço para plenária;",
            "EVENT receptivo túnel lounge plenária nichos de ativação.",
            cid="plenary",
        ),
    ])
    out = apply_completeness_guard(base)
    assert out.queue_count == 2
    assert out.recommend_confirm_count == 1
    assert out.recommend_partial_count == 1
    assert out.completeness_downgrade_count == 1

    materials = next(
        row for row in out.recommendation_rows
        if "Materiais Gráficos" in row["requirement_title"]
    )
    assert materials["machine_recommendation"] == "recommend_partial"
    assert materials["machine_rule_id"] == "unresolved_completeness_quantifier"
    assert materials["completeness_guard_applied"] is True

    plenary = next(
        row for row in out.recommendation_rows
        if "plenária" in row["requirement_title"]
    )
    assert plenary["machine_recommendation"] == "recommend_confirm"
    assert plenary["completeness_guard_applied"] is False


def test_existing_reject_is_never_promoted():
    row = _confirm(
        "Todos os convidados devem responder à pesquisa.",
        "Guests arrive and receive gifts.",
    )
    row["machine_recommendation"] = "recommend_reject"
    row["machine_rule_id"] = "missing_core_survey"
    base = _base([row])
    out = apply_completeness_guard(base)
    assert out.recommend_reject_count == 1
    assert out.completeness_downgrade_count == 0
    assert out.recommendation_rows[0]["machine_rule_id"] == "missing_core_survey"


def test_full_kit_quantifier_is_detected():
    assert _completeness_scope(
        "Os convidados devem testar todo o kit de acessórios."
    ) == "full_kit"


def test_universal_guest_quantifier_is_detected():
    assert _completeness_scope(
        "A plenária precisa ter visibilidade para todos os convidados."
    ) == "universal_guests"
