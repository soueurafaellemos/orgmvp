from __future__ import annotations

"""Dossie Inteligente NAVE - projecao editorial do mesmo Unified Snapshot."""

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#121B42")
CYAN = colors.HexColor("#18CDEA")
INK = colors.HexColor("#2B3040")
MUTED = colors.HexColor("#6E778D")
LINE = colors.HexColor("#DDE3EE")
SOFT = colors.HexColor("#F5F7FA")
WARN = colors.HexColor("#FFF6DD")
GOOD = colors.HexColor("#EAF8EF")
BLUE = colors.HexColor("#EAF3FF")

SOURCE_ROLE_LABELS = {
    "briefing_original": "Briefing original",
    "proposal_presentation": "Apresentação / proposta",
    "final_presentation": "Apresentação / proposta",
    "cost_sheet": "Planilha de custos",
    "detailed_costs": "Planilha de custos",
    "post_event_report": "Relatório pós-execução",
    "closure_report": "Relatório de encerramento",
    "feedback": "Feedback do cliente",
    "approval": "Aprovação / decisão",
}


def _logo_flowable():
    path = Path(__file__).resolve().parent / "assets" / "nave_lockup.png"
    if not path.exists():
        return None
    width = 23 * mm
    height = width * (1187 / 4064)
    image = Image(str(path), width=width, height=height)
    image.hAlign = "LEFT"
    return image


