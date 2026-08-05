from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from knowledge_details import (
    ENTITY_TYPE_LABELS,
    formatted_sections_for_export,
)


NAVY = colors.HexColor("#121B42")
CYAN = colors.HexColor("#18CDEA")
SURFACE = colors.HexColor("#F4F6F9")
BORDER = colors.HexColor("#E1E6EF")
MUTED = colors.HexColor("#687188")
WHITE = colors.white


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value)).replace("\n", "<br/>")


def _paragraph(
    value: Any,
    style: ParagraphStyle,
) -> Paragraph:
    return Paragraph(
        _safe_text(value) or "-",
        style,
    )


def _image_flowable(
    image_bytes: bytes | None,
) -> Image | None:
    if not image_bytes:
        return None

    try:
        pil = PILImage.open(BytesIO(image_bytes))
        width, height = pil.size
        if width <= 0 or height <= 0:
            return None

        max_width = 72 * mm
        max_height = 54 * mm
        scale = min(
            max_width / width,
            max_height / height,
        )

        return Image(
            BytesIO(image_bytes),
            width=width * scale,
            height=height * scale,
        )
    except Exception:
        return None


def _summary_fields(
    entity_type: str,
    record: dict,
) -> list[tuple[str, Any]]:
    if entity_type == "product":
        return [
            ("Categoria", record.get("category")),
            ("Fornecedor", record.get("supplier_name")),
            (
                "Valor",
                record.get("unit_price")
                or record.get("base_price")
                or record.get("price_min"),
            ),
            ("Pedido mínimo", record.get("min_order_qty")),
        ]

    if entity_type == "activation":
        return [
            ("Categoria", record.get("category")),
            ("Fornecedor", record.get("supplier_name")),
            ("Valor", record.get("base_price")),
            ("Localização", record.get("location")),
        ]

    return [
        ("Tipo de espaço", record.get("venue_type")),
        ("Cidade", record.get("city")),
        ("Valor", record.get("base_price")),
        (
            "Capacidade",
            record.get("standing_capacity")
            or record.get("seated_capacity")
            or record.get("auditorium_capacity"),
        ),
    ]


def _format_summary_value(
    label: str,
    value: Any,
    record: dict,
) -> str:
    if value is None or str(value).strip() == "":
        return "Não informado"

    if label == "Valor":
        prefix = {
            "BRL": "R$ ",
            "USD": "US$ ",
            "EUR": "€ ",
        }.get(str(record.get("currency") or ""), "")

        try:
            number = float(value)
            formatted = f"{number:,.2f}"
            formatted = (
                formatted
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            return f"{prefix}{formatted}"
        except (TypeError, ValueError):
            return f"{prefix}{value}"

    return str(value)


def build_selection_pdf(
    items: list[dict],
    *,
    title: str = "Seleção de possibilidades",
    introduction: str = "",
) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="NAVE by VOE",
    )

    styles = {
        "brand": ParagraphStyle(
            "brand",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=CYAN,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            spaceAfter=8,
        ),
        "intro": ParagraphStyle(
            "intro",
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "item_title": ParagraphStyle(
            "item_title",
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=22,
            textColor=NAVY,
            spaceAfter=3,
        ),
        "type": ParagraphStyle(
            "type",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=CYAN,
            spaceAfter=8,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=CYAN,
        ),
        "value": ParagraphStyle(
            "value",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=NAVY,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=NAVY,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
    }

    story = [
        Paragraph("NAVE BY VOE", styles["brand"]),
        Paragraph(_safe_text(title), styles["title"]),
    ]

    if introduction.strip():
        story.append(
            Paragraph(
                _safe_text(introduction),
                styles["intro"],
            )
        )

    story.append(
        Paragraph(
            (
                f"{len(items)} possibilidade(s) selecionada(s) "
                f"em {datetime.now().strftime('%d/%m/%Y')}."
            ),
            styles["intro"],
        )
    )
    story.append(Spacer(1, 3 * mm))

    for item_index, item in enumerate(items):
        entity_type = str(item.get("entity_type") or "")
        record = dict(item.get("record") or {})
        image_bytes = item.get("image_bytes")
        item_name = (
            record.get("name")
            or item.get("name")
            or "Possibilidade"
        )

        header_content = [
            Paragraph(
                _safe_text(item_name),
                styles["item_title"],
            ),
            Paragraph(
                _safe_text(
                    ENTITY_TYPE_LABELS.get(
                        entity_type,
                        entity_type,
                    ).upper()
                ),
                styles["type"],
            ),
        ]

        image = _image_flowable(image_bytes)

        if image:
            header = Table(
                [
                    [
                        header_content,
                        image,
                    ]
                ],
                colWidths=[104 * mm, 72 * mm],
            )
            header.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(header)
        else:
            story.extend(header_content)

        summary_data = []
        for label, value in _summary_fields(
            entity_type,
            record,
        ):
            summary_data.append(
                [
                    _paragraph(label, styles["label"]),
                    _paragraph(
                        _format_summary_value(
                            label,
                            value,
                            record,
                        ),
                        styles["value"],
                    ),
                ]
            )

        summary_table = Table(
            summary_data,
            colWidths=[37 * mm, 139 * mm],
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend(
            [
                Spacer(1, 4 * mm),
                summary_table,
                Spacer(1, 2 * mm),
            ]
        )

        for section_title, fields in formatted_sections_for_export(
            entity_type,
            record,
        ):
            section_rows = []

            for label, value in fields:
                section_rows.append(
                    [
                        _paragraph(label, styles["label"]),
                        _paragraph(value, styles["body"]),
                    ]
                )

            if not section_rows:
                continue

            section_table = Table(
                section_rows,
                colWidths=[42 * mm, 134 * mm],
                repeatRows=0,
            )
            section_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
                        ("INNERGRID", (0, 0), (-1, -1), 0.2, BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )

            story.extend(
                [
                    Paragraph(
                        _safe_text(section_title),
                        styles["section"],
                    ),
                    section_table,
                ]
            )

        if item_index < len(items) - 1:
            story.append(PageBreak())

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(
            17 * mm,
            12 * mm,
            A4[0] - 17 * mm,
            12 * mm,
        )
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            17 * mm,
            7.5 * mm,
            "NAVE by VOE - Conectando briefing, repertório e decisão.",
        )
        canvas.drawRightString(
            A4[0] - 17 * mm,
            7.5 * mm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    return buffer.getvalue()
