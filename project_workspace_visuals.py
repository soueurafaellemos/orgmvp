from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from html import escape
from typing import Any, Iterable

import fitz
import pandas as pd
import streamlit as st
from supabase import Client

from nave_storage import get_bytes as storage_get_bytes, put_bytes, r2_bucket_marker

from project_workspace_db import create_storage_signed_url
from project_workspace_intelligence import (
    SECTION_LABELS,
    VISUAL_SECTIONS,
    ensure_automatic_cost_links,
    infer_section_from_record,
    is_project_relevant_record,
    normalise_text,
    proposal_cost_items,
    section_cost_context,
)


MEMORY_BUCKET = "nave-memory"

VISUAL_CSS = """
<style>
.nave-horizontal-visual {
    background: #FFFFFF;
    border: 1px solid #E1E6EF;
    border-radius: 16px;
    margin-bottom: 0.9rem;
    padding: 0.85rem;
}
.nave-horizontal-image {
    align-items: center;
    aspect-ratio: 16 / 9;
    background: #F4F6F9;
    border: 1px solid #E1E6EF;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    overflow: hidden;
    width: 100%;
}
.nave-horizontal-image img {
    height: 100%;
    object-fit: contain;
    width: 100%;
}
.nave-horizontal-placeholder {
    color: #7D869C;
    font-size: 0.78rem;
    padding: 1rem;
    text-align: center;
}
.nave-horizontal-title {
    color: #121B42;
    font-size: 1.16rem;
    font-weight: 800;
    line-height: 1.23;
}
.nave-horizontal-meta {
    color: #687188;
    font-size: 0.76rem;
    margin-top: 0.22rem;
}
.nave-horizontal-summary {
    color: #4F5971;
    font-size: 0.88rem;
    line-height: 1.55;
    margin-top: 0.65rem;
}
.nave-cost-badge {
    background: #F0FAFC;
    border-radius: 9px;
    color: #126A7A;
    display: inline-block;
    font-size: 0.76rem;
    font-weight: 750;
    margin: 0.65rem 0.35rem 0 0;
    padding: 0.48rem 0.58rem;
}
.nave-cost-context {
    background: #FFF8E7;
    border-radius: 9px;
    color: #745710;
    display: inline-block;
    font-size: 0.74rem;
    margin-top: 0.65rem;
    padding: 0.48rem 0.58rem;
}
.nave-section-cost-summary {
    background: #F4F6F9;
    border: 1px solid #E1E6EF;
    border-radius: 12px;
    color: #556078;
    font-size: 0.8rem;
    line-height: 1.45;
    margin: 0 0 0.9rem;
    padding: 0.72rem 0.85rem;
}
</style>
"""


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _money(value: Any) -> str:
    number = _safe_float(value)
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _normalise_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


def _maps(snapshot: dict[str, Any]) -> dict[str, Any]:
    pages = snapshot.get("memory_pages", [])
    documents = snapshot.get("memory_documents", [])
    cost_items = proposal_cost_items(snapshot)
    requirements = snapshot.get("briefing_requirements", [])
    return {
        "page_by_id": {str(row.get("id")): row for row in pages if row.get("id")},
        "page_by_doc_number": {
            (str(row.get("document_id")), int(row.get("page_number") or 0)): row
            for row in pages if row.get("document_id") and row.get("page_number")
        },
        "document_by_id": {str(row.get("id")): row for row in documents if row.get("id")},
        "cost_item_by_id": {str(row.get("id")): row for row in cost_items if row.get("id")},
        "requirement_by_id": {str(row.get("id")): row for row in requirements if row.get("id")},
        "outcome_by_item": {
            str(row.get("item_id")): row
            for row in snapshot.get("item_outcomes", []) if row.get("item_id")
        },
    }


def _linked_maps(snapshot: dict[str, Any], maps: dict[str, Any]):
    costs: dict[str, list[dict]] = defaultdict(list)
    for link in snapshot.get("cost_links", []):
        if link.get("link_status") == "rejected":
            continue
        item_id = str(link.get("memory_item_id") or "")
        cost = maps["cost_item_by_id"].get(str(link.get("cost_item_id") or ""))
        if item_id and cost:
            costs[item_id].append({"link": link, "cost": cost})

    briefings: dict[str, list[dict]] = defaultdict(list)
    for link in snapshot.get("briefing_links", []):
        if link.get("link_status") == "rejected":
            continue
        item_id = str(link.get("memory_item_id") or "")
        req = maps["requirement_by_id"].get(str(link.get("requirement_id") or ""))
        if item_id and req:
            briefings[item_id].append({"link": link, "requirement": req})
    return costs, briefings


