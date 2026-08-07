from __future__ import annotations

import importlib
import sys
import types

import pytest


class VenueBatch:
    pass


class CatalogBatch:
    pass


def _fresh_runtime_fixes(monkeypatch, structured_call, record_event):
    gemini = types.ModuleType("gemini_extractor")
    gemini._structured_call = structured_call
    monkeypatch.setitem(sys.modules, "gemini_extractor", gemini)

    supabase = types.ModuleType("supabase_db")
    supabase._record_enrichment_event = record_event

    def integer_or_none(value):
        if value is None or value == "":
            return None
        number = float(value)
        return int(number) if number.is_integer() else None

    supabase._integer_or_none = integer_or_none
    monkeypatch.setitem(sys.modules, "supabase_db", supabase)

    sys.modules.pop("nave_runtime_fixes", None)
    module = importlib.import_module("nave_runtime_fixes")
    return module, gemini, supabase


def test_truncated_venue_json_retries_once_with_compact_prompt(monkeypatch):
    calls = []

    def structured_call(client, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError(
                "Estrutura inválida: Invalid JSON: EOF while parsing a string "
                "[type=json_invalid]"
            )
        return "ok"

    def record_event(client, **kwargs):
        return None

    module, gemini, _ = _fresh_runtime_fixes(
        monkeypatch,
        structured_call,
        record_event,
    )
    module.apply_runtime_fixes()

    result = gemini._structured_call(
        object(),
        model="gemini-test",
        prompt="PROMPT ORIGINAL",
        docs=[object()],
        schema=VenueBatch,
        context="volume03_p13.pdf",
    )

    assert result == "ok"
    assert len(calls) == 2
    assert calls[0]["prompt"] == "PROMPT ORIGINAL"
    assert "REPROCESSAMENTO DE SEGURANÇA NAVE" in calls[1]["prompt"]
    assert "evidence: no máximo 300 caracteres" in calls[1]["prompt"]
    assert calls[1]["context"].endswith("[retry compacto NAVE]")


def test_non_venue_schema_does_not_retry(monkeypatch):
    calls = []

    def structured_call(client, **kwargs):
        calls.append(kwargs)
        raise RuntimeError(
            "Estrutura inválida: Invalid JSON: EOF while parsing a string"
        )

    def record_event(client, **kwargs):
        return None

    module, gemini, _ = _fresh_runtime_fixes(
        monkeypatch,
        structured_call,
        record_event,
    )
    module.apply_runtime_fixes()

    with pytest.raises(RuntimeError):
        gemini._structured_call(
            object(),
            model="gemini-test",
            prompt="PROMPT",
            docs=[],
            schema=CatalogBatch,
            context="catalogo.pdf",
        )

    assert len(calls) == 1


def test_non_json_venue_error_does_not_retry(monkeypatch):
    calls = []

    def structured_call(client, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("Falha de rede não relacionada ao JSON")

    def record_event(client, **kwargs):
        return None

    module, gemini, _ = _fresh_runtime_fixes(
        monkeypatch,
        structured_call,
        record_event,
    )
    module.apply_runtime_fixes()

    with pytest.raises(RuntimeError):
        gemini._structured_call(
            object(),
            model="gemini-test",
            prompt="PROMPT",
            docs=[],
            schema=VenueBatch,
            context="local.pdf",
        )

    assert len(calls) == 1


def test_source_page_decimal_string_is_normalized_before_event_insert(monkeypatch):
    received = []

    def structured_call(client, **kwargs):
        return "ok"

    def record_event(client, **kwargs):
        received.append(kwargs)

    module, _, supabase = _fresh_runtime_fixes(
        monkeypatch,
        structured_call,
        record_event,
    )
    module.apply_runtime_fixes()

    supabase._record_enrichment_event(
        object(),
        entity_type="venue",
        entity_id="venue-1",
        import_id="import-1",
        source_file_id=None,
        source_file="volume03.pdf",
        source_page="2.0",
        match_method="name",
        strategy="fill_missing",
        existing={},
        incoming={},
        result={},
    )

    assert received[0]["source_page"] == 2
    assert isinstance(received[0]["source_page"], int)


def test_source_page_fraction_becomes_none_instead_of_invalid_integer(monkeypatch):
    received = []

    def structured_call(client, **kwargs):
        return "ok"

    def record_event(client, **kwargs):
        received.append(kwargs)

    module, _, supabase = _fresh_runtime_fixes(
        monkeypatch,
        structured_call,
        record_event,
    )
    module.apply_runtime_fixes()

    supabase._record_enrichment_event(
        object(),
        entity_type="venue",
        entity_id="venue-1",
        import_id="import-1",
        source_file_id=None,
        source_file="volume03.pdf",
        source_page="2.5",
        match_method="name",
        strategy="fill_missing",
        existing={},
        incoming={},
        result={},
    )

    assert received[0]["source_page"] is None


def test_apply_runtime_fixes_is_idempotent(monkeypatch):
    def structured_call(client, **kwargs):
        return "ok"

    def record_event(client, **kwargs):
        return None

    module, gemini, supabase = _fresh_runtime_fixes(
        monkeypatch,
        structured_call,
        record_event,
    )

    first = module.apply_runtime_fixes()
    patched_structured = gemini._structured_call
    patched_event = supabase._record_enrichment_event
    second = module.apply_runtime_fixes()

    assert first == {
        "gemini_venue_retry": True,
        "enrichment_page_normalizer": True,
    }
    assert second == {
        "gemini_venue_retry": False,
        "enrichment_page_normalizer": False,
    }
    assert gemini._structured_call is patched_structured
    assert supabase._record_enrichment_event is patched_event
