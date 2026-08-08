from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import fitz
import pandas as pd

from document_io import InputDocument, split_pdf
from gemini_extractor import _structured_call, get_client
from memory_models import MemoryBatch, MemoryItem, MemoryOverview, MemorySlide
from memory_prompts import (
    MEMORY_OVERVIEW_PROMPT,
    MEMORY_SECTION_LABELS,
    MEMORY_SYSTEM_PROMPT,
)


DETAIL_PAGES_PER_PASS = 6
SYNTHESIS_CONTEXT_MAX_CHARS = 140_000

MEMORY_EDITOR_COLUMNS = [
    "_row_id",
    "Incluir",
    "Seção",
    "Tipo",
    "Título",
    "Resumo",
    "Status",
    "Página",
    "Arquivo",
    "Origem",
    "Confiança",
]


SECTION_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "strategy": [
        ("desafio", 8),
        ("objetivo", 6),
        ("insight", 10),
        ("conceito", 6),
        ("premissa", 7),
        ("narrativa", 6),
        ("manifesto", 7),
        ("publico", 4),
        ("pertencimento", 4),
        ("desejabilidade", 4),
        ("associacao de marca", 5),
        ("inspiracao", 3),
        ("benchmark", 3),
        ("contexto", 3),
        ("mensagem", 3),
        ("pilares", 4),
    ],
    "scenography": [
        ("cenografia", 10),
        ("camarote", 10),
        ("estande", 9),
        ("stand", 8),
        ("ambiente", 5),
        ("fachada", 6),
        ("palco", 7),
        ("lounge", 7),
        ("loja", 6),
        ("revestimento", 8),
        ("piso", 6),
        ("paredes", 6),
        ("painel de madeira", 7),
        ("totem", 5),
        ("implantacao", 8),
        ("planta", 7),
        ("area externa", 7),
        ("tunel", 6),
        ("credenciamento", 2),
        ("estrutura", 3),
    ],
    "activations": [
        ("ativacao", 10),
        ("experiencia", 4),
        ("jogo", 8),
        ("game", 8),
        ("ponto de foto", 12),
        ("photo op", 12),
        ("photo opportunity", 12),
        ("photo", 6),
        ("personalizacao", 9),
        ("realidade virtual", 8),
        ("vr", 7),
        ("simulador", 8),
        ("quiz", 7),
        ("roleta", 7),
        ("sampling", 6),
        ("participante", 3),
        ("desafio", 2),
        ("mecanica", 5),
    ],
    "gifts": [
        ("brinde", 11),
        ("caneca", 9),
        ("chapeu", 8),
        ("tiara", 8),
        ("botton", 8),
        ("uniforme", 10),
        ("pulseira", 10),
        ("credencial", 7),
        ("sacola", 7),
        ("kit", 5),
        ("residual", 7),
        ("colecionavel", 5),
        ("chaveiro", 8),
        ("pelucia", 8),
        ("capacete", 7),
        ("camiseta", 7),
        ("bone", 7),
        ("mochila", 7),
        ("copo", 6),
        ("bag", 6),
    ],
    "journey_operation": [
        ("jornada", 11),
        ("cadastro", 8),
        ("validacao", 7),
        ("fluxo", 8),
        ("retirada", 6),
        ("rodada", 5),
        ("tentativas", 5),
        ("entrada", 3),
        ("saida", 3),
        ("promotoria", 5),
        ("qr code", 6),
        ("pontuacao", 5),
        ("participacao", 3),
        ("fila", 5),
        ("circuito", 7),
        ("atendimento", 5),
        ("operacao", 6),
        ("agenda", 2),
    ],
    "communication": [
        ("kv", 12),
        ("key visual", 12),
        ("identidade visual", 10),
        ("comunicacao visual", 9),
        ("comunicacao", 5),
        ("protagonismo da marca", 7),
        ("desdobravel", 6),
        ("envelopamento", 9),
        ("aplicacao", 4),
        ("campanha", 5),
        ("sinalizacao", 6),
        ("tipografia", 5),
        ("paleta", 5),
        ("grafismo", 5),
    ],
    "content_agenda": [
        ("agenda", 9),
        ("programacao", 9),
        ("palestra", 7),
        ("workshop", 7),
        ("show", 5),
        ("horario", 5),
        ("masterclass", 8),
        ("conteudo", 3),
    ],
    "partners_sponsorship": [
        ("cota", 9),
        ("patrocinador", 8),
        ("parceiro", 6),
        ("naming rights", 9),
        ("oportunidade de marca", 8),
        ("apoio", 3),
    ],
    "pr_esg_legacy": [
        ("acao esg", 12),
        ("esg", 12),
        ("legado", 10),
        ("intervencao artistica", 11),
        ("artista local", 8),
        ("potencial pr", 12),
        ("imprensa", 5),
        ("midia espontanea", 8),
        ("impacto social", 8),
        ("diversidade", 4),
        ("comunidade", 4),
        ("sustentabilidade", 7),
        ("instituto", 5),
        ("associacao", 3),
    ],
}


