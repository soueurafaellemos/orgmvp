from pathlib import Path

from project_requirement_semantic_extractor import _classify, _discover_requirement_atoms, _observation_identity, _looks_like_unanswered_form_prompt, _legacy_recall_requirements
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


def test_unanswered_briefing_question_is_not_requirement():
    text = "Qual mensagem principal precisa ser transmitida: (O que as pessoas devem sentir, entender e lembrar após a ação)"
    assert _looks_like_unanswered_form_prompt(text) is True
    assert _discover_requirement_atoms(text) == []


def test_substantive_answer_after_form_label_is_not_blocked_as_template():
    text = "Qual mensagem principal precisa ser transmitida: Conhecer ambas as marcas e atributos"
    assert _looks_like_unanswered_form_prompt(text) is False


def test_numeric_form_prompt_parenthetical_only_is_not_requirement():
    text = "Números: (Quais são os números ou expectativa que o cliente quer alcançar com esse projeto?)"
    assert _looks_like_unanswered_form_prompt(text) is True
    assert _discover_requirement_atoms(text) == []


def test_legacy_template_prompt_is_no_domain_context():
    kind, role, occurrence_role = _classify(
        {"title": "Qual mensagem principal precisa ser transmitida: (O que as pessoas devem sentir após a ação)", "requirement_type": "other", "mandatory": True, "attributes": {}},
        "Qual mensagem principal precisa ser transmitida: (O que as pessoas devem sentir após a ação)",
    )
    assert (kind, role, occurrence_role) == ("context_signal", "form_prompt", "context")


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


def test_c022_sql_form_prompt_truth_and_lifecycle_contract():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_2C0_2_2_TEMPLATE_PROMPT_GUARD.sql").read_text(encoding="utf-8").casefold()
    assert "'form_prompt'" in sql
    assert "status='superseded'" in sql
    assert "set status='inactive'" in sql
    assert "status='active'" in sql
    assert "delete from public.project_requirements" not in sql
    assert "delete from public.semantic_observations" not in sql


def test_c023_legacy_recall_route_excludes_prior_evidence_led_identities():
    rows = [
        {"id": "legacy-domain", "legacy_source_id": "legacy-row", "title": "Legacy"},
        {"id": "evidence-led", "legacy_source_id": None, "title": "Evidence led", "attributes": {"origin": "evidence_led_v2872c0_2"}},
        {"id": "manual", "legacy_source_id": None, "title": "Manual"},
    ]
    out = _legacy_recall_requirements(rows)
    assert [row["id"] for row in out] == ["legacy-domain"]


def test_c023_sql_legacy_truth_lookup_is_identity_isolated():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_2C0_2_3_RERUN_ISOLATION_TRUTH_FIX.sql").read_text(encoding="utf-8").casefold()
    truth = sql.split("create or replace view public.project_requirement_truth_status", 1)[1].split("create or replace view public.project_requirement_reconciliation_status", 1)[0]
    assert "b.legacy_source_id is not null" in truth
    assert "=b.legacy_source_id::text" in truth
    assert "coalesce(b.legacy_source_id::text,''), b.id::text" not in truth
    assert "e.legacy_source_id is not null" in truth
    assert "=e.legacy_source_id::text" in truth
    assert "truth_state in ('verified','human_confirmed','review_required')" in sql
