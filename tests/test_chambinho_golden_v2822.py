from __future__ import annotations

import io
from pathlib import Path

import yaml
from docx import Document

from file_analyst import analyze_file
from iq_bench_runner import load_suite
from project_batch_ingestion import classify_document


def _docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_chambinho_like_briefing_reads_split_budget_audience_and_direct_payment_requirement():
    data = _docx_bytes([
        "4. BRIEFING",
        "INFORMAÇÕES LOGISTICAS: 01 de agosto | Parque Villa Lobos",
        "PUBLICO ALVO: Público do Festivalzinho: De 6 a 8 mil pessoas – a confirmar",
        "OBRIGATORIEDADES: Manter o conceito da campanha da Casa Chambinho, memoria afetiva entre os pais e filhos.",
        "FINANCEIRO_",
        "Precisamos organizar para pagarem a cenografia de forma direta antes do evento acontecer para evitar bitributação.",
        "BUDGET",
        "R$400.000,00.",
    ])
    result = analyze_file(
        file_name="VOE _Briefing Interno_Chambinho_no_Festivalzinho.docx",
        data=data,
        declared_role="briefing_original",
        enable_semantic=False,
    )
    claims = {(c.subject_key, c.predicate): c for c in result.claims}
    assert claims[("project", "budget_max")].value_numeric == 400_000.0
    assert claims[("project", "expected_attendees")].value_numeric == 8_000.0
    direct = [e for e in result.entities if e.entity_type == "requirement" and e.attributes.get("constraint_family") == "client_direct_payment"]
    assert direct
    assert "cenografia" in direct[0].canonical_name.casefold()
    assert any(r.source_key == direct[0].key and r.relation_type == "requirement_of" for r in result.relations)


def test_specific_post_event_role_is_sticky_against_internal_proposal_language():
    data = _docx_bytes([
        "Nossa proposta e estratégia",
        "Ativação Amarelinha",
        "RESULTADOS REALIZADOS",
        "8 mil pessoas presentes no evento",
    ])
    # DOCX is enough to exercise role-preservation; the declared role represents
    # the batch classifier/manual review before the File Analyst.
    result = analyze_file(
        file_name="RELATORIO_LACTALIS_FESTIVALZINHO26.docx",
        data=data,
        declared_role="post_event_report",
        enable_semantic=False,
    )
    assert result.source_role == "post_event_report"
    assert result.source_role_confidence >= 0.94


def test_report_filename_has_structural_priority_over_proposal_terms():
    role, confidence, reasons = classify_document(
        "RELATORIO_LACTALIS_FESTIVALZINHO26.pptx",
        "Nossa proposta estratégia ativações conceito. 8 mil pessoas presentes no evento. Produzidas distribuídas sobras.",
    )
    assert role == "post_event_report"
    assert confidence >= 0.95
    assert reasons


def test_chambinho_is_registered_as_golden_case_in_iq_suite():
    root = Path(__file__).resolve().parents[1]
    suite, cases = load_suite(root / "evals" / "suite.yaml")
    assert "golden_chambinho_festivalzinho_2026_full_cycle" in suite["cases"]
    case = next(c for c in cases if c["case_id"] == "golden_chambinho_festivalzinho_2026_full_cycle")
    assert len(case["sources"]) == 4
    assert case["expected"]["financial"]["after_tax_total"] == 554310.85
    assert any("8 mil" in item for item in case["expected"]["forbidden"])


def test_chambinho_fixture_hashes_are_declared_and_not_embedded_as_binary_files():
    root = Path(__file__).resolve().parents[1]
    case = yaml.safe_load((root / "evals" / "cases" / "golden_chambinho_festivalzinho_2026_full_cycle.yaml").read_text(encoding="utf-8"))
    hashes = {row["role"]: row["sha256"] for row in case["sources"]}
    assert hashes == {
        "briefing": "6d83d06f9b1985bdb7e7f3bce69458759ea29d6c09bb7321d965625425622957",
        "proposal": "2ab26a8876808860cecde7c2a37297aa275ce4fb71bb0ef1d7895b2075341457",
        "budget": "ea009afd09661a73737b75a2acf28d3aea8a4b656f47d6cd663a7ada96abc473",
        "report": "3e102c3ae5db728b68099d0df144c8b5b182584552f3541b857a7cc597b3024b",
    }
    private_names = {row["basename"] for row in case["sources"]}
    committed_files = {p.name for p in root.rglob("*") if p.is_file()}
    assert not (private_names & committed_files)
