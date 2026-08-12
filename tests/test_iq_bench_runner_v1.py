from __future__ import annotations

import json
from pathlib import Path

from iq_bench_runner import (
    ResponseDirectoryAdapter,
    evaluate_case,
    load_suite,
    render_markdown,
    resolve_fixtures,
    run_suite,
)


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evals" / "suite.yaml"


def _case(case_id: str):
    _, cases = load_suite(SUITE)
    return next(c for c in cases if c["case_id"] == case_id)


def test_suite_schema_is_valid_and_complete():
    suite, cases = load_suite(SUITE)
    assert suite["suite_id"] == "nave_iq_bench_v1"
    assert len(cases) == 8
    assert {c["case_id"] for c in cases} == set(suite["cases"])


def test_fixture_resolver_validates_basename_and_sha(tmp_path: Path):
    payload = b"fixture-real"
    file_path = tmp_path / "brief.docx"
    file_path.write_bytes(payload)
    import hashlib
    case = {
        "sources": [{
            "role": "briefing",
            "basename": "brief.docx",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }]
    }
    status = resolve_fixtures(case, [tmp_path])
    assert status["complete"] is True
    assert status["resolved"] == 1


def test_missing_execution_case_penalizes_false_execution():
    case = _case("adversarial_missing_execution_evidence")
    good_metrics, good_signals = evaluate_case(case, {"execution_state": "proposal_only"})
    bad_metrics, bad_signals = evaluate_case(case, {"execution_state": "executed"})
    assert good_signals["false_executed_without_evidence"] == 0
    assert bad_signals["false_executed_without_evidence"] == 1
    assert next(m.value for m in good_metrics if m.name == "uncertainty_calibration") == 1
    assert next(m.value for m in bad_metrics if m.name == "uncertainty_calibration") == 0


def test_financial_state_separation_scores_exact_values():
    case = _case("blind_financial_state_separation")
    candidate = {
        "facts": {
            "budget_max": 800000,
            "proposed_total": 850000,
            "contracted_total": 790000,
            "actual_total": 775500,
        }
    }
    metrics, _ = evaluate_case(case, candidate)
    by_name = {m.name: m.value for m in metrics}
    assert by_name["financial_state_accuracy"] == 1
    assert by_name["exact_numeric_accuracy"] == 1
    assert by_name["forbidden_inference_count"] == 0


def test_project_loss_does_not_invalidate_validated_concept():
    case = _case("blind_loss_with_validated_concept")
    candidate = {
        "claims": [
            {"subject": "project", "predicate": "commercial_result", "value_text": "lost"},
            {"subject": "city_pulse", "predicate": "sentiment", "value_text": "positive"},
        ]
    }
    metrics, signals = evaluate_case(case, candidate)
    by_name = {m.name: m.value for m in metrics}
    assert by_name["outcome_granularity"] == 1
    assert signals["lost_project_solution_overgeneralization"] == 0


def test_conflict_case_requires_both_claims_and_current_value():
    case = _case("adversarial_conflicting_sources")
    candidate = {
        "claims": [
            {"subject": "project", "predicate": "event_date", "value_date": "2026-09-10", "status": "superseded", "evidence_refs": ["briefing:1"]},
            {"subject": "project", "predicate": "event_date", "value_date": "2026-09-17", "status": "active", "evidence_refs": ["client_email:1"]},
        ],
        "conflict_sets": [{"predicate": "event_date", "claims": [0, 1]}],
        "current_values": {"event_date": "2026-09-17"},
    }
    metrics, _ = evaluate_case(case, candidate)
    by_name = {m.name: m.value for m in metrics}
    assert by_name["conflict_preservation"] == 1
    assert by_name["authority_resolution_accuracy"] == 1


def test_retrieval_semantic_case_scores_top_candidate():
    case = _case("retrieval_semantic_paraphrase")
    metrics, _ = evaluate_case(case, {"retrieval": {"ranking": ["B", "D", "A", "C"]}})
    by_name = {m.name: m.value for m in metrics}
    assert by_name["recall_at_3"] == 1
    assert by_name["mrr"] == 1
    assert by_name["semantic_relevance"] == 1


