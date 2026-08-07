from selection_pdf import build_selection_pdf


def test_selection_pdf_accepts_legacy_extra_arguments():
    data = build_selection_pdf(
        [{"item_type": "product", "name": "Brinde teste", "category": "Kit"}],
        {"unused": True},
        title="Teste NAVE",
        include_images=True,
    )
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_selection_pdf_accepts_keyword_selected_records():
    data = build_selection_pdf(selected_records=[{"entity_type": "activation", "name": "Ativação teste"}])
    assert data.startswith(b"%PDF")
