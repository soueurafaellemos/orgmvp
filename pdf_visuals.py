from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from document_io import InputDocument


MIN_VISUAL_CONFIDENCE = 0.55


@dataclass
class PreparedVisual:
    file_bytes: bytes
    file_name: str
    mime_type: str
    source_file: str
    source_page: int
    crop_box: dict[str, float]
    method: str
    confidence: float
    content_sha256: str
    title: str
    description: str


def _find_pdf(
    documents: list[InputDocument],
    source_file: str | None,
) -> InputDocument | None:
    pdfs = [
        document
        for document in documents
        if document.mime_type == "application/pdf"
    ]
    if not pdfs:
        return None

    if source_file:
        for document in pdfs:
            if document.name == source_file:
                return document

    return pdfs[0]


def parse_visual_crop(value: Any) -> dict[str, float] | None:
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None

    if not isinstance(value, dict):
        return None

    try:
        crop = {
            "x": float(value["x"]),
            "y": float(value["y"]),
            "width": float(value["width"]),
            "height": float(value["height"]),
            "confidence": float(value.get("confidence", 0.8)),
        }
    except (KeyError, TypeError, ValueError):
        return None

    if not all(0 <= crop[key] <= 1 for key in ("x", "y")):
        return None
    if not all(0 < crop[key] <= 1 for key in ("width", "height")):
        return None
    if crop["x"] + crop["width"] > 1.04:
        return None
    if crop["y"] + crop["height"] > 1.04:
        return None

    crop["x"] = max(0.0, min(1.0, crop["x"]))
    crop["y"] = max(0.0, min(1.0, crop["y"]))
    crop["width"] = min(1.0 - crop["x"], crop["width"])
    crop["height"] = min(1.0 - crop["y"], crop["height"])
    crop["confidence"] = max(0.0, min(1.0, crop["confidence"]))
    return crop


def _normalized_box(rect: fitz.Rect, page_rect: fitz.Rect) -> dict[str, float]:
    return {
        "x": max(0.0, rect.x0 / page_rect.width),
        "y": max(0.0, rect.y0 / page_rect.height),
        "width": min(1.0, rect.width / page_rect.width),
        "height": min(1.0, rect.height / page_rect.height),
    }


def _clip_from_normalized(
    crop: dict[str, float],
    page_rect: fitz.Rect,
    *,
    padding: float = 0.025,
) -> fitz.Rect:
    x0 = (crop["x"] - padding) * page_rect.width
    y0 = (crop["y"] - padding) * page_rect.height
    x1 = (crop["x"] + crop["width"] + padding) * page_rect.width
    y1 = (crop["y"] + crop["height"] + padding) * page_rect.height
    clip = fitz.Rect(x0, y0, x1, y1) & page_rect

    if clip.width < 24 or clip.height < 24:
        raise ValueError("O recorte visual é pequeno demais.")
    return clip


def _candidate_image_rects(page: fitz.Page) -> list[fitz.Rect]:
    page_rect = page.rect
    page_area = max(1.0, page_rect.width * page_rect.height)
    candidates: list[fitz.Rect] = []

    try:
        blocks = page.get_text("dict").get("blocks", [])
    except Exception:
        blocks = []

    for block in blocks:
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        rect = fitz.Rect(*bbox) & page_rect
        area_ratio = (rect.width * rect.height) / page_area
        if rect.width < 45 or rect.height < 45:
            continue
        if area_ratio < 0.018 or area_ratio > 0.88:
            continue
        candidates.append(rect)

    # Remove near-duplicates.
    unique: list[fitz.Rect] = []
    for rect in sorted(
        candidates,
        key=lambda item: (item.y0, item.x0, -(item.width * item.height)),
    ):
        duplicate = False
        for previous in unique:
            intersection = rect & previous
            if intersection.is_empty:
                continue
            overlap = (intersection.width * intersection.height) / max(
                1.0,
                min(rect.width * rect.height, previous.width * previous.height),
            )
            if overlap > 0.86:
                duplicate = True
                break
        if not duplicate:
            unique.append(rect)
    return unique


