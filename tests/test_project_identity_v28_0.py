from decimal import Decimal

from project_identity import (
    AUTO_LINK_THRESHOLD,
    ProjectSignals,
    compare_project_signals,
    infer_document_role,
    merge_project_signals,
    normalize_text,
    rank_project_matches,
    signals_from_mapping,
)


PLANEJA_27 = ProjectSignals(
    project_name="Bradesco — Planeja 27",
    client_brand="Bradesco Institucional",
    event_name="Planeja 27",
    edition="27",
    reference_year=2027,
    event_start=__import__("datetime").date(2026, 11, 30),
    event_end=__import__("datetime").date(2026, 12, 4),
    venue_name="Bourbon Atibaia Resort",
    city="Atibaia",
    state="SP",
    audience_size=250,
    budget_amount=Decimal("1700000"),
    keywords=("Varejo", "Prime", "Empresas"),
)


def test_normalization_handles_planeja_variations():
    assert normalize_text("Planeja27") == "planeja27"
    assert normalize_text("BRADESCO_PLANEJA 2027") == (
        "bradesco planeja 2027"
    )


def test_four_planeja_documents_match_same_project():
    documents = [
        signals_from_mapping(
            {
                "project_name": "Planeja27",
                "client_brand": "Bradesco Institucional",
                "event_name": "Planeja27",
                "edition": "27",
                "reference_year": 2027,
                "event_start": "30/11/2026",
                "event_end": "04/12/2026",
                "venue_name": "Hotel Bourbon Atibaia Resort",
                "audience_size": 250,
                "budget_amount": "R$ 1.700.000,00",
            },
            source_file="BRIEFING_Planeja27 - Produção.pdf",
        ),
        signals_from_mapping(
            {
                "project_name": "Bradesco Planeja 27",
                "client_brand": "Bradesco",
                "event_name": "Planeja 27",
                "reference_year": 2027,
                "event_start": "30/11/2026",
                "event_end": "04/12/2026",
                "venue_name": "Bourbon Atibaia",
                "audience_size": 250,
            },
            source_file=(
                "Planeja 27 Bradesco – Voe Ideias_compressed.pdf"
            ),
        ),
        signals_from_mapping(
            {
                "project_name": "BRADESCO_PLANEJA 2027",
                "client_brand": "Bradesco",
                "event_name": "Planeja 27",
                "edition": "27",
                "reference_year": 2027,
                "budget_amount": "2435028,72",
            },
            source_file="BRADESCO_PLANEJA 2027_13.07.xlsx",
        ),
        signals_from_mapping(
            {
                "project_name": "Estudo de verba Bradesco - Planeja 27",
                "client_brand": "Bradesco",
                "event_name": "Planeja 27",
                "edition": "27",
                "reference_year": 2027,
                "budget_amount": "R$ 1.700.000,00",
            },
            source_file=(
                "Estudo de verba Bradesco - Planeja 27.xlsx"
            ),
        ),
    ]

    decisions = [
        compare_project_signals(
            document,
            PLANEJA_27,
            project_id="planeja-27",
        )
        for document in documents
    ]

    assert all(result.project_id == "planeja-27" for result in decisions)
    assert decisions[0].decision == "auto_link"
    assert decisions[1].decision == "auto_link"
    assert decisions[2].score >= 0.70
    assert decisions[3].score >= 0.70


def test_planeja_26_is_not_linked_to_planeja_27():
    planeja_26 = signals_from_mapping(
        {
            "project_name": "Bradesco Planeja 26",
            "client_brand": "Bradesco",
            "event_name": "Planeja 26",
            "edition": "26",
            "reference_year": 2026,
        }
    )
    result = compare_project_signals(
        planeja_26,
        PLANEJA_27,
        project_id="planeja-27",
    )

    assert result.decision == "unmatched"
    assert result.critical_conflict is True
    assert any("edição divergente" in item for item in result.conflicts)


def test_same_client_without_event_is_not_auto_linked():
    sparse = signals_from_mapping(
        {
            "client_brand": "Bradesco",
            "project_name": "Evento corporativo",
        }
    )
    result = compare_project_signals(
        sparse,
        PLANEJA_27,
        project_id="planeja-27",
    )
    assert result.decision == "unmatched"


def test_document_roles_for_planeja_files():
    assert infer_document_role(
        "BRIEFING_Planeja27 - Produção.pdf"
    ) == "briefing_original"

    assert infer_document_role(
        "BRADESCO_PLANEJA 2027_13.07.xlsx",
        text_sample="planilha de custos do evento",
    ) == "cost_sheet"

    assert infer_document_role(
        "Estudo de verba Bradesco - Planeja 27.xlsx"
    ) == "budget_study"

    assert infer_document_role(
        "Planeja 27 Bradesco – Voe Ideias_compressed.pdf",
        title="Apresentação de proposta",
    ) == "final_presentation"


def test_rank_returns_best_project_first():
    incoming = signals_from_mapping(
        {
            "project_name": "Planeja 27",
            "client_brand": "Bradesco",
            "event_name": "Planeja 27",
            "edition": "27",
            "reference_year": 2027,
            "venue_name": "Bourbon Atibaia",
        }
    )
    other = ProjectSignals(
        project_name="Bradesco Oktoberfest 2026",
        client_brand="Bradesco",
        event_name="Oktoberfest",
        edition="26",
        reference_year=2026,
        venue_name="Blumenau",
    )
    ranked = rank_project_matches(
        incoming,
        [
            ("other", "Oktoberfest", other),
            ("planeja", "Planeja 27", PLANEJA_27),
        ],
    )

    assert ranked[0].project_id == "planeja"
    assert ranked[0].score > ranked[1].score


def test_merge_signals_builds_project_signature():
    documents = [
        signals_from_mapping(
            {
                "project_name": "Planeja 27",
                "client_brand": "Bradesco",
                "event_name": "Planeja 27",
                "edition": "27",
                "reference_year": 2027,
            }
        ),
        signals_from_mapping(
            {
                "venue_name": "Bourbon Atibaia Resort",
                "event_start": "30/11/2026",
                "event_end": "04/12/2026",
                "audience_size": 250,
                "budget_amount": "R$ 1.700.000,00",
            }
        ),
    ]
    merged = merge_project_signals(documents)

    assert merged.event_name == "Planeja 27"
    assert merged.venue_name == "Bourbon Atibaia Resort"
    assert merged.audience_size == 250
    assert merged.budget_amount == Decimal("1700000.00")


def test_auto_threshold_is_conservative():
    assert AUTO_LINK_THRESHOLD == 0.90
