from __future__ import annotations

"""Helpers for extracting DOCX text without losing checkbox/content-control state.

python-docx's ``Paragraph.text`` only concatenates direct runs. Word checkbox
content controls (``w:sdt``) are often nested below the paragraph and therefore
silently disappear from ``Paragraph.text`` even though the visible document
contains symbols such as ``☐`` / ``☒``.

The functions here walk the underlying OOXML in document order and preserve
nested text, tabs, line breaks and common checkbox control state. They are pure
extraction helpers and contain no project/client-specific logic.
"""

from io import BytesIO
from typing import Any


_CHECKED_VALUES = {"1", "true", "on", "yes"}
_UNCHECKED_VALUES = {"0", "false", "off", "no"}


def _local_name(tag: Any) -> str:
    value = str(tag or "")
    return value.rsplit("}", 1)[-1] if "}" in value else value.split(":")[-1]


def _attr_by_local_name(element: Any, name: str) -> str | None:
    for key, value in getattr(element, "attrib", {}).items():
        if _local_name(key) == name:
            return str(value)
    return None


def _checkbox_state(element: Any) -> bool | None:
    """Return checkbox state when an OOXML subtree explicitly carries one."""
    local = _local_name(getattr(element, "tag", ""))
    if local.casefold() == "checkbox":
        for child in element.iter():
            child_local = _local_name(getattr(child, "tag", ""))
            if child_local.casefold() in {"checked", "default"}:
                raw = (_attr_by_local_name(child, "val") or "").strip().casefold()
                if raw in _CHECKED_VALUES:
                    return True
                if raw in _UNCHECKED_VALUES:
                    return False
        # Some legacy form-field checkboxes use presence of <w:checked/>.
        if any(_local_name(getattr(child, "tag", "")).casefold() == "checked" for child in element.iter()):
            return True
    return None


def _render_ooxml_inline(element: Any) -> str:
    local = _local_name(getattr(element, "tag", ""))

    if local == "t":
        return str(getattr(element, "text", "") or "")
    if local == "tab":
        return "\t"
    if local in {"br", "cr"}:
        return "\n"
    if local == "sym":
        raw = (_attr_by_local_name(element, "char") or "").strip()
        if raw:
            try:
                codepoint = int(raw, 16)
                if 0 <= codepoint <= 0x10FFFF:
                    return chr(codepoint)
            except Exception:
                pass
        return ""

    children = list(element)
    rendered = "".join(_render_ooxml_inline(child) for child in children)

    # A content control may expose its checked state in sdtPr while the visible
    # glyph lives in sdtContent. If the glyph is absent from nested text, prepend
    # a canonical Unicode marker so downstream parsing can still observe state.
    if local == "sdt":
        state: bool | None = None
        for child in element.iter():
            if _local_name(getattr(child, "tag", "")) == "checkbox":
                state = _checkbox_state(child)
                if state is not None:
                    break
        if state is not None and "☒" not in rendered and "☑" not in rendered and "☐" not in rendered:
            rendered = ("☒" if state else "☐") + rendered

    # Checkbox definition nodes live in properties and are not visible text by
    # themselves. Their state is handled by the surrounding content control.
    return rendered


def paragraph_text_preserving_controls(paragraph: Any) -> str:
    """Render a python-docx paragraph including nested content controls."""
    raw = _render_ooxml_inline(paragraph._p)
    # Prefer the richer OOXML rendering, but keep python-docx text as a safe
    # fallback for malformed/unsupported XML constructs.
    return raw if raw.strip() else str(getattr(paragraph, "text", "") or "")


def cell_text_preserving_controls(cell: Any) -> str:
    """Render all paragraphs in a python-docx table cell with controls intact."""
    parts = [paragraph_text_preserving_controls(p) for p in getattr(cell, "paragraphs", [])]
    parts = [part for part in parts if str(part).strip()]
    return "\n".join(parts) if parts else str(getattr(cell, "text", "") or "")


def extract_docx_paragraphs_preserving_controls(data: bytes) -> list[dict[str, Any]]:
    """Return paragraph_index + visible text from DOCX bytes.

    ``paragraph_index`` follows the same 1-based index currently stored by
    ``file_analyst._extract_docx_units`` in the Evidence Unit locator.
    """
    from docx import Document  # type: ignore

    document = Document(BytesIO(data))
    rows: list[dict[str, Any]] = []
    for p_index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph_text_preserving_controls(paragraph).strip()
        if not text:
            continue
        rows.append({"paragraph_index": p_index, "text": text})
    return rows