def _render_visual(
    document: InputDocument,
    *,
    page_number: int,
    crop_box: dict[str, float],
    method: str,
    confidence: float,
    title: str,
) -> PreparedVisual:
    pdf = fitz.open(stream=document.data, filetype="pdf")
    try:
        page_index = int(page_number) - 1
        if page_index < 0 or page_index >= pdf.page_count:
            raise ValueError("Página visual fora do intervalo do PDF.")
        page = pdf.load_page(page_index)
        clip = _clip_from_normalized(crop_box, page.rect)
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(2.2, 2.2),
            clip=clip,
            colorspace=fitz.csRGB,
            alpha=False,
            annots=False,
        )
        image_bytes = pixmap.tobytes("png")
    finally:
        pdf.close()

    digest = hashlib.sha256(image_bytes).hexdigest()
    stem = Path(document.name).stem
    file_name = f"{stem}_p{page_number}_{digest[:10]}.png"
    return PreparedVisual(
        file_bytes=image_bytes,
        file_name=file_name,
        mime_type="image/png",
        source_file=document.name,
        source_page=int(page_number),
        crop_box={
            **{key: float(crop_box[key]) for key in ("x", "y", "width", "height")},
            "confidence": float(confidence),
        },
        method=method,
        confidence=float(confidence),
        content_sha256=digest,
        title=title,
        description=(
            f"Recorte automático da página {page_number} de {document.name}. "
            "Revisar visualmente antes de usar em uma apresentação final."
        ),
    )


def prepare_visual_assignments(
    records: list[dict],
    documents: list[InputDocument],
) -> list[PreparedVisual | None]:
    assignments: list[PreparedVisual | None] = [None] * len(records)
    pending_by_page: dict[tuple[str, int], list[int]] = {}
    used_boxes_by_page: dict[tuple[str, int], list[dict[str, float]]] = {}

    # First choice: bounding boxes returned by the visual model.
    for index, record in enumerate(records):
        source_file = str(record.get("source_file") or "").strip()
        try:
            page_number = int(record.get("source_page"))
        except (TypeError, ValueError):
            continue
        document = _find_pdf(documents, source_file)
        if document is None:
            continue

        crop = parse_visual_crop(record.get("visual_crop"))
        if crop and crop.get("confidence", 0.0) >= MIN_VISUAL_CONFIDENCE:
            try:
                assignments[index] = _render_visual(
                    document,
                    page_number=page_number,
                    crop_box=crop,
                    method="ai_bbox",
                    confidence=crop.get("confidence", 0.8),
                    title=f"Imagem automática — {record.get('name') or 'item'}",
                )
                used_boxes_by_page.setdefault(
                    (document.name, page_number),
                    [],
                ).append(crop)
                continue
            except Exception:
                pass

        pending_by_page.setdefault((document.name, page_number), []).append(index)

    # Fallback: use embedded image rectangles in reading order.
    document_map = {
        document.name: document
        for document in documents
        if document.mime_type == "application/pdf"
    }

    for (source_file, page_number), indexes in pending_by_page.items():
        document = document_map.get(source_file)
        if document is None:
            continue

        pdf = fitz.open(stream=document.data, filetype="pdf")
        try:
            page_index = page_number - 1
            if page_index < 0 or page_index >= pdf.page_count:
                continue
            page = pdf.load_page(page_index)
            candidates = _candidate_image_rects(page)
            page_rect = page.rect

            used_rects = [
                _clip_from_normalized(box, page_rect, padding=0.0)
                for box in used_boxes_by_page.get(
                    (source_file, page_number),
                    [],
                )
            ]
            available_candidates = []
            for candidate in candidates:
                overlaps_used = False
                for used_rect in used_rects:
                    intersection = candidate & used_rect
                    if intersection.is_empty:
                        continue
                    overlap = (
                        intersection.width * intersection.height
                    ) / max(
                        1.0,
                        min(
                            candidate.width * candidate.height,
                            used_rect.width * used_rect.height,
                        ),
                    )
                    if overlap > 0.55:
                        overlaps_used = True
                        break
                if not overlaps_used:
                    available_candidates.append(candidate)
            candidates = available_candidates
        finally:
            pdf.close()

        selected: list[fitz.Rect] = []
        if len(indexes) == 1 and candidates:
            selected = [max(candidates, key=lambda rect: rect.width * rect.height)]
        elif len(candidates) >= len(indexes):
            selected = candidates[:len(indexes)]

        for record_index, rect in zip(indexes, selected):
            record = records[record_index]
            crop = _normalized_box(rect, page_rect)
            crop["confidence"] = 0.62 if len(indexes) == 1 else 0.58
            try:
                assignments[record_index] = _render_visual(
                    document,
                    page_number=page_number,
                    crop_box=crop,
                    method="pdf_image_block",
                    confidence=crop["confidence"],
                    title=f"Imagem automática — {record.get('name') or 'item'}",
                )
            except Exception:
                assignments[record_index] = None

    return assignments