def _inventory_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("raw_data") if isinstance(document.get("raw_data"), dict) else {}
    return [row for row in raw.get("page_inventory") or [] if isinstance(row, dict)]


def _visual_inventory_section_hints(rows: list[dict[str, Any]]) -> dict[int, str]:
    """Reclassifica sequências visuais silenciosas sem hardcode de projeto.

    Apresentações de live marketing frequentemente introduzem o conceito espacial
    em texto ("casa", "espaço", "ambiente") e depois mostram uma sequência de
    renders quase sem texto. O parser textual tende a deixar esses slides em
    Estratégia. Esta heurística mantém o contexto espacial até surgir uma nova
    seção semanticamente forte (ativações, brindes, comunicação etc.).
    """
    hints: dict[int, str] = {}
    spatial_context = False
    spatial_terms = (
        "casa", "espaco", "ambiente", "cenografia", "cenograf", "estande",
        "stand", "fachada", "arquitetura", "implantacao", "estrutura",
    )
    hard_exit = {"activations", "gifts", "communication", "journey_operation", "content_agenda"}
    for row in sorted(rows, key=lambda value: int(value.get("page_number") or 0)):
        page_number = int(row.get("page_number") or 0)
        raw_text = " ".join(str(row.get(key) or "") for key in ("text", "normalized_text", "summary", "suggested_title"))
        norm = normalise_text(raw_text)
        explicit = str(row.get("suggested_section") or "").strip()
        image_count = int(row.get("image_count") or 0)
        text_length = int(row.get("text_length") or len(norm))

        if explicit in hard_exit or infer_section_from_record(
            {"title": row.get("suggested_title"), "summary": row.get("summary"), "raw_data": row},
            explicit_section=explicit,
        ) in hard_exit:
            spatial_context = False

        if explicit == "scenography" or any(term in norm for term in spatial_terms):
            # Só abre contexto espacial quando a linguagem sugere espaço físico;
            # uma menção solta a "casa" em conteúdo muito longo não basta.
            if explicit == "scenography" or any(term in norm for term in ("espaco", "ambiente", "cenografia", "estande", "stand", "fachada", "arquitetura", "implantacao")) or "casa" in norm:
                spatial_context = True

        # Slides de render são tipicamente image-heavy e têm pouquíssimo texto.
        if spatial_context and image_count >= 1 and text_length <= 70 and explicit not in hard_exit:
            hints[page_number] = "scenography"
        elif explicit:
            hints[page_number] = explicit
    return hints


