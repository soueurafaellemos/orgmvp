from pathlib import Path

from project_requirement_semantic_extractor import _classify, _discover_requirement_atoms, _observation_identity, _looks_like_unanswered_form_prompt, _legacy_recall_requirements
from project_requirement_reconciliation import build_requirement_reconciliation_plan, _semantic_gate
from project_requirement_identity import resolve_requirement_identity


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
    assert len(suggestion) == 1
    assert suggestion[0]["semantic_role"] == "suggestion_signal"
    assert suggestion[0]["mandatory"] is False
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


# V28.7.2C0.2.4 — Requirement Role & Binding Precision Gate

def test_c024_jovi_product_name_is_attribute_not_requirement():
    kind, role, occurrence_role = _classify(
        {"title": "JOVI X300 Ultra", "requirement_type": "other", "mandatory": True, "attributes": {}},
        "Foco do Produto\nJOVI X300 Ultra\nKit de lentes teleobjetivas destacáveis\nModo profissional avançado",
    )
    assert (kind, role, occurrence_role) == ("attribute_signal", "product_attribute", "attribute")


def test_c024_jovi_audience_fragment_is_context_not_requirement():
    kind, role, occurrence_role = _classify(
        {"title": "Frequentadores de festivais de música", "requirement_type": "other", "mandatory": True, "attributes": {}},
        "Público-Alvo Principal – X300 Ultra\nCriadores de conteúdo profissionais\nFrequentadores de festivais de música",
    )
    assert (kind, role, occurrence_role) == ("context_signal", "audience_context", "context")


def test_c024_jovi_platform_fit_fragment_is_scope_not_requirement():
    kind, role, occurrence_role = _classify(
        {"title": "Storytelling detalhado", "requirement_type": "deliverable", "mandatory": True, "attributes": {}},
        "Adequação à Plataforma - O YouTube é o ambiente ideal para:\nConteúdo de longa duração\nReviews técnicos aprofundados\nStorytelling detalhado",
    )
    assert (kind, role, occurrence_role) == ("scope_signal", "platform_scope", "scope")


def test_c024_jovi_example_after_como_is_example_signal():
    kind, role, occurrence_role = _classify(
        {"title": "Mini show ao vivo", "requirement_type": "other", "mandatory": True, "attributes": {}},
        "A experiência deve permitir testes em um ambiente dinâmico, como:\nMini show ao vivo\nPerformance com muito movimento",
    )
    assert (kind, role, occurrence_role) == ("reference_signal", "example_signal", "reference")


def test_c024_explicit_children_under_requirement_parent_remain_requirements():
    atoms = _discover_requirement_atoms(
        "A ativação deve explorar:\nLinhas arquitetônicas sofisticadas\nDesign urbano contemporâneo\nEspelhos conceituais\nIluminação premium para retratos"
    )
    roles = {row["name"]: row["semantic_role"] for row in atoms}
    assert any("Linhas arquitetônicas sofisticadas" in name and role == "requirement_candidate" for name, role in roles.items())


def test_c024_unconfirmed_presskit_is_suggestion_signal_not_requirement():
    atoms = _discover_requirement_atoms(
        "O cliente não nos confirmou em briefing, mas vale sugerirmos também o presskit para influenciadores e jornalistas pré-evento."
    )
    assert len(atoms) == 1
    assert atoms[0]["semantic_role"] == "suggestion_signal"
    assert atoms[0]["mandatory"] is False


def test_c024_consider_children_type_parameter_and_constraint_qualifier():
    atoms = _discover_requirement_atoms(
        "Considerar:\nTotal de participantes\nBuffer adicional de 10%"
    )
    by_role = {row["semantic_role"]: row["name"] for row in atoms}
    assert "parameter_signal" in by_role
    assert "constraint_qualifier" in by_role


def test_c024_evidence_first_timing_does_not_bind_to_mc_exclusion_description():
    existing = [{
        "id": "mc-id",
        "entity_id": "mc-entity",
        "title": "Não é necessário orçarmos MC para esse evento",
        "description": "Não é necessário orçarmos MC. É necessário desenharmos/sugerirmos o timming dessa apresentação no gancho final da plenária.",
        "requirement_type": "other",
    }]
    obs = {
        "observed_name": "É necessário desenharmos/sugerirmos o timming dessa apresentação",
        "observed_type": "deadline",
        "semantic_role": "requirement_candidate",
        "attributes": {"origin_route": "evidence_first"},
    }
    result = resolve_requirement_identity(obs, existing)
    assert result["action"] == "create_new"


