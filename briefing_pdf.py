from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 16 * mm
MARGIN_TOP = 18 * mm
MARGIN_BOTTOM = 17 * mm

INK = colors.HexColor("#20252B")
MUTED = colors.HexColor("#66717E")
LINE = colors.HexColor("#D8DEE5")
PANEL = colors.HexColor("#F3F5F7")
ACCENT = colors.HexColor("#24577A")
ACCENT_LIGHT = colors.HexColor("#E9F0F5")
CRITICAL = colors.HexColor("#B63B3B")
CRITICAL_BG = colors.HexColor("#FBECEC")
IMPORTANT = colors.HexColor("#A06716")
IMPORTANT_BG = colors.HexColor("#FFF4DF")
ENRICHMENT = colors.HexColor("#286780")
ENRICHMENT_BG = colors.HexColor("#EAF4F7")
WHITE = colors.white


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    replacements = {
        "–": "-",
        "—": "-",
        "•": "-",
        "→": "->",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "☒": "[X]",
        "☐": "[ ]",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _html(value: Any) -> str:
    return escape(_clean(value)).replace("\n", "<br/>")


def _list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value if _clean(item)]
    return [_clean(value)]


def _money(value: Any, currency: str | None = "BRL") -> str:
    if value in (None, ""):
        return "Não informado"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _clean(value)
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = {"BRL": "R$ ", "USD": "US$ ", "EUR": "€ "}.get(
        str(currency or "").upper(), ""
    )
    return prefix + formatted


