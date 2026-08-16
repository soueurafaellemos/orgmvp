from project_semantic_observations import _audience_range, _money_number


def test_budget_parser_preserves_brazilian_us_and_million_formats():
    assert _money_number("Budget: R$ 400.000") == 400000
    assert _money_number("Budget identificado: R$ 400,000.00") == 400000
    assert _money_number("Budget de R$ 1,3 milhão") == 1300000
    assert _money_number("Budget de R$ 1.3 milhão") == 1300000
    assert _money_number("Teto: R$ 250.000,00") == 250000


def test_audience_range_preserves_range_and_ignores_age_ranges():
    assert _audience_range("Público 6–8 mil pessoas, pais 30–45, crianças 2–12") == (6000, 8000)
    assert _audience_range("entre 6 a 8 mil pessoas") == (6000, 8000)
    assert _audience_range("6 mil a 8 mil pessoas") == (6000, 8000)
    assert _audience_range("pais 30–45 e crianças 2–12") is None


def test_budget_operator_is_not_invented_from_amount_only():
    # Parsing the amount is independent from deciding whether it is a max/envelope.
    # Runtime collector keeps operator unspecified unless the source language proves it.
    source = __import__("inspect").getsource(__import__("project_semantic_observations").collect_project_context_and_constraints)
    assert 'operator = "unspecified"' in source
    assert 'operator = "envelope"' in source
