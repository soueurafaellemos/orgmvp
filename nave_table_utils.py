from __future__ import annotations

from typing import Any

import pandas as pd

from nave_runtime_fixes import apply_runtime_fixes


# Mantém instalada a V28.0.3.4 de ingestão resiliente de Locais.
# ``branding`` importa este módulo antes dos extratores nas páginas da NAVE,
# portanto o hotfix transversal continua ativo sem duplicação de código.
apply_runtime_fixes()


COVER_COLUMN_NAMES = ("Capa", "capa")
_MISSING_COVER_TEXT = {"", "none", "nan", "null", "<na>", "n/a", "na"}


def clean_cover_value(value: Any) -> str | None:
    """Normaliza capa ausente como valor nulo real, nunca como texto ``None``."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.casefold() in _MISSING_COVER_TEXT:
        return None
    return text


def sanitize_cover_dataframe(data: Any) -> Any:
    """Copia DataFrames e limpa apenas colunas chamadas Capa/capa."""
    if not isinstance(data, pd.DataFrame):
        return data
    cover_columns = [name for name in COVER_COLUMN_NAMES if name in data.columns]
    if not cover_columns:
        return data
    result = data.copy()
    for column in cover_columns:
        result[column] = result[column].map(clean_cover_value)
    return result