def _candidate_visual_pages(snapshot: dict[str, Any], accepted: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for document in snapshot.get("memory_documents", []):
        inventory = _inventory_rows(document)
        section_hints = _visual_inventory_section_hints(inventory)
        for row in inventory:
            page_number = int(row.get("page_number") or 0)
            hinted_section = section_hints.get(page_number) or row.get("suggested_section")
            combined = {
                "title": row.get("suggested_title"),
                "summary": row.get("summary") or row.get("slide_summary"),
                "primary_section": hinted_section,
                "raw_data": row,
            }
            section = infer_section_from_record(
                combined,
                explicit_section=hinted_section,
            )
            if (
                section in accepted
                and page_number > 0
                and row.get("is_meaningful") is not False
                and is_project_relevant_record(combined)
            ):
                candidates.append({
                    **row,
                    "document": document,
                    "inferred_section": section,
                })
    return candidates


def has_missing_visual_pages(snapshot: dict[str, Any], section_keys: Iterable[str]) -> bool:
    accepted = set(section_keys) & VISUAL_SECTIONS
    existing = {
        (str(row.get("document_id")), int(row.get("page_number") or 0))
        for row in snapshot.get("memory_pages", [])
        if row.get("document_id") and row.get("page_number")
    }
    return any(
        (str(row["document"].get("id")), int(row.get("page_number") or 0)) not in existing
        for row in _candidate_visual_pages(snapshot, accepted)
    )


def recover_missing_visual_pages(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
    section_keys: Iterable[str],
) -> int:
    accepted = set(section_keys) & VISUAL_SECTIONS
    existing = {
        (str(row.get("document_id")), int(row.get("page_number") or 0))
        for row in snapshot.get("memory_pages", [])
        if row.get("document_id") and row.get("page_number")
    }
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _candidate_visual_pages(snapshot, accepted):
        document_id = str(row["document"].get("id") or "")
        page_number = int(row.get("page_number") or 0)
        if document_id and (document_id, page_number) not in existing:
            by_document[document_id].append(row)

    recovered = 0
    for document_id, candidates in by_document.items():
        document = candidates[0]["document"]
        bucket = str(document.get("storage_bucket") or MEMORY_BUCKET)
        original_path = str(document.get("storage_path") or "")
        if not original_path:
            continue
        try:
            pdf_bytes = storage_get_bytes(client, bucket_name=bucket, path=original_path)
            if not pdf_bytes:
                continue
            pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception:
            continue
        try:
            for row in candidates:
                page_number = int(row.get("page_number") or 0)
                if page_number < 1 or page_number > pdf.page_count:
                    continue
                page = pdf.load_page(page_number - 1)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.45, 1.45), alpha=False)
                image_bytes = pixmap.tobytes("jpeg", jpg_quality=84)
                digest = hashlib.sha256(image_bytes).hexdigest()
                storage_path = (
                    f"projects/{project_id}/documents/{document_id}/"
                    f"pages/recovered-v272-{page_number:04d}-{digest[:10]}.jpg"
                )
                try:
                    uploaded = put_bytes(
                        path=storage_path,
                        data=image_bytes,
                        content_type="image/jpeg",
                        cache_control="3600",
                        sha256=digest,
                        logical_kind="workspace-visual",
                    )
                except Exception:
                    continue
                payload = {
                    "project_id": project_id,
                    "document_id": document_id,
                    "page_number": page_number,
                    "slide_title": str(row.get("suggested_title") or "Material visual").strip(),
                    "slide_summary": row.get("summary") or row.get("slide_summary"),
                    "primary_section": row.get("inferred_section"),
                    "storage_bucket": str(uploaded.get("storage_bucket") or r2_bucket_marker()),
                    "storage_path": storage_path,
                    "content_sha256": digest,
                    "raw_data": {
                        "recovered_by": "workspace_v27_5",
                        "source": "page_inventory",
                        "suggested_section": row.get("suggested_section"),
                    },
                }
                try:
                    response = client.table("memory_pages").insert(payload).execute()
                    saved = dict(response.data[0]) if response.data else payload
                    snapshot.setdefault("memory_pages", []).append(saved)
                    recovered += 1
                    existing.add((document_id, page_number))
                except Exception:
                    pass
        finally:
            pdf.close()
    return recovered


def ensure_visual_page_items(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
    section_keys: Iterable[str],
) -> int:
    accepted = set(section_keys) & VISUAL_SECTIONS
    existing_pages = {
        (str(row.get("document_id")), int(row.get("source_page") or 0))
        for row in snapshot.get("memory_items", [])
        if row.get("document_id") and row.get("source_page")
    }
    created = 0
    for page in snapshot.get("memory_pages", []):
        document_id = str(page.get("document_id") or "")
        page_number = int(page.get("page_number") or 0)
        if not document_id or page_number <= 0 or (document_id, page_number) in existing_pages:
            continue
        if not is_project_relevant_record(page):
            continue
        section = infer_section_from_record(
            page,
            explicit_section=page.get("primary_section"),
        )
        if section not in accepted:
            continue
        payload = {
            "project_id": project_id,
            "document_id": document_id,
            "page_id": page.get("id"),
            "source_page": page_number,
            "section_key": section,
            "item_type": "Material visual",
            "title": page.get("slide_title") or "Material visual",
            "summary": page.get("slide_summary") or "Material visual preservado da apresentação do projeto.",
            "description": page.get("slide_summary"),
            "item_status": "Proposto",
            "tags": [],
            "objectives": [],
            "audiences": [],
            "mechanics": [],
            "technologies": [],
            "journey_stage": None,
            "slide_title": page.get("slide_title"),
            "visual_crop": None,
            "confidence": None,
            "evidence": None,
            "sort_order": 100000 + page_number,
            "raw_data": {
                "generated_by": "workspace_v27_5",
                "source": "recovered_visual_page",
            },
        }
        try:
            response = client.table("memory_items").insert(payload).execute()
            saved = dict(response.data[0]) if response.data else payload
            snapshot.setdefault("memory_items", []).append(saved)
            existing_pages.add((document_id, page_number))
            created += 1
        except Exception:
            continue
    return created


