from __future__ import annotations

from project_requirement_obligation_atom_gate import (
    _requirement_atoms,
    _classify,
)


def row(text, *, b29="CONTEXT_WINDOW_REVIEW", anchor=0.0):
    return {
        "b29_class": b29,
        "window_text": text,
        "title_anchor_coverage": anchor,
    }


def test_requirement_atoms_use_title_only_semantics():
    atoms = _requirement_atoms(
        "A agência deve propor insights relevantes e incluir os resultados no relatório."
    )
    assert {"insights", "results", "report"}.issubset(atoms)
    assert "guests" not in atoms
    assert "plenary" not in atoms
    assert "gifts" not in atoms


def test_brief_recap_is_source_role_rejected():
    result = _classify(
        "As agências deverão apresentar uma proposta criativa e logística considerando o cenário A.",
        row(
            "BRIEF RECAP | OUR GOAL | 250 guests | superior camera capabilities | content creators",
            anchor=0.0,
        ),
    )
    assert result["b210_class"] == "REJECT_SOURCE_ROLE_NON_RESPONSE"


def test_press_kit_seeding_is_high_confidence_review():
    result = _classify(
        "Item para ser incluído no press kit / Seeding",
        row(
            "PRESS KIT. Para os influenciadores, vamos enviar um kit personalizado.",
            anchor=0.25,
        ),
    )
    assert result["b210_class"] == "HIGH_CONFIDENCE_REVIEW_CANDIDATE"


def test_material_graphics_pt_en_is_high_confidence_review():
    result = _classify(
        "Materiais Gráficos: convite, STD, Reminder",
        row(
            "Save the Date / Online invitation / Reminder",
            anchor=0.1,
        ),
    )
    assert result["b210_class"] == "HIGH_CONFIDENCE_REVIEW_CANDIDATE"


def test_storytelling_detailed_is_high_confidence_review():
    result = _classify(
        "Storytelling detalhado.",
        row(
            "YouTube audiences come for deeper storytelling and tutorials.",
            anchor=0.5,
        ),
    )
    assert result["b210_class"] == "HIGH_CONFIDENCE_REVIEW_CANDIDATE"


def test_long_timing_requirement_not_high_from_guests_plenary_only():
    result = _classify(
        'É necessário sugerirmos o timming dessa apresentação, no gancho final da plenária e abertura da área de experiências, para causar surpresa nos convidados.',
        row(
            "Guest arrival. Main plenary presentation. Press kit delivery.",
            anchor=0.0,
        ),
    )
    assert result["b210_class"] != "HIGH_CONFIDENCE_REVIEW_CANDIDATE"


def test_promoters_monitors_is_partial_with_monitors_only():
    result = _classify(
        "Promotores e monitores",
        row(
            "Com o auxílio de monitores, pais e filhos criam o mascote.",
            anchor=0.5,
        ),
    )
    assert result["b210_class"] == "PARTIAL_OBLIGATION_COVERAGE"


def test_photo_video_is_partial_with_photo_only():
    result = _classify(
        "Cobertura de foto e vídeo",
        row(
            "Vamos tirar muitas fotos para lembrar do evento.",
            anchor=0.0,
        ),
    )
    assert result["b210_class"] == "PARTIAL_OBLIGATION_COVERAGE"


def test_gift_out_three_plus_stays_partial_without_options_quantity():
    result = _classify(
        "Gift Out: Apresentar 3 ou mais opções de brindes para os convidados.",
        row(
            "At the end of the event, guests will receive a gift.",
            anchor=0.0,
        ),
    )
    assert result["b210_class"] == "PARTIAL_OBLIGATION_COVERAGE"
    assert "minqty:3" in result["missing_hard_atoms"]
    assert "options" in result["missing_hard_atoms"]


def test_survey_requirement_not_high_from_event_close_gifts_only():
    result = _classify(
        "Pesquisa de satisfação aplicada ao final do evento, antes da entrega dos brindes.",
        row(
            "Gift distribution and event close.",
            anchor=0.0,
        ),
    )
    assert result["b210_class"] != "HIGH_CONFIDENCE_REVIEW_CANDIDATE"
