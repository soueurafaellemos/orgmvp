from venue_types import (
    ALL_VENUE_TYPES,
    UNDEFINED_VENUE_TYPE,
    deduplicate_venue_records,
    display_venue_type,
    filter_records_by_type,
    normalize_venue_type,
    safe_type_from_record,
    venue_group,
)


def _allianz_records():
    return [
        {
            "id": "1",
            "name": "Allianz Parque",
            "venue_type": "Arena / Estádio",
            "city": "São Paulo",
            "state": "SP",
        },
        {
            "id": "2",
            "name": "Allianz Parque",
            "venue_type": "Arena / Estádio",
            "city": "São Paulo",
            "state": "SP",
            "description": "Arena multiuso.",
        },
        {
            "id": "3",
            "name": "Allianz Parque (Nubank Parque)",
            "venue_type": "Arena / Estádio",
            "city": "São Paulo",
            "state": "SP",
            "website_url": "https://allianzparque.com.br/",
        },
        {
            "id": "4",
            "name": "PARQUE MIRANTE",
            "venue_type": "Espaço de Eventos",
            "city": "São Paulo",
            "state": "SP",
        },
    ]


def test_arena_estadio_alias_is_canonical_stadium():
    assert normalize_venue_type("Arena / Estádio") == "Estádios"
    assert normalize_venue_type("arena") == "Estádios"
    assert normalize_venue_type("ARENAS") == "Estádios"
    assert display_venue_type("Arena / Estádio") == "Estádios"
    assert venue_group("Arena / Estádio") == "Esportivo"


def test_stadium_filter_returns_allianz_instead_of_empty_list():
    filtered = filter_records_by_type(
        _allianz_records(),
        "Estádios",
    )
    assert len(filtered) == 1
    assert filtered[0]["name"].startswith("Allianz Parque")


def test_all_filter_hides_strong_allianz_repetitions():
    filtered = filter_records_by_type(
        _allianz_records(),
        ALL_VENUE_TYPES,
    )
    names = [record["name"] for record in filtered]
    assert len(filtered) == 2
    assert sum(name.startswith("Allianz Parque") for name in names) == 1
    assert "PARQUE MIRANTE" in names


def test_parque_mirante_is_not_collapsed_into_allianz():
    filtered = deduplicate_venue_records(_allianz_records())
    assert any(record["name"] == "PARQUE MIRANTE" for record in filtered)


def test_same_name_in_different_states_remains_separate():
    records = [
        {
            "id": "1",
            "name": "Arena Central",
            "venue_type": "Arena",
            "city": "São Paulo",
            "state": "SP",
        },
        {
            "id": "2",
            "name": "Arena Central",
            "venue_type": "Arena",
            "city": "Rio de Janeiro",
            "state": "RJ",
        },
    ]
    assert len(deduplicate_venue_records(records)) == 2


def test_explicit_raw_category_is_used_as_fallback():
    record = {
        "name": "Local legado",
        "venue_type": "Não informado",
        "raw_data": {"CATEGORIA": "ESTÁDIOS"},
    }
    assert safe_type_from_record(record) == "Estádios"
    assert len(filter_records_by_type([record], "Estádios")) == 1


def test_unknown_type_appears_in_undefined():
    record = {
        "name": "Local sem tipo",
        "venue_type": "Não informado",
    }
    assert len(
        filter_records_by_type(
            [record],
            UNDEFINED_VENUE_TYPE,
        )
    ) == 1


def test_all_ten_types_still_work():
    records = [
        {"name": "A", "venue_type": "Galpão / Fábrica"},
        {"name": "B", "venue_type": "Centro de Convenções / Pavilhão"},
        {"name": "C", "venue_type": "Espaço de Eventos"},
        {"name": "D", "venue_type": "Casas de Show"},
        {"name": "E", "venue_type": "Teatros / Auditórios"},
        {"name": "F", "venue_type": "Hotéis"},
        {"name": "G", "venue_type": "Bares"},
        {"name": "H", "venue_type": "Restaurantes"},
        {"name": "I", "venue_type": "Galerias de Arte"},
        {"name": "J", "venue_type": "Estádios"},
    ]
    labels = [
        "Galpão / Fábrica",
        "Centro de Convenções / Pavilhão",
        "Espaço de Eventos",
        "Casas de Show",
        "Teatros / Auditórios",
        "Hotéis",
        "Bares",
        "Restaurantes",
        "Galerias de Arte",
        "Estádios",
    ]
    for label in labels:
        assert len(filter_records_by_type(records, label)) == 1
