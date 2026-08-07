from knowledge_project_links import RELATIONSHIP_LABELS, relationship_display


def test_relationship_labels_are_stable():
    assert RELATIONSHIP_LABELS["origin_project"] == "Projeto de origem"
    assert RELATIONSHIP_LABELS["executed_in_project"] == "Executado no projeto"
    assert RELATIONSHIP_LABELS["venue_for_project"] == "Local do projeto"


def test_custom_relationship_label_wins():
    assert relationship_display("used_in_project", "Press kit da ação") == "Press kit da ação"
