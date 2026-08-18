from pathlib import Path

from project_requirement_semantic_extractor import _classify, _discover_requirement_atoms, _observation_identity
from project_requirement_reconciliation import build_requirement_reconciliation_plan


PROJECT_ID = "00000000-0000-0000-3000-000000000001"
REQ_ID = "00000000-0000-0000-1000-000000000001"
ENTITY_ID = "00000000-0000-0000-2000-000000000001"
EVIDENCE_ID = "00000000-0000-0000-7000-000000000001"
ASSET_ID = "00000000-0000-0000-6000-000000000001"


def test_existing_provenance_does_not_change_platform_scope_semantics():
    kind, role, occurrence_role = _classify(
        {"title": "Reels", "requirement_type": "deliverable", "mandatory": True, "attributes": {}},
        "Adequação à Plataforma:\nCuradoria visual\nReels\nStories",
    )
    assert kind == "scope_signal"
    assert role in {"channel_scope", "platform_scope"}
    assert occurrence_role == "scope"


def test_product_focus_child_is_attribute_not_requirement():
    kind, role, occurrence_role = _classify(
        {"title": "Kit de lentes destacáveis", "requirement_type": "deliverable", "mandatory": True, "attributes": {}},
        "Foco do Produto\nSmartphone Ultra\nKit de lentes destacáveis\nModo profissional avançado",
    )
    assert (kind, role, occurrence_role) == ("attribute_signal", "product_attribute", "attribute")


def test_filename_reference_cannot_be_requirement_truth():
    kind, role, occurrence_role = _classify(
        {"title": "Project_Acceptance_Report_EN.pptx", "requirement_type": "mandatory", "mandatory": True, "attributes": {}},
        "Relatório pós-evento contendo insights e aprendizados, seguindo o modelo Project_Acceptance_Report_EN.pptx",
    )
    assert (kind, role, occurrence_role) == ("reference_signal", "reference_signal", "reference")


def test_evidence_first_recovers_explicit_obligation_missing_from_legacy_inventory():
    atoms = _discover_requirement_atoms(
        "Ativações e Experiências por Plataforma:\nÉ necessário criar 4 ativações imersivas, cada uma customizada para uma plataforma social específica:"
    )
    names = [row["name"] for row in atoms]
    assert any("4 ativações imersivas" in name for name in names)


def test_suggestion_is_not_auto_promoted_but_negative_exclusion_is_requirement():
    suggestion = _discover_requirement_atoms("Vale sugerirmos também um presskit para convidados especiais.")
    exclusion = _discover_requirement_atoms("Não é necessário orçarmos mestre de cerimônias para este evento.")
    assert suggestion == []
    assert len(exclusion) == 1
    assert exclusion[0]["polarity"] == "negative"


def test_obligation_container_atomizes_child_bullets_and_skips_reference_file():
    atoms = _discover_requirement_atoms(
        "A proposta deverá contemplar métricas e mecanismos de acompanhamento para:\n"
        "- Controle de presença e participação qualificada;\n"
        "- Pesquisa de satisfação ao final do evento;\n"
        "- Relatório pós-evento contendo insights e recomendações;\n"
        "Project_Acceptance_Report_EN.pptx"
    )
    names = [row["name"] for row in atoms]
    assert any("Controle de presença" in name for name in names)
    assert any("Pesquisa de satisfação" in name for name in names)
    assert any("Relatório pós-evento" in name for name in names)
    assert not any(".pptx" in name for name in names)


def test_observation_identity_is_role_independent_for_reclassification():
    a = _observation_identity(
        project_id=PROJECT_ID,
        evidence_id=EVIDENCE_ID,
        observed_name="Stories",
        origin_route="legacy_recall",
        legacy_requirement_id=REQ_ID,
    )
    b = _observation_identity(
        project_id=PROJECT_ID,
        evidence_id=EVIDENCE_ID,
        observed_name="Stories",
        origin_route="legacy_recall",
        legacy_requirement_id=REQ_ID,
    )
    assert a == b


def test_legacy_and_evidence_first_routes_converge_to_one_occurrence():
    existing = [{
        "id": REQ_ID,
        "entity_id": ENTITY_ID,
        "legacy_source_id": "00000000-0000-0000-4000-000000000001",
        "title": "Criar quatro ativações imersivas",
        "description": "Criar quatro ativações imersivas para plataformas sociais.",
        "requirement_type": "deliverable",
    }]

    base = {
        "source_asset_id": ASSET_ID,
        "evidence_unit_id": EVIDENCE_ID,
        "observed_type": "other",
        "occurrence_phase": "briefing",
        "semantic_role": "requirement_candidate",
        "model_confidence": 0.98,
        "source_authority_score": 0.88,
    }
    observations = [
        {
            **base,
            "id": "00000000-0000-0000-5000-000000000001",
            "observed_name": "Criar quatro ativações imersivas",
            "attributes": {
                "requirement_id": REQ_ID,
                "legacy_requirement_id": existing[0]["legacy_source_id"],
                "evidence_text": "É necessário criar quatro ativações imersivas.",
            },
        },
        {
            **base,
            "id": "00000000-0000-0000-5000-000000000002",
            "observed_name": "Criar quatro ativações imersivas",
            "attributes": {
                "requirement_id": None,
                "legacy_requirement_id": None,
                "evidence_text": "É necessário criar quatro ativações imersivas.",
            },
        },
    ]
    plan = build_requirement_reconciliation_plan(PROJECT_ID, observations, existing)
    assert len(plan["occurrences"]) == 1
    assert len(plan["evidence_links"]) == 1


def test_c02_sql_truth_gate_and_supersession_contract():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_2C0_2_EVIDENCE_FIRST_REQUIREMENT_RECONCILIATION.sql").read_text(encoding="utf-8").casefold()
    truth = sql.split("create or replace view public.project_requirement_truth_status", 1)[1].split("create or replace view public.project_requirement_reconciliation_status", 1)[0]
    assert "when e.has_current_occurrence then 'verified'" in truth
    assert "when e.has_direct_domain_evidence" not in truth
    assert "legacy_explanation_status = 'no_domain_object'" in truth
    assert "status='superseded'" in sql
    assert "lifecycle_status='superseded'" in sql
    assert "empty observation bundle blocked" in sql
    assert "pg_catalog.sha256" in sql
    assert "delete from public.project_requirements" not in sql
