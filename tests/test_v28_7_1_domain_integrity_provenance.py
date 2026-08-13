from pathlib import Path

from project_domain_normalization import (
    _confidence_from_legacy,
    _dedicated_outcome_authority,
    _evidence_for_cost_item,
    _item_status_outcome,
    _proposal_execution_status,
)


def test_execution_never_manufactures_approval():
    assert _proposal_execution_status({"item_status": "Executado"}) == ("unknown", "executed")
    assert _item_status_outcome("Executado") == ("execution_status", "executed")


def test_legacy_confirmation_is_not_explicit_human_review():
    _, client_authority, client_human = _confidence_from_legacy("client_confirmed")
    _, voe_authority, voe_human = _confidence_from_legacy("voe_confirmed")
    assert client_authority > voe_authority
    assert client_human is False
    assert voe_human is False



def test_dedicated_outcome_record_outranks_extracted_item_status_without_becoming_human_review():
    _, base, human = _confidence_from_legacy("incomplete")
    authority = _dedicated_outcome_authority({"information_source": "document"}, base)
    assert authority >= 0.82
    assert human is False

def test_cost_evidence_uses_sheet_and_row_locator_not_global_ordinal():
    row = {"cost_document_id": "doc-1", "source_sheet": "ORÇAMENTO", "source_row": 42}
    docs = {"doc-1": {"content_sha256": "sha"}}
    assets = {"sha": {"id": "asset-1"}}
    evidence = {
        "asset-1": [
            {"id": "wrong", "source_asset_id": "asset-1", "unit_type": "row", "ordinal": 42, "locator": {"sheet": "OUTRA", "row": 42}, "extraction_confidence": 1.0},
            {"id": "right", "source_asset_id": "asset-1", "unit_type": "row", "ordinal": 77, "locator": {"sheet": "ORÇAMENTO", "row": 42}, "extraction_confidence": 0.99},
        ]
    }
    asset_id, match = _evidence_for_cost_item(
        row,
        cost_document_by_id=docs,
        asset_by_sha=assets,
        evidence_by_asset=evidence,
    )
    assert asset_id == "asset-1"
    assert match["id"] == "right"


def test_sql_adds_transactionality_occurrences_provenance_and_governance():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1_DOMAIN_INTEGRITY_PROVENANCE.sql").read_text(encoding="utf-8")
    folded = sql.casefold()
    for table in (
        "project_solution_occurrences",
        "domain_object_evidence",
        "domain_object_governance",
        "project_domain_migration_state",
    ):
        assert f"create table if not exists public.{table}" in folded
    assert "apply_project_domain_normalization_v2871" in folded
    assert "migration_mode in ('legacy_shadow','domain_primary')" in folded
    assert "on delete restrict" in folded
    assert "where event_status = 'active'" in folded
    assert "delete from public.memory_" not in folded
    assert "drop table" not in folded


def test_sql_projects_solution_status_only_from_current_outcomes():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1_DOMAIN_INTEGRITY_PROVENANCE.sql").read_text(encoding="utf-8").casefold()
    assert "única projeção de status" in sql
    assert "from public.entity_current_outcomes eco" in sql
    assert "proposal_status = coalesce" in sql
    assert "execution_status = coalesce" in sql


def test_normalization_code_uses_rpc_and_strict_reads():
    code = (Path(__file__).parents[1] / "project_domain_normalization.py").read_text(encoding="utf-8")
    assert 'client.rpc(NORMALIZATION_RPC' in code
    assert "class DomainReadError" in code
    assert "def _strict_rows" in code
    assert "No write occurred before this point" in code
    # The old migration bug must stay gone.
    assert 'proposal = "approved"' not in code


def test_file_analyst_evidence_identity_is_locator_aware():
    code = (Path(__file__).parents[1] / "intelligence_graph_db.py").read_text(encoding="utf-8")
    assert "def _locator_hash" in code
    assert "target_locator = _safe(dict(unit.locator or {}))" in code
    assert '"supersedes_evidence_id": supersedes_id' in code
    # Read failure is no longer silently converted to [] inside _persist_evidence.
    block = code.split("def _persist_evidence", 1)[1].split("def _find_entity", 1)[0]
    assert "except Exception:\n            existing_rows = []" not in block


