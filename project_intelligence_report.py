from __future__ import annotations

"""Dossiê Inteligente NAVE — projeção PDF do mesmo Unified Snapshot do workspace."""

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
    KeepTogether,
    PageTemplate,
    Image,
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


def _logo_flowable():
    """Logo institucional discreto apenas na abertura do dossiê."""
    path = Path(__file__).resolve().parent / "assets" / "nave_lockup.png"
    if not path.exists():
        return None
    # Lockup horizontal discreto, alinhado à margem editorial como nos demais
    # PDFs da NAVE. A marca assina; o projeto continua protagonista.
    width = 24 * mm
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
        "title": ParagraphStyle("NaveTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=28, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8),
        "eyebrow": ParagraphStyle("NaveEyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=CYAN, spaceAfter=5),
        "h1": ParagraphStyle("NaveH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=NAVY, spaceBefore=13, spaceAfter=7),
        "h2": ParagraphStyle("NaveH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY, spaceBefore=6, spaceAfter=4),
        "body": ParagraphStyle("NaveBody", parent=base["BodyText"], fontName="Helvetica", fontSize=9.3, leading=13.2, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("NaveSmall", parent=base["BodyText"], fontName="Helvetica", fontSize=7.7, leading=10.5, textColor=MUTED, spaceAfter=3),
        "tag": ParagraphStyle("NaveTag", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.2, leading=9, textColor=CYAN, spaceAfter=2),
        "callout": ParagraphStyle("NaveCallout", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK, leftIndent=4, rightIndent=4, spaceAfter=3),
    }


def _page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8.5 * mm, "NAVE by VOE - Dossiê Inteligente")
    canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"p. {doc.page}")
    canvas.restoreState()


def _section(story: list, title: str, styles: Mapping[str, Any]):
    story.append(Paragraph(title, styles["h1"]))


def _bullets(story: list, values: Sequence[Any], styles: Mapping[str, Any], *, empty: str | None = None):
    clean = [_safe(value) for value in values if _safe(value)]
    if not clean and empty:
        story.append(Paragraph(empty, styles["small"]))
        return
    for value in clean:
        story.append(Paragraph(f"• {value}", styles["body"]))


def _finding_block(row: Mapping[str, Any], styles: Mapping[str, Any]):
    kind_raw = _safe(row.get("kind") or row.get("finding_kind") or "inference").lower()
    kind = {
        "fact": "FATO", "inference": "INFERÊNCIA", "learning": "APRENDIZADO",
        "recommendation": "RECOMENDAÇÃO", "contradiction": "CONTRADIÇÃO",
        "risk": "RISCO", "unknown": "INCERTEZA",
    }.get(kind_raw, kind_raw.upper())
    title = _safe(row.get("title") or "Leitura NAVE")
    text = _safe(row.get("text") or row.get("statement"))
    evidence = row.get("evidence") or []
    parts = [Paragraph(kind, styles["tag"]), Paragraph(title, styles["h2"]), Paragraph(text, styles["callout"])]
    refs = []
    for ev in evidence[:4] if isinstance(evidence, list) else []:
        if not isinstance(ev, Mapping):
            continue
        source = _safe(ev.get("source_name") or "Fonte")
        locator = _safe(ev.get("locator_text"))
        refs.append(source + (f" - {locator}" if locator else ""))
    if refs:
        parts.append(Paragraph("Evidências: " + "; ".join(refs), styles["small"]))
    return KeepTogether(parts)


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
        title=f"Dossiê Inteligente - {_safe((snapshot.get('project') or {}).get('project_name'))}",
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
    result_summary = intelligence.get("result_summary") or {}

    story: list[Any] = []
    logo = _logo_flowable()
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 3.5 * mm))
    story.append(Paragraph("DOSSIÊ INTELIGENTE / INTELIGÊNCIA DE PROJETO", styles["eyebrow"]))
    story.append(Paragraph(_safe(project.get("project_name") or "Projeto"), styles["title"]))
    story.append(Paragraph(
        f"{_safe(project.get('client_brand') or 'Cliente não informado')} | {_safe(project.get('event_name') or 'Evento não informado')} | {_safe(truth.get('stage_label') or metrics.get('stage_label') or 'Situação não informada')}",
        styles["body"],
    ))
    story.append(Paragraph(
        f"Snapshot: {_safe(intelligence.get('source_signature'))[:16]} | Gerado em {_safe(intelligence.get('generated_at'))}",
        styles["small"],
    ))
    story.append(Spacer(1, 5 * mm))

    _section(story, "Resumo executivo", styles)
    executive = _safe(semantic.get("executive_summary"))
    if not executive:
        stage = _safe(truth.get("stage_label") or metrics.get("stage_label"))
        executive = f"Leitura consolidada do projeto. Situação atual: {stage}. O dossiê cruza briefing, proposta, custos, Intelligence Graph e evidências posteriores disponíveis."
    story.append(Paragraph(executive, styles["body"]))
    if semantic.get("strategic_reading"):
        story.append(Paragraph("Leitura estratégica", styles["h2"]))
        story.append(Paragraph(_safe(semantic.get("strategic_reading")), styles["body"]))
    framework = semantic.get("strategy_framework") if isinstance(semantic.get("strategy_framework"), Mapping) else {}
    if framework:
        story.append(Paragraph("Estrutura estratégica", styles["h2"]))
        for label, key in (
            ("Território", "territory"),
            ("Tensão", "tension"),
            ("Direção estratégica", "strategic_direction"),
            ("Conceito / POV", "concept"),
            ("Papel da experiência", "experience_role"),
            ("Aderência ao briefing", "briefing_adherence"),
        ):
            if framework.get(key):
                story.append(Paragraph(f"<b>{label}:</b> {_safe(framework.get(key))}", styles["body"]))
        pillars = [_safe(v) for v in framework.get("pillars") or [] if _safe(v)]
        if pillars:
            story.append(Paragraph("<b>Pilares:</b> " + " · ".join(pillars), styles["body"]))

    # Snapshot financeiro: o dossiê usa a mesma nuance da interface. Um total
    # bruto acima do budget não vira automaticamente "estouro" quando o briefing
    # prevê pagamento direto pelo cliente.
    _section(story, "Inteligência financeira", styles)
    financial_context = unified.get("financial_context") if isinstance(unified.get("financial_context"), Mapping) else {}
    direct_payment = bool(financial_context.get("direct_payment_signal"))
    delta_raw = metrics.get("budget_delta")
    delta_label = "Diferença"
    delta_value = "-"
    if delta_raw is not None:
        delta_number = float(delta_raw)
        delta_value = _money(abs(delta_number))
        if delta_number < 0 and direct_payment:
            delta_label = "Diferença bruta a reconciliar"
        elif delta_number < 0:
            delta_label = "Acima do teto"
        else:
            delta_label = "Folga no budget"
    fin_data = [
        ["Budget / referência", _money(metrics.get("budget_amount"))],
        ["Total da proposta", _money(metrics.get("cost_total"))],
        [delta_label, delta_value],
        ["Uso bruto do budget", f"{float(metrics.get('budget_usage_pct')):.1%}" if metrics.get("budget_usage_pct") is not None else "-"],
    ]
    table = Table(fin_data, colWidths=[65 * mm, 55 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    if direct_payment and delta_raw is not None and float(delta_raw) < 0:
        story.append(Paragraph(
            "A comparação acima é bruta. Há evidência de pagamento direto pelo cliente; a NAVE exige reconciliar responsabilidades financeiras antes de classificar o projeto como acima do envelope.",
            styles["small"],
        ))
    top_categories = (intelligence.get("advanced_insights") or {}).get("top_categories") or []
    if top_categories:
        story.append(Paragraph("Maiores categorias", styles["h2"]))
        for row in top_categories[:6]:
            share = row.get("share")
            suffix = f" ({float(share):.1%})" if share is not None else ""
            story.append(Paragraph(f"• {_safe(row.get('category'))}: {_money(row.get('value'))}{suffix}", styles["body"]))

    sections = [
        ("Diagnóstico", decision.get("diagnostic") or []),
        ("Resultados", [*(decision.get("results") or []), *([{"kind": "fact", "title": "Resumo do pós-evento", "text": result_summary.get("executive_summary"), "evidence": []}] if result_summary.get("executive_summary") else [])]),
        ("Conexões descobertas pela NAVE", decision.get("connections") or []),
        ("Aprendizados", decision.get("learnings") or []),
        ("Recomendações", decision.get("recommendations") or []),
    ]
    for title, rows in sections:
        _section(story, title, styles)
        if rows:
            for row in rows[:18]:
                if isinstance(row, Mapping):
                    story.append(_finding_block(row, styles))
                    story.append(Spacer(1, 2 * mm))
                else:
                    story.append(Paragraph(f"• {_safe(row)}", styles["body"]))
        else:
            story.append(Paragraph("Nenhuma conclusão consolidada nesta categoria com as fontes atuais.", styles["small"]))

    _section(story, "Repertório, benchmarks e pesquisas", styles)
    research_rows = intelligence.get("research_insights") or []
    if research_rows:
        for row in research_rows[:15]:
            if isinstance(row, Mapping):
                story.append(_finding_block(row, styles))
                story.append(Spacer(1, 2 * mm))
            else:
                story.append(Paragraph(f"• {_safe(row)}", styles["body"]))
    else:
        queries = snapshot.get("recommendation_queries") or []
        if queries:
            story.append(Paragraph("Pesquisas/recomendações históricas registradas no projeto:", styles["small"]))
            for row in queries[:10]:
                if isinstance(row, Mapping):
                    text = _safe(row.get("query_text") or row.get("brief_summary") or row.get("title") or row.get("id"))
                    if text:
                        story.append(Paragraph(f"• {text}", styles["body"]))
        else:
            story.append(Paragraph("Nenhuma pesquisa transversal ou benchmark histórico foi incorporado a este snapshot. O dossiê não inventa repertório ausente.", styles["small"]))

    _section(story, "Estratégia e conceito - evidências consolidadas", styles)
    strategy_units = (unified.get("domain_evidence") or {}).get("strategy") or []
    if strategy_units:
        for ev in strategy_units[:10]:
            source = _safe(ev.get("source_name") or "Fonte")
            locator = _safe(ev.get("locator_text"))
            story.append(Paragraph(f"{source}{' - ' + locator if locator else ''}", styles["tag"]))
            story.append(Paragraph(_safe(ev.get("text")), styles["body"]))
    else:
        story.append(Paragraph("Nenhuma evidência estratégica consolidada.", styles["small"]))

    _section(story, "Riscos, conflitos e incertezas", styles)
    # Erros de pipeline/legado pertencem à Saúde da leitura NAVE, não ao diagnóstico
    # de negócio. Aqui entram apenas contradições/risks já consolidados como decisão.
    business_risks = [
        row for row in (decision.get("diagnostic") or [])
        if str(row.get("kind") or "") in {"contradiction", "risk", "unknown"}
    ]
    for row in business_risks[:15]:
        story.append(_finding_block(row, styles))
        story.append(Spacer(1, 2 * mm))
    unknowns = semantic.get("unknowns") or []
    _bullets(story, unknowns[:15], styles, empty="Nenhuma incerteza adicional registrada pelo Project Analyst.")

    graph = snapshot.get("intelligence_graph") if isinstance(snapshot.get("intelligence_graph"), Mapping) else {}
    contexts = graph.get("contexts") or []
    assets = {str(row.get("id")): row for row in graph.get("source_assets") or [] if row.get("id")}
    source_rows = []
    for row in contexts:
        asset = assets.get(str(row.get("source_asset_id") or "")) or {}
        source_rows.append([
            Paragraph(_safe(asset.get("canonical_file_name") or "Fonte"), styles["small"]),
            Paragraph(_safe(row.get("context_role") or asset.get("source_role") or "-"), styles["small"]),
            Paragraph(_safe(asset.get("content_sha256"))[:12], styles["small"]),
        ])
    if source_rows:
        _section(story, "Apêndice de fontes e proveniência", styles)
        source_table = Table([["Fonte", "Papel", "SHA-256"]] + source_rows, colWidths=[95 * mm, 48 * mm, 25 * mm], repeatRows=1)
        source_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(source_table)

    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(
        "Legenda: FATO = informação suportada diretamente por fonte; INFERÊNCIA = conexão produzida pela NAVE; APRENDIZADO = conhecimento reutilizável; RECOMENDAÇÃO = decisão sugerida. Ausência de evidência não é tratada como prova de ausência.",
        styles["small"],
    ))

    doc.build(story)
    return buffer.getvalue()
