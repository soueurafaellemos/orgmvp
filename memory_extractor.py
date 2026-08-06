from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import fitz
import pandas as pd

from document_io import (
    InputDocument,
    split_pdf,
)
from gemini_extractor import (
    _structured_call,
    get_client,
)
from memory_models import (
    MemoryBatch,
    MemoryOverview,
)
from memory_prompts import (
    MEMORY_OVERVIEW_PROMPT,
    MEMORY_SECTION_LABELS,
    MEMORY_SYSTEM_PROMPT,
)


DETAIL_PAGES_PER_PASS = 6
SYNTHESIS_CONTEXT_MAX_CHARS = 120_000

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
        strategic_summary=(
            overview.strategic_summary
        ),
        creative_concept=(
            overview.creative_concept
        ),
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


def _clip(
    value: Any,
    limit: int,
) -> str | None:
    text = str(
        value or ""
    ).strip()

    if not text:
        return None

    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "…"


def _compact_batch(
    batch: MemoryBatch,
) -> dict:
    data = batch.model_dump()
    compact_slides = []

    for slide in data.get(
        "slides",
        [],
    ):
        compact_items = []

        for item in slide.get(
            "items",
            [],
        ):
            compact_items.append(
                {
                    "section": item.get(
                        "section_key"
                    ),
                    "type": _clip(
                        item.get("item_type"),
                        100,
                    ),
                    "title": _clip(
                        item.get("title"),
                        180,
                    ),
                    "summary": _clip(
                        item.get("summary"),
                        450,
                    ),
                    "status": item.get(
                        "status"
                    ),
                    "evidence": _clip(
                        item.get("evidence"),
                        240,
                    ),
                }
            )

        compact_slides.append(
            {
                "page": slide.get(
                    "source_page"
                ),
                "title": _clip(
                    slide.get("slide_title"),
                    180,
                ),
                "summary": _clip(
                    slide.get("slide_summary"),
                    500,
                ),
                "primary_section": slide.get(
                    "primary_section"
                ),
                "items": compact_items,
            }
        )

    return {
        "source_file": data.get(
            "source_file"
        ),
        "document_title": _clip(
            data.get("document_title"),
            250,
        ),
        "client_brand": _clip(
            data.get("client_brand"),
            180,
        ),
        "project_name": _clip(
            data.get("project_name"),
            250,
        ),
        "event_name": _clip(
            data.get("event_name"),
            220,
        ),
        "version_label": _clip(
            data.get("version_label"),
            100,
        ),
        "strategic_summary": _clip(
            data.get("strategic_summary"),
            900,
        ),
        "creative_concept": _clip(
            data.get("creative_concept"),
            500,
        ),
        "slides": compact_slides,
        "warnings": [
            _clip(warning, 260)
            for warning in (
                data.get("warnings")
                or []
            )
            if _clip(warning, 260)
        ],
    }


def _synthesis_context(
    batches: list[MemoryBatch],
) -> str:
    payload = [
        _compact_batch(batch)
        for batch in batches
    ]

    context = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
    )

    if (
        len(context)
        > SYNTHESIS_CONTEXT_MAX_CHARS
    ):
        context = (
            context[
                :SYNTHESIS_CONTEXT_MAX_CHARS
            ]
            + "\n[conteúdo abreviado "
            "automaticamente]"
        )

    return context


def _first_value(
    batches: list[MemoryBatch],
    field: str,
) -> str | None:
    for batch in batches:
        value = getattr(
            batch,
            field,
            None,
        )

        if value:
            return str(value)

    return None


def _fallback_overview(
    *,
    doc: InputDocument,
    detail_batches: list[MemoryBatch],
    warnings: list[str],
) -> MemoryOverview:
    file_title = Path(
        doc.name
    ).stem

    return MemoryOverview(
        source_file=doc.name,
        document_title=(
            _first_value(
                detail_batches,
                "document_title",
            )
            or file_title
        ),
        client_brand=_first_value(
            detail_batches,
            "client_brand",
        ),
        project_name=(
            _first_value(
                detail_batches,
                "project_name",
            )
            or _first_value(
                detail_batches,
                "document_title",
            )
            or file_title
        ),
        event_name=_first_value(
            detail_batches,
            "event_name",
        ),
        version_label=_first_value(
            detail_batches,
            "version_label",
        ),
        strategic_summary=_first_value(
            detail_batches,
            "strategic_summary",
        ),
        creative_concept=_first_value(
            detail_batches,
            "creative_concept",
        ),
        warnings=warnings,
    )