def _page_text_blob(page: dict[str, Any] | None) -> str:
    page = page or {}
    raw = page.get("raw_data") if isinstance(page.get("raw_data"), dict) else {}
    return normalise_text(" ".join(
        str(value or "")
        for value in (
            page.get("slide_title"),
            page.get("slide_summary"),
            page.get("text"),
            raw.get("slide_title"),
            raw.get("slide_summary"),
            raw.get("text"),
            raw.get("normalized_text"),
        )
    ))


def _is_plan_page(page: dict[str, Any] | None) -> bool:
    text = _page_text_blob(page)
    return bool(
        "planta" in text
        or "implantacao" in text
        or ("grand ballroom" in text and any(term in text for term in ("palco", "housemix", "photo op", "totem led")))
    )


def _plan_title(page: dict[str, Any]) -> str:
    text = _page_text_blob(page)
    if "sala londrina" in text:
        return "Planta — Sala Londrina / Empresas"
    if "grand ballroom" in text:
        return "Planta — Grand Ballroom I & II"
    return "Planta / implantação"


def _visual_context(page: dict[str, Any] | None) -> str:
    text = _page_text_blob(page)
    if "sala londrina" in text or " empresas " in f" {text} ":
        return "sala_londrina_empresas"
    if "grand ballroom" in text or "plenaria" in text or "foyer" in text:
        return "grand_ballroom"
    return ""


def _visual_signature(record: dict[str, Any]) -> tuple[str, str, str]:
    normalized = normalise_text(record.get("title"))
    normalized = re.sub(r"\b(?:vista do )?slide \d+\b", "", normalized).strip()
    aliases = {
        "photo op": "ponto de foto",
        "photoop": "ponto de foto",
        "ponto de foto": "ponto de foto",
        "quick massage": "massagem",
        "ilha de massagem": "massagem",
        "cadeiras de massagem": "massagem",
        "cadeira de massagem": "massagem",
    }
    normalized = aliases.get(normalized, normalized)
    return str(record.get("section") or ""), normalized, str(record.get("context_key") or "")


def _merge_visual_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    def score(record: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            1 if record.get("image_path") else 0,
            1 if record.get("kind") == "item" else 0,
            1 if not record.get("shared_page_visual") else 0,
            len(str(record.get("summary") or "")),
        )

    primary = dict(max(group, key=score))
    primary["related_evidence_count"] = len(group)
    for relation_key in ("costs", "briefings"):
        merged = []
        seen = set()
        for record in group:
            for value in record.get(relation_key) or []:
                marker = repr(value)
                if marker in seen:
                    continue
                seen.add(marker)
                merged.append(value)
        primary[relation_key] = merged
    return primary


def _dedupe_visual_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    order: list[tuple[str, str, str]] = []
    for record in records:
        signature = _visual_signature(record)
        if not signature[1]:
            signature = (signature[0], f"__{len(order)}", signature[2])
        if signature not in groups:
            groups[signature] = []
            order.append(signature)
        groups[signature].append(record)

    deduped: list[dict[str, Any]] = []
    for signature in order:
        group = groups[signature]
        if len(group) == 1:
            deduped.append(group[0])
            continue

        # Plantas/implantações iguais servem como evidência compartilhada e devem
        # aparecer uma única vez, mesmo quando a apresentação traz mais de uma
        # página destacando áreas diferentes sobre a mesma planta base.
        if all(record.get("item_type") == "Implantação / planta" for record in group):
            deduped.append(_merge_visual_group(group))
            continue

        image_paths = {str(record.get("image_path")) for record in group if record.get("image_path")}
        if len(image_paths) <= 1:
            deduped.append(_merge_visual_group(group))
            continue

        # Vistas realmente diferentes de uma mesma solução (ex.: vários renders do
        # palco) continuam disponíveis. O que desaparece são apenas duplicatas
        # semânticas/visuais, não repertório útil.
        by_image: dict[str, list[dict[str, Any]]] = {}
        no_image: list[dict[str, Any]] = []
        for record in group:
            path = str(record.get("image_path") or "")
            if not path:
                no_image.append(record)
                continue
            by_image.setdefault(path, []).append(record)
        for subgroup in by_image.values():
            deduped.append(_merge_visual_group(subgroup) if len(subgroup) > 1 else subgroup[0])
        if no_image:
            deduped.append(_merge_visual_group(no_image))
    return deduped


