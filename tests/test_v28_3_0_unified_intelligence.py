from __future__ import annotations

from project_intelligence_unified import build_unified_project_snapshot
from project_intelligence_report import build_project_intelligence_pdf


def _snapshot():
    project_entity = {"id": "pentity", "domain_table": "projects", "domain_id": "p1"}
    assets = [
        {"id": "a-brief", "canonical_file_name": "briefing.docx"},
        {"id": "a-prop", "canonical_file_name": "proposta.pdf"},
        {"id": "a-report", "canonical_file_name": "relatorio.pptx"},
    ]
    contexts = [
        {"source_asset_id": "a-brief", "context_role": "briefing_original"},
        {"source_asset_id": "a-prop", "context_role": "proposal_presentation"},
        {"source_asset_id": "a-report", "context_role": "post_event_report"},
    ]
    evidence = [
        {"id": "e1", "source_asset_id": "a-brief", "unit_type": "paragraph", "ordinal": 1, "locator": {"paragraph": 1}, "content_text": "Esse ano teremos menos dinheiro que ano passado e precisamos pensar em menos estrutura de cenografia.", "extraction_confidence": 0.99, "is_current": True},
        {"id": "e2", "source_asset_id": "a-prop", "unit_type": "page", "ordinal": 5, "locator": {"page": 5}, "content_text": "MEMÓRIA AFETIVA CONEXÃO PRESENÇA E ATENÇÃO PONTOS DE PARTIDA", "extraction_confidence": 0.99, "is_current": True},
        {"id": "e3", "source_asset_id": "a-prop", "unit_type": "page", "ordinal": 9, "locator": {"page": 9}, "content_text": "NOSTALGIA como território da marca", "extraction_confidence": 0.99, "is_current": True},
        {"id": "e4", "source_asset_id": "a-prop", "unit_type": "page", "ordinal": 18, "locator": {"page": 18}, "content_text": "JOGO DA MEMÓRIA. Através da brincadeira as crianças e suas famílias...", "extraction_confidence": 0.99, "is_current": True},
        {"id": "e5", "source_asset_id": "a-report", "unit_type": "slide", "ordinal": 3, "locator": {"slide": 3}, "content_text": "8 mil pessoas presentes no evento", "content_json": {}, "extraction_confidence": 0.98, "is_current": True},
        {"id": "e6", "source_asset_id": "a-report", "unit_type": "slide", "ordinal": 8, "locator": {"slide": 8}, "content_text": "Visão Geral Pescaria Oficina de origami Amarelinha Jogo da memória Mascote Chambinho", "content_json": {}, "extraction_confidence": 0.98, "is_current": True},
        {"id": "e7", "source_asset_id": "a-report", "unit_type": "slide", "ordinal": 40, "locator": {"slide": 40}, "content_text": "Material Produzidas Sobras Distribuídas", "content_json": {"tables": [["bad"]]}, "extraction_confidence": 0.98, "is_current": True},
        {"id": "e8", "source_asset_id": "a-report", "unit_type": "slide", "ordinal": 39, "locator": {"slide": 39}, "content_text": "FOTOS: clique aqui AFTER MOVIE V1: AGUARDANDO", "content_json": {}, "extraction_confidence": 0.98, "is_current": True},
    ]
    return {
        "project": {"id": "p1", "project_name": "Festivalzinho Chambinho", "client_brand": "Chambinho", "event_name": "Festivalzinho 2026", "status": "apresentado"},
        "outcome": {"process_type": "direct", "commercial_result": "in_evaluation", "execution_result": "not_informed"},
        "project_files": [{"id": "pf1", "file_role": "post_execution_report", "is_archived": False}],
        "briefing_documents": [{"id": "b1", "budget_amount": None}],
        "briefing_requirements": [{"id": "r1", "title": "Espaço e ativações Chambinho", "description": "Criar ativações para famílias", "requirement_type": "deliverable", "mandatory": False}],
        "memory_documents": [{"id": "d1"}],
        "memory_items": [{"id": "i1", "title": "Jogo da memória", "section_key": "activations", "summary": "Brincadeira para famílias"}],
        "cost_documents": [],
        "cost_items": [{"id": "c1", "category": "3. INFRAESTRUTURA", "item_name": "Cenografia", "client_total": 353703.03}, {"id": "c2", "category": "ATIVAÇÕES", "item_name": "Jogos", "client_total": 200606.82}],
        "cost_links": [], "item_outcomes": [], "briefing_links": [], "feedback_entries": [], "report_analyses": [], "intelligence_snapshots": [], "recommendation_queries": [],
        "intelligence_graph": {
            "project_entity": project_entity,
            "contexts": contexts,
            "source_assets": assets,
            "evidence_units": evidence,
            "entities": [], "mentions": [], "aliases": [], "relations": [], "findings": [], "finding_evidence": [], "finding_entities": [],
            "claims": [{"id": "cl1", "subject_entity_id": "pentity", "predicate": "budget_max", "value_type": "numeric", "value_numeric": 400000, "model_confidence": 0.95, "authority_score": 0.95, "status": "active"}],
            "claim_evidence": [{"claim_id": "cl1", "evidence_unit_id": "e1", "support_type": "supports"}],
        },
    }


def test_unified_snapshot_prevents_false_strategy_empty_and_proposal_stage():
    unified = build_unified_project_snapshot(_snapshot())
    assert unified["project_truth"]["stage"] == "executed"
    assert unified["project_truth"]["budget_amount"] == 400000
    assert unified["coverage"]["strategy"]["state"] == "evidence_found_not_consolidated"
    assert len(unified["domain_evidence"]["strategy"]) >= 2
    assert unified["execution_matches"][0]["item_title"] == "Jogo da memória"
    assert unified["results"]["participants_count"] == 8000
    assert unified["results"]["participants_scope"] == "festival_event"
    assert any("After movie" in value for value in unified["results"]["pending"])
    assert any(row["code"] == "execution_stage_conflict" for row in unified["consistency_issues"])


def test_dossier_is_real_pdf_from_same_unified_brain():
    snap = _snapshot()
    unified = build_unified_project_snapshot(snap)
    snap["unified_intelligence"] = unified
    intelligence = {
        "source_signature": "abc123456789",
        "generated_at": "2026-08-12T18:00:00Z",
        "metrics": {"stage_label": "Executado", "budget_amount": 400000, "cost_total": 554309.85, "budget_delta": -154309.85, "budget_usage_pct": 1.3858},
        "unified": unified,
        "advanced_insights": {"top_categories": [{"category": "Infraestrutura", "value": 353703.03, "share": 0.638}]},
        "result_summary": unified["results"],
    }
    pdf = build_project_intelligence_pdf(snapshot=snap, intelligence=intelligence)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 3000


def test_project_analyst_packet_receives_unified_graph_evidence():
    from project_analyst import build_project_evidence_packet
    snap = _snapshot()
    unified = build_unified_project_snapshot(snap)
    snap["unified_intelligence"] = unified
    packet = build_project_evidence_packet(snap)
    assert packet["unified_snapshot"]["project_truth"]["stage"] == "executed"
    assert any(row.get("ref", "").startswith("EVID:") for row in packet["graph_evidence"])
    assert any(row.get("predicate") == "budget_max" for row in packet["graph_claims"])
