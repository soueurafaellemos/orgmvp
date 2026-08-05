from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#121B42")
CYAN = colors.HexColor("#18CDEA")
SURFACE = colors.HexColor("#F4F6F9")
BORDER = colors.HexColor("#E1E6EF")
MUTED = colors.HexColor("#687188")
WARNING = colors.HexColor("#A65C00")


def _safe(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value)).replace("\n", "<br/>")


def _money(
    value: Any,
    currency: str | None,
) -> str:
    if value is None or str(value).strip() == "":
        return "Não informado"

    prefix = {
        "BRL": "R$ ",
        "USD": "US$ ",
        "EUR": "€ ",
    }.get(str(currency or ""), "")

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


def _image(
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
        max_height = 58 * mm
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


def build_recommendation_shortlist_pdf(
    items: list[dict],
    *,
    brief: dict,
    scope_label: str,
    title: str,
    introduction: str = "",
    show_prices: bool = True,
    show_scores: bool = False,
) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="NAVE by VOE",
    )

    styles = {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=CYAN,
            spaceAfter=5,
        ),
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "item_title": ParagraphStyle(
            "item_title",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=21,
            textColor=NAVY,
            spaceAfter=4,
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
        "reason": ParagraphStyle(
            "reason",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=NAVY,
            backColor=SURFACE,
            borderColor=BORDER,
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=5,
            spaceAfter=7,
        ),
        "warning": ParagraphStyle(
            "warning",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=WARNING,
            spaceBefore=4,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=MUTED,
        ),
    }

    project_name = (
        brief.get("project_name")
        or brief.get("event_name")
        or "Projeto"
    )

    story = [
        Paragraph(
            "NAVE BY VOE - SHORTLIST",
            styles["eyebrow"],
        ),
        Paragraph(
            _safe(title),
            styles["title"],
        ),
        Paragraph(
            (
                f"<b>Projeto:</b> {_safe(project_name)}<br/>"
                f"<b>Escopo:</b> {_safe(scope_label)}<br/>"
                f"<b>Gerado em:</b> "
                f"{datetime.now().strftime('%d/%m/%Y')}"
            ),
            styles["subtitle"],
        ),
    ]

    if introduction.strip():
        story.append(
            Paragraph(
                _safe(introduction),
                styles["subtitle"],
            )
        )

    brief_rows = [
        [
            Paragraph("Objetivo", styles["label"]),
            Paragraph(
                _safe(
                    brief.get("objective")
                    or "Não informado"
                ),
                styles["value"],
            ),
        ],
        [
            Paragraph("Público", styles["label"]),
            Paragraph(
                _safe(
                    brief.get("audience_profile")
                    or "Não informado"
                ),
                styles["value"],
            ),
        ],
        [
            Paragraph("Praça", styles["label"]),
            Paragraph(
                _safe(
                    ", ".join(
                        item
                        for item in [
                            brief.get("location_city"),
                            brief.get("location_state"),
                        ]
                        if item
                    )
                    or "Não informada"
                ),
                styles["value"],
            ),
        ],
    ]

    if show_prices:
        brief_rows.append(
            [
                Paragraph("Budget", styles["label"]),
                Paragraph(
                    _safe(
                        _money(
                            brief.get("budget_total_brl"),
                            "BRL",
                        )
                    ),
                    styles["value"],
                ),
            ]
        )

    brief_table = Table(
        brief_rows,
        colWidths=[35 * mm, 141 * mm],
    )
    brief_table.setStyle(
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
            brief_table,
            Spacer(1, 5 * mm),
        ]
    )

    for index, item in enumerate(items):
        row = dict(item.get("row") or {})
        image = _image(item.get("image_bytes"))

        heading = [
            Paragraph(
                f"{int(row.get('rank') or index + 1)}. "
                f"{_safe(row.get('name') or 'Possibilidade')}",
                styles["item_title"],
            ),
            Paragraph(
                _safe(
                    (
                        f"{row.get('category') or 'Categoria não informada'}"
                        f" · {row.get('supplier_name') or 'Fornecedor não informado'}"
                    )
                ),
                styles["subtitle"],
            ),
        ]

        if image:
            header_table = Table(
                [[heading, image]],
                colWidths=[104 * mm, 72 * mm],
            )
            header_table.setStyle(
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
            story.append(header_table)
        else:
            story.extend(heading)

        summary_rows = [
            [
                Paragraph("Tipo", styles["label"]),
                Paragraph(
                    _safe(
                        row.get("item_type")
                        or "Não informado"
                    ),
                    styles["value"],
                ),
            ],
            [
                Paragraph("Cobertura", styles["label"]),
                Paragraph(
                    _safe(
                        row.get("coverage_status")
                        or "Não cadastrada"
                    ),
                    styles["value"],
                ),
            ],
        ]

        if show_prices:
            summary_rows.extend(
                [
                    [
                        Paragraph(
                            "Estimativa total",
                            styles["label"],
                        ),
                        Paragraph(
                            _safe(
                                _money(
                                    row.get("estimated_total"),
                                    row.get("currency"),
                                )
                            ),
                            styles["value"],
                        ),
                    ],
                    [
                        Paragraph(
                            "Preço de referência",
                            styles["label"],
                        ),
                        Paragraph(
                            _safe(
                                _money(
                                    row.get("base_price"),
                                    row.get("currency"),
                                )
                            ),
                            styles["value"],
                        ),
                    ],
                ]
            )

        if show_scores:
            summary_rows.append(
                [
                    Paragraph(
                        "Aderência NAVE",
                        styles["label"],
                    ),
                    Paragraph(
                        _safe(
                            f"{float(row.get('total_score') or 0):.0f}/100"
                        ),
                        styles["value"],
                    ),
                ]
            )

        summary_table = Table(
            summary_rows,
            colWidths=[43 * mm, 133 * mm],
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, BORDER),
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
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
                Spacer(1, 3 * mm),
                summary_table,
                Paragraph(
                    _safe(
                        row.get("reason")
                        or row.get("description")
                        or "Sem justificativa disponível."
                    ),
                    styles["reason"],
                ),
            ]
        )

        warnings = row.get("warnings") or []
        if warnings:
            story.append(
                Paragraph(
                    "<b>Pontos de atenção:</b> "
                    + _safe(" ".join(warnings)),
                    styles["warning"],
                )
            )

        if index < len(items) - 1:
            story.append(PageBreak())

    def draw_footer(canvas, document_state):
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
            f"Página {document_state.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    return buffer.getvalue()