CANDIDATE_PATTERNS: list[tuple[str, str, str]] = [
    (r"\bphoto[\s-]?op\b|\bponto de foto\b|\bphoto opportunity\b", "Ponto de foto", "activations"),
    (r"\bquick massage\b|\bilha de massagem\b|\bmassagem\b", "Quick Massage", "activations"),
    (r"\bbar de caf[eé]s?\b|\bcoffee bar\b", "Bar de cafés", "activations"),
    (r"\bbacio di latte\b", "Bacio di Latte", "activations"),
    (r"\bjogo da mem[oó]ria\b", "Jogo da memória", "activations"),
    (r"\brealidade virtual\b|\bexperi[eê]ncia vr\b", "Experiência em realidade virtual", "activations"),
    (r"\bpersonaliza[cç][aã]o\b", "Personalização", "activations"),
    (r"\bsampling\b|\bdegusta[cç][aã]o\b", "Sampling", "activations"),
    (r"\bquiz\b", "Quiz", "activations"),
    (r"\broleta\b", "Roleta", "activations"),
    (r"\bsimulador\b", "Simulador", "activations"),
    (r"\bkit de boas[- ]vindas\b|\bkit boas[- ]vindas\b|\bwelcome kit\b", "Kit de boas-vindas", "gifts"),
    (r"\bcamiseta(?:s)?\b|\bcamisa(?:s)?\b", "Camisetas", "gifts"),
    (r"\bmala para esportes\b|\bmala esportiva\b|\bmochila(?:s)?\b", "Mala / mochila", "gifts"),
    (r"\bcaneca(?:s)?\b", "Caneca", "gifts"),
    (r"\btiara(?:s)?\b", "Tiara", "gifts"),
    (r"\bchap[eé]u(?:s)?\b", "Chapéu", "gifts"),
    (r"\bbottons?\b|\bbotons?\b|\bpins?\b", "Bottons personalizados", "gifts"),
    (r"\bchaveiro(?:s)?\b", "Chaveiro", "gifts"),
    (r"\bpel[uú]cia(?:s)?\b", "Pelúcia", "gifts"),
    (r"\buniforme(?:s)?\b", "Uniformes", "gifts"),
    (r"\bpulseira(?:s)?\b", "Pulseiras", "gifts"),
    (r"\bcredencial(?:is)?\b", "Credenciais", "gifts"),
    (r"\bsacola(?:s)?\b|\bbag(?:s)?\b", "Sacola / bag", "gifts"),
    (r"\bcapacete(?:s)?\b|\bhelmet(?:s)?\b", "Capacete / helmet", "gifts"),
    (r"\bjantar tem[aá]tico\b", "Jantar temático", "content_agenda"),
    (r"\bbanda(?: studio 4)?\b|\bm[uú]sica ao vivo\b|\bshow musical\b", "Atração musical", "content_agenda"),
    (r"\bpalestrante(?:s)?\b|\bmestre de cerim[oô]nias\b", "Conteúdo artístico / palestrantes", "content_agenda"),
    (r"\bcamarote\b", "Camarote", "scenography"),
    (r"\bestande\b|\bstand\b", "Estande", "scenography"),
    (r"\bpalco\b", "Palco", "scenography"),
    (r"\blounge\b", "Lounge", "scenography"),
    (r"\bloja\b", "Loja", "scenography"),
    (r"\bt[uú]nel\b", "Túnel", "scenography"),
    (r"\btotem(?: led)?\b", "Totem", "scenography"),
    (r"\bfachada\b", "Fachada", "scenography"),
    (r"\bkv\b|\bkey visual\b", "Key visual", "communication"),
    (r"\bidentidade visual\b", "Identidade visual", "communication"),
    (r"\benvelopamento\b", "Envelopamento", "communication"),
    (r"\bsinaliza[cç][aã]o\b", "Sinalização", "communication"),
    (r"\bcredenciamento\b", "Credenciamento", "journey_operation"),
    (r"\bcircuito\b", "Circuito da experiência", "journey_operation"),
    (r"\bfluxo\b", "Fluxo da experiência", "journey_operation"),
    (r"\bpontua[cç][aã]o\b|\branking\b", "Sistema de pontuação", "journey_operation"),
    (r"\bpotencial (?:de )?pr\b|\bm[ií]dia espont[aâ]nea\b", "Potencial de PR", "pr_esg_legacy"),
    (r"\besg\b|\bsustentabilidade\b", "Ação ESG", "pr_esg_legacy"),
    (r"\blegado\b", "Legado", "pr_esg_legacy"),
]



DIVIDER_TERMS = {
    "voe apresenta": "Key visual",
    "vamos comecar a jornada": "Jornada do projeto",
    "camarote": "Camarote",
    "ativacoes experiencias": "Ativações & Experiências",
    "ativacao geral": "Ativação geral",
    "acao esg": "Ação ESG",
    "conteudo agenda": "Conteúdo & Agenda",
    "parceiros cotas": "Parceiros & Cotas",
}


GENERIC_TITLE_RE = re.compile(
    r"^(foto|imagem|visual|conteudo|item|proposta)\s*[\-_]?\s*\d*$",
    flags=re.IGNORECASE,
)


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_lines(text: str) -> list[str]:
    ignored = {
        "voe ideias",
        "imagem ilustrativa",
        "imagem meramente ilustrativa",
        "opcao 1",
        "opcao 2",
    }
    lines: list[str] = []

    for raw_line in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        normalized = _normalize_text(line)
        if normalized in ignored:
            continue
        lines.append(line)

    return lines


