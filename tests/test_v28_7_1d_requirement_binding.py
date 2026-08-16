from project_domain_normalization import (
    _direct_commercial_process_evidence,
    _evidence_for_requirement,
)


def _ctx(evidence):
    return {
        "briefing_document_by_id": {"brief": {
            "content_sha256": "sha",
            "objective": "Criar a Casa Chambinho como experiência proprietária.",
            "audience": "Pais de 30 a 45 anos e crianças de 2 a 12 anos, classes A/B; público de 6 a 8 mil pessoas.",
            "budget_amount": 400000,
        }},
        "asset_by_sha": {"sha": {"id": "asset"}},
        "evidence_by_asset": {"asset": evidence},
    }


def test_audience_requirement_binds_to_same_source_without_literal_title():
    evidence = [{
        "id": "audience", "unit_type": "paragraph", "ordinal": 4,
        "content_text": "Pais de 30 a 45 anos e crianças de 2 a 12 anos, classes A/B; público de 6 a 8 mil pessoas.",
    }]
    row = {
        "briefing_document_id": "brief", "requirement_type": "audience",
        "title": "Público-alvo", "description": "Considerar o perfil de público informado no briefing.",
    }
    asset_id, match = _evidence_for_requirement(row, **_ctx(evidence))
    assert asset_id == "asset"
    assert match and match["id"] == "audience"


def test_objective_requirement_binds_from_typed_briefing_field():
    evidence = [{
        "id": "objective", "unit_type": "paragraph", "ordinal": 2,
        "content_text": "Criar a Casa Chambinho como experiência proprietária.",
    }]
    row = {
        "briefing_document_id": "brief", "requirement_type": "objective",
        "title": "Objetivo principal", "description": "Materializar o objetivo central da marca.",
    }
    _asset_id, match = _evidence_for_requirement(row, **_ctx(evidence))
    assert match and match["id"] == "objective"


def test_budget_requirement_binds_number_but_does_not_infer_operator():
    evidence = [{
        "id": "budget", "unit_type": "paragraph", "ordinal": 6,
        "content_text": "BUDGET: R$ 400.000",
    }]
    row = {
        "briefing_document_id": "brief", "requirement_type": "budget",
        "title": "Respeitar o budget informado", "description": "Budget identificado no briefing.",
    }
    _asset_id, match = _evidence_for_requirement(row, **_ctx(evidence))
    assert match and match["id"] == "budget"
    # Quantitative operator semantics remain a V28.7.2 concern.
    code = __import__("pathlib").Path(__file__).parents[1].joinpath("project_domain_normalization.py").read_text(encoding="utf-8")
    assert "Quantitative parsing is V28.7.2. Do not invent it here." in code


def test_ambiguous_budget_support_fails_closed():
    evidence = [
        {"id": "a", "unit_type": "paragraph", "ordinal": 1, "content_text": "Budget R$ 400.000"},
        {"id": "b", "unit_type": "paragraph", "ordinal": 2, "content_text": "Orçamento R$ 400.000"},
    ]
    row = {
        "briefing_document_id": "brief", "requirement_type": "budget",
        "title": "Respeitar o budget informado", "description": "Budget identificado no briefing.",
    }
    _asset_id, match = _evidence_for_requirement(row, **_ctx(evidence))
    assert match is None


def test_non_competition_wording_can_ground_direct_process_rule():
    match = _direct_commercial_process_evidence(
        briefing_documents=[{"content_sha256": "sha"}],
        asset_by_sha={"sha": {"id": "asset"}},
        evidence_by_asset={"asset": [{
            "id": "competition", "unit_type": "paragraph", "ordinal": 3,
            "content_text": "CONCORRÊNCIA: NÃO.",
        }]},
    )
    assert match and match["id"] == "competition"
