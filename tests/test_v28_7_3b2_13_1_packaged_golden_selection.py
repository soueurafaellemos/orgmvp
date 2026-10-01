from pathlib import Path
import hashlib

from project_requirement_response_truth_impact_shadow import (
    BASELINE_VERSION,
    GOLDEN_BASELINES,
    VERSION,
    golden_project_options,
    load_packaged_golden_baseline,
)


def test_version_and_two_golden_projects():
    assert VERSION == "V28.7.3B2.13.1"
    assert set(GOLDEN_BASELINES) == {
        "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136",
        "01415104-72f2-4b8e-aeca-2dd24c231a7d",
    }
    labels = {item["label"] for item in golden_project_options()}
    assert labels == {"Festivalzinho Chambinho", "Lançamento Jovi X300"}


def test_packaged_baselines_are_pinned_and_valid():
    root = Path(__file__).resolve().parents[1]
    for project_id, meta in GOLDEN_BASELINES.items():
        path = root / meta["relative_path"]
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"]
        payload = load_packaged_golden_baseline(project_id, repo_root=root)
        assert payload["version"] == BASELINE_VERSION
        assert payload["project_id"] == project_id


def test_page_uses_selector_not_manual_upload():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "pages/41_Response_Truth_Impact_Shadow.py"
    ).read_text(encoding="utf-8")
    assert "st.selectbox(" in source
    assert '"Projeto"' in source
    assert "st.file_uploader(" not in source
    assert "load_packaged_golden_baseline" in source


def test_shadow_module_has_no_db_mutation_calls():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_response_truth_impact_shadow.py"
    ).read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".delete(" not in source
    assert ".rpc(" not in source
