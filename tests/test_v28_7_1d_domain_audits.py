from pathlib import Path

from project_domain_truth_audit import (
    _report_result_candidates,
    _solution_is_resolved,
)


def test_report_candidates_preserve_unmatched_execution_names_for_coverage_audit():
    rows = [{
        "report_file_id": "report-1",
        "activation_results": [
            {"name": "Amarelinha", "status": "executed", "evidence": "A amarelinha foi executada."},
        ],
        "item_results": [
            {"item_name": "Pescaria", "outcome_status": "executed", "evidence": "Pescaria ativa durante o evento."},
        ],
    }]
    candidates = _report_result_candidates(rows)
    assert [row["name"] for row in candidates] == ["Amarelinha", "Pescaria"]


def test_solution_matching_is_conservative_but_accepts_clear_alias_containment():
    solutions = [{"id": "1", "name": "Mascote em Tamanho Real"}]
    assert _solution_is_resolved("Mascote em Tamanho Real", solutions)
    assert _solution_is_resolved("Mascote em Tamanho Real Chambinho", solutions)
    assert not _solution_is_resolved("Pescaria", solutions)


def test_audits_never_create_merge_or_reclassify_solution_instances():
    code = (Path(__file__).parents[1] / "project_domain_truth_audit.py").read_text(encoding="utf-8")
    assert 'client.table("project_solution_instances").insert' not in code
    assert 'client.table("project_solution_instances").update' not in code
    assert 'finding_type="missing_solution_instance"' in code
    assert 'finding_type="possible_duplicate_identity"' in code
    assert '"domain_coverage_audit"' in code
    assert '"domain_identity_audit"' in code