def _shorten(text: str | None, limit: int) -> str | None:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return None
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def _section_scores(normalized_text: str) -> dict[str, int]:
    scores = {section: 0 for section in SECTION_KEYWORDS}
    for section, keywords in SECTION_KEYWORDS.items():
        for phrase, weight in keywords:
            if phrase in normalized_text:
                scores[section] += weight
    return scores


def _best_section(
    normalized_text: str,
    *,
    context_section: str | None,
) -> tuple[str, int]:
    scores = _section_scores(normalized_text)

    if any(
        signal in normalized_text
        for signal in (
            "inspiracao",
            "referencia estetica",
            "benchmark",
            "insight",
            "o que se busca",
        )
    ) and not any(
        signal in normalized_text
        for signal in (
            "ativacao proposta",
            "mecanica",
            "o participante",
        )
    ):
        scores["strategy"] += 10

    if context_section and context_section in scores:
        scores[context_section] += 2
    section, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return context_section or "strategy", 0
    return section, score


def _candidate_items(text: str) -> list[dict]:
    candidates: list[dict] = []
    normalized_titles: set[str] = set()

    for pattern, title, section in CANDIDATE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            signature = _normalize_text(title)
            if signature in normalized_titles:
                continue
            normalized_titles.add(signature)
            candidates.append(
                {
                    "title": title,
                    "section_key": section,
                    "pattern": pattern,
                }
            )

    return candidates


def _divider_label(normalized_text: str) -> str | None:
    compact = normalized_text.strip()
    if "danke" in compact and len(compact) < 80:
        return "Encerramento"
    for phrase, label in DIVIDER_TERMS.items():
        if compact == phrase or (
            len(compact) < 90 and phrase in compact
        ):
            return label
    return None


def _looks_like_cover(page_number: int, normalized_text: str) -> bool:
    if page_number != 1:
        return False
    return bool(
        "apresentacao" in normalized_text
        or "projeto" in normalized_text
        or len(normalized_text) < 140
    )


def _is_generic_title(title: str | None) -> bool:
    clean = str(title or "").strip()
    if not clean:
        return True
    return bool(GENERIC_TITLE_RE.match(clean))


def _derive_title(
    *,
    lines: list[str],
    candidates: list[dict],
    anchor_label: str | None,
    section_key: str,
    page_number: int,
) -> str:
    if candidates:
        return str(candidates[0]["title"])

    for line in lines:
        normalized = _normalize_text(line)
        if 3 <= len(line) <= 110 and normalized not in {
            "imagem ilustrativa",
            "imagem meramente ilustrativa",
            "voe apresenta",
        } and normalized not in DIVIDER_TERMS:
            return line

    if anchor_label:
        return f"{anchor_label} — vista do slide {page_number}"

    section_label = MEMORY_SECTION_LABELS.get(
        section_key,
        "Conteúdo do projeto",
    )
    return f"{section_label} — slide {page_number}"


def _fallback_status(normalized_text: str, section_key: str) -> str:
    if "opcao" in normalized_text or "alternativa" in normalized_text:
        return "Opção"
    if (
        "inspiracao" in normalized_text
        or "referencia" in normalized_text
        or "moodboard" in normalized_text
    ):
        return "Referência"
    if section_key in {
        "scenography",
        "activations",
        "gifts",
        "communication",
        "pr_esg_legacy",
        "journey_operation",
    }:
        return "Proposto"
    return "Não identificado"


def _fallback_item_type(section_key: str, title: str) -> str:
    normalized = _normalize_text(title)
    if "uniforme" in normalized:
        return "Uniforme"
    if "pulseira" in normalized:
        return "Pulseira"
    if any(term in normalized for term in ("caneca", "chapeu", "tiara", "botton", "chaveiro", "pelucia", "kit", "bag", "sacola")):
        return "Brinde"
    if "ponto de foto" in normalized or "photo" in normalized:
        return "Photo-op"
    if "jogo" in normalized or "game" in normalized:
        return "Game"
    if "kv" in normalized or "identidade" in normalized:
        return "Identidade visual"
    return {
        "strategy": "Conteúdo estratégico",
        "scenography": "Ambiente",
        "activations": "Ativação",
        "gifts": "Brinde ou material",
        "journey_operation": "Etapa da jornada",
        "communication": "Desdobramento de comunicação",
        "content_agenda": "Conteúdo",
        "partners_sponsorship": "Oportunidade de parceria",
        "pr_esg_legacy": "Iniciativa de PR, ESG ou legado",
    }.get(section_key, "Conteúdo do projeto")


def _candidate_evidence(text: str | None, candidate: dict | None) -> str | None:
    candidate = candidate or {}
    pattern = str(candidate.get("pattern") or "").strip()
    lines = _clean_lines(str(text or ""))
    if not lines:
        return None
    if not pattern:
        return _shorten(" ".join(lines), 320)

    for index, line in enumerate(lines):
        if not re.search(pattern, line, flags=re.IGNORECASE):
            continue
        selected = [line]
        for next_line in lines[index + 1:index + 3]:
            if any(
                re.search(other_pattern, next_line, flags=re.IGNORECASE)
                for other_pattern, _, _ in CANDIDATE_PATTERNS
                if other_pattern != pattern
            ):
                break
            if len(" ".join(selected + [next_line])) > 260:
                break
            selected.append(next_line)
        return _shorten(" ".join(selected), 320)
    return _shorten(" ".join(lines), 320)


