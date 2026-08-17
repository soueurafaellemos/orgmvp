from project_semantic_observations import (_explicit_proposal_activation_candidate, _file_analyst_mention_candidates, _phase_role, _report_candidates)


def test_report_candidates_preserve_execution_status_and_keep_untyped_items_out_of_solution_domain():
    reports = [{
        "report_file_id": "f1",
        "activation_results": [
            {"name": "Ativação A", "status": "Executado"},
            {"name": "Ativação B", "status": "Não executado"},
        ],
        "item_results": [
            {"item_name": "Garrafinhas", "outcome_status": "Executado"},
            {"item_name": "Oficina X", "item_type": "Ativação", "outcome_status": "Parcial"},
        ],
    }]
    rows = _report_candidates(reports)
    by_name = {row["name"]: row for row in rows}
    assert by_name["Ativação A"]["kind"] == "solution_candidate"
    assert by_name["Ativação A"]["observed_status"] == "executed"
    assert by_name["Ativação B"]["observed_status"] == "not_executed"
    assert by_name["Garrafinhas"]["kind"] == "material_mention"
    assert by_name["Garrafinhas"]["observed_status"] is None
    assert by_name["Oficina X"]["kind"] == "solution_candidate"
    assert by_name["Oficina X"]["observed_status"] == "partial"


def test_file_analyst_mentions_are_signals_only_for_solution_domain_types():
    entities = {
        "e1": {"id": "e1", "entity_type": "activation", "canonical_name": "Amarelinha", "confidence": 0.9},
        "e2": {"id": "e2", "entity_type": "strategy", "canonical_name": "Território X", "confidence": 0.9},
        "e3": {"id": "e3", "entity_type": "product", "canonical_name": "Petit Morango", "confidence": 0.9},
        "e4": {"id": "e4", "entity_type": "gift", "canonical_name": "Meias", "confidence": 0.9},
    }
    mentions = [
        {"entity_id": "e1", "evidence_unit_id": "u1", "mention_text": "Amarelinha", "mention_role": "file_analyst_entity"},
        {"entity_id": "e2", "evidence_unit_id": "u2", "mention_text": "Território X", "mention_role": "file_analyst_entity"},
        {"entity_id": "e3", "evidence_unit_id": "u3", "mention_text": "Petit Morango", "mention_role": "file_analyst_entity"},
        {"entity_id": "e4", "evidence_unit_id": "u4", "mention_text": "Meias", "mention_role": "file_analyst_entity"},
    ]
    rows = _file_analyst_mention_candidates(mentions, entities)
    assert {row["name"] for row in rows} == {"Amarelinha", "Meias"}


def test_source_role_aliases_map_to_semantic_lifecycle():
    assert _phase_role("proposal_presentation") == ("proposal", "proposal")
    assert _phase_role("final_presentation") == ("proposal", "proposal")
    assert _phase_role("post_event_report") == ("post_event", "result")
    assert _phase_role("briefing_original") == ("briefing", "mention")
    assert _phase_role("detailed_costs") == ("reference", "budget_reference")


def test_non_file_analyst_mentions_are_not_consumed_by_reconciler():
    entities = {"e1": {"id": "e1", "entity_type": "activation", "canonical_name": "Amarelinha"}}
    mentions = [{"entity_id": "e1", "evidence_unit_id": "u1", "mention_text": "Amarelinha", "mention_role": "cross_source_projection"}]
    assert _file_analyst_mention_candidates(mentions, entities) == []



def test_explicit_proposal_activation_page_creates_generic_candidate_without_platform_hardcode():
    row = _explicit_proposal_activation_candidate(
        "YOUTUBE — A CAMERA IN YOUR POCKET. ENDLESS STORIES "
        "YouTube is the go-to platform for long-form video. "
        "This activation will bring those possibilities to life. OPTION 1 A photo-ready installation."
    )
    assert row is not None
    assert row["name"] == "YOUTUBE activation"
    assert row["observed_type"] == "activation"


def test_explicit_proposal_space_with_options_can_be_activation_candidate():
    row = _explicit_proposal_activation_candidate(
        "KWAI — AUTHENTIC CONTENT. BUILT TO GO VIRAL. "
        "For this space, we will create a Brazil-inspired content corner. "
        "OPTION 1 A setting with a small table. OPTION 2 A poster-customization station."
    )
    assert row is not None
    assert row["name"] == "KWAI activation"


def test_generic_event_or_journey_heading_is_not_promoted_as_activation():
    assert _explicit_proposal_activation_candidate(
        "EVENT — PRODUCT REVEAL. This activation will begin after the plenary. OPTION 1."
    ) is None
