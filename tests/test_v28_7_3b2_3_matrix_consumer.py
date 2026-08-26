from __future__ import annotations

from project_requirement_compatibility import build_requirement_compatibility_from_rows
from project_requirement_matrix_consumer import (
    build_domain_matrix_overlay,
)


def _domain(domain_id="d1", legacy_id="l1"):
    return {
        "id": domain_id,
        "entity_id": f"e-{domain_id}",
        "legacy_source_id": legacy_id,
        "title": "Requirement",
        "requirement_type": "deliverable",
        "truth_state": "verified",
    }


def _legacy_req(legacy_id="l1"):
    return {
        "id": legacy_id,
        "title": "Requirement",
        "requirement_type": "deliverable",
        "adherence_status": "not_assessed",
    }


def _link(link_id="b1", req_id="l1", item_id="i1",
          adherence="not_assessed", status="suggested"):
    return {
        "id": link_id,
        "requirement_id": req_id,
        "memory_item_id": item_id,
        "link_status": status,
        "adherence_status": adherence,
        "evidence": None,
        "notes": None,
    }


def _compat(domain_rows=None, legacy_rows=None, links=None, occurrences=None):
    return build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain()] if domain_rows is None else domain_rows,
        legacy_requirement_rows=[_legacy_req()] if legacy_rows is None else legacy_rows,
        occurrence_rows=[] if occurrences is None else occurrences,
        legacy_link_rows=[_link()] if links is None else links,
    )


def _intel(briefing="Relacionada, ainda não avaliada"):
    return {
        "matrix": [{
            "item_id": "i1",
            "section_key": "activations",
            "Item apresentado": "Item 1",
            "Área": "Ativações e experiências",
            "Situação na apresentação": "Proposto",
            "Briefing": briefing,
            "Custo direto": 0.0,
            "Correlação do custo": "Sem linha direta",
            "Execução": "Sem evidência de execução",
            "Evidência / resultado": "—",
        }],
        "metrics": {"briefing_requirements": 1},
        "discrepancies": {"briefing_gaps": [], "briefing_evidence_unconsolidated": []},
        "unified": {"briefing_matches": []},
    }


