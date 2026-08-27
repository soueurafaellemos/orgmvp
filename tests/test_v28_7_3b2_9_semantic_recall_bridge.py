from __future__ import annotations

from project_requirement_semantic_recall_bridge import (
    strict_entailment_signal,
    semantic_bridge_signal,
    audit_semantic_recall_bridge,
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


def _contract(req_id, status="no_verified_response"):
    return {
        "requirement_id": req_id,
        "response_contract_status": status,
    }


def _evidence(ev_id, text, ordinal=10):
    return {
        "evidence_id": ev_id,
        "source_name": "proposal.pdf",
        "source_roles": ["proposal_presentation"],
        "locator_text": f"page {ordinal}",
        "text": text,
        "ordinal": ordinal,
    }


def test_compound_promoters_monitors_downgrades():
    s = strict_entailment_signal(
        requirement_title="Promotores e monitores",
        evidence_text="Com o auxílio de monitores, pais e filhos criam o mascote.",
    )
    assert s["old_permissive_auto"] is True
    assert s["strict_auto"] is False
    assert s["title_anchor_coverage"] == 0.5


def test_storytelling_detailed_downgrades_if_only_storytelling_anchor():
    s = strict_entailment_signal(
        requirement_title="Storytelling detalhado.",
        evidence_text="YouTube audiences come for storytelling and tutorials.",
    )
    assert s["old_permissive_auto"] is True
    assert s["strict_auto"] is False
    assert s["title_anchor_coverage"] == 0.5


def test_multilingual_invitation_bridge_is_review_signal():
    s = semantic_bridge_signal(
        requirement_text="Materiais Gráficos: convite, STD, Reminder",
        evidence_text="PRE-EVENT Save the Date Online invitation Reminder",
    )
    assert s["review"] is True
    assert "invitation" in s["shared_concepts"]
    assert "save_the_date" in s["shared_concepts"]
    assert "reminder" in s["shared_concepts"]


def test_single_atomic_term_can_be_strict_auto():
    s = strict_entailment_signal(
        requirement_title="Reels",
        evidence_text="The Instagram activation includes Reels for social content.",
    )
    assert s["strict_auto"] is True


def test_context_window_can_surface_press_kit_review():
    result = audit_semantic_recall_bridge(
        project_id="p1",
        current_requirement_rows=[
            _req("r1", "Item para ser incluído no press kit / Seeding")
        ],
        current_contract_rows=[_contract("r1")],
        proposal_evidence_rows=[
            _evidence("e1", "PRESS KIT", 37),
            _evidence(
                "e2",
                "Para os influenciadores, vamos enviar um kit personalizado.",
                38,
            ),
        ],
    )
    assert result.context_window_review_requirement_count == 1


def test_audit_downgrades_compound_old_auto():
    result = audit_semantic_recall_bridge(
        project_id="p1",
        current_requirement_rows=[_req("r1", "Promotores e monitores")],
        current_contract_rows=[_contract("r1")],
        proposal_evidence_rows=[
            _evidence(
                "e1",
                "Com o auxílio de monitores, pais e filhos criam o mascote.",
                32,
            )
        ],
    )
    assert result.old_permissive_auto_count == 1
    assert result.strict_safe_auto_count == 0
    assert result.downgraded_compound_atom_count == 1
