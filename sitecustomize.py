"""NAVE: normaliza campos inteiros antes de qualquer envio ao PostgREST.

Planilhas lidas pelo Pandas podem representar valores inteiros como floats
quando a mesma coluna possui células vazias. Assim, capacidades como 250,
2000 e 6400 podem chegar ao payload como ``250.0`` ou ``"250.0"``. O
PostgreSQL rejeita essas strings em colunas do tipo integer.

Este arquivo usa o mecanismo padrão ``sitecustomize`` do Python para aplicar
a correção antes da inicialização do Streamlit, sem substituir o restante do
``supabase_db.py`` e sem interferir em áreas, preços ou outros decimais.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real
from typing import Any

_INTEGER_TEXT = re.compile(r"^[+-]?\d+$")
_INTEGER_FLOAT_TEXT = re.compile(r"^[+-]?\d+\.0+$")

# Campos inteiros atualmente usados pela NAVE e alguns equivalentes mantidos
# para compatibilidade com importações anteriores.
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

_INTEGER_PREFIXES = (
    "capacity_",
)

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
    """Converte apenas valores integralmente representáveis em ``int``."""
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

    # Valores não integrais e textos descritivos permanecem inalterados.
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
        # A aplicação pode iniciar sem Supabase em ambientes locais de teste.
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


_install_postgrest_patch()