def test_c024_constraint_family_can_use_narrow_description_support():
    existing = [{
        "id": "budget-id", "entity_id": "budget-entity",
        "title": "Restrição de verba e estrutura",
        "description": "Esse ano temos menos dinheiro que no ano passado e precisamos pensar uma casa com menos estrutura de cenografia.",
        "requirement_type": "budget",
    }]
    obs = {
        "observed_name": "Esse ano temos menos dinheiro que no ano passado, precisamos pensar em criar uma casa com menos estrutura de cenografia",
        "observed_type": "budget",
        "semantic_role": "requirement_candidate",
        "attributes": {"origin_route": "evidence_first"},
    }
    result = resolve_requirement_identity(obs, existing)
    assert result["action"] == "attach_existing"


def test_c024_two_pass_blocks_no_domain_legacy_identity_from_absorbing_current_obligation():
    existing = [{
        "id": REQ_ID, "entity_id": ENTITY_ID, "legacy_source_id": "legacy-product",
        "title": "JOVI X300 Ultra", "description": "É necessário criar uma ativação para JOVI X300 Ultra.", "requirement_type": "other",
    }]
    legacy_obs = {
        "id": "00000000-0000-0000-5000-000000000010", "source_asset_id": ASSET_ID, "evidence_unit_id": EVIDENCE_ID,
        "observed_name": "JOVI X300 Ultra", "observed_type": "other", "occurrence_phase": "briefing",
        "semantic_role": "product_attribute", "model_confidence": 0.99, "source_authority_score": 0.9,
        "attributes": {"origin_route": "legacy_recall", "legacy_requirement_id": "legacy-product", "requirement_id": REQ_ID, "evidence_text": "Foco do Produto: JOVI X300 Ultra"},
    }
    current_obs = {
        "id": "00000000-0000-0000-5000-000000000011", "source_asset_id": ASSET_ID, "evidence_unit_id": "00000000-0000-0000-7000-000000000011",
        "observed_name": "É necessário criar uma ativação para JOVI X300 Ultra", "observed_type": "other", "occurrence_phase": "briefing",
        "semantic_role": "requirement_candidate", "model_confidence": 0.99, "source_authority_score": 0.9,
        "attributes": {"origin_route": "evidence_first", "legacy_requirement_id": None, "requirement_id": None, "evidence_text": "É necessário criar uma ativação para JOVI X300 Ultra"},
    }
    plan = build_requirement_reconciliation_plan(PROJECT_ID, [legacy_obs, current_obs], existing)
    assert len(plan["requirements"]) == 1
    assert plan["requirements"][0]["id"] != REQ_ID


def test_c024_semantic_gate_is_fail_closed_on_observation_review():
    gate = _semantic_gate({
        "observations_open": 0,
        "observations_review_required": 3,
        "unexplained_legacy_shadow": 0,
        "conflicted": 0,
        "review_required": 0,
    })
    assert gate["pass"] is False
    assert gate["blockers"] == 3


def test_c024_sql_role_precision_and_fail_closed_contract():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_2C0_2_4_REQUIREMENT_ROLE_BINDING_PRECISION_GATE.sql").read_text(encoding="utf-8").casefold()
    for role in ("suggestion_signal", "example_signal", "parameter_signal", "constraint_qualifier"):
        assert role in sql
    assert "semantic_gate_blockers" in sql
    assert "semantic_gate_pass" in sql
    assert "28.7.2c0.2.4" in sql
    assert "delete from" not in sql
    assert "domain_primary" not in sql


def test_c024_audience_children_under_mandatory_alignment_parent_are_context():
    kind, role, occurrence_role = _classify(
        {"title": "Frequentadores de festivais de música", "requirement_type": "other", "mandatory": True, "attributes": {}},
        "Alinhamento Estratégico:\nA proposta deve estar fortemente conectada ao nosso público-alvo principal:\nCriadores de conteúdo\nFilmmakers\nFotógrafos\nFrequentadores de festivais de música\nUniverso da moda e lifestyle",
    )
    assert (kind, role, occurrence_role) == ("context_signal", "audience_context", "context")


