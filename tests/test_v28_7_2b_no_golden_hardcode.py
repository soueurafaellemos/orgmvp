from pathlib import Path


def test_production_core_semantic_files_have_no_golden_specific_names():
    root = Path(__file__).parents[1]
    files = [
        root / "project_core_semantic_extractor.py",
        root / "project_core_semantic_domains.py",
        root / "project_semantic_relations.py",
        root / "project_intelligence_pipeline.py",
    ]
    forbidden = ("chambinho", "jovi", "on tour")
    for path in files:
        text = path.read_text(encoding="utf-8").casefold()
        for token in forbidden:
            assert token not in text, f"{token!r} leaked into production core: {path.name}"