def test_identity_only_overlay_preserves_matrix_semantics():
    links = [_link()]
    compat = _compat(links=links)
    snapshot = {
        "briefing_links": links,
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    routed, meta = build_domain_matrix_overlay(
        snapshot=snapshot,
        legacy_intelligence=_intel(),
        compatibility=compat,
        domain_requirement_rows=[_domain()],
        expected_domain_rows=1,
        expected_matrix_rows=1,
        expected_active_links=1,
    )
    assert routed["matrix"][0]["Briefing"] == "Relacionada, ainda não avaliada"
    assert routed["unified"] == {"briefing_matches": []}
    assert meta["persisted_intelligence_source"] == "legacy"
    assert meta["unified_source"] == "legacy"


def test_positive_link_state_is_preserved():
    links = [_link(adherence="fulfilled")]
    compat = _compat(links=links)
    snapshot = {
        "briefing_links": links,
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    routed, _ = build_domain_matrix_overlay(
        snapshot=snapshot,
        legacy_intelligence=_intel("Com evidência de aderência"),
        compatibility=compat,
        domain_requirement_rows=[_domain()],
        expected_domain_rows=1,
    )
    assert routed["matrix"][0]["Briefing"] == "Com evidência de aderência"


def test_not_fulfilled_link_state_is_preserved():
    links = [_link(adherence="not_fulfilled")]
    compat = _compat(links=links)
    snapshot = {
        "briefing_links": links,
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    routed, _ = build_domain_matrix_overlay(
        snapshot=snapshot,
        legacy_intelligence=_intel("Não cumprida"),
        compatibility=compat,
        domain_requirement_rows=[_domain()],
        expected_domain_rows=1,
    )
    assert routed["matrix"][0]["Briefing"] == "Não cumprida"


def test_missing_relation_is_preserved():
    compat = _compat(links=[])
    snapshot = {
        "briefing_links": [],
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    routed, _ = build_domain_matrix_overlay(
        snapshot=snapshot,
        legacy_intelligence=_intel("Sem demanda relacionada"),
        compatibility=compat,
        domain_requirement_rows=[_domain()],
        expected_domain_rows=1,
        expected_active_links=0,
    )
    assert routed["matrix"][0]["Briefing"] == "Sem demanda relacionada"


def test_semantic_matrix_drift_blocks():
    links = [_link()]
    compat = _compat(links=links)
    snapshot = {
        "briefing_links": links,
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    try:
        build_domain_matrix_overlay(
            snapshot=snapshot,
            legacy_intelligence=_intel("Sem demanda relacionada"),
            compatibility=compat,
            domain_requirement_rows=[_domain()],
            expected_domain_rows=1,
        )
    except Exception as exc:
        assert getattr(exc, "code", "") == "MATRIX_BRIEFING_SEMANTIC_DRIFT"
    else:
        raise AssertionError("semantic drift should block")


def test_active_link_runtime_drift_blocks():
    compat = _compat(links=[_link("b1")])
    snapshot = {
        "briefing_links": [_link("b1"), _link("b2")],
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    try:
        build_domain_matrix_overlay(
            snapshot=snapshot,
            legacy_intelligence=_intel(),
            compatibility=compat,
            domain_requirement_rows=[_domain()],
            expected_domain_rows=1,
        )
    except Exception as exc:
        assert getattr(exc, "code", "") == "ACTIVE_LINK_RUNTIME_DRIFT"
    else:
        raise AssertionError("runtime drift should block")


def test_domain_row_count_drift_blocks():
    compat = _compat()
    snapshot = {
        "briefing_links": [_link()],
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    try:
        build_domain_matrix_overlay(
            snapshot=snapshot,
            legacy_intelligence=_intel(),
            compatibility=compat,
            domain_requirement_rows=[_domain()],
            expected_domain_rows=2,
        )
    except Exception as exc:
        assert getattr(exc, "code", "") == "DOMAIN_ROW_COUNT_DRIFT"
    else:
        raise AssertionError("domain row count drift should block")


def test_matrix_row_count_drift_blocks():
    compat = _compat()
    snapshot = {
        "briefing_links": [_link()],
        "briefing_requirements": [_legacy_req()],
        "memory_items": [{"id": "i1"}],
    }
    try:
        build_domain_matrix_overlay(
            snapshot=snapshot,
            legacy_intelligence=_intel(),
            compatibility=compat,
            domain_requirement_rows=[_domain()],
            expected_domain_rows=1,
            expected_matrix_rows=2,
        )
    except Exception as exc:
        assert getattr(exc, "code", "") == "MATRIX_ROW_COUNT_DRIFT"
    else:
        raise AssertionError("matrix row count drift should block")


def test_non_matrix_active_link_is_kept_as_governed_observation_not_orphan():
    domain_rows = [_domain("d1", "l1"), _domain("d2", "l2")]
    legacy_rows = [_legacy_req("l1"), _legacy_req("l2")]
    links = [_link("b1", "l1", "i1"), _link("b2", "l2", "i2")]
    compat = _compat(domain_rows=domain_rows, legacy_rows=legacy_rows, links=links)
    snapshot = {
        "briefing_links": links,
        "briefing_requirements": legacy_rows,
        "memory_items": [{"id": "i1"}, {"id": "i2"}],
    }
    routed, meta = build_domain_matrix_overlay(
        snapshot=snapshot,
        legacy_intelligence=_intel(),
        compatibility=compat,
        domain_requirement_rows=domain_rows,
        expected_domain_rows=2,
        expected_active_links=2,
    )
    assert routed["matrix"][0]["Briefing"] == "Relacionada, ainda não avaliada"
    assert meta["non_matrix_active_link_count"] == 1