def test_bundle_preserves_identity_occurrences_and_evidence_without_execution_approval():
    from project_domain_normalization import _build_bundle, _validate_bundle

    project_id = "11111111-1111-1111-1111-111111111111"
    item_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    item_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    doc_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    req_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    brief_doc_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    cost_doc_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    cost_id = "99999999-9999-9999-9999-999999999999"
    data = {
        "project": {"id": project_id, "project_name": "Golden"},
        "project_mirror": None,
        "memory_items": [
            {"id": item_a, "project_id": project_id, "document_id": doc_id, "source_page": 3, "section_key": "activations", "title": "Jogo", "item_type": "Ativação", "item_status": "Proposto", "confidence": 0.9},
            {"id": item_b, "project_id": project_id, "document_id": doc_id, "source_page": 8, "section_key": "activations", "title": "Jogo", "item_type": "Ativação", "item_status": "Executado", "confidence": 0.95},
        ],
        "memory_documents": [{"id": doc_id, "content_sha256": "proposal-sha", "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "file_name": "proj.pptx", "document_status": "sent_to_client"}],
        "requirements": [{"id": req_id, "project_id": project_id, "briefing_document_id": brief_doc_id, "requirement_type": "objective", "title": "Conectar gerações", "source_quote": "conectar pais e filhos", "adherence_status": "not_assessed"}],
        "briefing_documents": [{"id": brief_doc_id, "content_sha256": "brief-sha"}],
        "cost_documents": [{"id": cost_doc_id, "content_sha256": "cost-sha", "currency": "BRL", "client_total": 100.0, "extraction_status": "pronto"}],
        "cost_items": [{"id": cost_id, "project_id": project_id, "cost_document_id": cost_doc_id, "source_sheet": "ORC", "source_row": 5, "item_name": "Jogo", "client_total": 100.0, "item_status": "included", "estimate_type": "quoted"}],
        "item_outcomes": [],
        "project_outcomes": [],
        "existing_solutions": [],
        "existing_requirements": [],
        "existing_financial_documents": [],
        "existing_financial_line_items": [],
        "existing_occurrences": [],
        "governance": [],
        "source_assets": [
            {"id": "12121212-1212-1212-1212-121212121212", "content_sha256": "proposal-sha"},
            {"id": "13131313-1313-1313-1313-131313131313", "content_sha256": "brief-sha"},
            {"id": "14141414-1414-1414-1414-141414141414", "content_sha256": "cost-sha"},
        ],
        "evidence_units": [
            {"id": "15151515-1515-1515-1515-151515151515", "source_asset_id": "12121212-1212-1212-1212-121212121212", "unit_type": "slide", "ordinal": 3, "locator": {"slide": 3}, "content_text": "Jogo proposto", "extraction_confidence": 0.99},
            {"id": "16161616-1616-1616-1616-161616161616", "source_asset_id": "12121212-1212-1212-1212-121212121212", "unit_type": "slide", "ordinal": 8, "locator": {"slide": 8}, "content_text": "Jogo executado", "extraction_confidence": 0.99},
            {"id": "17171717-1717-1717-1717-171717171717", "source_asset_id": "13131313-1313-1313-1313-131313131313", "unit_type": "paragraph", "ordinal": 2, "locator": {"paragraph_index": 2}, "content_text": "Precisamos conectar pais e filhos", "extraction_confidence": 0.99},
            {"id": "18181818-1818-1818-1818-181818181818", "source_asset_id": "14141414-1414-1414-1414-141414141414", "unit_type": "row", "ordinal": 20, "locator": {"sheet": "ORC", "row": 5}, "content_text": "Jogo 100", "extraction_confidence": 0.99},
        ],
    }
    bundle, warnings = _build_bundle(project_id, data)
    _validate_bundle(bundle, data)
    assert len(bundle["solutions"]) == 1
    assert len(bundle["solution_occurrences"]) == 2
    assert len(bundle["evidence_links"]) == 4
    solution_entity = bundle["solutions"][0]["entity_id"]
    solution_outcomes = [o for o in bundle["outcomes"] if o["entity_id"] == solution_entity]
    assert {o["outcome_type"] for o in solution_outcomes} == {"proposal_status", "execution_status"}
    assert not any(o["outcome_type"] == "proposal_status" and o["outcome_status"] == "approved" for o in solution_outcomes)
    assert any(o["outcome_type"] == "execution_status" and o["outcome_status"] == "executed" for o in solution_outcomes)
    assert warnings == []


def test_sql_enforces_field_level_authority_and_lifecycle_visibility():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1_DOMAIN_INTEGRITY_PROVENANCE.sql").read_text(encoding="utf-8").casefold()
    assert "nave_domain_field_locked" in sql
    assert "nave_merge_field_authority" in sql
    assert "field_authority = public.nave_merge_field_authority" in sql
    assert "review_status in ('confirmed','corrected','rejected')" in sql
    assert "g.lifecycle_status <> 'active'" in sql
    assert "coalesce(g.lifecycle_status,'active') = 'active'" in sql


def test_sql_uses_monotonic_null_safe_updates_for_existing_domain_knowledge():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1_DOMAIN_INTEGRITY_PROVENANCE.sql").read_text(encoding="utf-8").casefold()
    assert "coalesce(excluded.description, public.project_solution_instances.description)" in sql
    assert "coalesce(excluded.base_total, public.financial_documents.base_total)" in sql
    assert "coalesce(excluded.total_value, public.financial_line_items.total_value)" in sql
    assert "excluded.paid_by = 'unknown'" in sql
    assert "public.financial_line_items.cost_state in ('approved','contracted','invoiced','actual')" in sql


def test_evidence_writer_uses_locator_hash_fast_path_and_ordinal_compatibility_fallback():
    code = (Path(__file__).parents[1] / "intelligence_graph_db.py").read_text(encoding="utf-8")
    block = code.split("def _persist_evidence", 1)[1].split("def _find_entity", 1)[0]
    assert '.eq("locator_sha256", locator_hash)' in block
    assert '.eq("ordinal", unit.ordinal)' in block
    assert "exact locator equality remains the final identity check" in block
    assert "Collapse accidental duplicate-current rows" in block


def test_normalized_outcomes_are_versioned_to_supersede_pre_v2871_semantics():
    code = (Path(__file__).parents[1] / "project_domain_normalization.py").read_text(encoding="utf-8")
    assert "def _normalized_event_version_key" in code
    assert "|{DOMAIN_NORMALIZATION_VERSION}" in code
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1_DOMAIN_INTEGRITY_PROVENANCE.sql").read_text(encoding="utf-8").casefold()
    assert "superseded_by_outcome_id = v_domain_id" in sql
    assert "and event_status = 'active'" in sql


def test_ambiguous_fragment_evidence_is_not_bound_by_confidence_only():
    from project_domain_normalization import _conservative_evidence_match

    candidates = [
        {"id": "a", "unit_type": "slide", "locator": {"slide": 5, "shape_index": 1}, "content_text": "Jogo da Memória", "extraction_confidence": 0.99},
        {"id": "b", "unit_type": "slide", "locator": {"slide": 5, "shape_index": 2}, "content_text": "Jogo da Memória", "extraction_confidence": 0.80},
    ]
    assert _conservative_evidence_match(
        candidates,
        text_hints=("Jogo da Memória",),
        locator_key="slide",
        locator_value=5,
    ) is None


def test_unique_container_evidence_can_support_page_level_occurrence():
    from project_domain_normalization import _conservative_evidence_match

    candidates = [
        {"id": "container", "unit_type": "slide", "locator": {"slide": 5}, "content_text": "Slide completo", "extraction_confidence": 0.90},
        {"id": "fragment", "unit_type": "slide", "locator": {"slide": 5, "shape_index": 2}, "content_text": "Fragmento", "extraction_confidence": 0.99},
    ]
    match = _conservative_evidence_match(candidates, locator_key="slide", locator_value=5)
    assert match and match["id"] == "container"


def test_executed_document_context_does_not_turn_every_mention_into_execution():
    code = (Path(__file__).parents[1] / "project_domain_normalization.py").read_text(encoding="utf-8")
    assert 'item_status == "executado" or doc_status == "executed"' not in code
    assert "A post-event/executed document is context, not proof" in code


def test_occurrence_semantics_do_not_promote_unknown_mentions():
    from project_domain_normalization import _occurrence_semantics
    assert _occurrence_semantics("Executado") == ("execution", "execution")
    assert _occurrence_semantics("Proposto") == ("proposal", "proposal")
    assert _occurrence_semantics("Aprovado") == ("approval", "mention")
    assert _occurrence_semantics("Não identificado") == ("other", "mention")


def test_evidence_content_hash_excludes_parser_ordinal_and_locator():
    code = (Path(__file__).parents[1] / "intelligence_graph_db.py").read_text(encoding="utf-8")
    block = code.split("def _content_hash", 1)[1].split("def _locator_hash", 1)[0]
    assert '"text": unit.content_text' in block
    assert '"json": unit.content_json' in block
    assert '"ordinal"' not in block
    assert '"locator"' not in block


def test_legacy_confidence_label_does_not_become_source_authority_by_itself():
    from project_domain_normalization import _confidence_from_legacy, _dedicated_outcome_authority

    _, base, human = _confidence_from_legacy("client_confirmed")
    assert human is False
    assert base < 0.80
    assert _dedicated_outcome_authority({"information_source": "not_informed"}, base) == base
    assert _dedicated_outcome_authority({"information_source": "client_feedback"}, base) >= 0.95


def test_sql_removes_destructive_service_role_deletes_from_normalized_knowledge():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1_DOMAIN_INTEGRITY_PROVENANCE.sql").read_text(encoding="utf-8").casefold()
    for table in (
        "project_solution_instances",
        "project_requirements",
        "financial_documents",
        "financial_line_items",
    ):
        assert f"revoke delete on public.{table} from service_role" in sql
    assert "revoke update, delete on public.entity_outcomes from service_role" in sql
