from __future__ import annotations

from pathlib import Path

import pytest

from project_domain_consumer_canary import (
    ConsumerCanaryBlocked,
    stable_fingerprint,
    validate_active_preconditions,
)
from project_domain_requirement_consumer import (
    adapt_domain_requirements,
    adapt_legacy_requirements,
    validate_requirement_contract,
)


def _config(**overrides):
    row = {
        "status": "active",
        "fallback_policy": "legacy_fail_closed",
        "expected_domain_row_count": 13,
        "approved_comparator_version": "V28.7.3A3.1.1",
        "approved_semantic_scope_version": "V28.7.3A3.1.1",
        "approved_legacy_adapter_version": "V28.7.3A3.1",
        "approved_reader_version": "V28.7.3A2",
    }
    row.update(overrides)
    return row


def _readiness(**overrides):
    row = {
        "read_mode": "shadow_compare",
        "readiness_state": "ready",
        "semantic_gate_ok": True,
        "current_evidence_ok": True,
        "domain_row_count": 13,
        "governed_findings": [],
    }
    row.update(overrides)
    return row


def _a31(**overrides):
    row = {
        "comparison_status": "semantic_pass",
        "read_mode": "shadow_compare",
        "served_source": "legacy",
        "domain_row_count": 13,
        "reader_version": "V28.7.3A2",
        "metadata": {
            "semantic_conflicts": 0,
            "review_required": 0,
            "comparator_version": "V28.7.3A3.1.1",
            "semantic_scope_version": "V28.7.3A3.1.1",
            "legacy_adapter_version": "V28.7.3A3.1",
        },
    }
    row.update(overrides)
    return row


def test_active_preconditions_pass_for_clean_shadow_snapshot():
    validate_active_preconditions(
        config=_config(),
        readiness=_readiness(),
        a31_audit=_a31(),
    )


@pytest.mark.parametrize(
    ("readiness_override", "expected_code"),
    [
        ({"read_mode": "domain_primary"}, "REGISTRY_MODE_DRIFT"),
        ({"readiness_state": "not_ready"}, "READINESS_NOT_READY"),
        ({"semantic_gate_ok": False}, "SEMANTIC_GATE_DRIFT"),
        ({"current_evidence_ok": False}, "CURRENT_EVIDENCE_DRIFT"),
        ({"domain_row_count": 12}, "REGISTRY_ROW_COUNT_DRIFT"),
        ({"governed_findings": [{"x": 1}]}, "GOVERNED_FINDING_PRESENT"),
    ],
)
def test_active_preconditions_fail_closed_on_registry_drift(readiness_override, expected_code):
    with pytest.raises(ConsumerCanaryBlocked) as exc:
        validate_active_preconditions(
            config=_config(),
            readiness=_readiness(**readiness_override),
            a31_audit=_a31(),
        )
    assert exc.value.code == expected_code


def test_active_preconditions_fail_closed_on_stale_a31_version():
    audit = _a31()
    audit["metadata"] = dict(audit["metadata"], comparator_version="V28.7.3A3.1")
    with pytest.raises(ConsumerCanaryBlocked) as exc:
        validate_active_preconditions(config=_config(), readiness=_readiness(), a31_audit=audit)
    assert exc.value.code == "A31_VERSION_DRIFT"


def test_active_preconditions_fail_closed_on_review_required():
    audit = _a31()
    audit["metadata"] = dict(audit["metadata"], review_required=1)
    with pytest.raises(ConsumerCanaryBlocked) as exc:
        validate_active_preconditions(config=_config(), readiness=_readiness(), a31_audit=audit)
    assert exc.value.code == "A31_REVIEW_REQUIRED"


def test_domain_adapter_uses_truth_fields_without_fabricating_mandatory():
    rows = adapt_domain_requirements([
        {
            "id": "req-1",
            "requirement_name": "Cobertura de foto e vídeo",
            "requirement_type": "deliverable",
            "truth_state": "verified",
            "evidence_unit_id": "ev-1",
        }
    ])
    assert rows == [
        {
            "stable_key": "req-1",
            "title": "Cobertura de foto e vídeo",
            "description": None,
            "requirement_type": "deliverable",
            "mandatory": None,
            "priority": None,
            "source_excerpt": None,
            "source_reference": None,
            "evidence_ref": "ev-1",
            "truth_status": "verified",
            "source_kind": "domain",
            "legacy_id": None,
            "adherence_status": None,
        }
    ]
    validate_requirement_contract(rows, expected_source="domain")


