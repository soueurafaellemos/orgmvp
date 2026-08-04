from __future__ import annotations

import base64
import os
from typing import Type, TypeVar

from google import genai
from pydantic import BaseModel

from document_io import InputDocument, split_pdf
from models import (
    ActivationBatch,
    CatalogBatch,
    DocumentClassification,
    ProjectBriefing,
    VenueBatch,
)
from prompts import (
    ACTIVATION_SYSTEM_PROMPT,
    BRIEFING_SYSTEM_PROMPT,
    CATALOG_SYSTEM_PROMPT,
    CLASSIFICATION_SYSTEM_PROMPT,
    VENUE_SYSTEM_PROMPT,
)


SchemaT = TypeVar("SchemaT", bound=BaseModel)


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
            _structured_call(
                client,
                model=model,
                prompt=ACTIVATION_SYSTEM_PROMPT + "\n\n" + instruction,
                docs=[doc],
                schema=ActivationBatch,
                context=doc.name,
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
