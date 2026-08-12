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



# A V28.2 não altera mais arquivos-fonte durante o runtime.
# A correção de seleção de Locais está versionada diretamente na página.

_install_postgrest_patch()
