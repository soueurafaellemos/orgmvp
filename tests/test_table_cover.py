import pandas as pd
from nave_table_utils import clean_cover_value, sanitize_cover_dataframe


def test_none_never_appears_as_cover_text():
    df = pd.DataFrame({"Capa": [None, "None", "https://example.com/a.jpg"], "Nome": ["A", "B", "C"]})
    result = sanitize_cover_dataframe(df)
    assert result["Capa"].tolist() == ["", "", "https://example.com/a.jpg"]


def test_non_table_value_is_unchanged():
    value = [{"Capa": None}]
    assert sanitize_cover_dataframe(value) is value