def _synthesize_overview(
    client,
    *,
    doc: InputDocument,
    page_count: int,
    model: str,
    detail_batches: list[MemoryBatch],
    warnings: list[str],
) -> MemoryOverview:
    context = _synthesis_context(
        detail_batches
    )

    prompt = (
        MEMORY_OVERVIEW_PROMPT
        + "\n\nVocê recebeu abaixo o resultado estruturado "
        "da leitura de TODOS os slides da apresentação. "
        "Consolide esses resultados como um único projeto. "
        "Não invente informações e não liste fichas individuais."
        + "\n\nARQUIVO ORIGINAL: "
        + doc.name
        + "\nTOTAL DE SLIDES: "
        + str(page_count)
        + "\n\nCONTEÚDO ESTRUTURADO DE TODOS OS SLIDES:\n"
        + context
    )

    try:
        overview = _structured_call(
            client,
            model=model,
            prompt=prompt,
            docs=[],
            schema=MemoryOverview,
            context=(
                "consolidação global da Memória de "
                + doc.name
            ),
        )
        overview.source_file = doc.name
        overview.warnings = list(
            dict.fromkeys(
                [
                    *(
                        overview.warnings
                        or []
                    ),
                    *warnings,
                ]
            )
        )
        return overview

    except Exception as exc:
        return _fallback_overview(
            doc=doc,
            detail_batches=(
                detail_batches
            ),
            warnings=list(
                dict.fromkeys(
                    [
                        *warnings,
                        (
                            "A consolidação automática do "
                            "projeto foi concluída com os "
                            "metadados disponíveis nas "
                            "leituras dos slides. "
                            f"Detalhe técnico: {exc}"
                        ),
                    ]
                )
            ),
        )


def extract_memory(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    progress_callback=None,
) -> list[MemoryBatch]:
    """
    Analisa a apresentação inteira em um único fluxo para a pessoa.

    O PDF é lido internamente em passagens automáticas para respeitar
    os limites do modelo. Depois, todos os resultados são consolidados
    em uma visão global única do projeto.

    Nenhuma configuração de lotes aparece na interface.
    """
    client = get_client(api_key)
    all_batches = []

    plans = []

    for doc in docs:
        if doc.mime_type != "application/pdf":
            raise ValueError(
                "A Memória visual precisa de "
                "uma apresentação em PDF."
            )

        page_count = _pdf_page_count(
            doc
        )
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
        len(parts) + 1
        for _, _, parts in plans
    )
    completed_steps = 0

    for doc, page_count, parts in plans:
        detail_batches = []
        document_warnings = []

        for part, first, last in parts:
            if progress_callback:
                progress_callback(
                    completed_steps,
                    total_steps,
                    (
                        "Lendo a apresentação completa "
                        f"— slides {first} a {last} "
                        f"de {page_count}"
                    ),
                )

            detail_prompt = (
                MEMORY_SYSTEM_PROMPT
                + "\n\nARQUIVO ORIGINAL: "
                + doc.name
                + "\nTOTAL DE SLIDES DO ARQUIVO: "
                + str(page_count)
                + "\nSLIDES DESTA LEITURA: "
                + str(first)
                + " a "
                + str(last)
                + "\nAnalise todos os slides desta leitura. "
                "Use a numeração ORIGINAL do PDF em source_page. "
                "Esta é uma parte de uma apresentação maior; "
                "preserve títulos, evidências e relações explícitas "
                "sem inventar o restante do projeto."
            )

            try:
                detail_batch = (
                    _structured_call(
                        client,
                        model=model,
                        prompt=detail_prompt,
                        docs=[part],
                        schema=MemoryBatch,
                        context=(
                            f"Memória de {doc.name}, "
                            f"slides {first}-{last}"
                        ),
                    )
                )

                detail_batches.append(
                    _normalize_detailed_batch(
                        detail_batch,
                        source_file=(
                            doc.name
                        ),
                        first_page=first,
                        last_page=last,
                    )
                )

            except Exception as exc:
                document_warnings.append(
                    (
                        f"Os slides {first} a {last} "
                        "não puderam ser estruturados "
                        "nesta tentativa. "
                        f"Detalhe técnico: {exc}"
                    )
                )

            completed_steps += 1

        if not detail_batches:
            raise RuntimeError(
                "Nenhum conjunto de slides pôde ser "
                "analisado. Tente novamente após alguns "
                "minutos ou confirme o modelo configurado."
            )

        if progress_callback:
            progress_callback(
                completed_steps,
                total_steps,
                (
                    "Consolidando o projeto completo "
                    f"— {page_count} slides"
                ),
            )

        overview = _synthesize_overview(
            client,
            doc=doc,
            page_count=page_count,
            model=model,
            detail_batches=detail_batches,
            warnings=document_warnings,
        )

        all_batches.extend(
            [
                _overview_as_batch(
                    overview
                ),
                *detail_batches,
            ]
        )
        completed_steps += 1

    if progress_callback:
        progress_callback(
            total_steps,
            total_steps,
            "Projeto completo organizado.",
        )

    return all_batches


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
