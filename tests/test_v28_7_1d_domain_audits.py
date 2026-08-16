from pathlib import Path

from project_domain_truth_audit import (
    _compositional_identity_signal,
    _report_result_candidates,
    _solution_is_resolved,
)


def test_report_candidates_keep_result_kind_so_material_logistics_can_be_filtered():
    rows = [{
        "report_file_id": "report-1",
        "activation_results": [
            {"name": "Amarelinha", "status": "executed", "evidence": "A amarelinha foi executada."},
        ],
        "item_results": [
            {"item_name": "Bola de sabão", "outcome_status": "executed", "evidence": "400 produzidas."},
        ],
    }]
    candidates = _report_result_candidates(rows)
    by_name = {row["name"]: row for row in candidates}
    assert by_name["Amarelinha"]["result_kinds"] == ["activation_result"]
    assert by_name["Bola de sabão"]["result_kinds"] == ["item_result"]


def test_solution_matching_resolves_obvious_execution_aliases_without_full_entity_resolution():
    solutions = [
        {"id": "1", "name": "Mascote em Tamanho Real"},
        {"id": "2", "name": "Oficina Origami de Coração"},
        {"id": "3", "name": "Tatuagens Temporárias"},
        {"id": "4", "name": "Jogo da memória"},
    ]
    assert _solution_is_resolved("Mascote Chambinho (Chambão)", solutions)
    assert _solution_is_resolved("Oficina de Origami", solutions)
    assert _solution_is_resolved("Tatuagem", solutions)
    assert _solution_is_resolved("Jogo da Memória", solutions)
    assert not _solution_is_resolved("Amarelinha", solutions)
    assert not _solution_is_resolved("Pescaria", solutions)
    assert not _solution_is_resolved("Distribuição de Produtos", solutions)
    assert not _solution_is_resolved("Folhas para colorir", solutions)


def test_identity_signal_distinguishes_compositional_phrase_from_sibling_labels():
    assert _compositional_identity_signal(
        "Chaveiro", "Pelúcia", "Material necessário: Chaveiro de pelúcia de coração e miçangas"
    )
    assert not _compositional_identity_signal("Meias", "Asas", "ASAS\nMEIAS\nBRINDES")
    assert not _compositional_identity_signal(
        "Munhequeira", "Adesivos", "FAIXA PARA CABELO\nTATUAGENS\nBRINDES\nADESIVOS MUNHEQUEIRA"
    )
    assert not _compositional_identity_signal(
        "Adesivos", "Faixa para Cabelo", "FAIXA PARA CABELO\nTATUAGENS\nBRINDES\nADESIVOS MUNHEQUEIRA"
    )


def test_audits_never_create_merge_or_reclassify_solution_instances():
    code = (Path(__file__).parents[1] / "project_domain_truth_audit.py").read_text(encoding="utf-8")
    assert 'client.table("project_solution_instances").insert' not in code
    assert 'client.table("project_solution_instances").update' not in code
    assert 'finding_type="missing_solution_instance"' in code
    assert 'finding_type="possible_duplicate_identity"' in code
    assert '"domain_coverage_audit"' in code
    assert '"domain_identity_audit"' in code
