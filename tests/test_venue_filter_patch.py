from venue_filter_patch import canonical_type, filter_venues, option_code


VENUES = [
    {"LOCAL": "ARCA", "CATEGORIA": "GALPÃO / FÁBRICA", "GRUPO_LOCAL": "industrial", "ESTADO": "SP"},
    {"LOCAL": "São Paulo Expo", "TIPO_LOCAL_PADRONIZADO": "CENTRO DE CONVENÇÕES/ PAVILHÃO", "GRUPO_LOCAL": "convencoes_pavilhoes", "ESTADO": "SP"},
    {"LOCAL": "Casa Petra", "CATEGORIA": "ESPAÇO DE EVENTOS", "GRUPO_LOCAL": "espacos_eventos", "ESTADO": "SP"},
    {"LOCAL": "Audio", "CATEGORIA": "CASAS DE SHOW", "GRUPO_LOCAL": "casas_show", "ESTADO": "SP"},
    {"LOCAL": "Teatro Gazeta", "CATEGORIA": "TEATROS / AUDITÓRIOS", "GRUPO_LOCAL": "teatros_auditorios", "ESTADO": "SP"},
    {"LOCAL": "Hotel Unique", "CATEGORIA": "HOTÉIS", "GRUPO_LOCAL": "hoteis", "ESTADO": "SP"},
    {"LOCAL": "Riviera Bar", "CATEGORIA": "BARES", "GRUPO_LOCAL": "bares", "ESTADO": "SP"},
    {"LOCAL": "Restaurante Praça São Lourenço", "CATEGORIA": "RESTAURANTES", "GRUPO_LOCAL": "restaurantes", "ESTADO": "SP"},
    {"LOCAL": "Pinacoteca de São Paulo", "CATEGORIA": "GALERIAS DE ARTE", "GRUPO_LOCAL": "galerias_arte", "ESTADO": "SP"},
    {"LOCAL": "Neo Química Arena", "CATEGORIA": "ESTÁDIOS", "GRUPO_LOCAL": "estadios", "ESTADO": "SP"},
]


def test_all_ten_types_are_filterable():
    type_codes = [
        "industrial",
        "convencoes_pavilhoes",
        "espacos_eventos",
        "casas_show",
        "teatros_auditorios",
        "hoteis",
        "bares",
        "restaurantes",
        "galerias_arte",
        "estadios",
    ]
    for code in type_codes:
        result = filter_venues(VENUES, type_code=code)
        assert len(result) == 1, code


def test_arena_plus_stadium_type_returns_neo_quimica_arena():
    result = filter_venues(VENUES, search="arena", type_code="Estádios")
    assert [item["LOCAL"] for item in result] == ["Neo Química Arena"]


def test_new_stadium_label_works():
    result = filter_venues(VENUES, type_code="Estádios e arenas")
    assert [item["LOCAL"] for item in result] == ["Neo Química Arena"]


def test_case_and_accents_do_not_change_results():
    assert option_code("ESTADIOS") == "estadios"
    assert option_code("Estádios") == "estadios"
    assert option_code("estádios e arenas") == "estadios"


def test_legacy_unclassified_arena_is_inferred_safely():
    record = {"LOCAL": "Arena Teste", "CATEGORIA": "", "GRUPO_LOCAL": None}
    assert canonical_type(record) == "estadios"
    assert len(filter_venues([record], type_code="estadios")) == 1


def test_unknown_record_only_appears_in_all_or_undefined():
    record = {"LOCAL": "Local sem classificação"}
    assert len(filter_venues([record])) == 1
    assert len(filter_venues([record], type_code="Tipo não definido")) == 1
    assert len(filter_venues([record], type_code="estadios")) == 0


def test_state_filter_is_independent():
    records = VENUES + [
        {"LOCAL": "Arena RJ", "CATEGORIA": "ESTÁDIOS", "GRUPO_LOCAL": "estadios", "ESTADO": "RJ"}
    ]
    result = filter_venues(records, search="arena", type_code="estadios", state="SP")
    assert [item["LOCAL"] for item in result] == ["Neo Química Arena"]


def test_collection_filter_is_independent():
    records = [
        {"LOCAL": "Arena com foto", "GRUPO_LOCAL": "estadios", "media_count": 1},
        {"LOCAL": "Arena sem foto", "GRUPO_LOCAL": "estadios", "media_count": 0},
    ]
    with_media = filter_venues(records, type_code="estadios", collection="Com acervo")
    without_media = filter_venues(records, type_code="estadios", collection="Sem acervo")
    assert [item["LOCAL"] for item in with_media] == ["Arena com foto"]
    assert [item["LOCAL"] for item in without_media] == ["Arena sem foto"]
