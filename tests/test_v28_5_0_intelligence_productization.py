from __future__ import annotations

from pathlib import Path

from project_analyst import derive_advanced_project_insights, sanitize_semantic_payload
from project_intelligence_unified import build_unified_project_snapshot


def test_semantic_projection_blocks_backend_and_unsupported_performance():
    snapshot = {
        "feedback_entries": [],
        "report_analyses": [{
            "kpis": [{"name": "Público Presente", "unit": "pessoas", "actual": 8000}],
            "issues": ["Tatuagem: produzidas (3000), sobras (0) e distribuídas (225) não reconciliam."],
        }],
        "unified_intelligence": {
            "results": {
                "data_quality": ["Tatuagem: produzidas (3000), sobras (0) e distribuídas (225) não reconciliam."]
            }
        },
    }
    payload = {
        "executive_summary": "O Intelligence Graph já contém dados. A ativação foi realizada com sucesso.",
        "diagnostic": [
            {"title": "Projeto com evidência de execução", "analysis": "Há fonte pós-evento."},
            {"title": "Leitura útil", "analysis": "O relatório comprova que a ativação foi executada."},
        ],
        "validated_learnings": [
            "O território da nostalgia é altamente eficaz e tem alto índice de participação.",
            "A proposta e o relatório mostram continuidade entre estratégia e execução.",
        ],
        "challenged_learnings": [
            "Tatuagens geraram 92% de sobra e desperdício de verba.",
        ],
    }

    safe = sanitize_semantic_payload(payload, snapshot)

    assert "Intelligence Graph" not in safe.get("executive_summary", "")
    assert "sucesso" not in safe.get("executive_summary", "").casefold()
    assert all(row.get("title") != "Projeto com evidência de execução" for row in safe.get("diagnostic", []))
    assert any("continuidade" in value.casefold() for value in safe.get("validated_learnings", []))
    assert not any("altamente eficaz" in value.casefold() for value in safe.get("validated_learnings", []))
    assert not any("92%" in value for value in safe.get("challenged_learnings", []))


def test_host_event_audience_never_becomes_cost_per_activation_participant():
    snapshot = {
        "cost_items": [{"id": "c1", "category": "Infraestrutura", "item_name": "Casa", "client_total": 554310.85}],
        "cost_links": [],
        "item_outcomes": [],
        "memory_items": [],
        "feedback_entries": [],
        "briefing_links": [],
        "briefing_requirements": [],
        "intelligence_graph": {
            "project_entity": {"id": "project-1"},
            "claims": [{
                "predicate": "expected_attendees",
                "subject_entity_id": "project-1",
                "status": "active",
                "value_numeric": 8000,
                "value_json": {"scope": "project_attendees"},
                "authority_score": 0.8,
                "model_confidence": 0.8,
            }],
        },
        "unified_intelligence": {
            "results": {"participants_count": 8000, "participants_scope": "festival_event"},
            "financial_context": {"direct_payment_signal": True},
        },
    }

    advanced = derive_advanced_project_insights(snapshot, proposal_total=554310.85, budget_amount=400000.0)

    assert advanced["audience_scope"] == "festival_event"
    assert advanced["cost_per_attendee"] is None
    titles = [row.get("title") for row in advanced.get("findings", [])]
    assert "Diferença bruta a reconciliar" in titles
    assert "Aderência financeira" not in titles


def test_unified_briefing_diagnostic_names_actual_demands_instead_of_only_count():
    snapshot = {
        "project": {"status": "executado"},
        "outcome": {"execution_result": "executed"},
        "project_files": [],
        "briefing_documents": [{"budget_amount": 400000.0}],
        "briefing_requirements": [
            {"id": "r1", "title": "Brindes", "description": "Prever brindes para o público", "requirement_type": "deliverable"},
        ],
        "memory_items": [],
        "cost_items": [],
        "report_analyses": [],
        "intelligence_graph": {
            "project_entity": {"id": "p1"},
            "source_assets": [
                {"id": "a1", "canonical_file_name": "proposta.pdf"},
            ],
            "contexts": [
                {"source_asset_id": "a1", "context_role": "proposal_presentation"},
            ],
            "evidence_units": [
                {"id": "e1", "source_asset_id": "a1", "content_text": "BRINDES: adesivos, meias e press kit para o público", "ordinal": 10, "locator": {"page": 20}},
            ],
            "claims": [],
            "relations": [],
        },
    }

    unified = build_unified_project_snapshot(snapshot)
    diagnostics = unified.get("decision_intelligence", {}).get("diagnostic", [])
    combined = " ".join(str(row.get("text") or "") for row in diagnostics)

    assert "Brindes" in combined
    assert "links legados" not in combined.casefold()
    assert not any(str(row.get("title") or "") == "Projeto com evidência de execução" for row in diagnostics)


def test_visual_cost_badge_does_not_repeat_section_unallocated_total_per_card():
    text = Path("project_workspace_visuals.py").read_text(encoding="utf-8")
    start = text.index("def _cost_badges")
    end = text.index("def _render_item_details", start)
    body = text[start:end]
    assert "Sem linha direta" not in body
    assert "unallocated_total" not in body
    assert "total <= 0" in body


def test_executive_report_source_has_no_backend_lexicon_in_main_structure():
    text = Path("project_intelligence_report.py").read_text(encoding="utf-8").casefold()
    # A nota final pode dizer que detalhes técnicos ficam na NAVE; o corpo não deve
    # usar termos de implementação como títulos/explicações executivas.
    for forbidden in ("links legados", "project analyst deve", "fact ·", "inference ·"):
        assert forbidden not in text
    assert "o projeto em 1 minuto" in text
    assert "briefing x resposta da proposta" in text
    assert "estratégia x materialização" in text