def _golden_candidate():
    return {
        "source_roles": {
            "briefing": "briefing_original",
            "proposal": "proposal_presentation",
            "budget": "cost_sheet",
            "feedback": "feedback",
        },
        "entities": [
            {"id": "on_tour_concept", "type": "concept", "canonical_name": "JOVI X300 Series ON TOUR"},
            {"id": "cinemateca", "type": "venue", "canonical_name": "Cinemateca"},
            {"id": "youtube", "type": "platform", "canonical_name": "YouTube"},
            {"id": "instagram", "type": "platform", "canonical_name": "Instagram"},
            {"id": "tiktok", "type": "platform", "canonical_name": "TikTok"},
            {"id": "presskit", "type": "presskit", "canonical_name": "Press Kit"},
            {"id": "client", "type": "client", "canonical_name": "JOVI"},
        ],
        "claims": [
            {"subject": "project", "predicate": "budget_max", "value_numeric": 1300000, "currency": "BRL", "evidence_refs": ["briefing:p20"]},
            {"subject": "project", "predicate": "expected_attendees", "value_numeric": 250, "unit": "people", "evidence_refs": ["briefing:p2"]},
            {"subject": "youtube_requirement", "predicate": "required_platform_behavior", "value_text": "record horizontally", "evidence_refs": ["briefing:p5"]},
            {"subject": "project", "predicate": "proposed_total", "value_numeric": 1499590.31, "currency": "BRL", "evidence_refs": ["budget:row94"]},
            {"subject": "project", "predicate": "commercial_result", "value_text": "lost", "evidence_refs": ["feedback:decision"]},
            {"subject": "on_tour_concept", "predicate": "sentiment", "value_text": "positive", "evidence_refs": ["feedback:concept"]},
            {"subject": "cinemateca", "predicate": "approval_status", "value_text": "challenged", "evidence_refs": ["feedback:venue"]},
        ],
        "relations": [
            {"source": "project", "relation": "uses_venue", "target": "cinemateca", "evidence_refs": ["proposal:p48"]},
            {"source": "youtube_activation", "relation": "responds_to", "target": "youtube_requirement", "evidence_refs": ["briefing:p5", "proposal:youtube"]},
            {"source": "instagram_activation", "relation": "responds_to", "target": "instagram_requirement", "evidence_refs": ["briefing:p6", "proposal:instagram"]},
            {"source": "tiktok_activation", "relation": "responds_to", "target": "tiktok_requirement", "evidence_refs": ["briefing:p7", "proposal:tiktok"]},
            {"source": "on_tour_concept", "relation": "validated_by", "target": "client", "target_type": "client", "evidence_refs": ["feedback:concept"]},
            {"source": "cinemateca", "relation": "challenged_by", "target": "client", "target_type": "client", "evidence_refs": ["feedback:venue"]},
        ],
        "financial": {
            "base_cost_total": 1291226.22,
            "agency_markup_total": 127122.62,
            "before_tax_total": 1418348.84,
            "tax_amount_total": 81241.47,
            "after_tax_total": 1499590.31,
            "budget_delta": 199590.31,
            "budget_delta_pct": 15.3531,
            "top4_concentration_pct": 75.3106,
            "top_categories_after_tax": [
                ["Scenic & Event Production", 416586.36],
                ["Venue & Infrastructure", 276182.18],
                ["AV & Technical", 231754.55],
                ["Staffing & Talent", 204826.68],
                ["Food & Beverage", 124852.43],
            ],
            "largest_line_items_after_tax": [
                ["Booth Construction & Scenography", 313939.39],
                ["Venue Rental", 238720.97],
            ],
        },
        "feedback_claims": [
            {"target": "on_tour_concept", "polarity": "positive", "topic": "concept_campaign_alignment"},
            {"target": "cinemateca", "polarity": "negative", "topic": "venue_capacity"},
            {"target": "youtube_activation", "polarity": "negative", "topic": "platform_format_alignment"},
            {"target": "instagram_activation", "polarity": "negative", "topic": "lifestyle_self_content"},
            {"target": "tiktok_activation", "polarity": "negative", "topic": "repetition_market_standard"},
            {"target": "project", "polarity": "negative", "topic": "budget_cap"},
            {"target": "project", "polarity": "negative", "topic": "deadline"},
            {"target": "project", "polarity": "negative", "topic": "commercial_decision"},
        ],
        "findings": [
            {"kind": "risk", "severity": "high", "text": "A proposta está acima do teto de budget.", "evidence_roles": ["briefing", "budget"]},
            {"kind": "learning", "severity": "high", "text": "O conceito foi validado apesar da perda da concorrência.", "evidence_roles": ["proposal", "feedback"]},
            {"kind": "contradiction", "severity": "high", "text": "Uma solução de venue financeiramente relevante foi criticada por capacidade e adequação.", "evidence_roles": ["briefing", "proposal", "budget", "feedback"]},
            {"kind": "learning", "severity": "high", "text": "A aderência à linguagem nativa da plataforma deve ser validada entre briefing, estratégia e materialização.", "evidence_roles": ["briefing", "proposal", "feedback"]},
        ],
        "execution_state": "not_evidenced",
    }


def test_golden_case_can_score_full_contract():
    case = _case("golden_jovi_x300_multisource")
    metrics, signals = evaluate_case(case, _golden_candidate())
    by_name = {m.name: m.value for m in metrics}
    assert by_name["source_role_accuracy"] == 1
    assert by_name["claim_recall"] == 1
    assert by_name["critical_relation_precision"] == 1
    assert by_name["feedback_target_accuracy"] == 1
    assert by_name["exact_numeric_accuracy"] == 1
    assert by_name["cross_source_finding_quality"] == 1
    assert by_name["forbidden_inference_count"] == 0
    assert signals["exact_numeric_accuracy"] == 1


def test_runner_supports_response_directory_and_emits_reports(tmp_path: Path):
    responses = tmp_path / "responses"
    responses.mkdir()
    # Um case é suficiente quando require_all=False.
    (responses / "retrieval_semantic_paraphrase.json").write_text(
        json.dumps({"retrieval": {"ranking": ["B", "D", "A", "C"]}}),
        encoding="utf-8",
    )
    result = run_suite(SUITE, ResponseDirectoryAdapter(responses), require_all=False)
    assert result.status in {"provisional", "blocked"}  # gates não avaliados tornam o run provisório.
    md = render_markdown(result)
    assert "NAVE IQ Bench" in md
    assert "retrieval_semantic_paraphrase" in md


def test_blind_regression_gate_detects_material_drop(tmp_path: Path):
    responses = tmp_path / "responses"
    responses.mkdir()
    # Resposta ruim no blind financeiro.
    (responses / "blind_financial_state_separation.json").write_text(
        json.dumps({"facts": {"budget_max": 800000, "proposed_total": 775500, "contracted_total": 790000, "actual_total": 850000}}),
        encoding="utf-8",
    )
    baseline = {
        "case_results": [
            {"case_id": "blind_financial_state_separation", "score": 1.0}
        ]
    }
    result = run_suite(SUITE, ResponseDirectoryAdapter(responses), baseline=baseline, regression_tolerance=0.03)
    gate = next(g for g in result.gates if g.name == "blind_project_regression_allowed")
    assert gate.status == "fail"
