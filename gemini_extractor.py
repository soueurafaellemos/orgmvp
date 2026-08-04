from __future__ import annotations

import base64
import os

from google import genai

from document_io import InputDocument, split_pdf
from models import CatalogBatch, ProjectBriefing
from prompts import CATALOG_SYSTEM_PROMPT, BRIEFING_SYSTEM_PROMPT


def get_client(api_key: str | None = None) -> genai.Client:
    resolved = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved:
        raise RuntimeError(
            "Configure GEMINI_API_KEY nos Secrets do Streamlit ou no ambiente."
        )
    return genai.Client(api_key=resolved, http_options={"api_version": "v1"})


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


def _catalog_from_interaction(interaction, source_name: str) -> CatalogBatch:
    if not interaction.output_text:
        raise RuntimeError(f"O Gemini não devolveu conteúdo para {source_name}.")
    try:
        return CatalogBatch.model_validate_json(interaction.output_text)
    except Exception as exc:
        raise RuntimeError(
            f"O Gemini devolveu uma estrutura inválida para {source_name}: {exc}"
        ) from exc


def _briefing_from_interaction(interaction) -> ProjectBriefing:
    if not interaction.output_text:
        raise RuntimeError("O Gemini não devolveu conteúdo para o briefing.")
    try:
        return ProjectBriefing.model_validate_json(interaction.output_text)
    except Exception as exc:
        raise RuntimeError(
            f"O Gemini devolveu um briefing em estrutura inválida: {exc}"
        ) from exc


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
    jobs: list[tuple[InputDocument, str]] = []

    for doc in docs:
        if doc.mime_type == "application/pdf":
            for part, first, last in split_pdf(
                doc,
                pages_per_batch=pages_per_batch,
                start_page=start_page,
                end_page=end_page,
            ):
                jobs.append(
                    (
                        part,
                        (
                            f"Arquivo original: {doc.name}. "
                            f"Este lote corresponde às páginas {first} a {last}. "
                            "Extraia todos os produtos e regras gerais presentes. "
                            "Use a numeração original das páginas do catálogo."
                        ),
                    )
                )
        else:
            jobs.append(
                (
                    doc,
                    f"Arquivo: {doc.name}. Extraia todos os produtos e regras gerais.",
                )
            )

    results: list[CatalogBatch] = []
    total = len(jobs)

    for index, (doc, instruction) in enumerate(jobs, start=1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")

        interaction = client.interactions.create(
            model=model,
            input=[
                {
                    "type": "text",
                    "text": CATALOG_SYSTEM_PROMPT + "\n\n" + instruction,
                },
                _input_item(doc),
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": CatalogBatch.model_json_schema(),
            },
        )
        results.append(_catalog_from_interaction(interaction, doc.name))

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return results


def extract_briefing(
    docs: list[InputDocument],
    *,
    pasted_text: str,
    api_key: str | None,
    model: str,
) -> ProjectBriefing:
    client = get_client(api_key)

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                BRIEFING_SYSTEM_PROMPT
                + "\n\nConsolide todas as fontes em um único briefing "
                "estruturado. Sinalize divergências e ausências sem inventar."
            ),
        }
    ]

    for doc in docs:
        content.append(_input_item(doc))

    if pasted_text.strip():
        content.append(
            {
                "type": "text",
                "text": "Texto colado pelo usuário:\n" + pasted_text.strip(),
            }
        )

    interaction = client.interactions.create(
        model=model,
        input=content,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ProjectBriefing.model_json_schema(),
        },
    )
    return _briefing_from_interaction(interaction)