def test_domain_contract_rejects_unverified_truth():
    rows = adapt_domain_requirements([
        {
            "id": "req-1",
            "title": "Algo",
            "requirement_type": "mandatory",
            "truth_state": "candidate",
        }
    ])
    with pytest.raises(ConsumerCanaryBlocked) as exc:
        validate_requirement_contract(rows, expected_source="domain")
    assert exc.value.code == "CONTRACT_DOMAIN_TRUTH_INVALID"


def test_domain_contract_rejects_unknown_requirement_type():
    rows = adapt_domain_requirements([
        {
            "id": "req-1",
            "title": "Algo",
            "requirement_type": "mystery_type",
            "truth_state": "verified",
        }
    ])
    with pytest.raises(ConsumerCanaryBlocked) as exc:
        validate_requirement_contract(rows, expected_source="domain")
    assert exc.value.code == "CONTRACT_REQUIREMENT_TYPE_INVALID"


def test_legacy_adapter_preserves_legacy_id_and_adherence_only_for_control():
    rows = adapt_legacy_requirements([
        {
            "id": "legacy-1",
            "title": "Promotores e monitores",
            "description": "Equipe necessária",
            "requirement_type": "operation",
            "priority": "high",
            "mandatory": True,
            "adherence_status": "fulfilled",
            "source_quote": "promotores e monitores",
        }
    ])
    assert rows[0]["legacy_id"] == "legacy-1"
    assert rows[0]["adherence_status"] == "fulfilled"
    assert rows[0]["source_kind"] == "legacy"
    validate_requirement_contract(rows, expected_source="legacy")


def test_fingerprint_is_deterministic_and_order_sensitive():
    a = [{"stable_key": "1", "title": "A"}, {"stable_key": "2", "title": "B"}]
    b = [{"title": "A", "stable_key": "1"}, {"title": "B", "stable_key": "2"}]
    c = list(reversed(a))
    assert stable_fingerprint(a) == stable_fingerprint(b)
    assert stable_fingerprint(a) != stable_fingerprint(c)



def test_domain_contract_accepts_real_current_other_requirement_shape():
    rows = adapt_domain_requirements([
        {
            "id": "b876b37f-7c80-5b87-b182-155b0d7f6499",
            "title": "Precisamos organizar o pagamento direto da cenografia",
            "description": "Lactalis paga em 90/120 dias.",
            "requirement_type": "other",
            "mandatory": True,
            "priority": "not_informed",
            "truth_state": "verified",
            "has_current_evidence": True,
            "has_direct_domain_evidence": True,
            "attributes": {
                "source_observation_id": "obs-1",
            },
        }
    ])
    validate_requirement_contract(rows, expected_source="domain")
    assert rows[0]["requirement_type"] == "other"
    assert rows[0]["evidence_ref"] == "obs-1"


def test_domain_adapter_reads_current_view_provenance_from_nested_attributes():
    rows = adapt_domain_requirements([
        {
            "id": "req-legacy-bound",
            "title": "Promotores e monitores",
            "requirement_type": "deliverable",
            "priority": "high",
            "mandatory": False,
            "truth_state": "verified",
            "legacy_explanation_evidence_id": "ev-legacy-explanation",
            "attributes": {
                "source_quote": "Promotores e monitores",
                "source_reference": "Entregáveis",
            },
        }
    ])
    validate_requirement_contract(rows, expected_source="domain")
    assert rows[0]["source_excerpt"] == "Promotores e monitores"
    assert rows[0]["source_reference"] == "Entregáveis"
    assert rows[0]["evidence_ref"] == "ev-legacy-explanation"

def test_runtime_modules_do_not_hardcode_golden_ids_or_write_global_read_mode():
    root = Path(__file__).resolve().parents[1]
    runtime_text = "\n".join(
        (root / name).read_text(encoding="utf-8")
        for name in (
            "project_domain_consumer_canary.py",
            "project_domain_requirement_consumer.py",
            "project_workspace_ui_b1.py",
        )
    )
    assert "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136" not in runtime_text
    assert "01415104-72f2-4b8e-aeca-2dd24c231a7d" not in runtime_text
    assert ".update({\"read_mode\"" not in runtime_text
    assert "domain_primary" not in runtime_text


def test_workspace_overlay_replaces_only_briefing_renderer():
    root = Path(__file__).resolve().parents[1]
    text = (root / "project_workspace_ui_b1.py").read_text(encoding="utf-8")
    assert "_legacy._render_briefing = _render_briefing_b1" in text
    assert "render_projects_page = _legacy.render_projects_page" in text
    assert "read_requirement_consumer" in text
