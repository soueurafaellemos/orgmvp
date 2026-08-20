from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import project_domain_legacy_adapters as legacy
import project_domain_semantic_comparator as cmp
import project_domain_semantic_scope as scope


class Resp:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = {}
        self._limit = None
        self.insert_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters[key] = ("eq", value)
        return self

    def in_(self, key, values):
        self.filters[key] = ("in", set(values))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.table in self.client.fail_tables:
            raise RuntimeError("boom")
        if self.insert_payload is not None:
            self.client.inserts.append((self.table, dict(self.insert_payload)))
            return Resp([self.insert_payload])
        rows = [dict(row) for row in self.client.tables.get(self.table, [])]
        for key, filter_spec in self.filters.items():
            op, value = filter_spec
            if op == "eq":
                rows = [row for row in rows if row.get(key) == value]
            elif op == "in":
                rows = [row for row in rows if row.get(key) in value]
        if self._limit is not None:
            rows = rows[: self._limit]
        return Resp(rows)


class Client:
    def __init__(self, tables=None, fail_tables=None):
        self.tables = tables or {}
        self.fail_tables = set(fail_tables or [])
        self.inserts = []

    def table(self, name):
        return Query(self, name)


def legacy_row(text: str, *, human=False, source="memory_briefing_requirements", **extra):
    return {
        "id": extra.pop("id", "l1"),
        "_legacy_text": text,
        "_legacy_source_id": extra.pop("source_id", "l1"),
        "_legacy_source_table": source,
        "_legacy_human_confirmed": human,
        **extra,
    }


