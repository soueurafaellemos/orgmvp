from pathlib import Path
import importlib.util


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "sitecustomize.py"
    spec = importlib.util.spec_from_file_location(
        "nave_sitecustomize_test",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _vulnerable_page() -> str:
    return '''from __future__ import annotations
import importlib
import pandas as pd

table_df = pd.DataFrame(table_rows)
if table_df.empty:
    selected_record = None
else:
    event = st.dataframe(
        table_df.drop(columns=["_id"]),
        key="nave_venue_type_table",
    )
    selected_rows = event.selection.rows if event else []
    selected_record = None
    if selected_rows:
        selected_id = str(table_df.iloc[selected_rows[0]]["_id"])
        selected_record = next(
            (
                row
                for row in venues
                if str(row.get("id") or "") == selected_id
            ),
            None,
        )
'''


def test_source_patch_adds_all_three_defenses():
    module = _load_module()
    corrected, recognized = module._patch_venue_selection_source(
        _vulnerable_page()
    )

    assert recognized is True
    assert "import hashlib" in corrected
    assert "reset_index(drop=True)" in corrected
    assert "table_signature_payload" in corrected
    assert "nave_venue_type_table_{table_signature}" in corrected
    assert "0 <= selected_position < len(table_df)" in corrected
    assert "table_df.iloc[selected_rows[0]]" not in corrected
    compile(corrected, "<patched_page>", "exec")


def test_patch_is_idempotent():
    module = _load_module()
    corrected, _ = module._patch_venue_selection_source(
        _vulnerable_page()
    )
    corrected_again, recognized = module._patch_venue_selection_source(
        corrected
    )

    assert recognized is True
    assert corrected_again == corrected


def test_invalid_selection_is_guarded():
    module = _load_module()
    corrected, _ = module._patch_venue_selection_source(
        _vulnerable_page()
    )

    assert "selected_position = -1" in corrected
    assert "if 0 <= selected_position < len(table_df):" in corrected
    assert "except (AttributeError, TypeError):" in corrected


def test_existing_integer_normalization_is_preserved():
    module = _load_module()
    payload = {
        "standing_capacity": "300.0",
        "nested": {"room_count": 4.0},
        "description": "300.0 pessoas",
    }

    normalized = module._normalize_payload(payload)

    assert normalized["standing_capacity"] == 300
    assert normalized["nested"]["room_count"] == 4
    assert normalized["description"] == "300.0 pessoas"
