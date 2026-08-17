from __future__ import annotations

"""NAVE V28.7.2B — explicit Core Semantic Domain extraction.

The extractor is deliberately conservative. It materializes only source-explicit
Strategy / Creative Platform / Experience / Journey signals. Project Analyst synthesis
is never used as factual input here.
"""

from dataclasses import dataclass, asdict
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from project_semantic_observations import _project_evidence, _source_role, _phase_role
from nave_storage import get_bytes as storage_get_bytes

CORE_SEMANTIC_VERSION = "V28.7.2B"


@dataclass(frozen=True)
class CoreSemanticSignal:
    domain_hint: str
    semantic_role: str
    observed_name: str
    statement: str
    assertion_mode: str = "source_explicit"
    confidence: float = 0.94
    sequence_index: int | None = None
    attributes: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attributes"] = dict(self.attributes or {})
        return data


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _clean_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in re.split(r"[\r\n]+", str(text or "")):
        line = re.sub(r"\s+", " ", raw).strip(" \t•·|:-_")
        if line:
            out.append(line)
    return out


def _short_label(line: str) -> bool:
    words = [w for w in re.split(r"\s+", line.strip()) if w]
    return 1 <= len(words) <= 9 and len(line) <= 100


def _is_headingish(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio >= 0.68 and _short_label(line)


def _sentence_after_heading(lines: Sequence[str], heading_idx: int) -> str:
    return " ".join(lines[heading_idx + 1:]).strip()[:1800]


def _extract_named_phrase_after_create(text: str) -> str | None:
    patterns = [
        r"\b(?:criar|create|creating|criarmos)\s+((?:a|o|the)\s+[^\.!?\n]{4,140})",
        r"\b(?:conceito|concept|point of view|pov|big idea)\s*[:|\-]?\s*([^\n\.!?]{3,140})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;\"'“”")
            if 2 <= len(value.split()) <= 22:
                return value
    return None


def _dedupe(signals: Sequence[CoreSemanticSignal]) -> list[CoreSemanticSignal]:
    seen: set[tuple[str, str, str]] = set()
    out: list[CoreSemanticSignal] = []
    for signal in signals:
        key = (signal.domain_hint, signal.semantic_role, _norm(signal.observed_name))
        if not key[2] or key in seen:
            continue
        seen.add(key)
        out.append(signal)
    return out


def _exact_stage(line: str) -> tuple[str, str, int] | None:
    n = _norm(line)
    patterns = [
        ("pre_event", "PRE-EVENT", 1, r"^(?:\d+\s+)?pre event\b"),
        ("event", "EVENT", 2, r"^(?:\d+\s+)?event\b"),
        ("post_event", "POST-EVENT", 3, r"^(?:\d+\s+)?post event\b"),
    ]
    for moment_type, label, seq, pattern in patterns:
        if re.search(pattern, n) and n not in {"event journey", "experience journey"}:
            return moment_type, label, seq
    return None


def extract_explicit_core_signals(text: str) -> list[CoreSemanticSignal]:
    """Extract explicit semantic objects from one Evidence Unit, fail-closed."""
    raw = str(text or "").strip()
    norm = _norm(raw)
    if not raw or not norm:
        return []
    lines = _clean_lines(raw)
    signals: list[CoreSemanticSignal] = []

    # Strategy: explicit challenge / tension headings.
    for idx, line in enumerate(lines):
        n = _norm(line)
        if n in {"our challenge", "challenge", "desafio", "nosso desafio"}:
            statement = _sentence_after_heading(lines, idx) or raw
            signals.append(CoreSemanticSignal("strategy", "challenge", line, statement, confidence=0.98))
        elif n in {"tensao", "tension"}:
            statement = _sentence_after_heading(lines, idx) or raw
            signals.append(CoreSemanticSignal("strategy", "tension", line, statement, confidence=0.98))

    # Territory is emitted only when the source either names it explicitly or uses a
    # demonstrative reference ("this territory" / "desse território") next to one clear,
    # non-meta heading. Generic analytical headings such as HIGHLIGHTS/INSIGHT are not
    # themselves territory names.
    if re.search(r"\b(territorio|territory)\b", norm):
        is_creative_territory = bool(re.search(r"\b(territorio criativo|creative territory)\b", norm))
        explicit = re.search(r"\b(?:territorio(?: criativo)?|creative territory|territory)\s*[:\-]\s*([^\n\.!?]{2,110})", raw, flags=re.I)
        name = explicit.group(1).strip() if explicit else None
        if not name:
            referential_territory = bool(re.search(
                r"\b(?:this|that|the|esse|essa|este|esta|desse|dessa|deste|desta|nesse|nessa)\s+(?:territorio|territory)\b",
                norm,
            ))
            meta_headings = {
                "pontos de partida", "starting points", "point of view", "our challenge",
                "challenge", "creative territory", "territorio criativo", "highlights",
                "insight", "insights", "opportunity", "oportunidade", "brief recap",
                "our goal", "goal", "event", "journey", "event journey",
            }
            if referential_territory:
                candidates = [
                    line for line in lines[:6]
                    if _is_headingish(line) and _norm(line) not in meta_headings
                ]
                if len(candidates) == 1:
                    name = candidates[0]
        if name:
            if is_creative_territory:
                signals.append(CoreSemanticSignal("creative", "creative_territory", name, raw[:1800], confidence=0.97))
            else:
                signals.append(CoreSemanticSignal("strategy", "territory", name, raw[:1800], confidence=0.97))

    # Explicit strategic headings. The adjacent-evidence collector below extracts the
    # body/bullets when DOCX splits heading and content into separate paragraphs.
    if re.search(r"\b(objetivos estrategicos|strategic objectives?|strategic direction|direcao estrategica|alinhamento estrategico)\b", norm):
        heading = next((line for line in lines if re.search(r"objetiv|strateg|alinhamento", _norm(line))), "Direção estratégica")
        signals.append(CoreSemanticSignal("strategy", "strategic_direction", heading, raw[:1800], confidence=0.96))

    # Explicit pillars / starting points. Preserve the source's semantic framing:
    # "Pilares" becomes pillar; "Pontos de partida" becomes strategic_principle.
    marker_idx = next((i for i, line in enumerate(lines) if re.search(r"\b(pilares|pillars|pontos de partida|starting points)\b", _norm(line))), None)
    if marker_idx is not None:
        marker_norm = _norm(lines[marker_idx])
        marker_role = "pillar" if re.search(r"\b(pilares|pillars)\b", marker_norm) else "strategic_principle"
        candidate_rows: list[tuple[int, str]] = []
        start = max(0, marker_idx - 7)
        end = min(len(lines), marker_idx + 8)
        for line_idx in range(start, end):
            if line_idx == marker_idx:
                continue
            line = lines[line_idx]
            n = _norm(line)
            if _short_label(line) and _is_headingish(line) and not re.search(r"pontos|partida|pilares|pillars|starting", n):
                candidate_rows.append((line_idx, line))
        candidate_rows = candidate_rows[:8]
        candidate_positions = [idx for idx, _ in candidate_rows]
        for line_idx, line in candidate_rows:
            statement = raw[:1800]
            # When the source page visually presents heading -> body -> next heading, keep
            # the Strategy statement atomic instead of copying the entire page into every
            # element. Candidates that precede the marker retain the full Evidence text
            # because their body association is not structurally unambiguous.
            if line_idx > marker_idx:
                next_positions = [idx for idx in candidate_positions if idx > line_idx]
                segment_end = min(next_positions) if next_positions else len(lines)
                body = [value for value in lines[line_idx + 1:segment_end] if _norm(value)]
                if body:
                    statement = "\n".join(body)[:1800]
            signals.append(CoreSemanticSignal("strategy", marker_role, line, statement, confidence=0.97))

    # Explicit insight/opportunity labels are Strategy facts when the same Evidence Unit
    # contains substantive body text. Do not promote a bare section divider.
    for idx, line in enumerate(lines):
        n = _norm(line)
        role = "insight" if n in {"insight", "insights"} else "opportunity" if n in {"opportunity", "oportunidade"} else None
        if not role:
            continue
        body_lines = [value for j, value in enumerate(lines) if j != idx and _norm(value) not in {"insight", "insights", "opportunity", "oportunidade"}]
        statement = " ".join(body_lines).strip()
        if len(_norm(statement).split()) < 5:
            continue
        observed_name = statement[:180].rstrip(" .,:;")
        signals.append(CoreSemanticSignal("strategy", role, observed_name, statement[:1800], confidence=0.98))

    # Creative Platform / POV. Only explicit project-level concept headings qualify; the
    # generic word "concept" inside activation copy is not enough.
    creative_heading_idx = None
    for idx, line in enumerate(lines):
        n = _norm(line)
        if (
            n.startswith("point of view")
            or n in {"pov", "big idea", "the big idea", "concept", "the concept", "conceito", "o conceito"}
            or n.startswith("creative concept")
            or n.startswith("conceito criativo")
            or n.startswith("event concept")
            or n.startswith("conceito do evento")
        ):
            creative_heading_idx = idx
            break
    if creative_heading_idx is not None:
        name = _extract_named_phrase_after_create(raw)
        if not name:
            for nxt in lines[creative_heading_idx + 1: creative_heading_idx + 5]:
                if _short_label(nxt) and _norm(nxt) not in {"event", "evento", "point of view", "concept", "conceito", "the concept"}:
                    name = nxt
                    break
        if name:
            signals.append(CoreSemanticSignal("creative", "pov", name, raw[:1800], confidence=0.98))

    # Named idea references in quotes. Generic; no Golden/project strings in production.
    idea_match = re.search(r"(?:idea|ideia|concept|conceito)\s+[\"“']([^\"”']{2,90})[\"”']", raw, flags=re.I)
    if not idea_match:
        idea_match = re.search(r"[\"“']([^\"”']{2,90})[\"”']\s+(?:idea|ideia|concept|conceito)", raw, flags=re.I)
    if idea_match:
        name = idea_match.group(1).strip()
        if _short_label(name):
            signals.append(CoreSemanticSignal("creative", "big_idea", name, raw[:1800], confidence=0.97))

    # Experience Architecture only with explicit journey language. A bare "JOURNEY"
    # can be creative copy (e.g. "invitation to the journey"), so it only qualifies when
    # the same Evidence Unit also contains multiple lifecycle stages.
    specific_journey_heading = next(
        (line for line in lines if _norm(line) in {"event journey", "jornada do evento", "experience journey"}),
        None,
    )
    generic_journey_heading = next(
        (line for line in lines if _norm(line) in {"journey", "jornada"}),
        None,
    )
    explicit_stages = [stage for line in lines if (stage := _exact_stage(line))]
    journey_heading = specific_journey_heading
    if journey_heading is None and generic_journey_heading is not None and len({stage[0] for stage in explicit_stages}) >= 2:
        journey_heading = generic_journey_heading
    if journey_heading:
        signals.append(CoreSemanticSignal(
            "experience", "experience_architecture", journey_heading, raw[:1800], confidence=0.99,
            attributes={"explicit_journey_heading": True},
        ))
        for line in lines:
            stage = _exact_stage(line)
            if not stage:
                continue
            moment_type, label, seq = stage
            signals.append(CoreSemanticSignal(
                "journey", "stage", label, line, confidence=0.99, sequence_index=seq,
                attributes={"moment_type": moment_type, "architecture_name": journey_heading, "parent_stage_hint": moment_type},
            ))

    # Explicit named journey moments must be labels/headings, not a phrase buried in copy.
    explicit_moments = {
        "product reveal": ("product_reveal", "PRODUCT REVEAL"),
        "revelacao do produto": ("product_reveal", "PRODUCT REVEAL"),
        "activation reveal": ("activation_reveal", "ACTIVATION REVEAL"),
        "revelacao das ativacoes": ("activation_reveal", "ACTIVATION REVEAL"),
        "content creation": ("content_creation", "CONTENT CREATION"),
        "criacao de conteudo": ("content_creation", "CONTENT CREATION"),
    }
    for line in lines:
        n = _norm(line)
        # Some PDF pages prepend the stage to the moment title: "EVENT PRODUCT REVEAL".
        n_without_stage = re.sub(r"^(pre event|event|post event)\s+", "", n).strip()
        if n_without_stage in explicit_moments:
            moment_type, label = explicit_moments[n_without_stage]
            parent_stage = "event"
            if n.startswith("pre event "):
                parent_stage = "pre_event"
            elif n.startswith("post event "):
                parent_stage = "post_event"
            signals.append(CoreSemanticSignal(
                "journey", "moment", label, raw[:1800], confidence=0.98,
                attributes={"moment_type": moment_type, "parent_stage_hint": parent_stage},
            ))

    return _dedupe(signals)



def _pdf_page_number(unit: Mapping[str, Any]) -> int | None:
    locator = unit.get("locator") if isinstance(unit.get("locator"), Mapping) else {}
    value = locator.get("page")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        page = int(value)
        return page if page >= 1 else page + 1
    try:
        page = int(str(value).strip())
        return page if page >= 1 else page + 1
    except Exception:
        return None


def _pdf_layout_lines(payload: bytes, page_numbers: Sequence[int]) -> dict[int, str]:
    """Recover visual text-line boundaries from a stored PDF master.

    Evidence Units created by the historical PDF extractor intentionally store one
    flattened string per page. Core semantics sometimes depends on headings that share a
    page (e.g. several strategic starting points). Re-reading the *same source page* with
    PyMuPDF line geometry restores those boundaries without creating new Evidence or
    changing provenance.
    """
    if not payload or not page_numbers:
        return {}
    try:
        import pymupdf
    except Exception:
        return {}
    out: dict[int, str] = {}
    try:
        doc = pymupdf.open(stream=payload, filetype="pdf")
    except Exception:
        return {}
    try:
        for page_number in sorted(set(int(v) for v in page_numbers if int(v) >= 1)):
            index = page_number - 1
            if index < 0 or index >= len(doc):
                continue
            page = doc[index]
            try:
                data = page.get_text("dict", sort=True) or {}
            except TypeError:
                data = page.get_text("dict") or {}
            rows: list[tuple[float, float, str]] = []
            for block in data.get("blocks") or []:
                if int(block.get("type") or 0) != 0:
                    continue
                for line in block.get("lines") or []:
                    spans = line.get("spans") or []
                    text = "".join(str(span.get("text") or "") for span in spans)
                    text = re.sub(r"\s+", " ", text).strip()
                    if not text:
                        continue
                    bbox = line.get("bbox") or block.get("bbox") or (0, 0, 0, 0)
                    try:
                        x0, y0 = float(bbox[0]), float(bbox[1])
                    except Exception:
                        x0, y0 = 0.0, 0.0
                    rows.append((round(y0, 1), round(x0, 1), text))
            rows.sort(key=lambda item: (item[0], item[1]))
            text = "\n".join(item[2] for item in rows).strip()
            if text:
                out[page_number] = text
    finally:
        try:
            doc.close()
        except Exception:
            pass
    return out


def _recover_pdf_layout_texts(
    client: Any,
    evidence: Sequence[Mapping[str, Any]],
    source: Mapping[str, Any],
) -> dict[str, str]:
    """Return Evidence id -> same-page text with visual line boundaries restored.

    This is a semantic-read recovery, not a new source extraction: every generated
    observation remains bound to the original page Evidence Unit.
    """
    asset_by_id = source.get("asset_by_id") if isinstance(source.get("asset_by_id"), Mapping) else {}
    by_asset: dict[str, list[Mapping[str, Any]]] = {}
    for unit in evidence:
        asset_id = str(unit.get("source_asset_id") or "")
        asset = asset_by_id.get(asset_id) or {}
        mime = str(asset.get("mime_type") or "").casefold()
        name = str(asset.get("canonical_file_name") or asset.get("storage_path") or "").casefold()
        if not (mime == "application/pdf" or name.endswith(".pdf")):
            continue
        if str(unit.get("unit_type") or "") != "page" or _pdf_page_number(unit) is None:
            continue
        by_asset.setdefault(asset_id, []).append(unit)

    recovered: dict[str, str] = {}
    for asset_id, units in by_asset.items():
        asset = asset_by_id.get(asset_id) or {}
        try:
            payload = storage_get_bytes(
                client,
                bucket_name=str(asset.get("storage_bucket") or ""),
                path=str(asset.get("storage_path") or ""),
            )
        except Exception:
            payload = None
        if not payload:
            continue
        pages = [_pdf_page_number(unit) for unit in units]
        layout_by_page = _pdf_layout_lines(payload, [p for p in pages if p is not None])
        for unit in units:
            page_number = _pdf_page_number(unit)
            layout_text = layout_by_page.get(page_number or -1, "")
            if not layout_text:
                continue
            # Do not use a suspiciously incomplete recovery. Token overlap is deliberately
            # permissive because layout reads can legitimately omit decorative duplicates.
            original_tokens = set(_norm(unit.get("content_text")).split())
            layout_tokens = set(_norm(layout_text).split())
            overlap = (len(original_tokens & layout_tokens) / max(1, len(original_tokens))) if original_tokens else 1.0
            if overlap < 0.55:
                continue
            recovered[str(unit.get("id") or "")] = layout_text
    return recovered


def _structured_list_title(text: str) -> str | None:
    value = re.sub(r"^[•\-\u2022\s]+", "", str(text or "")).strip()
    if not value:
        return None
    # Explicit bullet-like prose often uses an en/em dash to separate the semantic label
    # from its explanation. Preserve the source label instead of synthesizing one.
    parts = re.split(r"\s+[–—-]\s+|\s*:\s+", value, maxsplit=1)
    candidate = parts[0].strip(" .,:;–—-")
    words = candidate.split()
    if 1 <= len(words) <= 10 and len(candidate) <= 120:
        return candidate
    if len(value.split()) <= 9 and len(value) <= 120:
        return value.strip(" .,:;")
    return None


def _adjacent_explicit_group_signals(evidence: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Recover source-explicit pillars/starting-points split across DOCX paragraphs."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for unit in evidence:
        grouped.setdefault(str(unit.get("source_asset_id") or ""), []).append(unit)
    out: dict[str, list[dict[str, Any]]] = {}
    marker_re = re.compile(r"^(pilares|pillars|pontos de partida|starting points)\s*$")
    stop_re = re.compile(
        r"\b(diretrizes|deliverables|entregaveis|ativacoes|experiencias|budget|financeiro|obrigatoriedades|"
        r"objetivos estrategicos|strategic objectives?|point of view|conceito|concept)\b"
    )
    for units in grouped.values():
        ordered = sorted(units, key=_ordinal)
        active_role: str | None = None
        marker_evidence_id: str | None = None
        remaining = 0
        for unit in ordered:
            if str(unit.get("unit_type") or "") != "paragraph":
                active_role = None
                marker_evidence_id = None
                remaining = 0
                continue
            text = str(unit.get("content_text") or "").strip()
            n = _norm(text).rstrip(" :")
            marker = marker_re.match(n)
            if marker:
                active_role = "pillar" if marker.group(1) in {"pilares", "pillars"} else "strategic_principle"
                marker_evidence_id = str(unit.get("id") or "")
                remaining = 8
                continue
            if not active_role or remaining <= 0:
                continue
            # A new explicit section heading terminates the group even when its label is
            # unknown to the Strategy ontology. This prevents metadata/resource sections
            # such as ``Canais oficiais:`` from leaking into a preceding ``Pilares:``
            # block. The terminal colon matters: ``Inovação: simplificar a jornada`` is
            # still a valid item because the paragraph does not *end* at the label.
            terminal_section_heading = bool(text.rstrip().endswith(":") and 1 <= len(n.split()) <= 10)
            if terminal_section_heading or (stop_re.search(n) and (_is_headingish(text) or len(n.split()) <= 4)):
                active_role = None
                marker_evidence_id = None
                remaining = 0
                continue
            title = _structured_list_title(text)
            if title and len(_norm(title).split()) >= 1:
                signal = CoreSemanticSignal(
                    "strategy",
                    active_role,
                    title,
                    text[:1800],
                    confidence=0.98,
                    attributes={
                        "heading_evidence_id": marker_evidence_id,
                        "adjacent_explicit_group_heading": True,
                    },
                )
                out.setdefault(str(unit.get("id") or ""), []).append(signal.to_dict())
            remaining -= 1
            if remaining <= 0:
                active_role = None
                marker_evidence_id = None
    return out

def _mention_core_signals(client: Any, evidence_ids: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """Use File Analyst entities as weak extraction signals, never as domain identity."""
    if not evidence_ids:
        return {}
    mentions: list[dict[str, Any]] = []
    for start in range(0, len(evidence_ids), 80):
        mentions.extend(_rows(client.table("entity_mentions").select("*").in_("evidence_unit_id", list(evidence_ids[start:start + 80])).execute()))
    entity_ids = list(dict.fromkeys(str(row.get("entity_id") or "") for row in mentions if row.get("entity_id")))
    entities: list[dict[str, Any]] = []
    for start in range(0, len(entity_ids), 80):
        entities.extend(_rows(client.table("knowledge_entities").select("*").in_("id", entity_ids[start:start + 80]).execute()))
    entity_by_id = {str(row.get("id")): row for row in entities if row.get("id")}
    out: dict[str, list[dict[str, Any]]] = {}
    for mention in mentions:
        if _norm(mention.get("mention_role")).replace(" ", "_") != "file_analyst_entity":
            continue
        entity = entity_by_id.get(str(mention.get("entity_id") or "")) or {}
        entity_type = _norm(entity.get("entity_type")).replace(" ", "_")
        if entity_type not in {"strategy", "concept", "journey_stage"}:
            continue
        evidence_id = str(mention.get("evidence_unit_id") or "")
        name = str(mention.get("mention_text") or entity.get("canonical_name") or "").strip()
        if not evidence_id or not name:
            continue
        confidence = float(mention.get("confidence") or entity.get("confidence") or 0.0)
        # File Analyst mentions below the domain threshold remain source signals only.
        if entity_type == "concept":
            signal = CoreSemanticSignal("creative", "big_idea", name, name, assertion_mode="analyst_inference", confidence=confidence or 0.86)
        elif entity_type == "journey_stage":
            signal = CoreSemanticSignal("journey", "stage", name, name, assertion_mode="analyst_inference", confidence=confidence or 0.84)
        else:
            signal = CoreSemanticSignal("strategy", "strategic_direction", name, name, assertion_mode="analyst_inference", confidence=confidence or 0.84)
        out.setdefault(evidence_id, []).append({**signal.to_dict(), "file_analyst_entity_id": str(entity.get("id") or "")})
    return out


def _ordinal(unit: Mapping[str, Any]) -> int:
    value = unit.get("ordinal")
    if isinstance(value, (int, float)):
        return int(value)
    locator = unit.get("locator") if isinstance(unit.get("locator"), Mapping) else {}
    for key in ("paragraph_index", "slide", "page", "row", "ordinal"):
        candidate = locator.get(key)
        if isinstance(candidate, (int, float)):
            return int(candidate)
    return 10**9


def _adjacent_strategic_signals(evidence: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Recover explicit strategic bodies split from their heading in paragraph-level DOCX.

    The heading is context only; the current Evidence Unit remains the factual evidence for
    the emitted statement.
    """
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for unit in evidence:
        grouped.setdefault(str(unit.get("source_asset_id") or ""), []).append(unit)
    out: dict[str, list[dict[str, Any]]] = {}
    strategic_heading = re.compile(r"\b(objetivos estrategicos|strategic objectives?|direcao estrategica|strategic direction|alinhamento estrategico)\b")
    stop_heading = re.compile(
        r"^(diretrizes|deliverables|entregaveis|ativacoes|experiencias|para as plataformas|budget|financeiro|obrigatoriedades)\b"
    )
    for units in grouped.values():
        ordered = sorted(units, key=_ordinal)
        active_heading_id: str | None = None
        remaining = 0
        for unit in ordered:
            text = str(unit.get("content_text") or "").strip()
            n = _norm(text)
            if not n:
                continue
            if strategic_heading.search(n):
                # V28.7.2B6: a strategic heading can explicitly frame an audience-alignment
                # section (e.g. "Alinhamento Estratégico: ... público-alvo principal").
                # In that case the heading itself may remain a Strategy element, but the
                # following bullets are audience/context facts, not child strategic
                # directions. Do not open adjacency across an audience-scoped heading.
                audience_scoped_heading = bool(re.search(
                    r"\b(publico alvo|target audience|audience profile|perfil de publico)\b",
                    n,
                ))
                if audience_scoped_heading:
                    active_heading_id = None
                    remaining = 0
                else:
                    active_heading_id = str(unit.get("id") or "")
                    remaining = 4
                continue
            if active_heading_id and remaining > 0:
                terminal_section_heading = bool(text.rstrip().endswith(":") and 1 <= len(n.split()) <= 28)
                audience_boundary = bool(
                    re.search(r"\b(publico alvo|target audience)\b", n)
                    and (terminal_section_heading or len(n.split()) <= 22)
                )
                section_boundary = bool(
                    stop_heading.search(n)
                    and (terminal_section_heading or _is_headingish(text) or len(n.split()) <= 12)
                )
                if audience_boundary or section_boundary:
                    active_heading_id = None
                    remaining = 0
                    continue
                # Prefer statement-like/bullet units; generic one-line section labels are skipped.
                if len(n.split()) >= 4 and len(text) <= 1800:
                    name = re.sub(r"^[•\-\u2022\s]+", "", text).strip()
                    signal = CoreSemanticSignal(
                        "strategy", "strategic_direction", name[:180], text[:1800], confidence=0.97,
                        attributes={"heading_evidence_id": active_heading_id, "adjacent_explicit_heading": True},
                    )
                    out.setdefault(str(unit.get("id") or ""), []).append(signal.to_dict())
                remaining -= 1
                if remaining <= 0:
                    active_heading_id = None
    return out


def collect_project_core_semantic_observations(client: Any, project_id: str) -> dict[str, Any]:
    source = _project_evidence(client, project_id)
    evidence = list(source.get("evidence") or [])
    evidence_ids = [str(row.get("id")) for row in evidence if row.get("id")]
    mention_signals = _mention_core_signals(client, evidence_ids)
    adjacent_signals = _adjacent_strategic_signals(evidence)
    adjacent_group_signals = _adjacent_explicit_group_signals(evidence)
    recovered_pdf_text = _recover_pdf_layout_texts(client, evidence, source)
    observations: list[dict[str, Any]] = []

    for unit in evidence:
        evidence_id = str(unit.get("id") or "")
        asset_id = str(unit.get("source_asset_id") or "")
        stored_text = str(unit.get("content_text") or "").strip()
        text = str(recovered_pdf_text.get(evidence_id) or stored_text).strip()
        semantic_text_recovery_method = "stored_pdf_layout_lines" if evidence_id in recovered_pdf_text else None
        source_role, primary = _source_role(asset_id, source)
        phase, role = _phase_role(source_role)
        # Decision/feedback/execution semantics belong to later domains. B only reads
        # briefing/proposal/reference evidence.
        if phase in {"execution", "post_event", "feedback"}:
            continue
        signal_entries: list[tuple[dict[str, Any], str | None]] = [
            (s.to_dict(), semantic_text_recovery_method)
            for s in extract_explicit_core_signals(text)
        ]
        # Layout recovery restores headings/columns but can split a quoted named idea.
        # The stored flattened text remains valid evidence from the exact same page, so
        # parse it as a fallback as well and dedupe semantically.
        if semantic_text_recovery_method and stored_text and _norm(stored_text) != _norm(text):
            signal_entries.extend(
                (s.to_dict(), "stored_flat_text_fallback")
                for s in extract_explicit_core_signals(stored_text)
            )
        signal_entries.extend((row, None) for row in (adjacent_signals.get(evidence_id) or []))
        signal_entries.extend((row, None) for row in (adjacent_group_signals.get(evidence_id) or []))
        signal_entries.extend((row, None) for row in (mention_signals.get(evidence_id) or []))
        local_seen: set[tuple[str, str, str]] = set()
        for signal, signal_text_method in signal_entries:
            domain_hint = str(signal.get("domain_hint") or "other")
            semantic_role = str(signal.get("semantic_role") or "other")
            name = str(signal.get("observed_name") or "").strip()
            assertion_mode = str(signal.get("assertion_mode") or "source_explicit")
            if not name or assertion_mode != "source_explicit":
                # The first B rollout does not auto-create evidence synthesis or Analyst inference.
                continue
            key = (domain_hint, semantic_role, _norm(name))
            if key in local_seen:
                continue
            local_seen.add(key)
            signal_attrs = dict(signal.get("attributes") or {})
            payload = {
                "project_id": project_id,
                "source_asset_id": asset_id,
                "evidence_unit_id": evidence_id,
                "observation_kind": {
                    "strategy": "strategy_signal",
                    "creative": "creative_signal",
                    "experience": "experience_signal",
                    "journey": "journey_signal",
                }.get(domain_hint, "other"),
                "observed_name": name,
                "observed_type": domain_hint,
                "observed_status": None,
                "occurrence_phase": phase,
                "occurrence_role": role,
                "domain_hint": domain_hint,
                "semantic_role": semantic_role,
                "assertion_mode": assertion_mode,
                "attributes": {
                    **signal_attrs,
                    "statement": str(signal.get("statement") or text)[:4000],
                    "sequence_index": signal.get("sequence_index"),
                    "source_role": source_role,
                    "is_primary_source": bool(primary),
                    "normalized_by": CORE_SEMANTIC_VERSION,
                    **({"semantic_text_recovery_method": signal_text_method} if signal_text_method else {}),
                    **({"file_analyst_entity_id": signal.get("file_analyst_entity_id")} if signal.get("file_analyst_entity_id") else {}),
                },
                "source_authority_score": min(0.98, (0.88 if phase == "briefing" else 0.86) + (0.02 if primary else 0.0)),
                "model_confidence": max(0.0, min(1.0, float(signal.get("confidence") or 0.90))),
                "extraction_method": "core_semantic_explicit_evidence",
            }
            identity = {
                "project_id": project_id,
                "evidence_unit_id": evidence_id,
                "domain_hint": domain_hint,
                "semantic_role": semantic_role,
                "observed_name": _norm(name),
                "assertion_mode": assertion_mode,
            }
            observation_hash = _sha(identity)
            payload["observation_hash"] = observation_hash
            payload["id"] = _stable_uuid("nave:core-semantic-observation:" + observation_hash)
            observations.append(payload)

    by_id = {row["id"]: row for row in observations}
    return {
        "project_id": project_id,
        "observations": list(by_id.values()),
        "counts": {
            "total": len(by_id),
            "strategy": sum(1 for row in by_id.values() if row.get("domain_hint") == "strategy"),
            "creative": sum(1 for row in by_id.values() if row.get("domain_hint") == "creative"),
            "experience": sum(1 for row in by_id.values() if row.get("domain_hint") == "experience"),
            "journey": sum(1 for row in by_id.values() if row.get("domain_hint") == "journey"),
        },
    }