def _visual_records(snapshot: dict[str, Any], section_keys: Iterable[str]) -> list[dict[str, Any]]:
    accepted = set(section_keys)
    maps = _maps(snapshot)
    inventory_section_hints: dict[tuple[str, int], str] = {}
    for document in snapshot.get("memory_documents", []):
        document_id = str(document.get("id") or "")
        if not document_id:
            continue
        for page_number, section in _visual_inventory_section_hints(_inventory_rows(document)).items():
            inventory_section_hints[(document_id, int(page_number))] = section
    costs_by_item, briefings_by_item = _linked_maps(snapshot, maps)
    relevant_items: list[tuple[dict[str, Any], str, dict[str, Any] | None]] = []
    page_item_counts: dict[tuple[str, int], int] = {}

    for item in snapshot.get("memory_items", []):
        if not is_project_relevant_record(item):
            continue
        section = infer_section_from_record(item, explicit_section=item.get("section_key"))
        if section not in accepted:
            continue
        page = maps["page_by_id"].get(str(item.get("page_id") or ""))
        if page is None:
            page = maps["page_by_doc_number"].get((str(item.get("document_id") or ""), int(item.get("source_page") or 0)))
        relevant_items.append((item, section, page))
        page_key = (str(item.get("document_id") or ""), int(item.get("source_page") or 0))
        if page_key[1] > 0:
            page_item_counts[page_key] = page_item_counts.get(page_key, 0) + 1

    used_full_pages: set[tuple[str, int]] = set()
    records: list[dict[str, Any]] = []
    for item, section, page in relevant_items:
        item_id = str(item.get("id") or "")
        page_key = (str(item.get("document_id") or ""), int(item.get("source_page") or 0))
        has_item_crop = bool(item.get("visual_storage_path"))
        shared_page = page_item_counts.get(page_key, 0) > 1
        plan_page = _is_plan_page(page)
        use_page_fallback = bool(page) and not has_item_crop and not shared_page and not plan_page
        image_bucket = item.get("visual_storage_bucket") if has_item_crop else ((page or {}).get("storage_bucket") if use_page_fallback else None)
        image_path = item.get("visual_storage_path") if has_item_crop else ((page or {}).get("storage_path") if use_page_fallback else None)
        if use_page_fallback:
            used_full_pages.add(page_key)
        document = maps["document_by_id"].get(str(item.get("document_id") or ""), {})
        records.append({
            "kind": "item",
            "item_id": item_id,
            "section": section,
            "title": item.get("title") or "Conteúdo sem título",
            "summary": item.get("summary") or item.get("description") or "Sem resumo disponível.",
            "description": item.get("description"),
            "item_type": item.get("item_type") or "Conteúdo",
            "status": item.get("item_status") or "Não informado",
            "tags": _normalise_list(item.get("tags")),
            "evidence": item.get("evidence"),
            "image_bucket": image_bucket,
            "image_path": image_path,
            "document": document,
            "costs": costs_by_item.get(item_id, []),
            "briefings": briefings_by_item.get(item_id, []),
            "outcome": maps["outcome_by_item"].get(item_id),
            "sort_order": int(item.get("sort_order") or 0),
            "source_page": int(item.get("source_page") or 0),
            "context_key": _visual_context(page),
            "shared_page_visual": shared_page or plan_page,
        })

    # Plantas são evidências compartilhadas: aparecem uma única vez como implantação,
    # nunca repetidas como capa de Palco, Totem, Photo-op etc.
    for page in snapshot.get("memory_pages", []):
        if not is_project_relevant_record(page):
            continue
        page_key = (str(page.get("document_id") or ""), int(page.get("page_number") or 0))
        plan_page = _is_plan_page(page)
        hinted_page_section = inventory_section_hints.get(page_key)
        page_section = infer_section_from_record(
            page,
            explicit_section=hinted_page_section or page.get("primary_section"),
        )
        shared_page = page_item_counts.get(page_key, 0) > 1
        if plan_page:
            page_section = "scenography"
        if page_section not in accepted:
            continue
        if page_key in used_full_pages and not plan_page:
            continue
        if not plan_page and not shared_page and page_item_counts.get(page_key, 0) > 0:
            continue
        document = maps["document_by_id"].get(str(page.get("document_id") or ""), {})
        title = _plan_title(page) if plan_page else (page.get("slide_title") or "Material visual")
        summary = (
            "Implantação geral preservada como evidência compartilhada dos elementos desta área."
            if plan_page
            else (page.get("slide_summary") or "Visual preservado da apresentação do projeto.")
        )
        records.append({
            "kind": "page",
            "item_id": None,
            "section": page_section,
            "title": title,
            "summary": summary,
            "description": None,
            "item_type": "Implantação / planta" if plan_page else "Material visual",
            "status": document.get("document_status") or "Preservado",
            "tags": [],
            "evidence": None,
            "image_bucket": page.get("storage_bucket"),
            "image_path": page.get("storage_path"),
            "document": document,
            "costs": [],
            "briefings": [],
            "outcome": None,
            "sort_order": 100000 + int(page.get("page_number") or 0),
            "source_page": int(page.get("page_number") or 0),
            "context_key": _visual_context(page),
            "shared_page_visual": True,
        })

    records = _dedupe_visual_records(records)
    return sorted(records, key=lambda row: (row.get("sort_order", 0), str(row.get("title") or "").casefold()))

