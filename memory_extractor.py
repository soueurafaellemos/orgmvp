from __future__ import annotations

import copy
import hashlib
from collections import Counter

import pandas as pd

import fitz

from document_io import InputDocument, split_pdf
from gemini_extractor import _structured_call, get_client
from memory_models import MemoryBatch, MemoryOverview
from memory_prompts import (
    MEMORY_OVERVIEW_PROMPT,
    MEMORY_SECTION_LABELS,
    MEMORY_SYSTEM_PROMPT,
)



def _pdf_page_count(
    doc: InputDocument,
) -> int:
    pdf = fitz.open(
        stream=doc.data,
        filetype="pdf",
    )
    try:
        return int(pdf.page_count)
    finally:
        pdf.close()



DETAIL_PAGES_PER_PASS = 6

MEMORY_EDITOR_COLUMNS = [
    "_row_id",
    "Incluir",
    "Seção",
    "Tipo",
    "Título",
    "Resumo",
    "Status",
    "Página",
    "Arquivo",
    "Confiança",
]


def _overview_as_batch(
    overview: MemoryOverview,
) -> MemoryBatch:
    return MemoryBatch(
        source_file=overview.source_file,
        document_title=overview.document_title,
        client_brand=overview.client_brand,
        project_name=overview.project_name,
        event_name=overview.event_name,
        version_label=overview.version_label,
        strategic_summary=overview.strategic_summary,
        creative_concept=overview.creative_concept,
        slides=[],
        warnings=overview.warnings,
    )


def _normalize_detailed_batch(
    batch: MemoryBatch,
    *,
    source_file: str,
    first_page: int,
    last_page: int,
) -> MemoryBatch:
    batch.source_file = source_file

    slides = list(
        batch.slides or []
    )
    page_numbers = [
        int(slide.source_page)
        for slide in slides
        if int(slide.source_page) > 0
    ]
    local_page_count = (
        last_page - first_page + 1
    )

    uses_relative_numbering = (
        first_page > 1
        and bool(page_numbers)
        and min(page_numbers) >= 1
        and max(page_numbers)
        <= local_page_count
    )

    for slide in slides:
        slide.source_file = source_file

        if uses_relative_numbering:
            slide.source_page = (
                int(slide.source_page)
                + first_page
                - 1
            )

    return batch


def extract_memory(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    progress_callback=None,
) -> list[MemoryBatch]:
    """
    Analisa cada apresentação inteira em um único fluxo.

    Primeiro, o PDF completo é lido para compreender narrativa,
    estratégia e metadados. Depois, passagens internas automáticas
    organizam os detalhes de todos os slides usando o contexto global.

    Não existe configuração de lotes para a pessoa usuária.
    """
    client = get_client(api_key)

    plans = []

    for doc in docs:
        if doc.mime_type != "application/pdf":
            raise ValueError(
                "A Memória visual precisa de uma apresentação "
                "exportada em PDF."
            )

        page_count = _pdf_page_count(doc)
        parts = split_pdf(
            doc,
            pages_per_batch=(
                DETAIL_PAGES_PER_PASS
            ),
            start_page=1,
            end_page=None,
        )
        plans.append(
            (
                doc,
                page_count,
                parts,
            )
        )

    total_steps = sum(
        1 + len(parts)
        for _, _, parts in plans
    )
    completed_steps = 0
    batches = []

    for doc, page_count, parts in plans:
        if progress_callback:
            progress_callback(
                completed_steps,
                total_steps,
                (
                    "Compreendendo a apresentação completa "
                    f"{doc.name} — {page_count} slides"
                ),
            )

        try:
            overview = _structured_call(
                client,
                model=model,
                prompt=(
                    MEMORY_OVERVIEW_PROMPT
                    + "\n\nARQUIVO ORIGINAL: "
                    + doc.name
                    + "\nTOTAL DE SLIDES: "
                    + str(page_count)
                ),
                docs=[doc],
                schema=MemoryOverview,
                context=(
                    "leitura global da Memória de "
                    + doc.name
                ),
            )
        except RuntimeError as exc:
            overview = MemoryOverview(
                source_file=doc.name,
                document_title=(
                    Path(doc.name).stem
                ),
                warnings=[
                    (
                        "A leitura global não retornou uma "
                        "estrutura completa. A NAVE prosseguiu "
                        "com a organização detalhada dos slides. "
                        f"Detalhe técnico: {exc}"
                    )
                ],
            )

        overview.source_file = doc.name
        batches.append(
            _overview_as_batch(
                overview
            )
        )
        completed_steps += 1

        global_context = json.dumps(
            overview.model_dump(),
            ensure_ascii=False,
            default=str,
        )

        for part, first, last in parts:
            if progress_callback:
                progress_callback(
                    completed_steps,
                    total_steps,
                    (
                        "Organizando o conteúdo da apresentação "
                        f"— slides {first} a {last} "
                        f"de {page_count}"
                    ),
                )

            detailed_prompt = (
                MEMORY_SYSTEM_PROMPT
                + "\n\nCONTEXTO GLOBAL DA APRESENTAÇÃO:\n"
                + global_context
                + "\n\nARQUIVO ORIGINAL: "
                + doc.name
                + "\nSLIDES DESTA PASSAGEM: "
                + str(first)
                + " a "
                + str(last)
                + "\nAnalise todos os slides desta passagem. "
                "Use a numeração ORIGINAL do PDF em source_page. "
                "O contexto global acima deve orientar a leitura, "
                "mas toda ficha precisa estar sustentada pelo slide."
            )

            detail_batch = _structured_call(
                client,
                model=model,
                prompt=detailed_prompt,
                docs=[part],
                schema=MemoryBatch,
                context=(
                    f"Memória de {doc.name}, "
                    f"slides {first}-{last}"
                ),
            )

            batches.append(
                _normalize_detailed_batch(
                    detail_batch,
                    source_file=doc.name,
                    first_page=first,
                    last_page=last,
                )
            )
            completed_steps += 1

    if progress_callback:
        progress_callback(
            total_steps,
            total_steps,
            "Apresentação completa organizada.",
        )

    return batches


