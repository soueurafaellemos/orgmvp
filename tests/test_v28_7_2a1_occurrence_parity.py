from project_domain_normalization import _legacy_occurrence_coverage


def _memory(n=3):
    return [{"id": f"m{i}"} for i in range(1, n + 1)]


def test_legacy_occurrence_coverage_allows_semantic_growth():
    rows = [
        {"id": "o1", "legacy_memory_item_id": "m1"},
        {"id": "o2", "legacy_memory_item_id": "m2"},
        {"id": "o3", "legacy_memory_item_id": "m3"},
        # V28.7.2A evidence-led occurrences: no legacy memory_item identity.
        {"id": "o4", "legacy_memory_item_id": None},
        {"id": "o5", "legacy_memory_item_id": None},
    ]
    result = _legacy_occurrence_coverage(_memory(), rows)
    assert result["ok"] is True
    assert result["expected"] == 3
    assert result["represented_exactly_once"] == 3
    assert result["semantic_or_other_occurrences"] == 2
    assert result["total_occurrences"] == 5


def test_legacy_occurrence_coverage_fails_closed_when_memory_item_missing():
    rows = [
        {"id": "o1", "legacy_memory_item_id": "m1"},
        {"id": "o2", "legacy_memory_item_id": "m2"},
        {"id": "semantic", "legacy_memory_item_id": None},
    ]
    result = _legacy_occurrence_coverage(_memory(), rows)
    assert result["ok"] is False
    assert result["missing_ids"] == ["m3"]


def test_legacy_occurrence_coverage_fails_closed_on_duplicate_legacy_reference():
    rows = [
        {"id": "o1", "legacy_memory_item_id": "m1"},
        {"id": "o1b", "legacy_memory_item_id": "m1"},
        {"id": "o2", "legacy_memory_item_id": "m2"},
        {"id": "o3", "legacy_memory_item_id": "m3"},
    ]
    result = _legacy_occurrence_coverage(_memory(), rows)
    assert result["ok"] is False
    assert result["duplicate_ids"] == ["m1"]