def _inventory_item(row: dict, candidate: dict | None = None) -> MemoryItem:
    candidate = candidate or {}
    section_key = str(
        candidate.get("section_key")
        or row["suggested_section"]
    )
    title = str(
        candidate.get("title")
        or row["suggested_title"]
    )
    scoped_evidence = _candidate_evidence(row.get("text"), candidate)
    summary = scoped_evidence or row.get("summary") or (
        "Registro visual da proposta apresentada "
        f"no slide {row['page_number']}."
    )

    return MemoryItem(
        section_key=section_key,
        item_type=_fallback_item_type(section_key, title),
        title=title,
        summary=_shorten(summary, 420),
        description=_shorten(scoped_evidence, 900)
        or "Slide visual preservado para consulta do projeto.",
        status=_fallback_status(
            row.get("normalized_text", ""),
            section_key,
        ),
        tags=list(
            dict.fromkeys(
                [
                    MEMORY_SECTION_LABELS.get(section_key, section_key),
                    *(
                        [str(row["anchor_label"])]
                        if row.get("anchor_label")
                        else []
                    ),
                ]
            )
        ),
        visual_crop=None,
        confidence=0.58,
        evidence=_shorten(scoped_evidence, 240),
        extraction_origin="automatic_repair",
    )


def _extract_page_inventory(doc: InputDocument) -> list[dict]:
    pdf = fitz.open(stream=doc.data, filetype="pdf")
    inventory: list[dict] = []
    context_section: str | None = None
    anchor_label: str | None = None

    try:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            normalized = _normalize_text(text)
            lines = _clean_lines(text)
            image_count = len(page.get_images(full=True))
            candidates = _candidate_items(text)
            divider = _divider_label(normalized)
            cover = _looks_like_cover(page_number, normalized)
            section_key, section_score = _best_section(
                normalized,
                context_section=context_section,
            )

            if candidates:
                candidate_sections = Counter(
                    str(item["section_key"])
                    for item in candidates
                )
                candidate_section, candidate_count = candidate_sections.most_common(1)[0]
                if candidate_count >= 1:
                    section_key = candidate_section
                    section_score = max(section_score, 8)

            if divider:
                anchor_label = divider
                if divider == "Camarote":
                    context_section = "scenography"
                elif divider in {"Ativações & Experiências", "Ativação geral"}:
                    context_section = "activations"
                elif divider == "Ação ESG":
                    context_section = "pr_esg_legacy"
                elif divider == "Jornada do projeto":
                    context_section = "journey_operation"
                elif divider == "Conteúdo & Agenda":
                    context_section = "content_agenda"
                elif divider == "Parceiros & Cotas":
                    context_section = "partners_sponsorship"
                elif divider == "Key visual":
                    context_section = "communication"
                if context_section:
                    section_key = context_section

            if candidates:
                anchor_label = str(candidates[0]["title"])

            is_closing = divider == "Encerramento"
            is_divider = bool(divider) and divider not in {"Key visual"}
            meaningful = (
                not cover
                and not is_closing
                and not is_divider
                and (
                    len(normalized) >= 24
                    or image_count >= 1
                )
            )

            if divider == "Key visual":
                meaningful = True

            title = _derive_title(
                lines=lines,
                candidates=candidates,
                anchor_label=anchor_label,
                section_key=section_key,
                page_number=page_number,
            )

            inventory.append(
                {
                    "source_file": doc.name,
                    "page_number": page_number,
                    "text": text,
                    "normalized_text": normalized,
                    "text_length": len(normalized),
                    "image_count": image_count,
                    "is_meaningful": meaningful,
                    "exclusion_reason": (
                        "Capa"
                        if cover
                        else (
                            "Encerramento"
                            if is_closing
                            else (
                                "Divisória de seção"
                                if is_divider
                                else None
                            )
                        )
                    ),
                    "suggested_section": section_key,
                    "section_score": section_score,
                    "suggested_title": title,
                    "summary": _shorten(" ".join(lines), 520),
                    "anchor_label": anchor_label,
                    "content_kind": "visual" if image_count > 0 else "textual",
                    "candidate_items": candidates,
                    "expected_min_items": len(candidates) if meaningful else 0,
                }
            )
    finally:
        pdf.close()

    return inventory


def _inventory_for_range(
    inventory: list[dict],
    first_page: int,
    last_page: int,
) -> list[dict]:
    return [
        row
        for row in inventory
        if first_page <= int(row["page_number"]) <= last_page
    ]


def _prompt_inventory(rows: list[dict]) -> str:
    payload = []
    for row in rows:
        payload.append(
            {
                "page": row["page_number"],
                "text": _shorten(row.get("text"), 1800),
                "image_count": row["image_count"],
                "is_meaningful_hint": row["is_meaningful"],
                "suggested_section_hint": row["suggested_section"],
                "suggested_title_hint": row["suggested_title"],
                "candidate_items_hint": row["candidate_items"],
                "expected_min_items_hint": row["expected_min_items"],
                "anchor_hint": row.get("anchor_label"),
            }
        )
    return json.dumps(payload, ensure_ascii=False, default=str)


