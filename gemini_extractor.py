from __future__ import annotations

import base64
import os
import re
from typing import Type, TypeVar

from google import genai
from pydantic import BaseModel

from document_io import InputDocument, split_pdf
from models import (
    ActivationBatch,
    ActivationFallbackBatch,
    CatalogBatch,
    DocumentClassification,
    ProjectBriefing,
    RecommendationBrief,
    VenueBatch,
)
from prompts import (
    ACTIVATION_FALLBACK_PROMPT,
    ACTIVATION_SYSTEM_PROMPT,
    BRIEFING_SYSTEM_PROMPT,
    CATALOG_SYSTEM_PROMPT,
    CLASSIFICATION_SYSTEM_PROMPT,
    RECOMMENDATION_BRIEF_PROMPT,
    VENUE_SYSTEM_PROMPT,
)


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GeminiQuotaError(RuntimeError):
    """Friendly error for Gemini 429 / quota exhaustion."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.model = model


def _quota_retry_seconds(message: str) -> int | None:
    patterns = [
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retryDelay[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"retry after\s+([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1)) + 0.999))
    return None


def _is_quota_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    signals = (
        "ratelimiterror",
        "too_many_requests",
        "resource_exhausted",
        "quota exceeded",
        "exceeded your current quota",
        "error code: 429",
        "code': 429",
        '"code": 429',
    )
    return any(signal in text for signal in signals)


def get_client(api_key: str | None = None) -> genai.Client:
    resolved = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved:
        raise RuntimeError(
            "Configure GEMINI_API_KEY nos Secrets do Streamlit."
        )
    return genai.Client(
        api_key=resolved,
        http_options={"api_version": "v1"},
    )


def _input_item(doc: InputDocument) -> dict:
    if doc.mime_type.startswith("text/"):
        return {
            "type": "text",
            "text": (
                f"\n\n===== FONTE: {doc.name} =====\n"
                + doc.data.decode("utf-8", errors="replace")
            ),
        }
    return {
        "type": "document",
        "data": base64.b64encode(doc.data).decode("utf-8"),
        "mime_type": doc.mime_type,
    }


def _structured_call(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    docs: list[InputDocument],
    schema: Type[SchemaT],
    context: str,
) -> SchemaT:
    try:
        interaction = client.interactions.create(
            model=model,
            input=[
                {"type": "text", "text": prompt},
                *[_input_item(doc) for doc in docs],
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema.model_json_schema(),
            },
        )
    except Exception as exc:
        if _is_quota_error(exc):
            retry_after = _quota_retry_seconds(str(exc))
            wait_text = (
                f" Aguarde aproximadamente {retry_after} segundos."
                if retry_after
                else " Aguarde um pouco antes de tentar novamente."
            )
            raise GeminiQuotaError(
                "O limite temporário do Gemini foi atingido."
                + wait_text,
                retry_after_seconds=retry_after,
                model=model,
            ) from exc
        raise
    if not interaction.output_text:
        raise RuntimeError(f"O Gemini não devolveu conteúdo para {context}.")
    try:
        return schema.model_validate_json(interaction.output_text)
    except Exception as exc:
        raise RuntimeError(
            f"Estrutura inválida devolvida para {context}: {exc}"
        ) from exc


def _classification_sample(
    docs: list[InputDocument],
) -> list[InputDocument]:
    sampled: list[InputDocument] = []
    for doc in docs:
        if doc.mime_type == "application/pdf":
            parts = split_pdf(
                doc,
                pages_per_batch=6,
                start_page=1,
                end_page=6,
            )
            if parts:
                sampled.append(parts[0][0])
        else:
            sampled.append(doc)
    return sampled


def classify_documents(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
) -> DocumentClassification:
    client = get_client(api_key)
    return _structured_call(
        client,
        model=model,
        prompt=(
            CLASSIFICATION_SYSTEM_PROMPT
            + "\n\nClassifique os arquivos e indique o modo e a base."
        ),
        docs=_classification_sample(docs),
        schema=DocumentClassification,
        context="classificação",
    )


def _jobs(
    docs: list[InputDocument],
    *,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
) -> list[tuple[InputDocument, int | None, int | None, str]]:
    result = []
    for doc in docs:
        if doc.mime_type == "application/pdf":
            for part, first, last in split_pdf(
                doc,
                pages_per_batch=pages_per_batch,
                start_page=start_page,
                end_page=end_page,
            ):
                result.append((part, first, last, doc.name))
        else:
            result.append((doc, None, None, doc.name))
    return result


def extract_catalog(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
    progress_callback=None,
) -> list[CatalogBatch]:
    client = get_client(api_key)
    jobs = _jobs(
        docs,
        pages_per_batch=pages_per_batch,
        start_page=start_page,
        end_page=end_page,
    )
    batches = []
    total = len(jobs)

    for index, (doc, first, last, original_name) in enumerate(jobs, 1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")
        instruction = (
            f"Arquivo original: {original_name}. "
            f"Páginas: {first or 'não aplicável'} a "
            f"{last or 'não aplicável'}. Use o nome original em source_file "
            "e a numeração original em source_page."
        )
        batches.append(
            _structured_call(
                client,
                model=model,
                prompt=CATALOG_SYSTEM_PROMPT + "\n\n" + instruction,
                docs=[doc],
                schema=CatalogBatch,
                context=doc.name,
            )
        )

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return batches



def _cost_from_text(text: str, source_page: int | None):
    from models import CostComponent

    return CostComponent(
        description=text,
        amount=None,
        currency="Não informado",
        treatment="Não informado",
        notes=(
            "Componente extraído como texto na etapa de segurança. "
            "Revisar valor e classificação manualmente."
        ),
        source_page=source_page,
        confidence=0.6,
    )


def _fallback_to_activation_batch(
    fallback: ActivationFallbackBatch,
) -> ActivationBatch:
    from models import ActivationSolution

    solutions = []

    for item in fallback.items:
        missing_fields = []
        if item.base_price is None:
            missing_fields.append("base_price")
        if item.lead_time_days is None:
            missing_fields.append("lead_time_days")
        if not item.supplier_name and not fallback.supplier_name:
            missing_fields.append("supplier_name")

        solutions.append(
            ActivationSolution(
                source_file=item.source_file,
                source_page=item.source_page,
                visual_crop=item.visual_crop,
                supplier_name=(
                    item.supplier_name or fallback.supplier_name
                ),
                client_brand=(
                    item.client_brand or fallback.client_brand
                ),
                project_name=(
                    item.project_name or fallback.project_name
                ),
                event_name=item.event_name,
                category="Solução de ativação",
                record_type="Outro",
                name=item.name,
                description=item.description,
                base_price=item.base_price,
                currency=item.currency,
                price_status=item.price_status,
                pricing_period=item.pricing_period,
                price_notes=item.price_notes,
                additional_costs=[
                    _cost_from_text(text, item.source_page)
                    for text in item.additional_costs_text
                ],
                included_items=item.included_items,
                excluded_items=item.excluded_items,
                infrastructure_requirements=(
                    item.infrastructure_requirements
                ),
                lead_time_days=item.lead_time_days,
                location=item.location,
                customizable=None,
                tags=item.tags,
                confidence=item.confidence,
                missing_fields=missing_fields,
                evidence=item.evidence,
            )
        )

    return ActivationBatch(
        supplier_name=fallback.supplier_name,
        supplier_contact=None,
        proposal_name=fallback.proposal_name,
        client_brand=fallback.client_brand,
        project_name=fallback.project_name,
        document_year=fallback.document_year,
        global_rules=[],
        solutions=solutions,
        warnings=[
            *fallback.warnings,
            (
                "A extração principal retornou zero soluções. "
                "Foi utilizada a extração de segurança simplificada."
            ),
        ],
    )


def _extract_activation_batch_with_fallback(
    client: genai.Client,
    *,
    model: str,
    doc: InputDocument,
    instruction: str,
) -> ActivationBatch:
    primary = _structured_call(
        client,
        model=model,
        prompt=ACTIVATION_SYSTEM_PROMPT + "\n\n" + instruction,
        docs=[doc],
        schema=ActivationBatch,
        context=doc.name,
    )

    if primary.solutions:
        return primary

    fallback = _structured_call(
        client,
        model=model,
        prompt=(
            ACTIVATION_FALLBACK_PROMPT
            + "\n\n"
            + instruction
            + "\n\nAtenção: gere ao menos uma linha para cada item "
              "comercial presente no documento."
        ),
        docs=[doc],
        schema=ActivationFallbackBatch,
        context=f"extração de segurança de {doc.name}",
    )

    return _fallback_to_activation_batch(fallback)


def extract_activation(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
    progress_callback=None,
) -> list[ActivationBatch]:
    client = get_client(api_key)
    jobs = _jobs(
        docs,
        pages_per_batch=pages_per_batch,
        start_page=start_page,
        end_page=end_page,
    )
    batches = []
    total = len(jobs)

    for index, (doc, first, last, original_name) in enumerate(jobs, 1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")
        instruction = (
            f"Arquivo original: {original_name}. "
            f"Páginas: {first or 'não aplicável'} a "
            f"{last or 'não aplicável'}. Use o nome original em source_file "
            "e a numeração original em source_page."
        )
        batches.append(
            _extract_activation_batch_with_fallback(
                client,
                model=model,
                doc=doc,
                instruction=instruction,
            )
        )

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return batches



def extract_venues(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
    progress_callback=None,
) -> list[VenueBatch]:
    client = get_client(api_key)
    jobs = _jobs(
        docs,
        pages_per_batch=pages_per_batch,
        start_page=start_page,
        end_page=end_page,
    )
    batches = []
    total = len(jobs)

    for index, (doc, first, last, original_name) in enumerate(jobs, 1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")

        instruction = (
            f"Arquivo original: {original_name}. "
            f"Páginas: {first or 'não aplicável'} a "
            f"{last or 'não aplicável'}. Use o nome original em source_file "
            "e a numeração original em source_page."
        )

        batches.append(
            _structured_call(
                client,
                model=model,
                prompt=VENUE_SYSTEM_PROMPT + "\n\n" + instruction,
                docs=[doc],
                schema=VenueBatch,
                context=doc.name,
            )
        )

    if progress_callback:
        progress_callback(total, total, "Extração concluída")

    return batches


def extract_briefing(
    docs: list[InputDocument],
    *,
    pasted_text: str,
    api_key: str | None,
    model: str,
) -> ProjectBriefing:
    client = get_client(api_key)
    all_docs = list(docs)
    if pasted_text.strip():
        all_docs.append(
            InputDocument(
                name="texto_colado_usuario.txt",
                data=pasted_text.strip().encode("utf-8"),
                mime_type="text/plain",
            )
        )
    return _structured_call(
        client,
        model=model,
        prompt=(
            BRIEFING_SYSTEM_PROMPT
            + "\n\nConsolide todas as fontes em um briefing estruturado."
        ),
        docs=all_docs,
        schema=ProjectBriefing,
        context="briefing",
    )




def _recommendation_call_with_fallback(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    docs: list[InputDocument],
    context: str,
) -> RecommendationBrief:
    models_to_try = [model]

    economical_model = "gemini-3.5-flash-lite"
    if model != economical_model:
        models_to_try.append(economical_model)

    last_quota_error: GeminiQuotaError | None = None

    for candidate_model in models_to_try:
        try:
            return _structured_call(
                client,
                model=candidate_model,
                prompt=prompt,
                docs=docs,
                schema=RecommendationBrief,
                context=context,
            )
        except GeminiQuotaError as exc:
            last_quota_error = exc

    if last_quota_error:
        raise GeminiQuotaError(
            (
                "Os modelos disponíveis atingiram o limite temporário "
                "do Gemini. Nenhuma informação do briefing foi perdida."
            ),
            retry_after_seconds=(
                last_quota_error.retry_after_seconds
            ),
            model=last_quota_error.model,
        ) from last_quota_error

    raise RuntimeError(
        "Não foi possível processar o briefing com os modelos disponíveis."
    )



def parse_recommendation_brief(
    text: str,
    *,
    api_key: str | None,
    model: str,
) -> RecommendationBrief:
    client = get_client(api_key)
    source = InputDocument(
        name="consulta_recomendador.txt",
        data=text.encode("utf-8"),
        mime_type="text/plain",
    )
    return _recommendation_call_with_fallback(
        client,
        model=model,
        prompt=(
            RECOMMENDATION_BRIEF_PROMPT
            + "\n\nEstruture a consulta abaixo."
        ),
        docs=[source],
        context="consulta do recomendador",
    )



def parse_recommendation_sources(
    docs: list[InputDocument],
    *,
    pasted_text: str,
    api_key: str | None,
    model: str,
) -> RecommendationBrief:
    client = get_client(api_key)

    all_docs = list(docs)
    if pasted_text.strip():
        all_docs.append(
            InputDocument(
                name="briefing_colado_usuario.txt",
                data=pasted_text.strip().encode("utf-8"),
                mime_type="text/plain",
            )
        )

    if not all_docs:
        raise ValueError(
            "Envie ao menos um arquivo ou cole o briefing."
        )

    result = _recommendation_call_with_fallback(
        client,
        model=model,
        prompt=(
            RECOMMENDATION_BRIEF_PROMPT
            + "\n\nLeia todas as fontes, consolide as informações e "
              "preencha o formulário da consulta."
        ),
        docs=all_docs,
        context="preenchimento automático do briefing",
    )

    result.source_files = [doc.name for doc in docs]
    return result
