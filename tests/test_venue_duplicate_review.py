from venue_duplicate_review import (
    collapse_duplicate_display_rows,
    compare_venues,
    find_existing_venue_duplicates,
)


VENUES = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "Allianz Parque",
        "venue_type": "Arena / Estádio",
        "address": "Av. Francisco Matarazzo, 1705 - Água Branca, São Paulo - SP",
        "city": "São Paulo",
        "state": "SP",
        "postal_code": "05001-200",
        "website_url": "https://www.nubankparque.com/",
        "created_at": "2026-08-01T10:00:00+00:00",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "name": "Allianz Parque",
        "venue_type": "Arena / Estádio",
        "address": "Av. Francisco Matarazzo, 1705 - Água Branca, São Paulo - SP",
        "city": "São Paulo",
        "state": "SP",
        "postal_code": "05001-200",
        "website_url": "https://nubankparque.com/",
        "created_at": "2026-08-02T10:00:00+00:00",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "name": "Allianz Parque (Nubank Parque)",
        "venue_type": "Arena / Estádio",
        "address": "Av. Francisco Matarazzo, 1705 - Água Branca, São Paulo - SP",
        "city": "São Paulo",
        "state": "SP",
        "postal_code": "05001-200",
        "website_url": "https://www.nubankparque.com/",
        "created_at": "2026-08-03T10:00:00+00:00",
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "name": "PARQUE MIRANTE",
        "venue_type": "Espaço de Eventos",
        "address": "Av. Francisco Matarazzo, 1705 - Água Branca, São Paulo - SP",
        "city": "São Paulo",
        "state": "SP",
        "postal_code": "05001-200",
        "website_url": "https://parquemirante.com/",
        "created_at": "2026-08-04T10:00:00+00:00",
    },
]


def test_exact_duplicate_is_detected():
    candidate = compare_venues(VENUES[0], VENUES[1])
    assert candidate is not None
    assert candidate.similarity_score == 1.0
    assert candidate.match_method == "exact_normalized_name"


def test_renamed_parenthetical_variant_is_detected():
    candidate = compare_venues(VENUES[0], VENUES[2])
    assert candidate is not None
    assert candidate.similarity_score >= 0.98
    assert candidate.match_method == "same_base_name"


def test_child_space_at_same_address_is_not_duplicate():
    assert compare_venues(VENUES[0], VENUES[3]) is None


def test_existing_scan_returns_allianz_pairs_but_not_parque_mirante():
    candidates = find_existing_venue_duplicates(VENUES)
    assert len(candidates) == 3
    names = {
        frozenset((candidate.source_name, candidate.candidate_name))
        for candidate in candidates
    }
    assert not any("PARQUE MIRANTE" in pair for pair in names)


def test_query_display_collapses_three_allianz_records():
    collapsed = collapse_duplicate_display_rows(VENUES)
    assert len(collapsed) == 2
    allianz = next(row for row in collapsed if row["name"] == "Allianz Parque")
    assert allianz["_duplicate_record_count"] == 3
    assert allianz["_duplicate_review_pending"] is True
    mirante = next(row for row in collapsed if row["name"] == "PARQUE MIRANTE")
    assert mirante["_duplicate_record_count"] == 1