def merge_memory_batches(batches: list[MemoryBatch]) -> dict:
    metadata_fields = [
        "document_title",
        "client_brand",
        "project_name",
        "event_name",
        "version_label",
        "creative_concept",
    ]
    metadata = {field: None for field in metadata_fields}
    summaries = []
    warnings = []
    slides_map = {}
    seen_items = set()

    for batch in batches:
        data = batch.model_dump()

        for field in metadata_fields:
            if not metadata[field] and data.get(field):
                metadata[field] = data[field]

        summary = str(data.get("strategic_summary") or "").strip()
        if summary and summary not in summaries:
            summaries.append(summary)

        warnings.extend(data.get("warnings") or [])

        for slide in data.get("slides") or []:
            source_file = str(
                slide.get("source_file") or data.get("source_file") or ""
            )
            source_page = int(slide.get("source_page") or 0)
            if not source_file or source_page <= 0:
                continue

            key = (source_file, source_page)
            target = slides_map.setdefault(
                key,
                {
                    "source_file": source_file,
                    "source_page": source_page,
                    "slide_title": slide.get("slide_title"),
                    "slide_summary": slide.get("slide_summary"),
                    "primary_section": slide.get("primary_section"),
                    "items": [],
                },
            )

            for item in slide.get("items") or []:
                title = str(item.get("title") or "").strip()
                section = str(item.get("section_key") or "")
                if not title or not section:
                    continue

                signature = (source_file, source_page, section, title.casefold())
                if signature in seen_items:
                    continue
                seen_items.add(signature)

                row_id = hashlib.sha256(
                    "|".join(str(value) for value in signature).encode("utf-8")
                ).hexdigest()[:16]

                target["items"].append(
                    {
                        **item,
                        "source_file": source_file,
                        "source_page": source_page,
                        "slide_title": target.get("slide_title"),
                        "_row_id": row_id,
                    }
                )

    slides = sorted(
        slides_map.values(),
        key=lambda row: (row["source_file"], row["source_page"]),
    )
    items = [item for slide in slides for item in slide["items"]]
    strategic_summary = " ".join(summaries).strip()

    return {
        **metadata,
        "strategic_summary": strategic_summary[:4000] or None,
        "slides": slides,
        "items": items,
        "warnings": list(dict.fromkeys(str(item) for item in warnings if str(item).strip())),
    }


def memory_editor_dataframe(extraction: dict) -> pd.DataFrame:
    rows = []
    for item in extraction.get("items", []):
        section = str(item.get("section_key") or "strategy")
        rows.append(
            {
                "_row_id": item["_row_id"],
                "Incluir": True,
                "Seção": MEMORY_SECTION_LABELS.get(section, section),
                "Tipo": item.get("item_type") or "Conteúdo",
                "Título": item.get("title") or "Sem título",
                "Resumo": item.get("summary") or "",
                "Status": item.get("status") or "Não identificado",
                "Página": int(item.get("source_page") or 0),
                "Arquivo": item.get("source_file") or "",
                "Confiança": round(float(item.get("confidence") or 0) * 100, 1),
            }
        )
    return pd.DataFrame(
        rows,
        columns=MEMORY_EDITOR_COLUMNS,
    )


def selected_memory_items(extraction: dict, editor: pd.DataFrame) -> list[dict]:
    source_map = {
        str(item["_row_id"]): item
        for item in extraction.get("items", [])
    }
    reverse_sections = {
        label: key for key, label in MEMORY_SECTION_LABELS.items()
    }
    selected = []

    if editor is None or editor.empty:
        return selected

    for row in editor.to_dict(orient="records"):
        if not bool(row.get("Incluir")):
            continue
        source = source_map.get(str(row.get("_row_id") or ""))
        if not source:
            continue

        item = copy.deepcopy(source)
        item["section_key"] = reverse_sections.get(
            str(row.get("Seção")),
            source.get("section_key", "strategy"),
        )
        item["item_type"] = str(row.get("Tipo") or "").strip() or "Conteúdo"
        item["title"] = str(row.get("Título") or "").strip() or "Sem título"
        item["summary"] = str(row.get("Resumo") or "").strip() or None
        item["status"] = str(row.get("Status") or "Não identificado")
        selected.append(item)

    return selected


def memory_section_counts(items: list[dict]) -> pd.DataFrame:
    counts = Counter(
        str(item.get("section_key") or "strategy")
        for item in items
    )
    rows = [
        {
            "Seção": MEMORY_SECTION_LABELS.get(section, section),
            "Itens": count,
        }
        for section, count in counts.items()
    ]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Itens", ascending=False)