def _normalize_relative_pages(
    batch: MemoryBatch,
    *,
    first_page: int,
    last_page: int,
) -> MemoryBatch:
    page_numbers = [
        int(slide.source_page)
        for slide in (batch.slides or [])
        if int(slide.source_page) > 0
    ]
    local_count = last_page - first_page + 1
    relative = (
        first_page > 1
        and bool(page_numbers)
        and min(page_numbers) >= 1
        and max(page_numbers) <= local_count
    )
    if relative:
        for slide in batch.slides:
            slide.source_page = int(slide.source_page) + first_page - 1
    return batch


def _sanitize_ai_item(item: MemoryItem, row: dict) -> MemoryItem:
    item.extraction_origin = "ai"
    if _is_generic_title(item.title):
        item.title = str(row["suggested_title"])
    if not item.summary:
        item.summary = row.get("summary")
    if not item.description:
        item.description = _shorten(row.get("text"), 900)
    if not item.evidence:
        item.evidence = _shorten(row.get("text"), 240)
    if not item.tags:
        item.tags = [
            MEMORY_SECTION_LABELS.get(
                item.section_key,
                item.section_key,
            )
        ]
    return item


def _item_matches_candidate(item: MemoryItem, candidate: dict) -> bool:
    item_text = _normalize_text(
        " ".join(
            [
                item.title,
                item.item_type,
                item.summary or "",
                item.description or "",
            ]
        )
    )
    candidate_text = _normalize_text(str(candidate.get("title") or ""))
    if not candidate_text:
        return False
    candidate_tokens = [token for token in candidate_text.split() if len(token) > 2]
    return bool(candidate_tokens) and all(token in item_text for token in candidate_tokens[:2])


def _repair_batch_coverage(
    batch: MemoryBatch | None,
    *,
    source_file: str,
    inventory_rows: list[dict],
) -> MemoryBatch:
    if batch is None:
        batch = MemoryBatch(source_file=source_file)

    batch.source_file = source_file
    ai_slides: dict[int, MemorySlide] = {}
    for slide in batch.slides or []:
        page_number = int(slide.source_page)
        if page_number > 0:
            ai_slides[page_number] = slide

    repaired_slides: list[MemorySlide] = []
    repaired_pages: list[int] = []
    ai_item_count = 0
    repair_item_count = 0

    for row in inventory_rows:
        page_number = int(row["page_number"])
        slide = ai_slides.get(page_number)

        if slide is None:
            slide = MemorySlide(
                source_file=source_file,
                source_page=page_number,
                slide_title=row["suggested_title"],
                slide_summary=row.get("summary"),
                primary_section=row["suggested_section"],
                is_meaningful=row["is_meaningful"],
                exclusion_reason=row.get("exclusion_reason"),
                content_kind=row.get("content_kind"),
                items=[],
            )
            repaired_pages.append(page_number)

        slide.source_file = source_file
        slide.source_page = page_number

        if _is_generic_title(slide.slide_title):
            slide.slide_title = str(row["suggested_title"])
        if not slide.slide_summary:
            slide.slide_summary = row.get("summary")
        if not slide.primary_section:
            slide.primary_section = row["suggested_section"]
        slide.content_kind = slide.content_kind or row.get("content_kind")

        if not row["is_meaningful"]:
            slide.is_meaningful = False
            slide.exclusion_reason = (
                slide.exclusion_reason
                or row.get("exclusion_reason")
                or "Sem conteúdo relevante"
            )
            slide.items = []
            repaired_slides.append(slide)
            continue

        slide.is_meaningful = True
        slide.exclusion_reason = None
        slide.items = [
            _sanitize_ai_item(item, row)
            for item in (slide.items or [])
        ]
        ai_item_count += len(slide.items)

        missing_candidates = [
            candidate
            for candidate in row.get("candidate_items") or []
            if not any(
                _item_matches_candidate(item, candidate)
                for item in slide.items
            )
        ]

        for candidate in missing_candidates:
            slide.items.append(_inventory_item(row, candidate))
            repair_item_count += 1
            repaired_pages.append(page_number)

        # Uma página relevante pode ser apenas contexto. Não criamos mais
        # fichas genéricas para "preencher" cobertura. O reparo automático
        # só materializa entidades explicitamente reconhecidas por padrão.
        if not slide.items and row.get("candidate_items"):
            for candidate in row.get("candidate_items") or []:
                slide.items.append(_inventory_item(row, candidate))
                repair_item_count += 1
            repaired_pages.append(page_number)

        repaired_slides.append(slide)

    batch.slides = repaired_slides
    batch.page_inventory = [
        {
            key: value
            for key, value in row.items()
            if key != "normalized_text"
        }
        for row in inventory_rows
    ]
    batch.coverage = {
        "pages_in_pass": len(inventory_rows),
        "meaningful_pages": sum(1 for row in inventory_rows if row["is_meaningful"]),
        "pages_with_items": sum(1 for slide in repaired_slides if slide.items),
        "ai_items": ai_item_count,
        "automatic_repair_items": repair_item_count,
        "automatic_repair_pages": sorted(set(repaired_pages)),
    }

    if repaired_pages:
        batch.warnings = list(
            dict.fromkeys(
                [
                    *(batch.warnings or []),
                    "A cobertura automática completou slides ou itens que não vieram estruturados na resposta do modelo.",
                ]
            )
        )

    return batch


