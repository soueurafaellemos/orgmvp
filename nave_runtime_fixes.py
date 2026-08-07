from __future__ import annotations

from typing import Any


_VENUE_JSON_ERROR_SIGNALS = (
    "invalid json",
    "json_invalid",
    "eof while parsing",
    "unterminated string",
    "end of data",
)

_VENUE_COMPACT_RETRY_INSTRUCTION = """

REPROCESSAMENTO DE SEGURANÇA NAVE — RESPOSTA COMPACTA OBRIGATÓRIA
A tentativa anterior gerou JSON inválido ou truncado. Refaça a extração deste
mesmo lote, preservando somente fatos realmente presentes na fonte.

Regras obrigatórias para esta nova resposta:
- devolva JSON completo e válido, encerrando todos os objetos e listas;
- não transcreva o documento, rodapés, URLs repetidas ou textos extensos;
- evidence: no máximo 300 caracteres por local;
- description: no máximo 600 caracteres por local;
- price_notes e demais campos textuais de apoio: no máximo 300 caracteres;
- cada lista deve ter no máximo 8 itens curtos e sem duplicação;
- global_rules e warnings: no máximo 8 itens curtos cada;
- extraia somente os locais efetivamente presentes neste lote/página;
- não reconstrua locais de páginas anteriores ou posteriores;
- se a página for apenas capa, índice, créditos ou resumo sem ficha de local,
  retorne venues=[] e use warnings para registrar isso de forma breve;
- source_file e source_page devem continuar apontando para a fonte original.
""".strip()


def _is_venue_schema(schema: Any) -> bool:
    return getattr(schema, "__name__", "") == "VenueBatch"


def _looks_like_truncated_json_error(exc: Exception) -> bool:
    text = str(exc).casefold()
    return any(signal in text for signal in _VENUE_JSON_ERROR_SIGNALS)


def _install_gemini_venue_retry() -> bool:
    import gemini_extractor

    current = gemini_extractor._structured_call
    if getattr(current, "_nave_v28_0_3_4", False):
        return False

    original = current

    def resilient_structured_call(
        client,
        *,
        model: str,
        prompt: str,
        docs,
        schema,
        context: str,
    ):
        try:
            return original(
                client,
                model=model,
                prompt=prompt,
                docs=docs,
                schema=schema,
                context=context,
            )
        except RuntimeError as exc:
            if not _is_venue_schema(schema):
                raise
            if not _looks_like_truncated_json_error(exc):
                raise

            retry_prompt = (
                prompt
                + "\n\n"
                + _VENUE_COMPACT_RETRY_INSTRUCTION
            )
            return original(
                client,
                model=model,
                prompt=retry_prompt,
                docs=docs,
                schema=schema,
                context=f"{context} [retry compacto NAVE]",
            )

    resilient_structured_call._nave_v28_0_3_4 = True
    resilient_structured_call._nave_original = original
    gemini_extractor._structured_call = resilient_structured_call
    return True


def _install_enrichment_page_normalizer() -> bool:
    import supabase_db

    current = supabase_db._record_enrichment_event
    if getattr(current, "_nave_v28_0_3_4", False):
        return False

    original = current

    def normalized_record_enrichment_event(
        client,
        *,
        entity_type: str,
        entity_id: str,
        import_id: str,
        source_file_id: str | None,
        source_file: str | None,
        source_page: int | None,
        match_method: str,
        strategy: str,
        existing: dict,
        incoming: dict,
        result: dict,
    ) -> None:
        normalized_page = supabase_db._integer_or_none(source_page)
        return original(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
            import_id=import_id,
            source_file_id=source_file_id,
            source_file=source_file,
            source_page=normalized_page,
            match_method=match_method,
            strategy=strategy,
            existing=existing,
            incoming=incoming,
            result=result,
        )

    normalized_record_enrichment_event._nave_v28_0_3_4 = True
    normalized_record_enrichment_event._nave_original = original
    supabase_db._record_enrichment_event = normalized_record_enrichment_event
    return True


def apply_runtime_fixes() -> dict[str, bool]:
    """Instala correções idempotentes de ingestão antes das páginas da NAVE."""
    return {
        "gemini_venue_retry": _install_gemini_venue_retry(),
        "enrichment_page_normalizer": _install_enrichment_page_normalizer(),
    }
