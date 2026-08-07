"""Ajustes de compatibilidade carregados antes da inicialização da NAVE.

Este arquivo mantém duas proteções independentes:

1. normalização de campos inteiros antes de envios ao PostgREST;
2. correção idempotente da seleção da tabela de Locais e espaços.

O segundo ajuste existe porque o Streamlit pode conservar a posição de uma
linha selecionada mesmo depois de busca ou filtros reduzirem a tabela. Sem a
validação, o Pandas recebe uma posição que já não existe e gera:

    IndexError: single positional indexer is out-of-bounds

A correção altera somente o bloco vulnerável da página e preserva o restante
do arquivo publicado no repositório.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 1. Normalização de campos inteiros enviados ao PostgREST
# ---------------------------------------------------------------------------

_INTEGER_TEXT = re.compile(r"^[+-]?\d+$")
_INTEGER_FLOAT_TEXT = re.compile(r"^[+-]?\d+\.0+$")

_EXACT_INTEGER_FIELDS = {
    "capacity",
    "capacity_ml",
    "standing_capacity",
    "seated_capacity",
    "auditorium_capacity",
    "capacity_standing",
    "capacity_seated",
    "capacity_auditorium",
    "parking_capacity",
    "parking_spaces",
    "rooms_count",
    "room_count",
    "document_year",
    "price_reference_qty",
    "min_order_qty",
    "lead_time_days",
    "travel_lead_days",
    "source_page",
    "page_count",
    "slides_count",
    "items_count",
    "rendered_pages_count",
    "visual_crops_count",
}

_INTEGER_PREFIXES = ("capacity_",)

_INTEGER_SUFFIXES = (
    "_capacity",
    "_count",
    "_days",
    "_qty",
    "_spaces",
    "_page",
    "_pages",
    "_year",
)


def _is_integer_field(key: Any) -> bool:
    normalized = str(key or "").strip().casefold()
    if not normalized:
        return False
    if normalized in _EXACT_INTEGER_FIELDS:
        return True
    if normalized.startswith(_INTEGER_PREFIXES):
        return True
    return normalized.endswith(_INTEGER_SUFFIXES)


def _normalize_integer(value: Any) -> Any:
    """Converte apenas valores integralmente representáveis em int."""
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, Integral):
        return int(value)

    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        if value == value.to_integral_value():
            return int(value)
        return value

    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            return None
        if number.is_integer():
            return int(number)
        return value

    text = str(value).strip()
    if not text:
        return None

    if _INTEGER_TEXT.fullmatch(text):
        return int(text)

    if _INTEGER_FLOAT_TEXT.fullmatch(text):
        try:
            return int(Decimal(text))
        except (InvalidOperation, ValueError, OverflowError):
            return value

    return value


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_integer_field(key):
                normalized[key] = _normalize_integer(item)
            else:
                normalized[key] = _normalize_payload(item)
        return normalized

    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_normalize_payload(item) for item in value)

    return value


def _install_postgrest_patch() -> None:
    """Aplica a normalização imediatamente antes do request HTTP."""
    try:
        from postgrest.base_request_builder import RequestConfig
    except Exception:
        return

    original_send = RequestConfig.send
    if getattr(original_send, "_nave_integer_normalization", False):
        return

    def patched_send(self: Any, additional_headers: Any):
        payload = getattr(self, "json", None)
        if payload is not None:
            self.json = _normalize_payload(payload)
        return original_send(self, additional_headers)

    patched_send._nave_integer_normalization = True  # type: ignore[attr-defined]
    patched_send.__name__ = getattr(original_send, "__name__", "send")
    patched_send.__doc__ = getattr(original_send, "__doc__", None)
    RequestConfig.send = patched_send


# ---------------------------------------------------------------------------
# 2. Correção definitiva da seleção da tabela de locais
# ---------------------------------------------------------------------------

_VULNERABLE_SELECTION_BLOCK = """\
    selected_rows = event.selection.rows if event else []
    selected_record = None
    if selected_rows:
        selected_id = str(table_df.iloc[selected_rows[0]][\"_id\"])
        selected_record = next(
            (
                row
                for row in venues
                if str(row.get(\"id\") or \"\") == selected_id
            ),
            None,
        )
"""

_SAFE_SELECTION_BLOCK = """\
    selected_rows = []
    if event:
        try:
            selected_rows = list(event.selection.rows or [])
        except (AttributeError, TypeError):
            selected_rows = []

    selected_record = None
    if selected_rows:
        try:
            selected_position = int(selected_rows[0])
        except (TypeError, ValueError):
            selected_position = -1

        # A seleção armazenada pelo Streamlit pode se referir à tabela
        # anterior. Só acessamos o DataFrame se a posição ainda existir.
        if 0 <= selected_position < len(table_df):
            selected_id = str(
                table_df.iloc[selected_position].get(\"_id\") or \"\"
            ).strip()
            if selected_id:
                selected_record = next(
                    (
                        row
                        for row in venues
                        if str(row.get(\"id\") or \"\") == selected_id
                    ),
                    None,
                )
"""

_VULNERABLE_TABLE_KEY = '        key="nave_venue_type_table",'
_SAFE_TABLE_KEY = '        key=f"nave_venue_type_table_{table_signature}",'

_VULNERABLE_DATAFRAME_LINE = "table_df = pd.DataFrame(table_rows)"
_SAFE_DATAFRAME_BLOCK = """\
table_df = pd.DataFrame(table_rows).reset_index(drop=True)

# A chave muda quando filtros ou linhas visíveis mudam. Isso impede que
# uma seleção da tabela anterior seja reaproveitada na tabela atual.
table_signature_payload = "\\x1f".join(
    [
        str(search),
        str(selected_type),
        str(selected_state),
        str(selected_media),
        *(
            table_df["_id"].astype(str).tolist()
            if "_id" in table_df.columns
            else []
        ),
    ]
)
table_signature = hashlib.sha256(
    table_signature_payload.encode("utf-8")
).hexdigest()[:16]
"""


def _patch_venue_selection_source(source: str) -> tuple[str, bool]:
    """Retorna o código corrigido e informa se reconheceu a estrutura."""
    updated = source

    if "import hashlib" not in updated:
        if "import importlib\n" in updated:
            updated = updated.replace(
                "import importlib\n",
                "import hashlib\nimport importlib\n",
                1,
            )
        else:
            updated = "import hashlib\n" + updated

    if (
        _VULNERABLE_DATAFRAME_LINE in updated
        and "table_signature_payload" not in updated
    ):
        updated = updated.replace(
            _VULNERABLE_DATAFRAME_LINE,
            _SAFE_DATAFRAME_BLOCK,
            1,
        )

    if _VULNERABLE_TABLE_KEY in updated:
        updated = updated.replace(
            _VULNERABLE_TABLE_KEY,
            _SAFE_TABLE_KEY,
            1,
        )

    if _VULNERABLE_SELECTION_BLOCK in updated:
        updated = updated.replace(
            _VULNERABLE_SELECTION_BLOCK,
            _SAFE_SELECTION_BLOCK,
            1,
        )

    already_safe = all(
        marker in updated
        for marker in (
            "import hashlib",
            "table_signature_payload",
            "nave_venue_type_table_{table_signature}",
            "0 <= selected_position < len(table_df)",
        )
    )

    return updated, already_safe


def _patch_venue_selection_page() -> None:
    """Corrige as cópias conhecidas da página sem alterar outros arquivos."""
    repository_root = Path(__file__).resolve().parent
    candidates = (
        repository_root / "pages" / "11_Locais_e_Espacos.py",
        repository_root / "11_Locais_e_Espacos.py",
    )

    for page_path in candidates:
        if not page_path.exists() or not page_path.is_file():
            continue

        try:
            original = page_path.read_text(encoding="utf-8")
        except OSError:
            continue

        corrected, recognized = _patch_venue_selection_source(original)
        if not recognized or corrected == original:
            continue

        try:
            page_path.write_text(corrected, encoding="utf-8")
        except OSError:
            # O app continua iniciando mesmo em ambiente somente leitura.
            continue


_install_postgrest_patch()
_patch_venue_selection_page()