def _money(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "-"
    text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("NaveTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8),
        "eyebrow": ParagraphStyle("NaveEyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=CYAN, spaceAfter=5),
        "h1": ParagraphStyle("NaveH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=NAVY, spaceBefore=13, spaceAfter=7),
        "h2": ParagraphStyle("NaveH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY, spaceBefore=6, spaceAfter=4),
        "body": ParagraphStyle("NaveBody", parent=base["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13.5, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("NaveSmall", parent=base["BodyText"], fontName="Helvetica", fontSize=7.7, leading=10.5, textColor=MUTED, spaceAfter=3),
        "label": ParagraphStyle("NaveLabel", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=CYAN, spaceAfter=2),
        "callout": ParagraphStyle("NaveCallout", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK, leftIndent=2, rightIndent=2, spaceAfter=3),
    }


def _page(canvas, doc):
    canvas.saveState()
    width, _height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8.5 * mm, "NAVE by VOE - Dossie Inteligente")
    canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"p. {doc.page}")
    canvas.restoreState()


def _section(story: list, title: str, styles: Mapping[str, Any]):
    story.append(Paragraph(title, styles["h1"]))


def _bullets(story: list, values: Sequence[Any], styles: Mapping[str, Any], *, empty: str | None = None, limit: int = 10):
    clean = [_safe(value) for value in values if _safe(value)]
    if not clean and empty:
        story.append(Paragraph(empty, styles["small"]))
        return
    for value in clean[:limit]:
        story.append(Paragraph(f"• {value}", styles["body"]))


def _insight_block(row: Mapping[str, Any], styles: Mapping[str, Any], *, tone: str = "blue"):
    title = _safe(row.get("title") or "Leitura NAVE")
    text = _safe(row.get("text") or row.get("statement") or row.get("analysis"))
    # Blocos executivos devem ser sintéticos. Além de melhorar a leitura, limitar
    # texto impede que um insight de backend enorme crie uma linha indivisível no PDF.
    if len(text) > 1200:
        text = text[:1197].rstrip() + "..."
    parts = [Paragraph(title, styles["h2"]), Paragraph(text, styles["callout"])]
    bg = {"good": GOOD, "warn": WARN, "blue": BLUE}.get(tone, BLUE)
    # ReportLab lida melhor com uma lista de flowables na célula do que com
    # KeepTogether aninhado, que pode produzir altura infinita em paginação.
    table = Table([[parts]], colWidths=[169 * mm], splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _conclusion_rows(intelligence: Mapping[str, Any], limit: int = 7) -> list[dict[str, str]]:
    metrics = intelligence.get("metrics") or {}
    semantic = metrics.get("semantic_synthesis") if isinstance(metrics.get("semantic_synthesis"), Mapping) else {}
    unified = intelligence.get("unified") or {}
    decision = unified.get("decision_intelligence") or {}
    rows: list[dict[str, str]] = []

    executive = _safe(semantic.get("executive_summary"))
    if executive:
        rows.append({"title": "Leitura central", "text": executive})

    for group in (decision.get("connections") or [], decision.get("diagnostic") or []):
        for row in group:
            if not isinstance(row, Mapping):
                continue
            title = _safe(row.get("title"))
            text = _safe(row.get("text"))
            if title and text and title.casefold() not in {r["title"].casefold() for r in rows}:
                rows.append({"title": title, "text": text})
            if len(rows) >= limit:
                return rows[:limit]
    return rows[:limit]


def build_project_intelligence_pdf(
    *,
    snapshot: Mapping[str, Any],
    intelligence: Mapping[str, Any],
) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=f"Dossie Inteligente - {_safe((snapshot.get('project') or {}).get('project_name'))}",
        author="NAVE by VOE",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=_page))

    project = snapshot.get("project") or {}
    metrics = intelligence.get("metrics") or {}
    unified = intelligence.get("unified") or {}
    truth = unified.get("project_truth") or {}
    semantic = metrics.get("semantic_synthesis") if isinstance(metrics.get("semantic_synthesis"), Mapping) else {}
    decision = unified.get("decision_intelligence") or {}
    results = intelligence.get("result_summary") or {}
    advanced = intelligence.get("advanced_insights") or {}

    story: list[Any] = []
    logo = _logo_flowable()
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 3.5 * mm))
    story.append(Paragraph("DOSSIÊ INTELIGENTE", styles["eyebrow"]))
    story.append(Paragraph(_safe(project.get("project_name") or "Projeto"), styles["title"]))
    story.append(Paragraph(
        f"{_safe(project.get('client_brand') or 'Cliente não informado')} | {_safe(project.get('event_name') or 'Evento não informado')} | {_safe(truth.get('stage_label') or metrics.get('stage_label') or 'Situação não informada')}",
        styles["body"],
    ))
    story.append(Paragraph(
        f"Versão de análise: {_safe(intelligence.get('generated_at'))}",
        styles["small"],
    ))
    story.append(Spacer(1, 4 * mm))

    # 1. O projeto em um minuto - conclusão antes de dado bruto.
    _section(story, "O projeto em 1 minuto", styles)
    conclusions = _conclusion_rows(intelligence)
    if conclusions:
        for row in conclusions:
            story.append(_insight_block(row, styles, tone="blue"))
            story.append(Spacer(1, 2.2 * mm))
    else:
        story.append(Paragraph("Ainda não há conclusões executivas suficientes para este snapshot.", styles["small"]))

    # 2. Briefing x resposta.
    _section(story, "Briefing x resposta da proposta", styles)
    briefing_matches = unified.get("briefing_matches") or []
    if briefing_matches:
        brief_rows = [["Demanda", "Leitura NAVE"]]
        for row in briefing_matches[:10]:
            demand = _safe(row.get("requirement_title") or "Demanda")
            evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
            response = _safe(evidence.get("text"))
            if len(response) > 360:
                response = response[:357].rstrip() + "..."
            brief_rows.append([
                Paragraph(demand, styles["small"]),
                Paragraph(response or "Há evidência de resposta na proposta.", styles["small"]),
            ])
        t = Table(brief_rows, colWidths=[58 * mm, 111 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.7),
            ("GRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("As fontes atuais ainda não permitem consolidar respostas do briefing item a item.", styles["small"]))

    # 3. Estratégia x materialização.
    _section(story, "Estratégia x materialização", styles)
    framework = semantic.get("strategy_framework") if isinstance(semantic.get("strategy_framework"), Mapping) else {}
    if semantic.get("strategic_reading"):
        story.append(Paragraph(_safe(semantic.get("strategic_reading")), styles["body"]))
    if framework:
        for label, key in (
            ("Território", "territory"),
            ("Tensão", "tension"),
            ("Direção", "strategic_direction"),
            ("Conceito / POV", "concept"),
            ("Papel da experiência", "experience_role"),
        ):
            if framework.get(key):
                story.append(Paragraph(f"<b>{label}:</b> {_safe(framework.get(key))}", styles["body"]))
    execution_matches = unified.get("execution_matches") or []
    if execution_matches:
        names = [_safe(row.get("item_title")) for row in execution_matches if _safe(row.get("item_title"))]
        if names:
            story.append(Paragraph("<b>Soluções apresentadas com evidência posterior de execução:</b> " + ", ".join(names[:10]) + ".", styles["body"]))
    story.append(Paragraph("A existência de evidência de execução comprova materialização; não comprova, por si só, performance ou sucesso.", styles["small"]))

    # 4. Inteligência financeira: interpretação antes das listas.
    _section(story, "Inteligência financeira", styles)
    financial_context = unified.get("financial_context") if isinstance(unified.get("financial_context"), Mapping) else {}
    direct_payment = bool(financial_context.get("direct_payment_signal"))
    delta_raw = metrics.get("budget_delta")
    budget = metrics.get("budget_amount")
    total = metrics.get("cost_total")
    if budget is not None and total is not None:
        if delta_raw is not None and float(delta_raw) < 0 and direct_payment:
            story.append(_insight_block({
                "title": "A comparação bruta exige reconciliação",
                "text": f"A proposta totaliza {_money(total)} frente a um budget nominal de {_money(budget)}. A diferença bruta é {_money(abs(float(delta_raw)))}; como o briefing indica pagamento direto pelo cliente, esse valor não deve ser tratado como estouro definitivo sem separar responsabilidades.",
            }, styles, tone="warn"))
        elif delta_raw is not None and float(delta_raw) < 0:
            story.append(_insight_block({
                "title": "A proposta supera o teto identificado",
                "text": f"A proposta totaliza {_money(total)} frente a um budget de {_money(budget)}, diferença de {_money(abs(float(delta_raw)))}.",
            }, styles, tone="warn"))
    top_categories = advanced.get("top_categories") or []
    if top_categories:
        lead = top_categories[0]
        story.append(Paragraph(
            f"<b>Principal concentração:</b> {_safe(lead.get('category'))} representa {float(lead.get('share') or 0):.1%} da proposta ({_money(lead.get('value'))}).",
            styles["body"],
        ))
        cat_rows = [["Categoria", "Valor", "% da proposta"]]
        for row in top_categories[:6]:
            cat_rows.append([
                Paragraph(_safe(row.get("category")), styles["small"]),
                Paragraph(_money(row.get("value")), styles["small"]),
                Paragraph(f"{float(row.get('share') or 0):.1%}" if row.get("share") is not None else "-", styles["small"]),
            ])
        t = Table(cat_rows, colWidths=[86 * mm, 45 * mm, 38 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.35, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    # 5. Resultados comprovados.
    _section(story, "Resultados comprovados", styles)
    participants = results.get("participants_count")
    if participants not in (None, ""):
        scope = results.get("participants_scope")
        label = "Público do evento/festival" if scope in {"festival_event", "event_or_report_scope"} else "Público registrado"
        story.append(Paragraph(f"<b>{label}:</b> {int(float(participants)):,} pessoas.".replace(",", "."), styles["body"]))
        if scope in {"festival_event", "event_or_report_scope"}:
            story.append(Paragraph("Esse número não representa automaticamente visitantes ou participantes da ativação da marca.", styles["small"]))
    activation_results = results.get("activation_results") or []
    if activation_results:
        result_rows = [["Entrega / ativação", "O que está comprovado"]]
        for row in activation_results[:14]:
            result_rows.append([
                Paragraph(_safe(row.get("name") or row.get("item_name") or "Entrega"), styles["small"]),
                Paragraph(_safe(row.get("result") or "Execução registrada no relatório."), styles["small"]),
            ])
        t = Table(result_rows, colWidths=[58 * mm, 111 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.35, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
    for value in results.get("pending") or []:
        story.append(Paragraph(f"<b>Pendente no snapshot:</b> {_safe(value)}", styles["body"]))
    for value in results.get("issues") or []:
        story.append(Paragraph(f"<b>Ponto de atenção:</b> {_safe(value)}", styles["body"]))

    # 6. O que ainda não foi medido - importante para qualidade de aprendizado.
    unknowns = [_safe(v) for v in semantic.get("unknowns") or [] if _safe(v)]
    if unknowns:
        _section(story, "O que ainda não foi possível medir", styles)
        _bullets(story, unknowns, styles, limit=10)

    # 7. Aprendizados e recomendações, sem labels de backend.
    _section(story, "Aprendizados para a VOE", styles)
    learnings = decision.get("learnings") or []
    if learnings:
        for row in learnings[:10]:
            story.append(_insight_block(row, styles, tone="good"))
            story.append(Spacer(1, 2 * mm))
    else:
        _bullets(story, semantic.get("validated_learnings") or [], styles, empty="Nenhum aprendizado consolidado com segurança neste snapshot.")

    _section(story, "Recomendações para próximos projetos", styles)
    recommendations = decision.get("recommendations") or []
    if recommendations:
        for row in recommendations[:10]:
            story.append(_insight_block(row, styles, tone="warn"))
            story.append(Spacer(1, 2 * mm))
    else:
        _bullets(story, semantic.get("decision_recommendations") or [], styles, empty="Nenhuma recomendação consolidada com segurança neste snapshot.")

    # 8. Fontes: apenas nomes e papéis, sem hashes, links internos ou backend.
    graph = snapshot.get("intelligence_graph") if isinstance(snapshot.get("intelligence_graph"), Mapping) else {}
    contexts = graph.get("contexts") or []
    assets = {str(row.get("id")): row for row in graph.get("source_assets") or [] if row.get("id")}
    source_rows = []
    seen = set()
    for row in contexts:
        asset = assets.get(str(row.get("source_asset_id") or "")) or {}
        name = _safe(asset.get("canonical_file_name"))
        role_raw = _safe(row.get("context_role") or asset.get("source_role"))
        role = SOURCE_ROLE_LABELS.get(role_raw, role_raw.replace("_", " ").strip().title())
        key = (name, role)
        if name and key not in seen:
            seen.add(key)
            source_rows.append([Paragraph(name, styles["small"]), Paragraph(role or "Fonte do projeto", styles["small"])])
    if source_rows:
        _section(story, "Fontes consideradas", styles)
        t = Table([["Fonte", "Papel"]] + source_rows, colWidths=[115 * mm, 54 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Este dossiê prioriza conclusões úteis para decisão. A consulta às fontes e aos detalhes de sustentação permanece disponível no workspace do projeto quando necessário.",
        styles["small"],
    ))

    doc.build(story)
    return buffer.getvalue()
