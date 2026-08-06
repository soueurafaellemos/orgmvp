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


VISUAL_SECTIONS = {"scenography", "activations", "gifts"}
MEMORY_BUCKET = "nave-memory"

VISUAL_CSS = """
<style>
.nave-visual-frame {
    align-items: center;
    aspect-ratio: 16 / 9;
    background: #F4F6F9;
    border: 1px solid #E1E6EF;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    margin-bottom: 0.75rem;
    overflow: hidden;
}
.nave-visual-frame img {
    height: 100%;
    object-fit: contain;
    width: 100%;
}
.nave-visual-placeholder {
    color: #7D869C;
    font-size: 0.78rem;
    padding: 1rem;
    text-align: center;
}
.nave-visual-title {
    color: #121B42;
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.25;
}
.nave-visual-meta {
    color: #687188;
    font-size: 0.75rem;
    margin-top: 0.22rem;
}
.nave-visual-summary {
    color: #4F5971;
    font-size: 0.82rem;
    line-height: 1.48;
    margin-top: 0.55rem;
    min-height: 3.7rem;
}
.nave-visual-cost {
    background: #F0FAFC;
    border-radius: 9px;
    color: #126A7A;
    font-size: 0.76rem;
    font-weight: 750;
    margin-top: 0.65rem;
    padding: 0.48rem 0.58rem;
}
.nave-visual-no-cost {
    color: #929AAF;
    font-size: 0.72rem;
    margin-top: 0.65rem;
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
            for row in pages
            if row.get("document_id") and row.get("page_number")
        },
        "document_by_id": {str(row.get("id")): row for row in documents if row.get("id")},
        "cost_item_by_id": {str(row.get("id")): row for row in cost_items if row.get("id")},
        "requirement_by_id": {str(row.get("id")): row for row in requirements if row.get("id")},
        "outcome_by_item": {
            str(row.get("item_id")): row
            for row in snapshot.get("item_outcomes", [])
            if row.get("item_id")
        },
    }


def _linked_maps(snapshot: dict[str, Any], maps: dict[str, Any]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
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


def has_missing_visual_pages(snapshot: dict[str, Any], section_keys: Iterable[str]) -> bool:
    accepted = set(section_keys) & VISUAL_SECTIONS
    existing = {
        (str(row.get("document_id")), int(row.get("page_number") or 0))
        for row in snapshot.get("memory_pages", [])
        if row.get("document_id") and row.get("page_number")
    }
    for document in snapshot.get("memory_documents", []):
        raw = document.get("raw_data") if isinstance(document.get("raw_data"), dict) else {}
        for row in raw.get("page_inventory") or []:
            section = str(row.get("suggested_section") or "")
            page_number = int(row.get("page_number") or 0)
            meaningful = row.get("is_meaningful") is not False
            if section in accepted and page_number > 0 and meaningful:
                if (str(document.get("id")), page_number) not in existing:
                    return True
    return False


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
    recovered = 0
    for document in snapshot.get("memory_documents", []):
        document_id = str(document.get("id") or "")
        bucket = str(document.get("storage_bucket") or MEMORY_BUCKET)
        original_path = str(document.get("storage_path") or "")
        raw = document.get("raw_data") if isinstance(document.get("raw_data"), dict) else {}
        candidates = []
        for row in raw.get("page_inventory") or []:
            section = str(row.get("suggested_section") or "")
            page_number = int(row.get("page_number") or 0)
            if section not in accepted or page_number <= 0 or row.get("is_meaningful") is False:
                continue
            if (document_id, page_number) in existing:
                continue
            candidates.append(row)
        if not candidates or not document_id or not original_path:
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
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
                image_bytes = pixmap.tobytes("jpeg", jpg_quality=82)
                digest = hashlib.sha256(image_bytes).hexdigest()
                storage_path = (
                    f"projects/{project_id}/documents/{document_id}/"
                    f"pages/recovered-{page_number:04d}-{digest[:10]}.jpg"
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
                    if "already exists" not in message and "duplicate" not in message and "409" not in message:
                        continue
                payload = {
                    "project_id": project_id,
                    "document_id": document_id,
                    "page_number": page_number,
                    "slide_title": str(row.get("suggested_title") or "Material visual").strip(),
                    "slide_summary": None,
                    "primary_section": str(row.get("suggested_section") or "") or None,
                    "storage_bucket": MEMORY_BUCKET,
                    "storage_path": storage_path,
                    "content_sha256": digest,
                    "raw_data": {"recovered_by": "workspace_v27_1", "source": "page_inventory"},
                }
                try:
                    client.table("memory_pages").insert(payload).execute()
                    recovered += 1
                    existing.add((document_id, page_number))
                except Exception:
                    pass
        finally:
            pdf.close()
    if recovered:
        for document in snapshot.get("memory_documents", []):
            document_id = document.get("id")
            if not document_id:
                continue
            try:
                count_response = (
                    client.table("memory_pages")
                    .select("id", count="exact")
                    .eq("document_id", document_id)
                    .execute()
                )
                count = getattr(count_response, "count", None)
                if count is not None:
                    (
                        client.table("memory_documents")
                        .update({"rendered_pages_count": int(count)})
                        .eq("id", document_id)
                        .execute()
                    )
            except Exception:
                pass
    return recovered


def _visual_records(snapshot: dict[str, Any], section_keys: Iterable[str]) -> list[dict[str, Any]]:
    accepted = set(section_keys)
    maps = _maps(snapshot)
    costs_by_item, briefings_by_item = _linked_maps(snapshot, maps)
    used_pages: set[tuple[str, int]] = set()
    records: list[dict[str, Any]] = []

    for item in snapshot.get("memory_items", []):
        if item.get("section_key") not in accepted:
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
        if page.get("primary_section") not in accepted:
            continue
        page_key = (str(page.get("document_id") or ""), int(page.get("page_number") or 0))
        if page_key in used_pages:
            continue
        document = maps["document_by_id"].get(str(page.get("document_id") or ""), {})
        records.append({
            "kind": "page",
            "item_id": None,
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


def _render_cost_summary(costs: list[dict[str, Any]]) -> None:
    confirmed = [row for row in costs if row["link"].get("link_status") == "confirmed"]
    active = confirmed or costs
    if not active:
        st.markdown('<div class="nave-visual-no-cost">Sem custo relacionado na planilha.</div>', unsafe_allow_html=True)
        return
    total = sum(_safe_float(row["cost"].get("client_total")) for row in active)
    label = "Custo confirmado" if confirmed else "Custo sugerido"
    st.markdown(
        f'<div class="nave-visual-cost">{escape(label)}: {escape(_money(total))}</div>',
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
                    "Correlação": "Confirmada" if link.get("link_status") == "confirmed" else "Sugerida",
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma linha da planilha foi relacionada a esta ficha.")
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
    columns_count: int = 3,
) -> None:
    st.markdown(VISUAL_CSS, unsafe_allow_html=True)
    keys = list(section_keys)
    if has_missing_visual_pages(snapshot, keys):
        with st.spinner("Recuperando os materiais visuais já preservados na apresentação..."):
            recovered = recover_missing_visual_pages(
                client,
                project_id=project_id,
                snapshot=snapshot,
                section_keys=keys,
            )
        if recovered:
            st.rerun()
    records = _visual_records(snapshot, keys)
    if not records:
        st.markdown(f'<div class="nave-workspace-empty">{escape(empty_message)}</div>', unsafe_allow_html=True)
        return
    for start in range(0, len(records), columns_count):
        columns = st.columns(columns_count, gap="medium")
        for column, record in zip(columns, records[start:start + columns_count]):
            with column:
                with st.container(border=True):
                    signed_url = create_storage_signed_url(
                        client,
                        bucket_name=record.get("image_bucket"),
                        storage_path=record.get("image_path"),
                    )
                    if signed_url:
                        st.markdown(
                            f'<div class="nave-visual-frame"><img src="{escape(signed_url, quote=True)}" alt="{escape(str(record.get("title") or "Material visual"), quote=True)}"></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown('<div class="nave-visual-frame"><div class="nave-visual-placeholder">Imagem não disponível</div></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="nave-visual-title">{escape(str(record.get("title") or "Sem título"))}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="nave-visual-meta">{escape(str(record.get("item_type") or "Conteúdo"))} · {escape(str(record.get("status") or "Não informado"))}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="nave-visual-summary">{escape(str(record.get("summary") or ""))}</div>', unsafe_allow_html=True)
                    _render_cost_summary(record.get("costs") or [])
                    _render_item_details(record)