def test_exact_semantics_pass_without_requiring_row_count_parity():
    result = cmp.compare_domain_candidates(
        "requirements",
        [{"id": "d1", "requirement_name": "Entregar vídeo de 30 segundos", "truth_state": "verified"}],
        [legacy_row("Entregar vídeo de 30 segundos")],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.classification_counts == {"same_semantics": 1}
    assert result.semantic_conflicts == 0
    assert result.review_required == 0


def test_unverified_legacy_recall_can_disappear_without_becoming_false_blocker():
    result = cmp.compare_domain_candidates(
        "requirements",
        [{"id": "d1", "requirement_name": "Entregar três unidades para teste", "truth_state": "verified"}],
        [legacy_row("Instagram")],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.classification_counts["domain_only_evidence_led"] == 1
    assert result.classification_counts["legacy_only_unverified"] == 1


def test_domain_only_current_truth_is_explicitly_evidence_led():
    result = cmp.compare_domain_candidates(
        "solutions",
        [{"id": "d1", "solution_name": "Oficina de Origami", "evidence_count": 2}],
        [],
        domain_evidence_ready=False,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.classification_counts == {"domain_only_evidence_led": 1}


def test_outcome_same_dimension_contradiction_is_hard_conflict():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [{
            "id": "d1",
            "outcome_type": "commercial_result",
            "outcome_status": "won",
            "truth_state": "verified",
            "_semantic_subject_key": "project:p1",
            "_semantic_evidence_backed": True,
        }],
        [legacy_row(
            "commercial_result: lost",
            human=True,
            _legacy_outcome_dimension="commercial_result",
            _legacy_outcome_value="lost",
            _semantic_subject_key="project:p1",
            _semantic_evidence_backed=True,
        )],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_conflict"
    assert result.semantic_conflicts == 1
    assert result.classification_counts["semantic_conflict"] == 1


def test_outcomes_never_pair_different_dimensions():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [{
            "id": "d1",
            "outcome_type": "execution_status",
            "outcome_status": "executed",
            "truth_state": "verified",
            "_semantic_subject_key": "solution:e1",
        }],
        [legacy_row(
            "commercial_result: won",
            _legacy_outcome_dimension="commercial_result",
            _semantic_subject_key="solution:e1",
            _legacy_outcome_value="won",
        )],
        domain_evidence_ready=True,
    )
    assert result.semantic_conflicts == 0
    assert result.classification_counts["domain_only_evidence_led"] == 1
    assert result.classification_counts["legacy_only_unverified"] == 1


def test_structural_container_atom_difference_is_explained_not_forced_to_parity():
    result = cmp.compare_domain_candidates(
        "journey",
        [
            {"id": "d1", "moment_name": "PRE-EVENT", "evidence_count": 1},
            {"id": "d2", "moment_name": "EVENT", "evidence_count": 1},
            {"id": "d3", "moment_name": "POST-EVENT", "evidence_count": 1},
        ],
        [legacy_row("PRE-EVENT; EVENT; POST-EVENT", source="memory_items")],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.review_required == 0
    assert result.semantic_conflicts == 0
    assert result.classification_counts.get("expected_structural_difference", 0) >= 1


def test_explicitly_human_confirmed_legacy_disappearance_requires_review():
    result = cmp.compare_domain_candidates(
        "solutions",
        [],
        [legacy_row("Ativação confirmada por revisão humana", human=True, source="manual_review")],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_review"
    assert result.review_required == 1
    assert result.classification_counts["review_required"] == 1


def test_legacy_adapter_fails_closed_on_technical_read_error():
    client = Client(fail_tables={"memory_items"})
    with pytest.raises(legacy.LegacyAdapterError):
        legacy.build_legacy_domain_snapshot(client, "p1")


def test_legacy_confidence_labels_do_not_manufacture_human_review():
    snapshot = {
        "project": {"id": "p1"},
        "briefing_documents": [],
        "briefing_requirements": [],
        "memory_documents": [],
        "memory_items": [],
        "project_outcomes": [{
            "id": "o1",
            "project_id": "p1",
            "process_type": "direct",
            "commercial_result": "not_applicable",
            "proposal_result": "not_informed",
            "execution_result": "executed",
            "confidence_level": "client_confirmed",
            "information_source": "client_feedback",
        }],
        "item_outcomes": [],
    }
    rows = legacy.legacy_rows_for_domain(snapshot, "p1", "outcomes")
    assert rows
    assert all(row["_legacy_human_confirmed"] is False for row in rows)
    semantics = {
        (row["_legacy_outcome_dimension"], row["_legacy_outcome_value"])
        for row in rows
    }
    assert ("process_type", "direct") in semantics
    assert ("commercial_result", "not_applicable") in semantics
    assert ("execution_status", "executed") in semantics


def test_semantic_audit_reuses_existing_audit_sink_and_contains_versions():
    client = Client()
    result = cmp.compare_domain_candidates("context", [], [], domain_evidence_ready=True)
    cmp.persist_semantic_comparison_audit(
        client,
        project_id="p1",
        domain_key="context",
        read_mode="shadow_compare",
        readiness_state="ready",
        served_source="legacy",
        domain_row_count=0,
        legacy_row_count=0,
        fallback_used=False,
        reader_version="V28.7.3A2",
        comparison=result,
        legacy_adapter_version=legacy.LEGACY_ADAPTER_VERSION,
        semantic_scope_version=scope.SCOPE_BINDING_VERSION,
    )
    assert len(client.inserts) == 1
    table, payload = client.inserts[0]
    assert table == "project_domain_read_audit"
    assert payload["request_scope"] == "v28.7.3a3_1_semantic_scope_compare"
    assert payload["read_mode"] == "shadow_compare"
    assert payload["metadata"]["comparator_version"] == "V28.7.3A3.1.1"
    assert payload["metadata"]["legacy_adapter_version"] == "V28.7.3A3.1"
    assert payload["metadata"]["semantic_scope_version"] == "V28.7.3A3.1.1"


def test_a3_sources_have_no_golden_hardcode_and_no_cutover_write():
    sources = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in (
            "project_domain_legacy_adapters.py",
            "project_domain_semantic_comparator.py",
            "project_domain_semantic_scope.py",
            "pages/15_Domain_Read_Canary.py",
        )
    ).casefold()
    assert "chambinho" not in sources
    assert "jovi" not in sources
    assert "01415104-72f2-4b8e-aeca-2dd24c231a7d" not in sources
    assert "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136" not in sources
    assert '.update({"read_mode"' not in sources
    assert '"domain_primary"' not in sources


def test_a3_canary_uses_existing_audit_read_at_contract():
    source = (ROOT / "pages/15_Domain_Read_Canary.py").read_text(encoding="utf-8")
    assert '.order("read_at", desc=True)' in source
    assert '.order("created_at", desc=True)' not in source


def test_same_outcome_dimension_different_subjects_never_conflict():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [{
            "id": "d1",
            "outcome_type": "proposal_status",
            "outcome_status": "proposed",
            "source_evidence_id": "ev1",
            "_semantic_subject_key": "solution:youtube",
            "_semantic_lifecycle_phase": "proposal",
        }],
        [legacy_row(
            "proposal_status: rejected",
            _legacy_outcome_dimension="proposal_status",
            _legacy_outcome_value="rejected",
            _semantic_subject_key="project:p1",
            _semantic_lifecycle_phase="feedback",
        )],
        domain_evidence_ready=False,
    )
    assert result.semantic_conflicts == 0
    assert result.classification_counts["domain_only_evidence_led"] == 1
    assert result.classification_counts["legacy_only_unverified"] == 1


def test_evidence_backed_domain_correction_beats_unverified_legacy_without_conflict():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [{
            "id": "d1",
            "outcome_type": "commercial_result",
            "outcome_status": "not_applicable",
            "source_evidence_id": "ev1",
            "_semantic_subject_key": "project:p1",
            "_semantic_lifecycle_phase": "project_current",
        }],
        [legacy_row(
            "commercial_result: won",
            _legacy_outcome_dimension="commercial_result",
            _legacy_outcome_value="won",
            _semantic_subject_key="project:p1",
            _semantic_lifecycle_phase="project_result",
        )],
        domain_evidence_ready=False,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.semantic_conflicts == 0
    assert result.review_required == 0
    assert result.classification_counts["expected_truth_correction"] == 1


def test_documented_client_feedback_without_current_domain_counterpart_requires_review():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [],
        [legacy_row(
            "proposal_status: rejected | client said no",
            source="memory_project_outcomes",
            _legacy_outcome_dimension="proposal_status",
            _legacy_outcome_value="rejected",
            _semantic_subject_key="project:p1",
            _semantic_lifecycle_phase="feedback",
            _semantic_material_feedback=True,
        )],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_review"
    assert result.review_required == 1
    assert result.semantic_conflicts == 0


def test_feedback_disagreement_same_subject_is_lifecycle_review_not_hard_conflict():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [{
            "id": "d1",
            "outcome_type": "proposal_status",
            "outcome_status": "proposed",
            "source_evidence_id": "proposal_ev",
            "_semantic_subject_key": "solution:s1",
            "_semantic_lifecycle_phase": "proposal",
        }],
        [legacy_row(
            "proposal_status: rejected | later feedback",
            source="memory_item_outcomes",
            _legacy_outcome_dimension="proposal_status",
            _legacy_outcome_value="rejected",
            _semantic_subject_key="solution:s1",
            _semantic_lifecycle_phase="feedback",
            _semantic_material_feedback=True,
        )],
        domain_evidence_ready=False,
    )
    assert result.semantic_status == "semantic_review"
    assert result.review_required == 1
    assert result.semantic_conflicts == 0


def test_solution_exact_identity_binding_prevents_long_legacy_text_false_review():
    result = cmp.compare_domain_candidates(
        "solutions",
        [{
            "id": "s1",
            "name": "Munhequeira",
            "description": "Munhequeira em tecido personalizada com identidade visual.",
            "legacy_source_ids": ["m1"],
            "evidence_count": 1,
        }],
        [legacy_row(
            "Munhequeira | Munhequeira personalizada | Brinde / kit | Crianças | Visitantes | Distribuição",
            id="m1",
            source_id="m1",
            source="memory_items",
            title="Munhequeira",
        )],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.review_required == 0
    assert result.classification_counts["same_semantics"] == 1


def test_scope_binder_uses_solution_entity_id_and_legacy_source_ids():
    snapshot = {
        "solution_instances": [{
            "id": "psi1",
            "project_id": "p1",
            "entity_id": "entity1",
            "name": "Jogo da memória",
            "legacy_source_ids": ["memory1"],
            "attributes": {},
        }],
        "solution_occurrences": [{
            "id": "occ1",
            "project_id": "p1",
            "solution_instance_id": "psi1",
            "evidence_unit_id": "ev1",
            "occurrence_phase": "execution",
            "lifecycle_status": "active",
        }],
    }
    domain_rows, legacy_rows = scope.bind_semantic_subjects(
        "outcomes",
        [{
            "id": "o1",
            "project_id": "p1",
            "entity_id": "entity1",
            "outcome_type": "execution_status",
            "outcome_status": "executed",
            "source_evidence_id": "ev1",
        }],
        [{
            "item_id": "memory1",
            "_legacy_source_table": "memory_item_outcomes",
            "_legacy_role": "item_outcome",
            "_legacy_outcome_dimension": "execution_status",
            "_legacy_outcome_value": "executed",
            "_legacy_text": "execution_status: executed",
        }],
        project_id="p1",
        scope_snapshot=snapshot,
    )
    assert domain_rows[0]["_semantic_subject_key"] == "solution:entity1"
    assert domain_rows[0]["_semantic_solution_instance_id"] == "psi1"
    assert domain_rows[0]["_semantic_lifecycle_phase"] == "execution"
    assert legacy_rows[0]["_semantic_subject_key"] == "solution:entity1"


def test_scope_binder_infers_project_entity_from_project_scoped_dimensions():
    domain_rows, legacy_rows = scope.bind_semantic_subjects(
        "outcomes",
        [
            {
                "id": "o1", "project_id": "p1", "entity_id": "project_entity",
                "outcome_type": "process_type", "outcome_status": "direct",
                "source_evidence_id": "ev1",
            },
            {
                "id": "o2", "project_id": "p1", "entity_id": "project_entity",
                "outcome_type": "commercial_result", "outcome_status": "not_applicable",
                "source_evidence_id": "ev1",
            },
        ],
        [{
            "_legacy_source_table": "memory_project_outcomes",
            "_legacy_role": "project_outcome",
            "_legacy_outcome_dimension": "process_type",
            "_legacy_outcome_value": "direct",
            "_legacy_text": "process_type: direct",
        }],
        project_id="p1",
        scope_snapshot={"solution_instances": [], "solution_occurrences": []},
    )
    assert all(row["_semantic_subject_key"] == "project:p1" for row in domain_rows)
    assert legacy_rows[0]["_semantic_subject_key"] == "project:p1"


def test_governed_feedback_context_is_nonblocking_and_preserved_as_context():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [],
        [legacy_row(
            "proposal_status: rejected | feedback transversal",
            source="memory_item_outcomes",
            _legacy_outcome_dimension="proposal_status",
            _legacy_outcome_value="rejected",
            _semantic_subject_key="solution:s1",
            _semantic_lifecycle_phase="feedback",
            _semantic_material_feedback=True,
            _semantic_governed_feedback_context=True,
        )],
        domain_evidence_ready=True,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.review_required == 0
    assert result.semantic_conflicts == 0
    assert result.classification_counts["governed_feedback_context"] == 1


def test_governed_feedback_context_never_pairs_as_current_outcome():
    result = cmp.compare_domain_candidates(
        "outcomes",
        [{
            "id": "d1",
            "outcome_type": "proposal_status",
            "outcome_status": "proposed",
            "source_evidence_id": "ev1",
            "_semantic_subject_key": "solution:s1",
            "_semantic_lifecycle_phase": "proposal",
        }],
        [legacy_row(
            "proposal_status: rejected | feedback transversal",
            source="memory_item_outcomes",
            _legacy_outcome_dimension="proposal_status",
            _legacy_outcome_value="rejected",
            _semantic_subject_key="solution:s1",
            _semantic_lifecycle_phase="feedback",
            _semantic_material_feedback=True,
            _semantic_governed_feedback_context=True,
        )],
        domain_evidence_ready=False,
    )
    assert result.semantic_status == "semantic_pass"
    assert result.review_required == 0
    assert result.semantic_conflicts == 0
    assert result.classification_counts["domain_only_evidence_led"] == 1
    assert result.classification_counts["governed_feedback_context"] == 1


def test_scope_snapshot_reads_only_reviews_for_project_outcomes():
    client = Client(tables={
        "project_solution_instances": [],
        "project_solution_occurrences": [],
        "entity_outcomes": [
            {"id": "o1", "project_id": "p1", "legacy_source_id": "m1",
             "outcome_type": "proposal_status", "outcome_status": "rejected"},
            {"id": "o2", "project_id": "p2", "legacy_source_id": "m2",
             "outcome_type": "proposal_status", "outcome_status": "rejected"},
        ],
        "intelligence_reviews": [
            {"id": "r1", "object_type": "outcome", "object_id": "o1", "decision": "correct",
             "corrected_payload": {"semantic_role": "feedback_context", "not_current_outcome": True}},
            {"id": "r2", "object_type": "outcome", "object_id": "o2", "decision": "correct",
             "corrected_payload": {"semantic_role": "feedback_context", "not_current_outcome": True}},
        ],
    })
    snapshot = scope.build_semantic_scope_snapshot(client, "p1")
    assert [row["id"] for row in snapshot["entity_outcomes"]] == ["o1"]
    assert [row["id"] for row in snapshot["outcome_reviews"]] == ["r1"]


def test_scope_binder_honors_explicit_feedback_context_correction_by_legacy_source():
    snapshot = {
        "solution_instances": [{
            "id": "psi1",
            "project_id": "p1",
            "entity_id": "entity1",
            "name": "Recomendação de creator",
            "legacy_source_ids": ["m1"],
            "attributes": {},
        }],
        "solution_occurrences": [],
        "entity_outcomes": [{
            "id": "o1",
            "project_id": "p1",
            "entity_id": "entity1",
            "legacy_source_id": "m1",
            "legacy_source_table": "memory_item_outcomes",
            "outcome_type": "proposal_status",
            "outcome_status": "rejected",
            "event_status": "invalidated",
        }],
        "outcome_reviews": [{
            "id": "r1",
            "object_type": "outcome",
            "object_id": "o1",
            "decision": "correct",
            "corrected_payload": {
                "semantic_role": "feedback_context",
                "not_current_outcome": True,
            },
        }],
    }
    _, legacy_rows = scope.bind_semantic_subjects(
        "outcomes",
        [],
        [{
            "item_id": "m1",
            "information_source": "client_feedback",
            "feedback_summary": "feedback transversal",
            "_legacy_source_table": "memory_item_outcomes",
            "_legacy_role": "item_outcome",
            "_legacy_outcome_dimension": "proposal_status",
            "_legacy_outcome_value": "rejected",
            "_legacy_text": "proposal_status: rejected | feedback transversal",
        }],
        project_id="p1",
        scope_snapshot=snapshot,
    )
    assert legacy_rows[0]["_semantic_governed_feedback_context"] is True
    result = cmp.compare_domain_candidates(
        "outcomes", [], legacy_rows, domain_evidence_ready=True
    )
    assert result.semantic_status == "semantic_pass"
    assert result.classification_counts["governed_feedback_context"] == 1


def test_unreviewed_material_feedback_still_fails_closed_after_governance_patch():
    snapshot = {
        "solution_instances": [],
        "solution_occurrences": [],
        "entity_outcomes": [],
        "outcome_reviews": [],
    }
    _, legacy_rows = scope.bind_semantic_subjects(
        "outcomes",
        [],
        [{
            "item_id": "m1",
            "information_source": "client_feedback",
            "feedback_summary": "feedback material",
            "_legacy_source_table": "memory_item_outcomes",
            "_legacy_role": "item_outcome",
            "_legacy_outcome_dimension": "proposal_status",
            "_legacy_outcome_value": "rejected",
            "_legacy_text": "proposal_status: rejected | feedback material",
        }],
        project_id="p1",
        scope_snapshot=snapshot,
    )
    result = cmp.compare_domain_candidates(
        "outcomes", [], legacy_rows, domain_evidence_ready=True
    )
    assert result.semantic_status == "semantic_review"
    assert result.review_required == 1
