from __future__ import annotations

"""PDF de seleção da Base de Conhecimento.

Compatibilidade V28.0.3.2: este módulo é deliberadamente independente de
``knowledge_details.py``. Assim, evoluções na ficha visual não impedem a Base
de Conhecimento de abrir.
"""

from io import BytesIO
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ENTITY_LABELS = {
    "product": "Brinde",
    "activation": "Ativação",
    "venue": "Local / espaço",
    "supplier": "Fornecedor",
}


def _as_rows(value: Any) -> list[dict]:
    if value is None:
        return []
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            return [dict(row) for row in value.to_dict(orient="records")]
    except Exception:
        pass
    if isinstance(value, dict):
        for key in ("items", "records", "rows", "selected_items", "selected_records"):
            nested = value.get(key)
            if isinstance(nested, (list, tuple)):
                return [dict(item) for item in nested if isinstance(item, dict)]
        return [dict(value)]
    if isinstance(value, (list, tuple, set)):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _first_rows(args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[dict]:
    for key in ("items", "records", "rows", "selected_items", "selected_records", "selection"):
        if key in kwargs:
            rows = _as_rows(kwargs.get(key))
            if rows:
                return rows
    for value in args:
        rows = _as_rows(value)
        if rows:
            return rows
    return []


def _value(record: dict, *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            text = ", ".join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        if text and text.casefold() not in {"none", "null", "nan", "nao informado", "não informado"}:
            return text
    return ""


def _item_type(record: dict) -> str:
    explicit = _value(record, "item_type", "entity_type", "type")
    if explicit:
        return explicit
    if "Brinde" in record:
        return "product"
    if "Ativação" in record:
        return "activation"
    if "Local" in record:
        return "venue"
    if "Fornecedor" in record:
        return "supplier"
    return "item"


def build_selection_pdf(*args: Any, **kwargs: Any) -> bytes:
    """Gera bytes PDF aceitando as assinaturas usadas pelas versões anteriores.

    O primeiro argumento/keyword que contenha uma lista de dicionários é
    tratado como a seleção. Argumentos extras são aceitos para manter
    compatibilidade com chamadas legadas da Base.
    """
    rows = _first_rows(args, kwargs)
    title = str(
        kwargs.get("title")
        or kwargs.get("document_title")
        or kwargs.get("heading")
        or "Seleção de possibilidades — NAVE by VOE"
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "NaveTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=22,
        textColor=colors.HexColor("#121B42"),
        alignment=TA_LEFT,
        spaceAfter=6 * mm,
    )
    item_style = ParagraphStyle(
        "NaveItem",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#121B42"),
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "NaveBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=13,
        textColor=colors.HexColor("#30384F"),
    )
    label = ParagraphStyle(
        "NaveLabel",
        parent=body,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#121B42"),
    )

    story: list[Any] = [Paragraph(title, title_style)]
    if not rows:
        story.append(Paragraph("Nenhum item foi selecionado.", body))
    for index, record in enumerate(rows, start=1):
        name = _value(
            record, "name", "Nome", "Brinde", "Ativação", "Local", "Fornecedor"
        ) or f"Item {index}"
        type_code = _item_type(record)
        type_label = ENTITY_LABELS.get(type_code, _value(record, "Tipo") or "Possibilidade")
        story.append(Paragraph(f"{index:02d} · {type_label} — {name}", item_style))

        fields = [
            ("Categoria", _value(record, "category", "record_type", "venue_type", "Categoria")),
            ("Fornecedor", _value(record, "supplier_name", "Fornecedor")),
            ("Marca / cliente", _value(record, "client_brand", "Marca / cliente")),
            ("Projeto", _value(record, "project_name", "Projeto")),
            ("Localização", _value(record, "location", "city", "Cidade")),
            ("Material", _value(record, "material", "Material")),
            ("Descrição", _value(record, "description", "Descrição")),
        ]
        data = []
        for field_label, field_value in fields:
            if field_value:
                data.append([
                    Paragraph(field_label, label),
                    Paragraph(field_value.replace("\n", "<br/>"), body),
                ])
        if data:
            table = Table(data, colWidths=[34 * mm, 128 * mm], hAlign="LEFT")
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E1E6EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(table)
        story.append(Spacer(1, 7 * mm))

    doc.build(story)
    return buffer.getvalue()
