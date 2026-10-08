from project_requirement_response_truth_projection_shadow import (
    _current_requirement_truth_rows,
)


def test_current_truth_filter_excludes_historical_rows():
    rows = [
        {
            "id": "a",
            "truth_state": "verified",
            "lifecycle_status": "active",
        },
        {
            "id": "b",
            "truth_state": "human_confirmed",
            "lifecycle_status": "active",
        },
        {
            "id": "c",
            "truth_state": "legacy_unverified",
            "lifecycle_status": "active",
        },
        {
            "id": "d",
            "truth_state": "verified",
            "lifecycle_status": "superseded",
        },
        {
            "id": "e",
            "truth_state": "verified",
            "lifecycle_status": "historical",
        },
    ]
    current = _current_requirement_truth_rows(rows)
    assert [row["id"] for row in current] == ["a", "b"]


def test_module_remains_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_response_truth_projection_shadow.py"
    ).read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".delete(" not in source
    assert ".rpc(" not in source
    assert "lifecycle_status" in source
    assert "human_confirmed" in source