def _date_text(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "Não informado"
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return f"{text[8:10]}/{text[5:7]}/{text[:4]}"
    return text


def _selected_line(options: Iterable[str], selected: Iterable[str]) -> str:
    normalized = {_clean(item).lower() for item in selected}
    return "   ".join(
        f"[{'X' if option.lower() in normalized else ' '}] {option.upper()}"
        for option in options
    )


def _bullet_paragraphs(items: Any, styles: dict[str, ParagraphStyle]) -> list[Any]:
    output: list[Any] = []
    for item in _list(items):
        output.append(
            Paragraph(
                f"<bullet>-</bullet>{_html(item)}",
                styles["bullet"],
            )
        )
    return output


def _metadata_table(brief: dict, styles: dict[str, ParagraphStyle]) -> Table:
    agency = brief.get("agency_context") or {}
    rows = [
        ["JOB", agency.get("job_code") or "Não informado", "ATENDIMENTO VOE", agency.get("account_manager") or "Não informado"],
        ["CLIENTE", brief.get("client_brand") or "Não informado", "CONTATO(S)", ", ".join(_list(agency.get("client_contacts"))) or "Não informado"],
        ["JOB / PROJETO", brief.get("project_name") or "Não informado", "EVENTO / INICIATIVA", brief.get("event_name") or "Não informado"],
        ["PASTA DO JOB", agency.get("job_folder") or "Não informado", "PERFIL", brief.get("briefing_profile") or "Não informado"],
    ]
    data = []
    for row in rows:
        data.append([
            Paragraph(f"<b>{_html(row[0])}</b>", styles["meta_label"]),
            Paragraph(_html(row[1]), styles["meta_value"]),
            Paragraph(f"<b>{_html(row[2])}</b>", styles["meta_label"]),
            Paragraph(_html(row[3]), styles["meta_value"]),
        ])
    table = Table(
        data,
        colWidths=[26 * mm, 60 * mm, 31 * mm, 62 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _section_title(number: int, title: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Spacer(1, 5),
        Paragraph(f"{number}. {_html(title.upper())}", styles["section"]),
        HRFlowable(width="100%", thickness=0.65, color=ACCENT, spaceBefore=2, spaceAfter=6),
    ]


def _field_block(title: str, value: Any, styles: dict[str, ParagraphStyle]) -> list[Any]:
    text = _clean(value)
    if not text:
        return []
    return [
        Paragraph(_html(title.upper()), styles["field_label"]),
        Paragraph(_html(text), styles["body"]),
        Spacer(1, 4),
    ]


def _simple_list_table(
    records: list[dict],
    columns: list[tuple[str, str]],
    styles: dict[str, ParagraphStyle],
    widths: list[float] | None = None,
) -> Table | None:
    if not records:
        return None
    headers = [Paragraph(f"<b>{_html(label)}</b>", styles["table_header"]) for _, label in columns]
    data: list[list[Any]] = [headers]
    for record in records:
        row: list[Any] = []
        for key, _ in columns:
            value = record.get(key)
            if isinstance(value, list):
                value = ", ".join(_list(value))
            elif key in {"budget_amount", "quantity"} and value not in (None, ""):
                value = _clean(value)
            elif key == "event_date":
                value = _date_text(value)
            row.append(Paragraph(_html(value or "-"), styles["table_cell"]))
        data.append(row)
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT_LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _diagnostic_item(item: dict, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    severity = item.get("severity") or "Importante"
    palette = {
        "Crítica": (CRITICAL, CRITICAL_BG),
        "Importante": (IMPORTANT, IMPORTANT_BG),
        "Enriquecimento": (ENRICHMENT, ENRICHMENT_BG),
    }
    accent, background = palette.get(severity, (ACCENT, ACCENT_LIGHT))
    content = [
        Paragraph(
            f"<b>{_html(item.get('title') or severity)}</b>",
            styles["diag_title"],
        ),
        Paragraph(
            f"<b>Tema:</b> {_html(item.get('category') or 'Outro')} &nbsp;&nbsp; "
            f"<b>Responsável:</b> {_html(item.get('responsible') or 'A definir')} &nbsp;&nbsp; "
            f"<b>Impacto:</b> {_html(item.get('impact') or 'Outro')}",
            styles["diag_meta"],
        ),
        Paragraph(_html(item.get("finding") or ""), styles["diag_body"]),
        Paragraph(
            f"<b>Pergunta:</b> {_html(item.get('question') or '')}",
            styles["diag_question"],
        ),
    ]
    table = Table([[content]], colWidths=[178 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.8, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return KeepTogether([table, Spacer(1, 5)])


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(MARGIN_X, PAGE_HEIGHT - 5.2 * mm, "VOE | DEBRIEFING INTERNO")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        MARGIN_X,
        8 * mm,
        "Documento gerado pela Plataforma de Pré-Produção VOE",
    )
    canvas.drawRightString(
        PAGE_WIDTH - MARGIN_X,
        8 * mm,
        f"Página {doc.page}",
    )
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_X, 11 * mm, PAGE_WIDTH - MARGIN_X, 11 * mm)
    canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=3,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            spaceAfter=9,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=ACCENT,
            spaceBefore=1,
            spaceAfter=0,
        ),
        "field_label": ParagraphStyle(
            "FieldLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10,
            textColor=INK,
            spaceAfter=1,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.7,
            leading=11.5,
            textColor=INK,
            spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            leftIndent=10,
            firstLineIndent=-6,
            bulletIndent=0,
            textColor=INK,
            spaceAfter=1.5,
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=6.5,
            leading=8,
            textColor=MUTED,
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.3,
            leading=9,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=6.6,
            leading=8,
            textColor=ACCENT,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6.7,
            leading=8.5,
            textColor=INK,
        ),
        "diag_title": ParagraphStyle(
            "DiagTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.6,
            leading=10.5,
            textColor=INK,
            spaceAfter=2,
        ),
        "diag_meta": ParagraphStyle(
            "DiagMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6.8,
            leading=8.5,
            textColor=MUTED,
            spaceAfter=3,
        ),
        "diag_body": ParagraphStyle(
            "DiagBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.6,
            leading=9.5,
            textColor=INK,
            spaceAfter=3,
        ),
        "diag_question": ParagraphStyle(
            "DiagQuestion",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.6,
            leading=9.5,
            textColor=INK,
        ),
        "status": ParagraphStyle(
            "Status",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=ACCENT,
            alignment=TA_CENTER,
        ),
    }


def build_internal_briefing_pdf(
    brief: dict,
    diagnostic: dict | None = None,
) -> bytes:
    """Generate a VOE-style internal debriefing PDF from structured data."""
    diagnostic = diagnostic or {}
    styles = _styles()
    buffer = BytesIO()

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"Debriefing interno - {_clean(brief.get('project_name') or 'Projeto')}",
        author="VOE - Plataforma de Pré-Produção",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(
        [PageTemplate(id="briefing", frames=[frame], onPage=_header_footer)]
    )

    story: list[Any] = [
        Paragraph("DEBRIEFING INTERNO", styles["title"]),
        Paragraph(
            "Briefing estruturado, diagnóstico e pauta de complementação",
            styles["subtitle"],
        ),
        _metadata_table(brief, styles),
        Spacer(1, 7),
    ]

    agency = brief.get("agency_context") or {}
    financial = brief.get("financial_context") or {}

    # 1. General information
    story += _section_title(1, "Infos gerais", styles)
    story.append(
        Paragraph(
            _selected_line(
                ["Sim", "Não"],
                [agency.get("competition_status")],
            )
            + (
                f" &nbsp;&nbsp; <b>Agências:</b> {_html(', '.join(_list(agency.get('competitors'))))}"
                if agency.get("competitors")
                else ""
            ),
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            f"<b>ORÇAMENTO:</b> {_html(financial.get('budget_status') or 'Não informado')} &nbsp;&nbsp; "
            f"<b>PRODUÇÃO:</b> {_html(', '.join(_list(agency.get('production_responsibility'))) or 'Não informado')}",
            styles["body"],
        )
    )

    # 2. Campaign type
    story += _section_title(2, "Tipo de campanha", styles)
    story.append(
        Paragraph(
            _selected_line(
                [
                    "Evento",
                    "Promoção",
                    "Ativação",
                    "Incentivo",
                    "Stand / feira",
                    "Campanha 360º",
                    "Digital",
                    "Endomarketing",
                ],
                agency.get("campaign_types") or [],
            ),
            styles["body"],
        )
    )

    # 3. Planning and creation
    story += _section_title(3, "Planejamento e criação", styles)
    story.append(
        Paragraph(
            _selected_line(
                ["Criação", "Arte-final", "Planejamento", "3D", "Produção", "Pré-produção"],
                agency.get("agency_services") or [],
            ),
            styles["body"],
        )
    )

    # 4. Briefing
    story += _section_title(4, "Briefing", styles)
    story += _field_block("Contextualizando", brief.get("source_summary"), styles)
    story += _field_block("Público-alvo", brief.get("audience_profile"), styles)
    if brief.get("audience_quantity"):
        story += _field_block("Quantidade / público", brief.get("audience_quantity"), styles)
    story += _field_block("Objetivo e desafio", brief.get("objective"), styles)
    story += _field_block("Mensagem principal", brief.get("key_message"), styles)
    story += _field_block("Resultado esperado", brief.get("expected_result"), styles)
    story += _field_block("Formato do evento / experiência", brief.get("event_format"), styles)

    products_table = _simple_list_table(
        brief.get("products_or_brands") or [],
        [("name", "Produto / marca"), ("brand", "Marca"), ("role", "Papel"), ("notes", "Observações")],
        styles,
        widths=[47 * mm, 34 * mm, 30 * mm, 67 * mm],
    )
    if products_table:
        story.append(Paragraph("PRODUTOS E MARCAS", styles["field_label"]))
        story += [products_table, Spacer(1, 5)]

    deliverables_table = _simple_list_table(
        brief.get("deliverables") or [],
        [("name", "Entregável"), ("quantity", "Qtd."), ("unit", "Unidade"), ("responsible", "Responsável"), ("notes", "Observações")],
        styles,
        widths=[58 * mm, 18 * mm, 24 * mm, 31 * mm, 47 * mm],
    )
    if deliverables_table:
        story.append(Paragraph("ENTREGÁVEIS", styles["field_label"]))
        story += [deliverables_table, Spacer(1, 5)]

    if brief.get("mandatory_requirements"):
        story.append(Paragraph("OBRIGATORIEDADES", styles["field_label"]))
        story += _bullet_paragraphs(brief.get("mandatory_requirements"), styles)
        story.append(Spacer(1, 4))

    if brief.get("operational_requirements"):
        story.append(Paragraph("REQUISITOS OPERACIONAIS", styles["field_label"]))
        story += _bullet_paragraphs(brief.get("operational_requirements"), styles)
        story.append(Spacer(1, 4))

    if brief.get("agenda_items"):
        story.append(Paragraph("AGENDA", styles["field_label"]))
        story += _bullet_paragraphs(brief.get("agenda_items"), styles)
        story.append(Spacer(1, 4))

    if brief.get("success_metrics"):
        metrics_table = _simple_list_table(
            brief.get("success_metrics") or [],
            [("name", "Métrica"), ("target", "Meta"), ("status", "Status"), ("notes", "Observações")],
            styles,
            widths=[55 * mm, 39 * mm, 29 * mm, 55 * mm],
        )
        if metrics_table:
            story.append(Paragraph("MÉTRICAS DE SUCESSO", styles["field_label"]))
            story += [metrics_table, Spacer(1, 5)]

    # 5. Logistics / executions
    story += _section_title(5, "Informações logísticas", styles)
    logistics = [
        f"Cidade principal: {brief.get('location_city') or 'Não informado'}",
        f"Estado principal: {brief.get('location_state') or 'Não informado'}",
        f"Data do evento: {_date_text(brief.get('event_date'))}",
        f"Data desejada de entrega: {_date_text(brief.get('desired_delivery_date'))}",
        f"Janela operacional: {brief.get('available_days') or 'Não informada'} dias",
    ]
    story += _bullet_paragraphs(logistics, styles)

    executions_table = _simple_list_table(
        brief.get("executions") or [],
        [
            ("name", "Execução / praça"),
            ("city", "Cidade"),
            ("institution", "Instituição"),
            ("status", "Status"),
            ("event_date", "Data"),
            ("product_name", "Produto"),
            ("audience_quantity", "Público"),
        ],
        styles,
        widths=[35 * mm, 25 * mm, 35 * mm, 24 * mm, 22 * mm, 22 * mm, 15 * mm],
    )
    if executions_table:
        story += [Spacer(1, 4), executions_table]

    # 6. Financial
    story += _section_title(6, "Financeiro e budget", styles)
    financial_rows = [
        ["Budget total", _money(brief.get("budget_total_brl"), financial.get("currency") or "BRL")],
        ["Budget unitário", _money(brief.get("budget_unit_brl"), financial.get("currency") or "BRL")],
        ["Status do budget", financial.get("budget_status") or "Não informado"],
        ["Escopo contemplado", financial.get("budget_scope") or "Não informado"],
        ["Saldo restante", _money(financial.get("remaining_budget"), financial.get("currency") or "BRL")],
        ["Condição de pagamento", financial.get("payment_terms") or "Não informado"],
        ["Pagamento direto", "Sim" if financial.get("direct_payment_required") else "Não / não informado"],
        ["Adiantamento", "Sim" if financial.get("advance_payment_required") else "Não / não informado"],
        ["Observações", financial.get("notes") or "-"],
    ]
    finance_data = [
        [
            Paragraph(f"<b>{_html(label)}</b>", styles["table_header"]),
            Paragraph(_html(value), styles["table_cell"]),
        ]
        for label, value in financial_rows
    ]
    finance_table = Table(finance_data, colWidths=[43 * mm, 135 * mm])
    finance_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), ACCENT_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(finance_table)

    # 7. References
    references_table = _simple_list_table(
        brief.get("related_references") or [],
        [("title", "Documento / referência"), ("reference_type", "Tipo"), ("status", "Status"), ("url_or_location", "Link / localização")],
        styles,
        widths=[54 * mm, 40 * mm, 28 * mm, 56 * mm],
    )
    if references_table:
        story += _section_title(7, "Referências e dependências", styles)
        story.append(references_table)

    # 8. Diagnostic
    if diagnostic:
        section_number = 8 if references_table else 7
        story += _section_title(section_number, "Diagnóstico do briefing", styles)
        status_data = [[
            Paragraph(f"<b>COMPLETUDE</b><br/>{int(diagnostic.get('completeness_score') or 0)}%", styles["status"]),
            Paragraph(f"<b>STATUS</b><br/>{_html(diagnostic.get('readiness_status') or 'Não informado')}", styles["status"]),
            Paragraph(f"<b>PENDÊNCIAS CRÍTICAS</b><br/>{int(diagnostic.get('critical_blockers') or 0)}", styles["status"]),
        ]]
        status_table = Table(status_data, colWidths=[44 * mm, 90 * mm, 44 * mm])
        status_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), ACCENT_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story += [status_table, Spacer(1, 5)]
        story += _field_block("Leitura geral", diagnostic.get("diagnostic_summary"), styles)
        story += _field_block("Próximo passo recomendado", diagnostic.get("recommended_next_step"), styles)

        issues = diagnostic.get("issues") or []
        for severity in ["Crítica", "Importante", "Enriquecimento"]:
            group = [item for item in issues if item.get("severity") == severity]
            if not group:
                continue
            story.append(Paragraph(f"{severity.upper()} ({len(group)})", styles["field_label"]))
            for item in group:
                story.append(_diagnostic_item(item, styles))

    doc.build(story)
    return buffer.getvalue()