def _clip(value: Any, limit: int) -> str | None:
    return _shorten(str(value or ""), limit)


def _compact_batch(batch: MemoryBatch) -> dict:
    data = batch.model_dump()
    compact_slides = []
    for slide in data.get("slides", []):
        compact_slides.append(
            {
                "page": slide.get("source_page"),
                "title": _clip(slide.get("slide_title"), 180),
                "summary": _clip(slide.get("slide_summary"), 500),
                "primary_section": slide.get("primary_section"),
                "items": [
                    {
                        "section": item.get("section_key"),
                        "type": _clip(item.get("item_type"), 100),
                        "title": _clip(item.get("title"), 180),
                        "summary": _clip(item.get("summary"), 450),
                        "status": item.get("status"),
                        "evidence": _clip(item.get("evidence"), 240),
                    }
                    for item in slide.get("items", [])
                ],
            }
        )
    return {
        "source_file": data.get("source_file"),
        "document_title": _clip(data.get("document_title"), 250),
        "client_brand": _clip(data.get("client_brand"), 180),
        "project_name": _clip(data.get("project_name"), 250),
        "event_name": _clip(data.get("event_name"), 220),
        "version_label": _clip(data.get("version_label"), 100),
        "strategic_summary": _clip(data.get("strategic_summary"), 900),
        "creative_concept": _clip(data.get("creative_concept"), 500),
        "slides": compact_slides,
        "warnings": [
            _clip(warning, 260)
            for warning in (data.get("warnings") or [])
            if _clip(warning, 260)
        ],
    }


def _synthesis_context(batches: list[MemoryBatch]) -> str:
    context = json.dumps(
        [_compact_batch(batch) for batch in batches],
        ensure_ascii=False,
        default=str,
    )
    if len(context) > SYNTHESIS_CONTEXT_MAX_CHARS:
        context = context[:SYNTHESIS_CONTEXT_MAX_CHARS] + "\n[conteúdo abreviado automaticamente]"
    return context


def _first_value(batches: list[MemoryBatch], field: str) -> str | None:
    for batch in batches:
        value = getattr(batch, field, None)
        if value:
            return str(value)
    return None


def _fallback_overview(
    *,
    doc: InputDocument,
    detail_batches: list[MemoryBatch],
    warnings: list[str],
) -> MemoryOverview:
    file_title = Path(doc.name).stem
    return MemoryOverview(
        source_file=doc.name,
        document_title=_first_value(detail_batches, "document_title") or file_title,
        client_brand=_first_value(detail_batches, "client_brand"),
        project_name=(
            _first_value(detail_batches, "project_name")
            or _first_value(detail_batches, "document_title")
            or file_title
        ),
        event_name=_first_value(detail_batches, "event_name"),
        version_label=_first_value(detail_batches, "version_label"),
        strategic_summary=_first_value(detail_batches, "strategic_summary"),
        creative_concept=_first_value(detail_batches, "creative_concept"),
        warnings=warnings,
    )


def _synthesize_overview(
    client,
    *,
    doc: InputDocument,
    page_count: int,
    model: str,
    detail_batches: list[MemoryBatch],
    warnings: list[str],
) -> MemoryOverview:
    prompt = (
        MEMORY_OVERVIEW_PROMPT
        + "\n\nVocê recebeu abaixo o resultado estruturado de TODOS os slides da apresentação. "
        "Consolide-os como um único projeto."
        + "\n\nARQUIVO ORIGINAL: "
        + doc.name
        + "\nTOTAL DE SLIDES: "
        + str(page_count)
        + "\n\nCONTEÚDO ESTRUTURADO DE TODOS OS SLIDES:\n"
        + _synthesis_context(detail_batches)
    )
    try:
        overview = _structured_call(
            client,
            model=model,
            prompt=prompt,
            docs=[],
            schema=MemoryOverview,
            context="consolidação global da Memória de " + doc.name,
        )
        overview.source_file = doc.name
        overview.warnings = list(dict.fromkeys([*(overview.warnings or []), *warnings]))
        return overview
    except Exception as exc:
        return _fallback_overview(
            doc=doc,
            detail_batches=detail_batches,
            warnings=list(
                dict.fromkeys(
                    [
                        *warnings,
                        "A consolidação global utilizou os metadados disponíveis nas leituras dos slides. "
                        f"Detalhe técnico: {exc}",
                    ]
                )
            ),
        )


def _overview_as_batch(overview: MemoryOverview) -> MemoryBatch:
    return MemoryBatch(
        source_file=overview.source_file,
        document_title=overview.document_title,
        client_brand=overview.client_brand,
        project_name=overview.project_name,
        event_name=overview.event_name,
        version_label=overview.version_label,
        strategic_summary=overview.strategic_summary,
        creative_concept=overview.creative_concept,
        slides=[],
        warnings=overview.warnings,
    )


