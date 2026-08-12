from pathlib import Path

import pytest

from project_batch_ingestion import ProjectBatchError, save_project_bundle


def test_save_project_bundle_rejects_shadowed_string_client_before_side_effects():
    with pytest.raises(ProjectBatchError) as exc:
        save_project_bundle(
            "Lactalis",
            documents=[],
            role_overrides=None,
            include_sha256=None,
            project_name="Festivalzinho Chambinho 2026",
            client_brand="Chambinho",
            event_name="Festivalzinho 2026",
        )
    assert "conexão de dados" in str(exc.value).casefold()


def test_import_page_does_not_shadow_global_client_in_existing_project_loop():
    page = Path(__file__).resolve().parents[1] / "pages" / "14_Importar_Projeto.py"
    text = page.read_text(encoding="utf-8")
    assert 'project_client_label = str(row.get("client_brand")' in text
    assert 'client = str(row.get("client_brand")' not in text


def test_destination_state_is_explicit_and_reset_for_new_upload_set():
    page = Path(__file__).resolve().parents[1] / "pages" / "14_Importar_Projeto.py"
    text = page.read_text(encoding="utf-8")
    assert 'key="v281_destination"' in text
    assert '"v281_destination",' in text
