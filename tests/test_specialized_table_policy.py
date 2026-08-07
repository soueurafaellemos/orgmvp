from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "knowledge_specialized.py").read_text(encoding="utf-8")


def test_specialized_pages_use_selectable_table_not_cards():
    assert 'selection_mode="single-row"' in SOURCE
    assert 'st.column_config.ImageColumn("Capa"' in SOURCE
    assert "def render_cards" not in SOURCE


def test_source_image_is_not_used_as_cover_fallback():
    fallback = SOURCE.split("def _fallback_image", 1)[1].split("def source_preview_url", 1)[0]
    assert "source_image_url" not in fallback
    assert "full_slide_url" not in fallback