def extract_memory(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    progress_callback=None,
) -> list[MemoryBatch]:
    client = get_client(api_key)
    all_batches: list[MemoryBatch] = []
    plans = []

    for doc in docs:
        if doc.mime_type != "application/pdf":
            raise ValueError("A Memória visual precisa de uma apresentação em PDF.")
        inventory = _extract_page_inventory(doc)
        parts = split_pdf(
            doc,
            pages_per_batch=DETAIL_PAGES_PER_PASS,
            start_page=1,
            end_page=None,
        )
        plans.append((doc, inventory, parts))

    total_steps = sum(len(parts) + 1 for _, _, parts in plans)
    completed_steps = 0

    for doc, inventory, parts in plans:
        detail_batches: list[MemoryBatch] = []
        document_warnings: list[str] = []
        page_count = len(inventory)

        for part, first, last in parts:
            rows = _inventory_for_range(inventory, first, last)
            if progress_callback:
                progress_callback(
                    completed_steps,
                    total_steps,
                    f"Decupando o projeto — slides {first} a {last} de {page_count}",
                )

            prompt = (
                MEMORY_SYSTEM_PROMPT
                + "\n\nARQUIVO ORIGINAL: "
                + doc.name
                + "\nTOTAL DE SLIDES: "
                + str(page_count)
                + "\nSLIDES DESTA LEITURA: "
                + str(first)
                + " a "
                + str(last)
                + "\n\nINVENTÁRIO OBRIGATÓRIO DE SLIDES:\n"
                + _prompt_inventory(rows)
            )

            ai_batch: MemoryBatch | None = None
            try:
                ai_batch = _structured_call(
                    client,
                    model=model,
                    prompt=prompt,
                    docs=[part],
                    schema=MemoryBatch,
                    context=f"Memória de {doc.name}, slides {first}-{last}",
                )
                ai_batch = _normalize_relative_pages(
                    ai_batch,
                    first_page=first,
                    last_page=last,
                )
            except Exception as exc:
                document_warnings.append(
                    f"A resposta estruturada dos slides {first} a {last} falhou; a cobertura automática preservou essas páginas. Detalhe técnico: {exc}"
                )

            detail_batches.append(
                _repair_batch_coverage(
                    ai_batch,
                    source_file=doc.name,
                    inventory_rows=rows,
                )
            )
            completed_steps += 1

        if progress_callback:
            progress_callback(
                completed_steps,
                total_steps,
                f"Consolidando o projeto completo — {page_count} slides",
            )

        overview = _synthesize_overview(
            client,
            doc=doc,
            page_count=page_count,
            model=model,
            detail_batches=detail_batches,
            warnings=document_warnings,
        )
        all_batches.extend([_overview_as_batch(overview), *detail_batches])
        completed_steps += 1

    if progress_callback:
        progress_callback(total_steps, total_steps, "Projeto completo decupado.")

    return all_batches