def test_c024_evidence_first_preserves_example_children_without_promoting_them():
    atoms = _discover_requirement_atoms(
        "A experiência deve permitir que os convidados testem o kit em um ambiente dinâmico, como:\nMini show ao vivo\nPerformance com muito movimento"
    )
    roles = {row["name"]: row["semantic_role"] for row in atoms}
    assert roles["Mini show ao vivo"] == "example_signal"
    assert roles["Performance com muito movimento"] == "example_signal"
    assert any(role == "requirement_candidate" for role in roles.values())


# V28.7.2C0.2.4H1 — resolution-action contract / runtime hotfix

def test_c024h1_plan_exposes_blocked_existing_ids_for_diagnostics():
    existing = [{
        "id": REQ_ID, "entity_id": ENTITY_ID, "legacy_source_id": "legacy-product",
        "title": "JOVI X300 Ultra", "description": "Foco do Produto", "requirement_type": "other",
    }]
    legacy_obs = {
        "id": "00000000-0000-0000-5000-000000000099", "source_asset_id": ASSET_ID, "evidence_unit_id": EVIDENCE_ID,
        "observed_name": "JOVI X300 Ultra", "observed_type": "other", "occurrence_phase": "briefing",
        "semantic_role": "product_attribute", "model_confidence": 0.99, "source_authority_score": 0.9,
        "attributes": {"origin_route": "legacy_recall", "legacy_requirement_id": "legacy-product", "requirement_id": REQ_ID, "evidence_text": "Foco do Produto: JOVI X300 Ultra"},
    }
    plan = build_requirement_reconciliation_plan(PROJECT_ID, [legacy_obs], existing)
    assert plan["blocked_existing_ids"] == [REQ_ID]


def test_c024h1_sql_allows_all_no_domain_resolution_actions():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_2C0_2_4H1_RESOLUTION_ACTION_CONTRACT_HOTFIX.sql").read_text(encoding="utf-8").casefold()
    for action in (
        "preserve_context", "preserve_reference", "preserve_suggestion", "preserve_example",
        "attach_parameter", "attach_constraint_qualifier", "attach_scope", "attach_attribute",
        "attach_constraint", "create_requirement", "attach_requirement_occurrence",
    ):
        assert action in sql
    assert "delete from" not in sql
    assert "domain_primary" not in sql

# V28.7.2C0.2.4H2 — Structural Role Boundary Hotfix


def test_h2_mandatory_clause_with_suggestion_verb_remains_requirement():
    atoms = _discover_requirement_atoms(
        "É necessário desenharmos/sugerirmos o timming dessa apresentação no gancho final da plenária."
    )
    assert len(atoms) == 1
    assert atoms[0]["semantic_role"] == "requirement_candidate"
    assert atoms[0]["mandatory"] is True


def test_h2_pure_suggestion_still_remains_no_domain_signal():
    atoms = _discover_requirement_atoms(
        "Vale sugerirmos também o presskit para influenciadores e jornalistas pré-evento."
    )
    assert len(atoms) == 1
    assert atoms[0]["semantic_role"] == "suggestion_signal"
    assert atoms[0]["mandatory"] is False


def test_h2_example_parent_carries_across_evidence_unit_boundary():
    atoms = _discover_requirement_atoms(
        "Mini show ao vivo;",
        previous_text=(
            "Direcionamento criativo para a Agência: Criar um ambiente que simule um estúdio fotográfico profissional. "
            "A experiência deve permitir que os convidados testem o kit em um ambiente dinâmico, como:"
        ),
    )
    assert len(atoms) == 1
    assert atoms[0]["semantic_role"] == "example_signal"
    assert atoms[0]["mandatory"] is False


def test_h2_product_model_listed_as_target_of_mandatory_experience_is_attribute():
    kind, role, occurrence_role = _classify(
        {"title": "JOVI X300 Ultra", "requirement_type": "deliverable", "mandatory": True, "attributes": {}},
        (
            "Experience & Hands-On Lab: Após a revelação dos produtos, deverá existir uma área de exposição "
            "para testes práticos de: JOVI X300 Ultra; JOVI X300 FE; JOVI Buds Pro."
        ),
    )
    assert (kind, role, occurrence_role) == ("attribute_signal", "product_attribute", "attribute")


def test_h2_product_target_parent_carries_across_evidence_unit_boundary():
    atoms = _discover_requirement_atoms(
        "Smartphone Ultra;",
        previous_text="A área de experiência deverá existir para testes práticos de:",
    )
    assert len(atoms) == 1
    assert atoms[0]["semantic_role"] == "product_attribute"
    assert atoms[0]["mandatory"] is False