def _cost_badges(record: dict[str, Any], section_context: dict[str, Any]) -> None:
    """Mostra somente custo realmente ligado à ficha.

    Valores não rateados pertencem ao contexto da SEÇÃO e são exibidos uma única
    vez no topo, nunca repetidos em todos os cards. Correlação com linha de valor
    zero também não vira um falso badge de R$ 0,00.
    """
    del section_context
    costs = record.get("costs") or []
    confirmed = [row for row in costs if row["link"].get("link_status") == "confirmed"]
    active = confirmed or costs
    if not active:
        return
    total = sum(_safe_float(row["cost"].get("client_total")) for row in active)
    if total <= 0:
        return
    best_score = max(_safe_float(row["link"].get("match_score")) for row in active)
    label = "Custo confirmado" if confirmed else f"Custo sugerido · {best_score:.0%}"
    st.markdown(
        f'<span class="nave-cost-badge">{escape(label)}: {escape(_money(total))}</span>',
        unsafe_allow_html=True,
    )


def _render_item_details(record: dict[str, Any]) -> None:
    with st.expander("Abrir ficha", expanded=False):
        description = record.get("description") or record.get("summary")
        if description:
            st.markdown("**Descrição**")
            st.write(description)
        tags = record.get("tags") or []
        if tags:
            st.markdown("**Tags**")
            st.write(" · ".join(tags))
        if record.get("evidence"):
            st.markdown("**Evidência preservada**")
            st.write(record.get("evidence"))
        costs = record.get("costs") or []
        st.markdown("**Custos relacionados**")
        if costs:
            rows = []
            for linked in costs:
                cost = linked["cost"]
                link = linked["link"]
                rows.append({
                    "Item da planilha": cost.get("item_name"),
                    "Categoria": cost.get("category"),
                    "Valor": _money(cost.get("client_total")),
                    "Situação": cost.get("item_status"),
                    "Correlação": "Confirmada" if link.get("link_status") == "confirmed" else f"Sugerida · {_safe_float(link.get('match_score')):.0%}",
                    "Motivo": link.get("match_reason"),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma linha direta da planilha foi relacionada a esta ficha.")
        briefings = record.get("briefings") or []
        st.markdown("**Briefing e aderência**")
        if briefings:
            for linked in briefings:
                req = linked["requirement"]
                link = linked["link"]
                status = str(link.get("adherence_status") or req.get("adherence_status") or "not_assessed").replace("_", " ")
                st.markdown(f"- **{req.get('title') or 'Demanda'}** — {status}")
                if link.get("evidence"):
                    st.caption(str(link.get("evidence")))
        else:
            st.caption("Nenhuma demanda do briefing foi relacionada a esta ficha.")
        outcome = record.get("outcome")
        st.markdown("**Resultado da ficha**")
        if outcome:
            st.write(str(outcome.get("outcome_status") or "Não avaliado").replace("_", " ").title())
            if outcome.get("feedback_summary"):
                st.caption(str(outcome.get("feedback_summary")))
            if outcome.get("execution_notes"):
                st.caption(str(outcome.get("execution_notes")))
        else:
            st.caption("Resultado ainda não registrado.")
        document = record.get("document") or {}
        if document:
            version = document.get("version_label") or "sem versão informada"
            st.markdown("**Origem**")
            st.caption(f"{document.get('title') or document.get('file_name') or 'Apresentação'} · {version}")


def render_visual_section(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
    section_keys: Iterable[str],
    empty_message: str,
    columns_count: int | None = None,
) -> int:
    del columns_count  # compatibilidade com chamadas antigas
    st.markdown(VISUAL_CSS, unsafe_allow_html=True)
    keys = list(section_keys)
    accepted = set(keys) & VISUAL_SECTIONS

    changed = False
    if has_missing_visual_pages(snapshot, keys):
        with st.spinner("Recuperando materiais visuais da apresentação..."):
            changed = recover_missing_visual_pages(
                client,
                project_id=project_id,
                snapshot=snapshot,
                section_keys=keys,
            ) > 0
    # Páginas sem ficha continuam disponíveis como registro visual, mas não
    # materializamos mais um item genérico no banco apenas para preencher a tela.
    # Isso evita poluir cenografia/ativações/brindes com "Material visual" sem semântica.
    ensure_automatic_cost_links(
        client,
        project_id=project_id,
        snapshot=snapshot,
    )
    if changed:
        st.rerun()

    records = _visual_records(snapshot, keys)
    if not records:
        st.markdown(f'<div class="nave-workspace-empty">{escape(empty_message)}</div>', unsafe_allow_html=True)
        return 0

    section = next(iter(accepted)) if len(accepted) == 1 else None
    context = section_cost_context(snapshot, section) if section else {"section_total": 0, "unallocated_total": 0}
    if context.get("section_total", 0) > 0:
        st.markdown(
            f'<div class="nave-section-cost-summary"><strong>Custos relacionados à seção:</strong> {_money(context["section_total"])}. '
            f'{_money(context["unallocated_total"])} ainda não estão rateados diretamente entre as fichas.</div>',
            unsafe_allow_html=True,
        )

    for record in records:
        with st.container(border=True):
            signed_url = create_storage_signed_url(
                client,
                bucket_name=record.get("image_bucket"),
                storage_path=record.get("image_path"),
            )
            content_target = None
            if signed_url:
                image_column, content_column = st.columns([0.4, 0.6], gap="large", vertical_alignment="center")
                with image_column:
                    st.markdown(
                        f'<div class="nave-horizontal-image"><img src="{escape(signed_url, quote=True)}" alt="{escape(str(record.get("title") or "Material visual"), quote=True)}"></div>',
                        unsafe_allow_html=True,
                    )
                content_target = content_column
            if content_target is None:
                st.markdown(f'<div class="nave-horizontal-title">{escape(str(record.get("title") or "Sem título"))}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="nave-horizontal-meta">{escape(str(record.get("item_type") or "Conteúdo"))} · {escape(str(record.get("status") or "Não informado"))}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f'<div class="nave-horizontal-summary">{escape(str(record.get("summary") or ""))}</div>', unsafe_allow_html=True)
                if int(record.get("related_evidence_count") or 0) > 1:
                    st.caption(f"{int(record['related_evidence_count'])} evidências da apresentação foram consolidadas nesta ficha.")
                _cost_badges(record, context)
                _render_item_details(record)
            else:
                with content_target:
                    st.markdown(f'<div class="nave-horizontal-title">{escape(str(record.get("title") or "Sem título"))}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="nave-horizontal-meta">{escape(str(record.get("item_type") or "Conteúdo"))} · {escape(str(record.get("status") or "Não informado"))}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="nave-horizontal-summary">{escape(str(record.get("summary") or ""))}</div>', unsafe_allow_html=True)
                    if int(record.get("related_evidence_count") or 0) > 1:
                        st.caption(f"{int(record['related_evidence_count'])} evidências da apresentação foram consolidadas nesta ficha.")
                    _cost_badges(record, context)
                    _render_item_details(record)

    return len(records)
