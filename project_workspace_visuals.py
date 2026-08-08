from __future__ import annotations

import hashlib
from collections import defaultdict
from html import escape
from typing import Any, Iterable

import fitz
import pandas as pd
import streamlit as st
from supabase import Client

from project_workspace_db import create_storage_signed_url
from project_workspace_intelligence import (
    SECTION_LABELS,
    VISUAL_SECTIONS,
    ensure_automatic_cost_links,
    infer_section_from_record,
    is_project_relevant_record,
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
    cost_items = snapshot.get("cost_items", [])
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


def _candidate_visual_pages(snapshot: dict[str, Any], accepted: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for document in snapshot.get("memory_documents", []):
        for row in _inventory_rows(document):
            combined = {
                "title": row.get("suggested_title"),
                "summary": row.get("slide_summary"),
                "primary_section": row.get("suggested_section"),
                "raw_data": row,
            }
            section = infer_section_from_record(
                combined,
                explicit_section=row.get("suggested_section"),
            )
            page_number = int(row.get("page_number") or 0)
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
            pdf_bytes = client.storage.from_(bucket).download(original_path)
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
                    client.storage.from_(MEMORY_BUCKET).upload(
                        path=storage_path,
                        file=image_bytes,
                        file_options={
                            "content-type": "image/jpeg",
                            "cache-control": "3600",
                            "upsert": "false",
                        },
                    )
                except Exception as exc:
                    message = str(exc).casefold()
                    if not any(token in message for token in ("already exists", "duplicate", "409")):
                        continue
                payload = {
                    "project_id": project_id,
                    "document_id": document_id,
                    "page_number": page_number,
                    "slide_title": str(row.get("suggested_title") or "Material visual").strip(),
                    "slide_summary": row.get("slide_summary"),
                    "primary_section": row.get("inferred_section"),
                    "storage_bucket": MEMORY_BUCKET,
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


def _visual_records(snapshot: dict[str, Any], section_keys: Iterable[str]) -> list[dict[str, Any]]:
    accepted = set(section_keys)
    maps = _maps(snapshot)
    costs_by_item, briefings_by_item = _linked_maps(snapshot, maps)
    used_pages: set[tuple[str, int]] = set()
    records: list[dict[str, Any]] = []

    for item in snapshot.get("memory_items", []):
        if not is_project_relevant_record(item):
            continue
        section = infer_section_from_record(
            item,
            explicit_section=item.get("section_key"),
        )
        if section not in accepted:
            continue
        item_id = str(item.get("id") or "")
        page = maps["page_by_id"].get(str(item.get("page_id") or ""))
        if page is None:
            page = maps["page_by_doc_number"].get((str(item.get("document_id") or ""), int(item.get("source_page") or 0)))
        image_bucket = item.get("visual_storage_bucket") or (page or {}).get("storage_bucket")
        image_path = item.get("visual_storage_path") or (page or {}).get("storage_path")
        document = maps["document_by_id"].get(str(item.get("document_id") or ""), {})
        page_key = (str(item.get("document_id") or ""), int(item.get("source_page") or 0))
        if page_key[1] > 0:
            used_pages.add(page_key)
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
        })

    for page in snapshot.get("memory_pages", []):
        if not is_project_relevant_record(page):
            continue
        section = infer_section_from_record(
            page,
            explicit_section=page.get("primary_section"),
        )
        if section not in accepted:
            continue
        page_key = (str(page.get("document_id") or ""), int(page.get("page_number") or 0))
        if page_key in used_pages:
            continue
        document = maps["document_by_id"].get(str(page.get("document_id") or ""), {})
        records.append({
            "kind": "page",
            "item_id": None,
            "section": section,
            "title": page.get("slide_title") or "Material visual",
            "summary": page.get("slide_summary") or "Visual preservado da apresentação do projeto.",
            "description": None,
            "item_type": "Material visual",
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
        })
    return sorted(records, key=lambda row: (row.get("sort_order", 0), str(row.get("title") or "").casefold()))


def _cost_badges(record: dict[str, Any], section_context: dict[str, Any]) -> None:
    costs = record.get("costs") or []
    confirmed = [row for row in costs if row["link"].get("link_status") == "confirmed"]
    active = confirmed or costs
    if active:
        total = sum(_safe_float(row["cost"].get("client_total")) for row in active)
        best_score = max(_safe_float(row["link"].get("match_score")) for row in active)
        label = "Custo confirmado" if confirmed else f"Custo sugerido · {best_score:.0%}"
        st.markdown(
            f'<span class="nave-cost-badge">{escape(label)}: {escape(_money(total))}</span>',
            unsafe_allow_html=True,
        )
    elif section_context.get("unallocated_total", 0) > 0:
        st.markdown(
            f'<span class="nave-cost-context">Sem linha direta · {escape(_money(section_context["unallocated_total"]))} em custos da seção ainda não rateados</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Nenhum custo relacionado foi identificado na planilha.")


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
) -> None:
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
        return

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
            image_column, content_column = st.columns([0.4, 0.6], gap="large", vertical_alignment="center")
            with image_column:
                signed_url = create_storage_signed_url(
                    client,
                    bucket_name=record.get("image_bucket"),
                    storage_path=record.get("image_path"),
                )
                if signed_url:
                    st.markdown(
                        f'<div class="nave-horizontal-image"><img src="{escape(signed_url, quote=True)}" alt="{escape(str(record.get("title") or "Material visual"), quote=True)}"></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="nave-horizontal-image"><div class="nave-horizontal-placeholder">Imagem não disponível</div></div>',
                        unsafe_allow_html=True,
                    )
            with content_column:
                st.markdown(f'<div class="nave-horizontal-title">{escape(str(record.get("title") or "Sem título"))}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="nave-horizontal-meta">{escape(str(record.get("item_type") or "Conteúdo"))} · {escape(str(record.get("status") or "Não informado"))}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f'<div class="nave-horizontal-summary">{escape(str(record.get("summary") or ""))}</div>', unsafe_allow_html=True)
                _cost_badges(record, context)
                _render_item_details(record)
