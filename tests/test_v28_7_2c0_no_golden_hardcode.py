from pathlib import Path


def test_c0_runtime_has_no_golden_project_or_client_hardcode():
    root = Path(__file__).parents[1]
    files = [
        root / "project_requirement_identity.py",
        root / "project_requirement_semantic_extractor.py",
        root / "project_requirement_reconciliation.py",
        root / "project_intelligence_pipeline.py",
    ]
    forbidden = ("chambinho", "festivalzinho", "jovi", "lactalis")
    for path in files:
        text = path.read_text(encoding="utf-8").casefold()
        for token in forbidden:
            assert token not in text, f"{token!r} leaked into C0 runtime: {path.name}"
