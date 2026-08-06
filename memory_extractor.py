from __future__ import annotations

import copy
import hashlib
from collections import Counter

import pandas as pd

from document_io import InputDocument, split_pdf
from gemini_extractor import _structured_call, get_client
from memory_models import MemoryBatch
from memory_prompts import MEMORY_SECTION_LABELS, MEMORY_SYSTEM_PROMPT


def _memory_jobs(docs: list[InputDocument], *, pages_per_batch: int):
    jobs = []
    for doc in docs:
        if doc.mime_type != "application/pdf":
            raise ValueError(
                "A Memória visual precisa de uma apresentação exportada em PDF."
            )
        for part, first, last in split_pdf(
            doc,
            pages_per_batch=pages_per_batch,
            start_page=1,
            end_page=None,
        ):
            jobs.append((part, first, last, doc.name))
    return jobs


def extract_memory(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int = 6,
    progress_callback=None,
) -> list[MemoryBatch]:
    client = get_client(api_key)
    jobs = _memory_jobs(docs, pages_per_batch=pages_per_batch)
    batches = []
    total = len(jobs)

    for index, (doc, first, last, original_name) in enumerate(jobs, start=1):
        if progress_callback:
            progress_callback(
                index - 1,
                total,
                f"Analisando {original_name} — páginas {first} a {last}",
            )

        instruction = (
            f"\n\nARQUIVO ORIGINAL: {original_name}\n"
            f"INTERVALO DE PÁGINAS: {first} a {last}\n"
            "Use o nome original em source_file e a numeração original "
            "do arquivo em source_page."
        )

        batches.append(
            _structured_call(
                client,
                model=model,
                prompt=MEMORY_SYSTEM_PROMPT + instruction,
                docs=[doc],
                schema=MemoryBatch,
                context=f"Memória de {original_name}, páginas {first}-{last}",
            )
        )

    if progress_callback:
        progress_callback(total, total, "Leitura da apresentação concluída.")

    return batches


def merge_memory_batches(batches: list[MemoryBatch]) -> dict:
    metadata_fields = [
        "document_title",
        "client_brand",
        "project_name",
        "event_name",
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
    return pd.DataFrame(rows)


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
