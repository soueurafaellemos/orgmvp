from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI

from document_io import InputDocument, split_pdf, to_data_url
from models import CatalogBatch, ProjectBriefing
from prompts import CATALOG_SYSTEM_PROMPT, BRIEFING_SYSTEM_PROMPT


def get_client(api_key: str | None = None) -> OpenAI:
    resolved = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved:
        raise RuntimeError(
            "Configure OPENAI_API_KEY nas secrets do Streamlit ou no ambiente."
        )
    return OpenAI(api_key=resolved)


def _file_item(doc: InputDocument, pdf_detail: str = "high") -> dict:
    item = {
        "type": "input_file",
        "filename": doc.name,
        "file_data": to_data_url(doc),
    }
    if doc.mime_type == "application/pdf":
        item["detail"] = pdf_detail
    return item


def extract_catalog(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    pdf_detail: str,
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
                            "Extraia todos os produtos e regras gerais presentes."
                        ),
                    )
                )
        else:
            jobs.append(
                (
                    doc,
                    (
                        f"Arquivo: {doc.name}. Extraia todos os produtos e regras "
                        "gerais presentes."
                    ),
                )
            )

    results: list[CatalogBatch] = []
    total = len(jobs)

    for index, (doc, instruction) in enumerate(jobs, start=1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")

        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": CATALOG_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        _file_item(doc, pdf_detail=pdf_detail),
                        {"type": "input_text", "text": instruction},
                    ],
                },
            ],
            text_format=CatalogBatch,
        )

        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError(f"A API não devolveu dados estruturados para {doc.name}.")
        results.append(parsed)

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return results


def extract_briefing(
    docs: list[InputDocument],
    *,
    pasted_text: str,
    api_key: str | None,
    model: str,
    pdf_detail: str,
) -> ProjectBriefing:
    client = get_client(api_key)

    content: list[dict] = []
    for doc in docs:
        content.append(_file_item(doc, pdf_detail=pdf_detail))

    if pasted_text.strip():
        content.append(
            {
                "type": "input_text",
                "text": "Texto colado pelo usuário:\n" + pasted_text.strip(),
            }
        )

    content.append(
        {
            "type": "input_text",
            "text": (
                "Consolide todas as fontes em um único briefing estruturado. "
                "Sinalize divergências e ausências sem inventar informações."
            ),
        }
    )

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text_format=ProjectBriefing,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("A API não devolveu um briefing estruturado.")
    return parsed
