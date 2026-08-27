from __future__ import annotations
from types import SimpleNamespace

from project_requirement_response_entailment_shadow import (
    response_entailment_signal,
    audit_response_entailment_from_ownership,
)


def test_budget_restriction_vs_charm_page_is_no_anchor():
    sig = response_entailment_signal(
        requirement_title='Restrição de verba e estrutura',
        evidence_text='PERSONALIZE O SEU CADARÇO CHARM DE CORAÇÃO miçangas crianças escrevem seus nomes',
    )
    assert sig['entailment_status'] == 'REVIEW_NO_TITLE_ANCHOR'


def test_press_kit_heading_only_requires_review():
    sig = response_entailment_signal(
        requirement_title='Item para ser incluído no press kit / Seeding',
        evidence_text='PRESS KIT',
    )
    assert sig['entailment_status'] == 'REVIEW_HEADING_ONLY'


def test_reels_in_substantive_instagram_activation_is_supported():
    sig = response_entailment_signal(
        requirement_title='Reels;',
        evidence_text='INSTAGRAM SUPER ZOOM. A platform with feed, Stories, Reels. For this activation the X300 camera is positioned on a tripod and the guest receives content to post.',
    )
    assert sig['entailment_status'] == 'SUPPORTED_EXPLICIT_ATOM'


def test_camera_superiority_product_reveal_is_supported():
    sig = response_entailment_signal(
        requirement_title='A superioridade das câmeras do JOVI X300 Ultra;',
        evidence_text='EVENT PRODUCT REVEAL. JOVI X300 Ultra showcasing superior camera capabilities and high-performance mobile photography.',
    )
    assert sig['entailment_status'].startswith('SUPPORTED_')


def test_governed_requirement_false_positive_becomes_hard_blocker():
    ownership = SimpleNamespace(detail_rows=({
        'side': 'legacy',
        'legacy_requirement_id': 'l1',
        'legacy_title': 'Restrição de verba e estrutura',
        'domain_requirement_id': 'd1',
        'domain_title': 'Restrição de verba e estrutura',
        'contract_disposition': 'requirement_owned_response',
        'ownership_domain': 'requirements',
        'ownership_labels': 'Restrição de verba e estrutura',
        'ownership_basis': 'governed_requirement_alias',
        'review_required': False,
        'match_score': 0.425,
        'evidence_id': 'ev1',
        'evidence_locator': 'page 32',
        'evidence_text': 'PERSONALIZE O SEU CADARÇO CHARM DE CORAÇÃO miçangas crianças',
    },))
    result = audit_response_entailment_from_ownership(project_id='p1', ownership_result=ownership)
    assert result.hard_blocker_count == 1
    assert result.status == 'BLOCKED_RESPONSE_EVIDENCE_FALSE_POSITIVE_RISK'
