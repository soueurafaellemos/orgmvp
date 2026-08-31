from project_requirement_semantic_eligibility import (
    classify_requirement_semantic_eligibility,
    derive_canonical_obligation_text,
)
import project_requirement_auto_adjudication_hardening as hardening
from project_requirement_auto_adjudication_hardening import (
    _core_obligation_guard,
    _augment_calibrated_atoms,
    _canonical_identity_collisions,
    harden_candidate,
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
    assert guard[0] == "recommend_reject"
    assert guard[2] == "physical_stage_led_not_jointly_supported"


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


def test_persisted_h3_no_domain_veto_beats_newer_requirement_candidate_observation():
    ok, reason, role = classify_requirement_semantic_eligibility(
        {
            "id": "legacy-storytelling",
            "truth_state": "verified",
            "legacy_explanation_role": "platform_scope",
            "legacy_explanation_status": "no_domain_object",
            "legacy_explanation_action": "attach_scope",
        },
        {
            "semantic_role": "requirement_candidate",
            "status": "reconciled",
            "resolution_action": "attach_requirement_occurrence",
        },
    )
    assert ok is False
    assert reason == "excluded_legacy_no_domain_veto"
    assert role == "platform_scope"


def test_human_confirmed_can_override_machine_no_domain_veto():
    ok, reason, role = classify_requirement_semantic_eligibility(
        {
            "id": "human-corrected",
            "truth_state": "human_confirmed",
            "legacy_explanation_role": "example_signal",
            "legacy_explanation_status": "no_domain_object",
            "legacy_explanation_action": "preserve_example",
        },
        {
            "semantic_role": "requirement_candidate",
            "status": "reconciled",
        },
    )
    assert ok is True
    assert reason == "eligible_human_confirmed_override"
    assert role == "requirement_candidate"


def test_plural_dietary_and_bilingual_qualifiers_are_explicit_hard_atoms():
    dietary = _augment_calibrated_atoms(
        "Considerar um A&B com opções veganas e vegetarianas.",
        "Food & beverage service with water and soda.",
        {
            "b210_class": "PARTIAL_OBLIGATION_COVERAGE",
            "requirement_atoms": "food_beverage | options",
            "candidate_atoms": "food_beverage",
        },
    )
    assert "vegan" in dietary["requirement_atoms"]
    assert "vegetarian" in dietary["requirement_atoms"]
    assert "vegan" in dietary["missing_hard_atoms"]
    assert "vegetarian" in dietary["missing_hard_atoms"]

    bilingual = _augment_calibrated_atoms(
        "O local deve contemplar promotores bilingues.",
        "Promotional staff will assist guests.",
        {
            "b210_class": "PARTIAL_OBLIGATION_COVERAGE",
            "requirement_atoms": "promoter",
            "candidate_atoms": "promoter",
        },
    )
    assert "bilingual" in bilingual["requirement_atoms"]
    assert "bilingual" in bilingual["missing_hard_atoms"]


def test_direct_payment_atom_handles_real_briefing_phrase():
    out = _augment_calibrated_atoms(
        "Devemos considerar em orçamento que o pagamento será realizado diretamente pela JOVI.",
        "Food & beverage service.",
        {
            "b210_class": "HIGH_CONFIDENCE_REVIEW_CANDIDATE",
            "requirement_atoms": "budget | food_beverage",
            "candidate_atoms": "food_beverage",
        },
    )
    assert "direct_payment" in out["requirement_atoms"]
    assert "direct_payment" in out["missing_hard_atoms"]
    assert out["b210_class"] == "PARTIAL_OBLIGATION_COVERAGE"


def test_specific_direct_payment_reason_beats_generic_financial_reason(monkeypatch):
    def fake_base(row):
        out = dict(row)
        out.update({
            "machine_recommendation": "recommend_reject",
            "machine_confidence": 0.99,
            "machine_rule_id": "missing_core_direct_payment",
            "machine_rationale": "specific direct payment",
        })
        return out
    monkeypatch.setattr(hardening, "_b2121_recommend_candidate", fake_base)

    row = {
        "requirement_title": "Pagamento direto",
        "canonical_obligation_text": (
            "Devemos considerar em orçamento que o pagamento será realizado diretamente pela JOVI."
        ),
        "evidence_text": "Food & beverage service with pão de queijo.",
        "projected_response_status": "response_review_partial",
        "obligation_atom_coverage": 0.25,
        "title_anchor_coverage": 0.0,
        "requirement_atoms": "budget | direct_payment | food_beverage",
        "shared_atoms": "food_beverage",
        "missing_atoms": "budget | direct_payment",
        "missing_hard_atoms": "direct_payment",
    }
    result = harden_candidate(row)
    assert result["machine_recommendation"] == "recommend_reject"
    assert result["machine_rule_id"] == "missing_core_direct_payment"


def test_specific_recap_video_reason_beats_generic_financial_reason(monkeypatch):
    def fake_base(row):
        out = dict(row)
        out.update({
            "machine_recommendation": "recommend_reject",
            "machine_confidence": 0.99,
            "machine_rule_id": "missing_core_recap_video",
            "machine_rationale": "specific recap video",
        })
        return out
    monkeypatch.setattr(hardening, "_b2121_recommend_candidate", fake_base)

    row = {
        "requirement_title": "Vídeo Memória",
        "canonical_obligation_text": (
            "Vídeo Memória: incluir cotação para vídeo resumo do evento nos formatos Horizontal e Vertical."
        ),
        "evidence_text": "The venue features photography, video and interactive works.",
        "projected_response_status": "response_review_partial",
        "obligation_atom_coverage": 0.2,
        "title_anchor_coverage": 0.0,
        "requirement_atoms": "budget | recap_video | horizontal | vertical | video",
        "shared_atoms": "video",
        "missing_atoms": "budget | recap_video | horizontal | vertical",
        "missing_hard_atoms": "recap_video | horizontal | vertical",
    }
    result = harden_candidate(row)
    assert result["machine_recommendation"] == "recommend_reject"
    assert result["machine_rule_id"] == "missing_core_recap_video"


def test_market_challenge_is_not_experience_capability_response():
    guard = _core_obligation_guard(
        (
            "A experiência deve demonstrar como o smartphone com câmera avançada é capaz "
            "de gerar imagens de nível profissional com facilidade."
        ),
        (
            "Brazil's smartphone market is highly competitive. Our challenge is to show "
            "consumers that smartphones stand out through advanced technology and camera capabilities."
        ),
    )
    assert guard is not None
    assert guard[0] == "recommend_reject"
    assert guard[2] == "missing_core_experience_capability_relation"


def test_same_canonical_obligation_is_reported_as_identity_collision_without_merge():
    rows = [
        {
            "id": "r1",
            "title": "Co-investimento truncado",
            "canonical_obligation_text": "Viabilizar parceria de co-investimento.",
        },
        {
            "id": "r2",
            "title": "Viabilizar parceria de co-investimento.",
            "canonical_obligation_text": "Viabilizar parceria de co-investimento.",
        },
    ]
    collisions = _canonical_identity_collisions(rows)
    assert len(collisions) == 1
    assert collisions[0]["requirement_ids"] == ["r1", "r2"]
    assert collisions[0]["auto_merge_performed"] is False
    assert collisions[0]["truth_effect_blocked"] is True
