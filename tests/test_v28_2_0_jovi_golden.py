from __future__ import annotations

import pytest

from project_analyst import (
    FeedbackClaim,
    best_item_for_claim,
    build_project_evidence_packet,
    derive_advanced_project_insights,
)


def _snapshot() -> dict:
    return {
        "project": {"id": "p1", "project_name": "Lançamento X300", "client_brand": "JOVI"},
        "outcome": {
            "process_type": "competition",
            "commercial_result": "lost",
            "proposal_result": "not_approved",
            "execution_result": "not_applicable",
            "information_source": "client_feedback",
            "confidence_level": "client_confirmed",
        },
        "briefing_documents": [
            {"id": "b1", "budget_amount": 1_300_000, "metadata": {"audience_quantity": "250 convidados"}}
        ],
        "briefing_requirements": [
            {"id": "r1", "title": "Local confortável para 250 convidados", "mandatory": True, "priority": "critical"},
            {"id": "r2", "title": "YouTube adequado a conteúdo horizontal", "mandatory": True, "priority": "high"},
        ],
        "memory_items": [
            {"id": "m1", "title": "JOVI X300 Series On Tour", "section_key": "strategy", "summary": "Travel and discovery concept"},
            {"id": "m2", "title": "Cinemateca", "section_key": "scenography", "summary": "Venue selected for launch"},
            {"id": "m3", "title": "YouTube Activation", "section_key": "activations", "summary": "Platform content experience"},
        ],
        "cost_items": [
            {"id": "c1", "category": "Event Production", "item_name": "Scenography", "client_total": 416_586.36},
            {"id": "c2", "category": "Venue & Infrastructure", "item_name": "Venue Rental", "client_total": 276_182.18},
            {"id": "c3", "category": "AV & Technical", "item_name": "AV", "client_total": 231_754.55},
            {"id": "c4", "category": "Staffing & Talent", "item_name": "Staff", "client_total": 204_826.68},
            {"id": "c5", "category": "Food & Beverage", "item_name": "F&B", "client_total": 124_852.43},
            {"id": "c6", "category": "Content & Documentation", "item_name": "Content", "client_total": 62_787.87},
            {"id": "c7", "category": "Hospitality & Travel", "item_name": "Travel", "client_total": 57_648.48},
            {"id": "c8", "category": "Logistics & Transportation", "item_name": "Logistics", "client_total": 46_000.00},
        ],
        "cost_links": [
            {"id": "cl2", "memory_item_id": "m2", "cost_item_id": "c2", "link_status": "confirmed"},
        ],
        "item_outcomes": [
            {"id": "o1", "item_id": "m1", "outcome_status": "approved", "feedback_summary": "Concept aligned strongly with campaign"},
            {"id": "o2", "item_id": "m2", "outcome_status": "not_approved", "feedback_summary": "Capacity was insufficient for 250 guests"},
            {"id": "o3", "item_id": "m3", "outcome_status": "not_approved", "feedback_summary": "Execution was not native enough to YouTube"},
        ],
        "briefing_links": [
            {"id": "bl1", "requirement_id": "r1", "memory_item_id": "m2", "link_status": "confirmed", "adherence_status": "not_fulfilled"},
            {"id": "bl2", "requirement_id": "r2", "memory_item_id": "m3", "link_status": "confirmed", "adherence_status": "not_fulfilled"},
        ],
        "feedback_entries": [
            {"id": "f1", "theme": "creative_concept", "sentiment": "positive", "original_feedback": "Concept praised"},
            {"id": "f2", "theme": "operation", "sentiment": "negative", "original_feedback": "Venue capacity issue"},
            {"id": "f3", "theme": "activation", "sentiment": "negative", "original_feedback": "YouTube execution issue"},
        ],
    }


def test_jovi_golden_financial_reading_and_concentration():
    snapshot = _snapshot()
    total = 1_499_590.31
    insights = derive_advanced_project_insights(snapshot, proposal_total=total, budget_amount=1_300_000)

    assert total - 1_300_000 == pytest.approx(199_590.31, abs=0.01)
    assert (total - 1_300_000) / 1_300_000 == pytest.approx(0.153531, rel=1e-4)
    assert insights["audience_quantity"] == 250
    assert insights["cost_per_attendee"] == pytest.approx(5_998.36124, rel=1e-6)
    assert insights["top4_category_share"] == pytest.approx(0.7531, rel=1e-3)
    assert insights["top_categories"][0]["category"] == "Event Production"
    assert any(row["title"] == "Crítica em investimento relevante" for row in insights["findings"])


def test_jovi_golden_preserves_good_concept_inside_lost_project():
    insights = derive_advanced_project_insights(_snapshot(), proposal_total=1_499_590.31, budget_amount=1_300_000)
    assert any(row["title"] == "JOVI X300 Series On Tour" for row in insights["validated_items"])
    assert any(row["title"] == "Cinemateca" for row in insights["challenged_items"])
    assert len(insights["requirement_risks"]) == 2


def test_jovi_golden_feedback_entity_matching_is_granular():
    items = _snapshot()["memory_items"]
    concept = FeedbackClaim(
        title="Concept & Campaign Alignment",
        theme="creative_concept",
        sentiment="positive",
        related_entities=["JOVI X300 Series On Tour"],
        item_outcome_status="approved",
    )
    venue = FeedbackClaim(
        title="Venue & Capacity Constraints",
        theme="operation",
        sentiment="negative",
        related_entities=["Cinemateca"],
        item_outcome_status="not_approved",
    )
    concept_item, _ = best_item_for_claim(concept, items)
    venue_item, _ = best_item_for_claim(venue, items)
    assert concept_item and concept_item["id"] == "m1"
    assert venue_item and venue_item["id"] == "m2"


def test_project_evidence_packet_keeps_cross_source_refs():
    packet = build_project_evidence_packet(_snapshot())
    assert packet["outcome"]["commercial_result"] == "lost"
    assert any(row["ref"] == "REQ:r1" for row in packet["requirements"])
    assert any(row["ref"] == "ITEM:m2" for row in packet["proposal_items"])
    assert any(row["ref"] == "COST:c2" for row in packet["cost_items"])
    assert any(row["item_ref"] == "ITEM:m2" and row["cost_ref"] == "COST:c2" for row in packet["solution_to_cost_links"])