def merge_memory_batches(batches: list[MemoryBatch]) -> dict:
    metadata_fields = [
        "document_title",
        "client_brand",
        "project_name",
        "event_name",
        "version_label",
        "creative_concept",
    ]
    metadata = {field: None for field in metadata_fields}
    summaries: list[str] = []
    warnings: list[str] = []
    slides_map: dict[tuple[str, int], dict] = {}
    inventory_map: dict[tuple[str, int], dict] = {}
    seen_items: set[tuple] = set()
    coverage_batches: list[dict] = []

    for batch in batches:
        data = batch.model_dump()
        for field in metadata_fields:
            if not metadata[field] and data.get(field):
                metadata[field] = data[field]

        summary = str(data.get("strategic_summary") or "").strip()
        if summary and summary not in summaries:
            summaries.append(summary)

        warnings.extend(data.get("warnings") or [])
        coverage_batches.append(data.get("coverage") or {})

        for row in data.get("page_inventory") or []:
            source_file = str(row.get("source_file") or data.get("source_file") or "")
            page_number = int(row.get("page_number") or 0)
            if source_file and page_number > 0:
                inventory_map[(source_file, page_number)] = {
                    **row,
                    "source_file": source_file,
                    "page_number": page_number,
                }

        for slide in data.get("slides") or []:
            source_file = str(slide.get("source_file") or data.get("source_file") or "")
            source_page = int(slide.get("source_page") or 0)
            if not source_file or source_page <= 0:
                continue

            key = (source_file, source_page)
            target = slides_map.setdefault(
                key,
                {
                    "source_file": source_file,
                    "source_page": source_page,
                    "slide_title": slide.get("slide_title"),
                    "slide_summary": slide.get("slide_summary"),
                    "primary_section": slide.get("primary_section"),
                    "is_meaningful": slide.get("is_meaningful", True),
                    "exclusion_reason": slide.get("exclusion_reason"),
                    "content_kind": slide.get("content_kind"),
                    "items": [],
                },
            )

            for field in (
                "slide_title",
                "slide_summary",
                "primary_section",
                "exclusion_reason",
                "content_kind",
            ):
                if not target.get(field) and slide.get(field):
                    target[field] = slide[field]

            for item in slide.get("items") or []:
                title = str(item.get("title") or "").strip()
                section_key = str(item.get("section_key") or "")
                if not title or not section_key:
                    continue
                signature = (
                    source_file,
                    source_page,
                    section_key,
                    _normalize_text(title),
                )
                if signature in seen_items:
                    continue
                seen_items.add(signature)
                row_id = hashlib.sha256(
                    "|".join(str(value) for value in signature).encode("utf-8")
                ).hexdigest()[:16]
                target["items"].append(
                    {
                        **item,
                        "source_file": source_file,
                        "source_page": source_page,
                        "slide_title": target.get("slide_title"),
                        "_row_id": row_id,
                    }
                )

    slides = sorted(
        slides_map.values(),
        key=lambda row: (row["source_file"], row["source_page"]),
    )
    items = [item for slide in slides for item in slide["items"]]
    page_inventory = sorted(
        inventory_map.values(),
        key=lambda row: (row["source_file"], row["page_number"]),
    )

    meaningful_pages = {
        (str(row["source_file"]), int(row["page_number"]))
        for row in page_inventory
        if bool(row.get("is_meaningful"))
    }
    pages_with_items = {
        (str(item["source_file"]), int(item["source_page"]))
        for item in items
    }
    uncovered_pages = sorted(
        meaningful_pages - pages_with_items,
        key=lambda value: (value[0], value[1]),
    )
    section_counts = Counter(
        str(item.get("section_key") or "strategy")
        for item in items
    )
    ai_items = sum(
        1
        for item in items
        if item.get("extraction_origin") == "ai"
    )
    repaired_items = sum(
        1
        for item in items
        if item.get("extraction_origin") == "automatic_repair"
    )

    coverage = {
        "total_pages": len(page_inventory),
        "meaningful_pages": len(meaningful_pages),
        "pages_with_items": len(pages_with_items),
        "uncovered_pages": [
            {"source_file": source_file, "page": page}
            for source_file, page in uncovered_pages
        ],
        "coverage_percent": round(
            (len(pages_with_items & meaningful_pages) / len(meaningful_pages) * 100)
            if meaningful_pages
            else 100.0,
            1,
        ),
        "items_total": len(items),
        "ai_items": ai_items,
        "automatic_repair_items": repaired_items,
        "section_counts": {
            MEMORY_SECTION_LABELS.get(section, section): count
            for section, count in section_counts.items()
        },
        "batch_details": [row for row in coverage_batches if row],
    }

    if uncovered_pages:
        warnings.append(
            f"{len(uncovered_pages)} slide(s) relevante(s) ainda não possuem ficha individual."
        )

    strategic_summary = " ".join(summaries).strip()

    return {
        **metadata,
        "strategic_summary": strategic_summary[:5000] or None,
        "slides": slides,
        "items": items,
        "page_inventory": page_inventory,
        "coverage": coverage,
        "warnings": list(
            dict.fromkeys(
                str(item)
                for item in warnings
                if str(item).strip()
            )
        ),
    }


def memory_editor_dataframe(extraction: dict) -> pd.DataFrame:
    rows = []
    for item in extraction.get("items", []):
        section = str(item.get("section_key") or "strategy")
        origin = str(item.get("extraction_origin") or "ai")
        rows.append(
            {
                "_row_id": item["_row_id"],
                "Incluir": True,
                "Seção": MEMORY_SECTION_LABELS.get(section, section),
                "Tipo": item.get("item_type") or "Conteúdo",
                "Título": item.get("title") or "Sem título",
                "Resumo": item.get("summary") or "",
                "Status": item.get("status") or "Não identificado",
                "Página": int(item.get("source_page") or 0),
                "Arquivo": item.get("source_file") or "",
                "Origem": (
                    "IA"
                    if origin == "ai"
                    else "Cobertura automática"
                ),
                "Confiança": round(float(item.get("confidence") or 0) * 100, 1),
            }
        )
    return pd.DataFrame(rows, columns=MEMORY_EDITOR_COLUMNS)


def selected_memory_items(extraction: dict, editor: pd.DataFrame) -> list[dict]:
    source_map = {
        str(item["_row_id"]): item
        for item in extraction.get("items", [])
    }
    reverse_sections = {
        label: key for key, label in MEMORY_SECTION_LABELS.items()
    }
    selected: list[dict] = []

    if editor is None or editor.empty:
        return selected

    for row in editor.to_dict(orient="records"):
        if not bool(row.get("Incluir")):
            continue
        source = source_map.get(str(row.get("_row_id") or ""))
        if not source:
            continue
        item = copy.deepcopy(source)
        item["section_key"] = reverse_sections.get(
            str(row.get("Seção")),
            source.get("section_key", "strategy"),
        )
        item["item_type"] = str(row.get("Tipo") or "").strip() or "Conteúdo"
        item["title"] = str(row.get("Título") or "").strip() or "Sem título"
        item["summary"] = str(row.get("Resumo") or "").strip() or None
        item["status"] = str(row.get("Status") or "Não identificado")
        selected.append(item)

    return selected


def memory_section_counts(items: list[dict]) -> pd.DataFrame:
    counts = Counter(
        str(item.get("section_key") or "strategy")
        for item in items
    )
    rows = [
        {
            "Seção": MEMORY_SECTION_LABELS.get(section, section),
            "Itens": count,
        }
        for section, count in counts.items()
    ]
    if not rows:
        return pd.DataFrame(columns=["Seção", "Itens"])
    return pd.DataFrame(rows).sort_values("Itens", ascending=False)
