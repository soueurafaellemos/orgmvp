from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Mapping

from entity_resolution import ResolutionEntity, entity_match_score
from project_analyst import _parse_people_quantity, derive_advanced_project_insights
from project_intelligence_unified import _match_score

ROOT = Path(__file__).resolve().parents[1]


def _isolated_function(path: Path, name: str, namespace: dict[str, Any] | None = None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"Any": Any, "Mapping": Mapping, "re": re}
    ns.update(namespace or {})
    exec(compile(module, str(path), "exec"), ns)
    return ns[name]


def _quality_gate():
    return _isolated_function(ROOT / "project_bundle_materializer.py", "_validate_rebuild_quality")


def test_quality_gate_blocks_financial_regression():
    ok, reason = _quality_gate()("detailed_costs", {"cost_items": 54}, {"cost_items": 0})
    assert ok is False
    assert "54" in str(reason) and "0" in str(reason)


def test_quality_gate_allows_cleaner_briefing_with_fewer_nonzero_requirements():
    ok, reason = _quality_gate()("briefing_original", {"briefing_requirements": 14}, {"briefing_requirements": 10})
    assert ok is True
    assert reason is None


def test_quality_gate_blocks_visual_page_loss():
    ok, reason = _quality_gate()(
        "proposal_presentation",
        {"memory_pages": 41, "memory_items": 5},
        {"memory_pages": 5, "memory_items": 4},
    )
    assert ok is False
    assert "páginas" in str(reason)


def test_year_alone_can_never_prove_cross_source_identity():
    assert _match_score("EM 2026 VAMOS CRIAR A EXPERIÊNCIA", "2026") == 0.0
    left = ResolutionEntity(id="a", entity_type="solution", canonical_name="2026", scope_entity_id="p1")
    right = ResolutionEntity(id="b", entity_type="solution", canonical_name="2026", scope_entity_id="p1")
    match = entity_match_score(left, right)
    assert match.decision == "DISTINCT"


def test_age_range_is_not_audience_quantity_and_festival_scope_is_preserved():
    value, scope = _parse_people_quantity("Mães e pais entre 30 e 45 anos")
    assert value is None
    value, scope = _parse_people_quantity("Público do Festivalzinho: de 6 a 8 mil pessoas")
    assert value == 8000
    assert scope == "festival_event"


def test_cost_per_attendee_not_calculated_from_festival_audience():
    snapshot = {
        "briefing_requirements": [
            {"title": "Público", "description": "Público do festival: de 6 a 8 mil pessoas", "requirement_type": "audience"}
        ],
        "cost_items": [{"id": "c1", "category": "Infra", "item_name": "Cenografia", "client_total": 400000}],
        "cost_links": [], "item_outcomes": [], "memory_items": [], "feedback_entries": [],
        "briefing_links": [], "intelligence_graph": {},
    }
    result = derive_advanced_project_insights(snapshot, proposal_total=400000, budget_amount=400000)
    assert result["audience_quantity"] == 8000
    assert result["audience_scope"] == "festival_event"
    assert result["cost_per_attendee"] is None


def test_reprocessor_contains_r2_fallback_and_pointer_healing():
    text = (ROOT / "project_bundle_materializer.py").read_text(encoding="utf-8")
    assert '"source_assets", "content_sha256"' in text
    assert "Master recuperado via" in text
    assert '"storage_bucket": bucket' in text
    assert "preserved_existing" in text


def test_internal_provenance_marker_cleaner_is_present_and_removes_marker():
    func = _isolated_function(
        ROOT / "project_workspace_ui.py", "_clean_user_note",
        {"_INTERNAL_NOTE_RE": re.compile(r"\[NAVE-V[^\]]+\]\s*[^\n:]+:\s*(?:documento anexado)?", re.IGNORECASE)},
    )
    raw = "[NAVE-V28.1.1:abcdef] RELATORIO_EVENTO.pptx: documento anexado"
    assert func(raw) == ""


def test_untrusted_document_outcome_does_not_preselect_won():
    func = _isolated_function(ROOT / "project_workspace_ui.py", "_trusted_outcome_default")
    outcome = {
        "commercial_result": "won",
        "confidence_level": "incomplete",
        "information_source": "document",
    }
    assert func(outcome, "commercial_result", {"won", "not_informed"}, "not_informed") == "not_informed"


def test_dossier_contains_discrete_nave_logo_asset():
    from project_intelligence_report import _logo_flowable
    logo = _logo_flowable()
    assert logo is not None
    assert float(logo.drawWidth) > 0


def test_post_event_report_does_not_auto_approve_or_win_project():
    text = (ROOT / "project_workspace_db.py").read_text(encoding="utf-8")
    assert '"fully_approved" if report_type == "post_execution"' not in text
    assert 'existing_is_confirmed' in text
    assert 'commercial_result = (' in text
    assert 'proposal_result = (' in text


def test_feedback_empty_state_distinguishes_no_explicit_client_feedback():
    text = (ROOT / "project_workspace_ui.py").read_text(encoding="utf-8")
    assert "Nenhum feedback explícito do cliente foi identificado nas fontes atuais." in text


def test_user_intelligence_separates_technical_health_from_business_diagnostic():
    text = (ROOT / "project_workspace_intelligence.py").read_text(encoding="utf-8")
    assert "Saúde da leitura NAVE · diagnóstico técnico" in text
    assert 'st.tabs(["Diagnóstico", "Recomendações", "Conexões descobertas"])' in text


def test_visual_projection_fallback_exists_for_rich_domains():
    text = (ROOT / "project_workspace_ui.py").read_text(encoding="utf-8")
    assert "Outras evidências visuais de ativações" in text
    assert "evidências visuais de brindes/press kits" in text
    assert "_render_unified_evidence_cards" in text


def test_r2_pointer_healing_updates_source_and_project_file_registry():
    text = (ROOT / "project_bundle_materializer.py").read_text(encoding="utf-8")
    assert 'client.table("source_files").update' in text
    assert 'client.table("project_files").update' in text
    assert 'source_file["storage_bucket"] = bucket' in text
