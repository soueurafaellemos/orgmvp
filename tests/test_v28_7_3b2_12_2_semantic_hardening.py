from project_requirement_semantic_eligibility import (
    classify_requirement_semantic_eligibility,
    derive_canonical_obligation_text,
)
from project_requirement_auto_adjudication_hardening import (
    _core_obligation_guard,
)


def test_platform_scope_is_excluded_even_if_truth_is_verified():
    ok, reason, role = classify_requirement_semantic_eligibility(
        {"id": "r1", "truth_state": "verified"},
        {
            "semantic_role": "platform_scope",
            "status": "no_domain_object",
            "resolution_action": "attach_scope",
        },
    )
    assert ok is False
    assert reason == "excluded_no_domain_semantic_role"
    assert role == "platform_scope"


def test_example_signal_is_not_a_requirement():
    ok, reason, role = classify_requirement_semantic_eligibility(
        {"id": "r2", "truth_state": "verified"},
        {
            "semantic_role": "example_signal",
            "status": "no_domain_object",
            "resolution_action": "preserve_example",
        },
    )
    assert ok is False
    assert reason == "excluded_no_domain_semantic_role"
    assert role == "example_signal"


def test_explicit_requirement_role_remains_eligible():
    ok, reason, role = classify_requirement_semantic_eligibility(
        {"id": "r3", "truth_state": "verified"},
        {
            "semantic_role": "requirement_candidate",
            "status": "reconciled",
            "resolution_action": "attach_requirement_occurrence",
        },
    )
    assert ok is True
    assert reason == "eligible_explicit_requirement_role"
    assert role == "requirement_candidate"


def test_machine_verified_without_semantic_role_fails_closed():
    ok, reason, role = classify_requirement_semantic_eligibility(
        {"id": "r4", "truth_state": "verified"},
        None,
    )
    assert ok is False
    assert reason == "semantic_eligibility_unknown"
    assert role is None


def test_canonical_obligation_recovers_truncated_source_clause():
    title = (
        "A experiência deve demonstrar como o smartphone com câmera avançada "
        "mais compacto da categoria é cap"
    )
    full = (
        "A experiência deve demonstrar como o smartphone com câmera avançada mais "
        "compacto da categoria é capaz de registrar imagens em movimento sem perder qualidade."
    )
    canonical, source, confidence = derive_canonical_obligation_text(
        {"title": title},
        {
            "semantic_role": "requirement_candidate",
            "attributes": {
                "origin_route": "legacy_recall",
                "evidence_text": full,
            },
        },
    )
    assert canonical == full
    assert source == "current_evidence.source_clause"
    assert confidence >= 0.9


def test_source_atom_beats_display_title_without_using_description():
    canonical, source, confidence = derive_canonical_obligation_text(
        {
            "title": "Formato adequado à plataforma",
            "description": "texto amplo que não deve contaminar a obrigação",
        },
        {
            "semantic_role": "requirement_candidate",
            "attributes": {
                "origin_route": "evidence_first",
                "source_atom": "A gravação deve ser feita no formato horizontal.",
            },
        },
    )
    assert canonical == "A gravação deve ser feita no formato horizontal."
    assert source == "semantic_observation.source_atom"
    assert confidence >= 0.99


def test_travel_presskit_does_not_become_travel_product_activation_via_pr_activation():
    guard = _core_obligation_guard(
        "Uma das ativações deve ter temática de viagens conectada à experimentação de produto.",
        (
            "Guest communications, press kit delivery, and PR activation.\n"
            "We will create a travel-inspired press kit with luggage tag and passport holder."
        ),
    )
    assert guard is not None
    assert guard[0] == "recommend_reject"
    assert guard[2] == "travel_presskit_not_product_activation"


def test_food_service_is_not_partial_answer_to_budget_reduction():
    guard = _core_obligation_guard(
        "Checar em orçamento a verba de alimentação e diminuir os valores para evitar custos de $220.",
        "Food & beverage service with pão de queijo, water, soda and dessert.",
    )
    assert guard is not None
    assert guard[0] == "recommend_reject"
    assert guard[2] == "missing_core_financial_obligation"


def test_set_the_stage_does_not_satisfy_physical_stage_led():
    guard = _core_obligation_guard(
        "O local deve contemplar palco com grande estrutura de LED Screen.",
        (
            "It is time to unveil the products and set the stage for the big reveal.\n"
            "The screen sequence fades to black."
        ),
    )
    assert guard is not None
    assert guard[0] in {"recommend_reject", "recommend_partial"}
    assert guard[2] != "high_confidence_full_obligation"


def test_horizontal_platform_qualifier_is_hard():
    guard = _core_obligation_guard(
        "As gravações devem ser feitas em formato horizontal adequado à plataforma.",
        "Content creators will receive their content ready to post on social media.",
    )
    assert guard is not None
    assert guard[0] == "recommend_reject"
    assert guard[2] == "missing_core_platform_format_qualifier"


def test_explicit_budget_evidence_is_not_blocked_by_financial_guard():
    guard = _core_obligation_guard(
        "Checar em orçamento a verba de alimentação e reduzir os custos.",
        "Budget: food & beverage cost reduced to R$ 180 per guest.",
    )
    assert guard is None
