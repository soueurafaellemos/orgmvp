from knowledge_specialized import _parse_editor_value


def test_product_capacity_remains_free_text():
    assert _parse_editor_value("capacity", "Até 500 pessoas", None) == "Até 500 pessoas"


def test_evidence_remains_text():
    assert _parse_editor_value("evidence", "Slide e orçamento confirmam a entrega.", None) == "Slide e orçamento confirmam a entrega."


def test_array_fields_stay_arrays():
    assert _parse_editor_value("tags", "photo-op\ninstagramável", []) == ["photo-op", "instagramável"]
