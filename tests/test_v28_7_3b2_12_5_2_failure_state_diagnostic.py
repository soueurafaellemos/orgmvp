from pathlib import Path


def test_failure_diagnostic_is_read_only():
    root = Path(__file__).resolve().parents[1]
    source = (root / "project_requirement_supersession_failure_diagnostic.py").read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".update(" not in source
    assert ".delete(" not in source
    assert ".rpc(" not in source
    assert "safe_to_retry_writer\": False" in source


def test_failure_page_has_no_writer_import():
    root = Path(__file__).resolve().parents[1]
    source = (root / "pages/39_Requirement_Supersession_Failure_State_Diagnostic.py").read_text(encoding="utf-8")
    assert "execute_governed_supersession" not in source
    assert "file_uploader" in source
    assert "read-only" in source.lower()
