from __future__ import annotations

from project_requirement_response_recall_shadow import (
    audit_response_recall,
)


def _req(req_id, title):
    return {
        "id": req_id,
        "truth_state": "verified",
        "requirement_name": title,
        "description": title,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
    }


def _contract(req_id, status):
    return {
        "requirement_id": req_id,
        "response_contract_status": status,
    }


def _evidence(ev_id, text, locator="page 10"):
    return {
        "evidence_id": ev_id,
        "source_name": "proposal.pdf",
        "source_roles": ["proposal_presentation"],
        "locator_text": locator,
        "text": text,
        "ordinal": 10,
    }


def test_already_verified_requirement_is_not_scanned():
    result = audit_response_recall(
        project_id="p1",
        current_requirement_rows=[_req("r1", "Brindes")],
        current_contract_rows=[_contract("r1", "verified_response")],
        proposal_evidence_rows=[
            _evidence("e1", "OFICINAS CRIATIVAS com brindes para visitantes")
        ],
    )
    assert result.already_verified_response_count == 1
    assert result.requirements_scanned_count == 0


def test_material_canonical_support_is_recoverable():
    result = audit_response_recall(
        project_id="p1",
        current_requirement_rows=[
            _req("r1", "Cobertura de foto e vídeo")
        ],
        current_contract_rows=[
            _contract("r1", "no_verified_response")
        ],
        proposal_evidence_rows=[
            _evidence(
                "e1",
                "COBERTURA DE FOTO E VÍDEO. Registro completo do evento com equipe dedicada.",
            )
        ],
    )
    assert result.recoverable_verified_candidate_count == 1
    assert any(
        row["candidate_class"]
        == "RECOVERABLE_VERIFIED_RESPONSE_CANDIDATE"
        for row in result.detail_rows
    )


def test_brief_recap_never_becomes_recoverable():
    result = audit_response_recall(
        project_id="p1",
        current_requirement_rows=[_req("r1", "Instagram")],
        current_contract_rows=[_contract("r1", "no_verified_response")],
        proposal_evidence_rows=[
            _evidence(
                "e1",
                "BRIEF RECAP | OUR GOAL | Instagram",
                locator="page 3",
            )
        ],
    )
    assert result.recoverable_verified_candidate_count == 0


def test_false_positive_requirement_can_search_for_replacement_evidence():
    result = audit_response_recall(
        project_id="p1",
        current_requirement_rows=[
            _req("r1", "Restrição de verba e estrutura")
        ],
        current_contract_rows=[
            _contract("r1", "false_positive_excluded")
        ],
        proposal_evidence_rows=[
            _evidence(
                "wrong",
                "PERSONALIZE O SEU CADARÇO com charm de coração",
                locator="page 32",
            ),
            _evidence(
                "right",
                "RESTRIÇÃO DE VERBA E ESTRUTURA. Reduzimos a estrutura cenográfica para adequação ao orçamento.",
                locator="page 45",
            ),
        ],
    )
    assert result.recoverable_verified_candidate_count == 1
    rows = [
        row for row in result.detail_rows
        if row.get("candidate_class")
        == "RECOVERABLE_VERIFIED_RESPONSE_CANDIDATE"
    ]
    assert rows[0]["evidence_id"] == "right"


def test_no_evidence_support_remains_no_candidate():
    result = audit_response_recall(
        project_id="p1",
        current_requirement_rows=[_req("r1", "Geladeiras")],
        current_contract_rows=[_contract("r1", "no_verified_response")],
        proposal_evidence_rows=[
            _evidence("e1", "Palco com iluminação e DJ")
        ],
    )
    assert result.no_candidate_count == 1
