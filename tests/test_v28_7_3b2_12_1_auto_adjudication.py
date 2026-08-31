from project_requirement_auto_adjudication_recommendation import (
    recommend_candidate,
    build_automated_adjudication_recommendations,
)

def row(title, evidence, status="response_review_partial", cov=0.5, anchor=0.0,
        req="", shared="", missing="", hard=""):
    return {
        "candidate_id": title[:8],
        "requirement_title": title,
        "evidence_text": evidence,
        "projected_response_status": status,
        "obligation_atom_coverage": cov,
        "title_anchor_coverage": anchor,
        "requirement_atoms": req,
        "shared_atoms": shared,
        "missing_atoms": missing,
        "missing_hard_atoms": hard,
    }

def test_high_confidence_full_obligation_auto_recommends_confirm():
    r = recommend_candidate(row(
        "Materiais Gráficos: convite, STD, Reminder",
        "Save the Date Online invitation Reminder",
        status="response_review_high_confidence",
        cov=1.0, anchor=0.1,
        req="invitation | reminder | save_the_date",
        shared="invitation | reminder | save_the_date",
    ))
    assert r["machine_recommendation"] == "recommend_confirm"
    assert r["human_review_created"] is False
    assert r["truth_effect_applied"] is False

def test_survey_without_survey_is_rejected():
    r = recommend_candidate(row(
        "Pesquisa de satisfação aplicada ao final do evento, antes da entrega dos brindes;",
        "Gift distribution and event close",
        cov=0.4,
        req="before | end_event | gifts | satisfaction | survey",
        shared="end_event | gifts",
        missing="before | satisfaction | survey",
    ))
    assert r["machine_recommendation"] == "recommend_reject"

def test_direct_payment_without_payment_evidence_is_rejected():
    r = recommend_candidate(row(
        "O pagamento será realizado diretamente pela JOVI nos casos dos fornecedores de cenografia, A&B, Artístico",
        "Food & beverage service with water and soda",
        cov=0.5, req="budget | food_beverage", shared="food_beverage", missing="budget",
    ))
    assert r["machine_recommendation"] == "recommend_reject"

def test_vegan_requirement_with_generic_food_is_partial():
    r = recommend_candidate(row(
        "Considerar um A&B que também tenha opções veganas e vegetarianas;",
        "Food & beverage service with water and soda",
        cov=0.5, req="food_beverage | options", shared="food_beverage", missing="options", hard="options",
    ))
    assert r["machine_recommendation"] == "recommend_partial"

def test_coinvestment_is_not_satisfied_by_generic_partnership():
    r = recommend_candidate(row(
        "Viabilizar parcerias de co-investimento, patrocínio e compartilhamento de verba",
        "Thank guests and value the partnership with JOVI",
        cov=0.5, req="content | partnership", shared="partnership", missing="content",
    ))
    assert r["machine_recommendation"] == "recommend_reject"

def test_recap_video_not_satisfied_by_venue_video_word():
    r = recommend_candidate(row(
        "Vídeo Memória: entrega de vídeo resumo do evento",
        "The cultural venue features photography, video and interactive works.",
        cov=1.0, anchor=0.1, req="video", shared="video",
    ))
    assert r["machine_recommendation"] == "recommend_reject"

def test_registration_checkin_is_partial_not_confirmed():
    r = recommend_candidate(row(
        "O local deve contemplar: Sistema de credenciamento;",
        "Guest arrival, check-in and welcome drinks.",
        cov=1.0, anchor=0.2, req="registration", shared="registration",
    ))
    assert r["machine_recommendation"] == "recommend_partial"

def test_visual_review_stays_visual():
    r = recommend_candidate(row(
        "Press kit",
        "PRESS KIT",
        status="response_review_visual_or_structured_evidence",
        cov=1.0, req="press_kit", shared="press_kit",
    ))
    assert r["machine_recommendation"] == "recommend_visual_review"

def test_package_is_machine_only():
    result = build_automated_adjudication_recommendations(
        project_id="p1",
        queue_rows=[
            row("Plenária", "plenary", status="response_review_high_confidence",
                cov=1.0, anchor=0.6, req="plenary", shared="plenary"),
            row("Pesquisa curta", "event close", cov=0.0, req="survey"),
        ],
    )
    d = result.to_dict()
    assert d["queue_count"] == 2
    assert d["human_review_created"] is False
    assert d["truth_changed"] is False
    assert d["persistence_performed"] is False
    assert d["cutover_approved"] is False
