from __future__ import annotations

"""NAVE V28.7.2C0.2.3 — Evidence-first Requirement Semantic Observation collector.

C0.2 removes the semantic privilege previously granted to legacy Requirements that
already had Evidence. Every legacy row is reclassified against the current source, and
the briefing Evidence is scanned independently to recover explicit obligations that the
legacy extractor never materialized.

Legacy Requirement rows remain recall hints only. Evidence is provenance only. The
semantic gate decides whether a signal is a Requirement, scope, attribute, context,
constraint or reference.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from project_requirement_identity import normalize_requirement_text
from project_semantic_observations import _project_evidence, _source_role, _phase_role, _authority

C0_VERSION = "V28.7.2C0.2.3"

CHANNEL_TERMS = {
    "youtube", "instagram", "tiktok", "tik tok", "kwai", "facebook", "linkedin",
    "stories", "story", "reels", "reel", "feed", "shorts", "twitter", "x",
}

AUDIENCE_MARKERS = (
    "publico alvo", "publico-alvo", "target audience", "audience", "perfil de publico",
)
PRODUCT_MARKERS = (
    "foco do produto", "product focus", "destaques", "highlights", "evidenciando",
    "product highlights", "features do produto", "product features",
)
PLATFORM_MARKERS = (
    "adequacao a plataforma", "adequacao à plataforma", "platform fit", "platform adequacy",
    "para a plataforma", "for the platform",
)
STRATEGY_MARKERS = (
    "alinhamento estrategico", "alinhamento estratégico", "objetivos estrategicos",
    "objetivos estratégicos", "strategic objectives", "strategic alignment",
    "para as plataformas", "for the platforms", "objetivo principal", "main objective",
)
REFERENCE_MARKERS = (
    "sites de referencia", "sites de referência", "referencias", "referências", "references",
    "como referencia", "como referência", "exemplo", "example",
)
DELIVERABLE_MARKERS = (
    "entregaveis", "entregáveis", "deliverables", "obrigatoriedades", "mandatory items",
)

# Strong source-language obligation. Naked words such as "necessário" are deliberately
# insufficient because they also occur in form labels (e.g. "NÃO NECESSÁRIO").
OBLIGATION_RE = re.compile(
    r"(?:\b(?:deve|devem|devera|deverá|deverao|deverão|devemos|precisa|precisam|precisamos|"
    r"temos\s+que|e\s+necessario|é\s+necessario|é\s+necessário|nao\s+e\s+necessario|não\s+é\s+necessário|"
    r"must|shall|required|needs?\s+to|have\s+to)\b|"
    r"(?:^|[\s:;\-])(?:considerar|apresentar|incluir|reservar|criar|desenvolver|desenhar|garantir|"
    r"entregar|utilizar|propor|prever|assegurar)\b)",
    re.I,
)

SUGGESTION_RE = re.compile(
    r"\b(?:vale\s+(?:sugerir|pensar|considerar)|podemos\s+(?:sugerir|considerar|inserir)|"
    r"se\s+acharmos\s+que\s+faz\s+sentido|recomenda-se|recomenda se|suggestion|could\s+consider|may\s+consider)\b",
    re.I,
)

NEGATIVE_OBLIGATION_RE = re.compile(
    r"\b(?:nao\s+e\s+necessario|não\s+é\s+necessário|nao\s+precisa|não\s+precisa|"
    r"nao\s+precisam|não\s+precisam|not\s+required|does\s+not\s+need|do\s+not\s+need)\b",
    re.I,
)

FILENAME_RE = re.compile(r"(?:^|\s)[^\s]+\.(?:pptx?|xlsx?|docx?|pdf|jpg|jpeg|png|webp)(?:$|\s)", re.I)
URL_RE = re.compile(r"https?://|www\.", re.I)


@dataclass(frozen=True)
class RequirementSemanticObservation:
    id: str
    project_id: str
    source_asset_id: str
    evidence_unit_id: str
    observation_kind: str
    observed_name: str
    observed_type: str | None
    observed_status: str | None
    occurrence_phase: str
    occurrence_role: str
    domain_hint: str
    semantic_role: str
    assertion_mode: str
    attributes: dict[str, Any]
    source_authority_score: float
    model_confidence: float
    extraction_method: str
    observation_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_rows(client: Any, table: str, *, equals: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    q = client.table(table).select("*")
    for key, value in (equals or {}).items():
        q = q.eq(key, value)
    return _rows(q.execute())


def _read_in(client: Any, table: str, field: str, values: Sequence[Any]) -> list[dict[str, Any]]:
    clean = list(dict.fromkeys(v for v in values if v not in (None, "")))
    if not clean:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(clean), 80):
        out.extend(_rows(client.table(table).select("*").in_(field, clean[start:start + 80]).execute()))
    return out


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _token_overlap(left: Any, right: Any) -> float:
    a = {t for t in _norm(left).split() if len(t) >= 3}
    b = {t for t in _norm(right).split() if len(t) >= 3}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def _requirement_evidence_links(client: Any, project_id: str) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    links = _read_rows(client, "domain_object_evidence", equals={"project_id": project_id, "domain_table": "project_requirements"})
    evidence = _read_in(client, "evidence_units", "id", [row.get("evidence_unit_id") for row in links])
    current = {str(row.get("id")): dict(row) for row in evidence if row.get("is_current") is True and row.get("id")}
    out: dict[str, list[dict[str, Any]]] = {}
    linked_ids: set[str] = set()
    for link in links:
        eid = str(link.get("evidence_unit_id") or "")
        did = str(link.get("domain_id") or "")
        if eid in current and did:
            out.setdefault(did, []).append(current[eid])
            linked_ids.add(eid)
    return out, linked_ids


def _best_requirement_evidence(req: Mapping[str, Any], evidence_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, float, str]:
    attrs = req.get("attributes") if isinstance(req.get("attributes"), Mapping) else {}
    hints = [attrs.get("source_quote"), attrs.get("source_reference"), req.get("description"), req.get("title")]
    hints = [str(v).strip() for v in hints if str(v or "").strip()]
    title = str(req.get("title") or "").strip()
    title_norm = _norm(title)
    best: tuple[float, int, dict[str, Any], str] | None = None
    for raw in evidence_rows:
        row = dict(raw)
        text = str(row.get("content_text") or "").strip()
        norm = _norm(text)
        if not norm:
            continue
        score = 0.0
        reason = ""
        for idx, hint in enumerate(hints):
            hnorm = _norm(hint)
            if len(hnorm) < 3:
                continue
            if hnorm == norm:
                cand, why = 1.0, "exact_evidence_text"
            elif len(hnorm) >= 8 and hnorm in norm:
                cand, why = (0.99 if idx == 0 else 0.95), "evidence_contains_requirement_hint"
            else:
                overlap = _token_overlap(hnorm, norm)
                cand, why = (0.60 + 0.30 * overlap if overlap >= 0.55 else 0.0), "token_overlap"
            if cand > score:
                score, reason = cand, why
        if title_norm and len(title_norm) >= 4 and title_norm in norm:
            score = max(score, 0.90 if len(title_norm.split()) > 1 else 0.80)
            reason = reason or "title_in_evidence"
        if score < 0.78:
            continue
        item = (score, -len(text), row, reason)
        if best is None or item[:2] > best[:2]:
            best = item
    if not best:
        return None, 0.0, "no_unambiguous_evidence"
    return best[2], float(best[0]), best[3]


def _is_channel_title(title: str) -> bool:
    return _norm(title) in {_norm(v) for v in CHANNEL_TERMS}


def _lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in re.split(r"[\r\n]+", str(text or "")):
        line = re.sub(r"\s+", " ", raw).strip(" \t•·")
        if line:
            out.append(line)
    return out


def _find_title_context(title: str, evidence_text: str, surrounding_text: str = "") -> str:
    """Return the closest structural label around a legacy fragment."""
    tnorm = _norm(title)
    lines = _lines(evidence_text)
    hit = None
    for idx, line in enumerate(lines):
        lnorm = _norm(line)
        if tnorm and (tnorm == lnorm or (len(tnorm) >= 4 and tnorm in lnorm)):
            hit = idx
            break
    if hit is not None:
        # Include the matched line itself because structured DOCX extraction often keeps
        # a label and its value on one line (e.g. "Público-Alvo: ..." or
        # "Foco do Produto: ...").
        before = lines[: hit + 1]
    else:
        before = lines
    context = " ".join(before[-8:] + _lines(surrounding_text)[-4:])
    return _norm(context)


def _has_any(norm_text: str, markers: Sequence[str]) -> bool:
    return any(_norm(marker) in norm_text for marker in markers)


def _looks_like_reference(value: str) -> bool:
    raw = str(value or "").strip()
    norm = _norm(raw)
    if not raw:
        return False
    if FILENAME_RE.search(raw) or URL_RE.search(raw):
        return True
    return norm in {"link", "links", "arquivo", "file", "modelo de ppt", "template"}


def _direct_obligation(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw or SUGGESTION_RE.search(raw):
        return False
    return bool(OBLIGATION_RE.search(raw) or NEGATIVE_OBLIGATION_RE.search(raw))


def _looks_like_unanswered_form_prompt(value: str) -> bool:
    """Detect briefing-template questions/instructions with no project-specific answer.

    A form scaffold such as:
      "Qual mensagem principal precisa ser transmitida: (O que as pessoas devem...)"
    contains obligation verbs inside the parenthetical guidance, but is not itself a
    Requirement. If substantive text exists after the colon, the line is NOT blocked.
    """
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    if not raw or ":" not in raw:
        return False

    label, answer = raw.split(":", 1)
    label_norm = _norm(label)
    answer = answer.strip()

    question_label = bool(re.match(
        r"^(?:qual|quais|quem|onde|quando|como|what|which|who|where|when|how)\b",
        label_norm,
    ))
    form_label = bool(re.match(
        r"^(?:numeros?|números?|resultado esperado|mensagem principal|objetivos? secundarios?|"
        r"secondary objectives?|expected results?)\b",
        label_norm,
    ))
    if not (question_label or form_label):
        return False

    # Blank or parenthetical-only content is template guidance, not an answer.
    if not answer:
        return True
    residual = re.sub(r"\([^)]*\)", " ", answer)
    residual = re.sub(r"[\s\-–—•·*;,.!?]+", " ", residual).strip()
    return residual == ""


def _classify(req: Mapping[str, Any], evidence_text: str, surrounding_text: str = "") -> tuple[str, str, str]:
    """Classify one legacy Requirement recall item against source semantics.

    Crucially, this function is called even when the legacy row already has Evidence.
    Existing provenance never grants semantic immunity.
    """
    title = str(req.get("title") or "").strip()
    title_norm = _norm(title)
    text_norm = _norm(evidence_text)
    req_type = _norm(req.get("requirement_type")).replace(" ", "_")
    attrs = req.get("attributes") if isinstance(req.get("attributes"), Mapping) else {}
    source_reference = _norm(attrs.get("source_reference"))
    local_context = _find_title_context(title, evidence_text, surrounding_text)
    context = " ".join(filter(None, [local_context, source_reference]))

    # Briefing-template scaffolding is not a Requirement identity, even when the
    # parenthetical helper text contains words such as "devem" or "precisa".
    if _looks_like_unanswered_form_prompt(title):
        return "context_signal", "form_prompt", "context"

    # A source-explicit obligation/exclusion wins over the descriptive context around it.
    # This keeps "não é necessário orçar MC" as a real Requirement exclusion.
    if _direct_obligation(title):
        return "requirement_candidate", "requirement_candidate", "requirement"

    if _looks_like_reference(title):
        return "reference_signal", "reference_signal", "reference"

    if _is_channel_title(title):
        return "scope_signal", "channel_scope", "scope"

    if title_norm.startswith("publico alvo") or title_norm.startswith("target audience"):
        return "context_signal", "audience_context", "context"
    if _has_any(context, AUDIENCE_MARKERS):
        return "context_signal", "audience_context", "context"

    if title_norm in {_norm(v) for v in PRODUCT_MARKERS} or _has_any(context, PRODUCT_MARKERS):
        return "attribute_signal", "product_attribute", "attribute"

    if title_norm in {_norm(v) for v in PLATFORM_MARKERS} or _has_any(context, PLATFORM_MARKERS):
        return "scope_signal", "platform_scope", "scope"

    if title_norm in {_norm(v) for v in STRATEGY_MARKERS} or _has_any(context, STRATEGY_MARKERS):
        return "context_signal", "strategy_context", "context"

    if _has_any(context, REFERENCE_MARKERS):
        return "reference_signal", "reference_signal", "reference"

    # Explicit obligation in the evidence can support a legacy title when the title is
    # the atom inside that same clause/list and no stronger descriptive context applies.
    if _direct_obligation(evidence_text):
        if re.search(r"\b(budget|orcamento|orçamento|verba|investimento|prazo|deadline|quantidade|participantes|attendees)\b", text_norm):
            if re.search(r"\d", evidence_text):
                return "constraint_candidate", "constraint_candidate", "constraint"
        return "requirement_candidate", "requirement_candidate", "requirement"

    # Legacy mandatory/deliverable signals remain eligible only after the semantic
    # context exclusions above. This protects concise valid requirements in older
    # projects without allowing audience/product/platform fragments to pass through.
    if source_reference and _has_any(source_reference, DELIVERABLE_MARKERS):
        return "requirement_candidate", "requirement_candidate", "requirement"
    if bool(req.get("mandatory")) and req_type not in {"audience", "publico", "publico_alvo", "context", "contexto"}:
        return "requirement_candidate", "requirement_candidate", "requirement"

    if re.search(r"\b(budget|orcamento|orçamento|verba|investimento|prazo|deadline|quantidade|participantes|attendees)\b", text_norm) and re.search(r"\d", evidence_text):
        return "constraint_candidate", "constraint_candidate", "constraint"

    # No explicit obligation and no structural evidence that this is a Requirement.
    # Preserve the signal, but do not let legacy presence become current truth.
    return "reference_signal", "reference_signal", "reference"


def _observation_identity(
    *, project_id: str, evidence_id: str, observed_name: str,
    origin_route: str, legacy_requirement_id: str | None,
) -> tuple[str, str]:
    # semantic_role is deliberately NOT part of the identity. Reclassification across
    # C0 runs updates the same observation instead of creating semantic duplicates.
    identity = {
        "project_id": project_id,
        "evidence_unit_id": evidence_id,
        "domain_hint": "requirement",
        "origin_route": origin_route,
        "legacy_requirement_id": legacy_requirement_id or None,
        "observed_name": _norm(observed_name),
    }
    ohash = _hash(identity)
    return ohash, str(uuid5(NAMESPACE_URL, "nave:requirement-observation:" + ohash))


def _make_observation(
    *, project_id: str, observed_name: str, evidence: Mapping[str, Any],
    semantic_role: str, occurrence_role: str, confidence: float,
    source_role: str, primary: bool, origin_route: str,
    requirement: Mapping[str, Any] | None = None, match_reason: str | None = None,
    observed_type: str | None = None, attributes: Mapping[str, Any] | None = None,
) -> RequirementSemanticObservation:
    req = dict(requirement or {})
    legacy_id = str(req.get("legacy_source_id") or "") or None
    domain_id = str(req.get("id") or "") or None
    source_asset_id = str(evidence.get("source_asset_id") or "")
    evidence_id = str(evidence.get("id") or "")
    ohash, oid = _observation_identity(
        project_id=project_id, evidence_id=evidence_id, observed_name=observed_name,
        origin_route=origin_route, legacy_requirement_id=legacy_id or domain_id if origin_route == "legacy_recall" else None,
    )
    phase, _source_occurrence_role = _phase_role(source_role)
    attrs = {
        "normalized_by": C0_VERSION,
        "origin_route": origin_route,
        "legacy_requirement_id": legacy_id,
        "requirement_id": domain_id,
        "requirement_entity_id": str(req.get("entity_id") or "") or None,
        "legacy_requirement_type": req.get("requirement_type"),
        "source_reference": (req.get("attributes") or {}).get("source_reference") if isinstance(req.get("attributes"), Mapping) else None,
        "match_reason": match_reason,
        "evidence_text": str(evidence.get("content_text") or "")[:2400],
    }
    attrs.update(dict(attributes or {}))
    role_map = {
        "requirement": "mention", "scope": "reference", "attribute": "reference",
        "constraint": "reference", "context": "reference", "reference": "reference",
    }
    return RequirementSemanticObservation(
        id=oid,
        project_id=project_id,
        source_asset_id=source_asset_id,
        evidence_unit_id=evidence_id,
        observation_kind="requirement_signal",
        observed_name=str(observed_name).strip(),
        observed_type=observed_type or str(req.get("requirement_type") or "other"),
        observed_status=None,
        occurrence_phase=phase,
        occurrence_role=role_map.get(occurrence_role, "reference"),
        domain_hint="requirement",
        semantic_role=semantic_role,
        assertion_mode="source_explicit",
        attributes=attrs,
        source_authority_score=_authority(source_role, primary=primary),
        model_confidence=max(0.0, min(1.0, confidence)),
        extraction_method=(
            "requirement_legacy_recall+semantic_gate+current_evidence"
            if origin_route == "legacy_recall"
            else "requirement_evidence_first_discovery"
        ),
        observation_hash=ohash,
    )


def _split_sentences(text: str) -> list[str]:
    chunks: list[str] = []
    for line in _lines(text):
        # Keep colon containers as lines; split prose sentences/semicolons otherwise.
        parts = re.split(r"(?<=[.!?;])\s+", line)
        for part in parts:
            clean = re.sub(r"\s+", " ", part).strip(" \t•·-")
            if clean:
                chunks.append(clean)
    return chunks


def _is_heading_only(text: str) -> bool:
    norm = _norm(text)
    words = norm.split()
    if not words or len(words) > 10:
        return False
    if text.strip().endswith(":") and not _direct_obligation(text):
        return True
    return norm in {
        "briefing", "entregaveis", "entregaveis da agencia cenario a", "obrigatoriedades",
        "considerar", "publico alvo", "objetivo", "informacoes logisticas", "foco do produto",
        "adequacao a plataforma", "destaques", "evidenciando", "inputs area de negocios",
    }


def _candidate_type(text: str) -> str:
    norm = _norm(text)
    if re.search(r"\b(budget|orcamento|verba|investimento|custo|custos|tributos|impostos)\b", norm):
        return "budget"
    if re.search(r"\b(prazo|deadline|data|horario|timing|timming|dia seguinte|12h)\b", norm):
        return "deadline"
    if re.search(r"\b(streaming|credenciamento|valet|logistica|hospedagem|transporte|operador|diretor tecnico)\b", norm):
        return "operation"
    if re.search(r"\b(kpi|relatorio|video|kv|jornada|proposta|cotacao|materiais graficos|gift|brinde)\b", norm):
        return "deliverable"
    return "other"


def _is_non_requirement_context(text: str, preceding_context: str) -> bool:
    """Block descriptive context even when a generic verb appears inside it."""
    norm = _norm(text)
    context = _norm(preceding_context)
    if _has_any(context, AUDIENCE_MARKERS) and not _direct_obligation(text):
        return True
    if _has_any(context, PRODUCT_MARKERS) and not _direct_obligation(text):
        return True
    if _has_any(context, PLATFORM_MARKERS) and not _direct_obligation(text):
        return True
    if _has_any(context, REFERENCE_MARKERS) and not _direct_obligation(text):
        return True
    if _looks_like_reference(text):
        return True
    if norm in {_norm(v) for v in CHANNEL_TERMS}:
        return True
    return False


def _previous_list_prefix(previous_text: str) -> str | None:
    lines = _lines(previous_text)
    if not lines:
        return None
    last = lines[-1].strip()
    norm = _norm(last.rstrip(":"))
    if not last.endswith(":") or not _direct_obligation(last):
        return None
    if (
        norm == "considerar"
        or norm.endswith(" considerar")
        or re.search(r"\bdeve(?:ra)?\s+contemplar(?:\s+.*\s+para)?$", norm)
        or re.search(r"\bdeve(?:ra)?\s+explorar$", norm)
    ):
        return last.rstrip(":")
    return None


def _discover_requirement_atoms(text: str, *, previous_text: str = "") -> list[dict[str, Any]]:
    """Return source-explicit atomic obligations from one briefing Evidence Unit.

    This is intentionally structural and client-agnostic. It never uses legacy Requirement
    rows as an inventory. Suggestions/references are preserved elsewhere and are not
    auto-promoted to Requirement truth.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    lines = _lines(raw)
    atoms: list[dict[str, Any]] = []

    # Track a local list container such as "O local deve contemplar:" or "Considerar:".
    inherited_prefix: str | None = _previous_list_prefix(previous_text)
    inherited_strength = 0.95

    for line_idx, line in enumerate(lines):
        stripped = line.strip()
        norm = _norm(stripped)
        if not norm:
            continue

        if _looks_like_reference(stripped):
            continue
        if _looks_like_unanswered_form_prompt(stripped):
            inherited_prefix = None
            continue
        if SUGGESTION_RE.search(stripped) and not NEGATIVE_OBLIGATION_RE.search(stripped):
            continue

        # Structural context labels reset inherited list semantics unless they themselves
        # are obligation containers.
        direct = _direct_obligation(stripped)
        if _is_heading_only(stripped) and not direct:
            inherited_prefix = None
            continue

        # A colon line with an obligation can be either a complete obligation or a
        # list container. Only structurally generic containers inherit child bullets;
        # named deliverables such as "Jornada: apresentar fluxos..." remain one atom
        # and keep their child bullets as scope/details in Evidence.
        if direct and stripped.endswith(":"):
            parent = stripped.rstrip(":")
            parent_norm = _norm(parent)
            is_atomic_list_container = bool(
                parent_norm == "considerar"
                or parent_norm.endswith(" considerar")
                or re.search(r"\bdeve(?:ra)?\s+contemplar(?:\s+.*\s+para)?$", parent_norm)
                or re.search(r"\bdeve(?:ra)?\s+explorar$", parent_norm)
            )
            inherited_prefix = parent if is_atomic_list_container else None
            if not is_atomic_list_container and len(parent_norm.split()) >= 4:
                atoms.append({
                    "name": parent,
                    "confidence": 0.97 if not re.match(r"^considerar\b", parent_norm) else 0.94,
                    "observed_type": _candidate_type(parent),
                    "polarity": "negative" if NEGATIVE_OBLIGATION_RE.search(parent) else "positive",
                    "source_atom": stripped,
                    "atom_index": line_idx,
                })
            continue

        # Bullet/list child under an explicit parent. Do not inherit into reference/example
        # prose or a new labeled section.
        if inherited_prefix and not direct:
            if re.match(r"^(obs|observacao|observação|ex|exemplo|example|link|mensagem chave|mensagem-chave)\b", norm):
                inherited_prefix = None
            elif len(norm.split()) >= 2 and not _looks_like_reference(stripped):
                if SUGGESTION_RE.search(stripped) and not NEGATIVE_OBLIGATION_RE.search(stripped):
                    inherited_prefix = None
                    continue
                child = re.sub(r"^[\-–—•·*]+\s*", "", stripped).strip()
                child_norm = _norm(child)
                # Numeric/location enumerations qualify a parent logistics requirement;
                # they are scope/quantity details, not new Requirement identities.
                if re.match(r"^\d+\s+(?:de|do|da|dos|das|from|of)\b", child_norm):
                    continue
                parent_norm = _norm(inherited_prefix)
                if parent_norm == "considerar":
                    name = f"Considerar {child}"
                else:
                    name = f"{inherited_prefix}: {child}"
                atoms.append({
                    "name": name,
                    "confidence": inherited_strength,
                    "observed_type": _candidate_type(name),
                    "polarity": "positive",
                    "source_atom": child,
                    "atom_index": line_idx,
                })
                continue

        # Split prose lines containing more than one obligation sentence.
        if re.match(r"^(ex|exemplo|example)\s*[:\-]", stripped, re.I):
            continue
        for sentence_idx, sentence in enumerate(re.split(r"(?<=[.!?;])\s+", stripped)):
            sentence = re.sub(r"\s+", " ", sentence).strip(" \t•·-")
            if not sentence or _looks_like_reference(sentence):
                continue
            if SUGGESTION_RE.search(sentence) and not NEGATIVE_OBLIGATION_RE.search(sentence):
                continue
            sentence_norm = _norm(sentence)
            if (
                re.search(r"\b(links?|materiais de referencia|planilhas de referencia|projetos anteriores|fotos de referencia)\b", sentence_norm)
                and not re.match(r"^(considerar|apresentar|incluir|reservar|criar|desenvolver|desenhar|garantir|entregar|utilizar|propor|prever)\b", sentence_norm)
            ):
                continue
            if not _direct_obligation(sentence):
                continue
            if _is_non_requirement_context(sentence, previous_text):
                continue

            confidence = 0.98
            if re.search(r"(?:^|\s)considerar\b", sentence, re.I):
                confidence = 0.95
            if NEGATIVE_OBLIGATION_RE.search(sentence):
                confidence = 0.99
            atoms.append({
                "name": sentence,
                "confidence": confidence,
                "observed_type": _candidate_type(sentence),
                "polarity": "negative" if NEGATIVE_OBLIGATION_RE.search(sentence) else "positive",
                "source_atom": sentence,
                "atom_index": line_idx * 100 + sentence_idx,
            })

    # Deduplicate inside the Evidence Unit by normalized source-derived name.
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for atom in atoms:
        key = _norm(atom.get("name"))
        if not key or key in seen:
            continue
        # A bare checkbox/form label is not an obligation.
        if key in {"orcamento estimado completo nao necessario", "producao voe cliente"}:
            continue
        seen.add(key)
        out.append(atom)
    return out


def _briefing_asset_ids(client: Any, project_id: str, source: Mapping[str, Any]) -> set[str]:
    """Resolve current briefing assets without scanning proposal/report Evidence as C0 input."""
    ids: set[str] = set()
    briefing_docs = _read_rows(client, "memory_briefing_documents", equals={"project_id": project_id})
    asset_by_sha = {str(row.get("content_sha256") or ""): dict(row) for row in (source.get("assets") or []) if row.get("content_sha256")}
    for row in briefing_docs:
        asset = asset_by_sha.get(str(row.get("content_sha256") or "")) or {}
        if asset.get("id"):
            ids.add(str(asset["id"]))
    if ids:
        return ids
    for asset in source.get("assets") or []:
        aid = str(asset.get("id") or "")
        role, _primary = _source_role(aid, source)
        if _norm(role).replace(" ", "_") in {"briefing", "briefing_original"}:
            ids.add(aid)
    return ids


def _surrounding_by_evidence(source: Mapping[str, Any], asset_ids: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for aid in asset_ids:
        rows = [dict(r) for r in (source.get("evidence_by_asset") or {}).get(aid, []) if r.get("id")]
        rows.sort(key=lambda r: (int(r.get("ordinal") or 0), str(r.get("id") or "")))
        for idx, row in enumerate(rows):
            parts = []
            for j in range(max(0, idx - 3), idx):
                parts.append(str(rows[j].get("content_text") or ""))
            out[str(row["id"])] = "\n".join(parts)[-3600:]
    return out


def _legacy_recall_requirements(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Only rows with a real legacy source belong to the legacy-recall route.

    Evidence-led identities from earlier C0 runs are current domain projections and
    must be rediscovered exclusively by Evidence-first on reruns.
    """
    return [dict(row) for row in rows if row.get("legacy_source_id")]


def collect_project_requirement_observations(client: Any, project_id: str) -> dict[str, Any]:
    source = _project_evidence(client, project_id)
    requirements = _read_rows(client, "project_requirements", equals={"project_id": project_id})
    # Route 1 is strictly legacy recall. Evidence-led identities created by a prior
    # C0 run must NOT re-enter through legacy_recall on rerun; they are rediscovered
    # (or disappear) through Route 2 Evidence-first. This is required for idempotence
    # and prevents one evidence-led identity from being treated as another legacy row.
    legacy_requirements = _legacy_recall_requirements(requirements)
    direct_by_requirement, _linked_evidence_ids = _requirement_evidence_links(client, project_id)
    briefing_assets = _briefing_asset_ids(client, project_id, source)
    surrounding = _surrounding_by_evidence(source, briefing_assets)

    # Map legacy briefing document lineage to the matching Source Asset.
    briefing_docs = _read_rows(client, "memory_briefing_documents", equals={"project_id": project_id})
    asset_by_sha = {str(row.get("content_sha256") or ""): dict(row) for row in (source.get("assets") or []) if row.get("content_sha256")}
    briefing_asset_by_id: dict[str, str] = {}
    for row in briefing_docs:
        asset = asset_by_sha.get(str(row.get("content_sha256") or "")) or {}
        if row.get("id") and asset.get("id"):
            briefing_asset_by_id[str(row["id"])] = str(asset["id"])

    observations: list[RequirementSemanticObservation] = []
    diagnostics: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Route 1: legacy recall, but EVERY row passes the semantic gate.
    # ------------------------------------------------------------------
    for req in legacy_requirements:
        req_id = str(req.get("id") or "")
        evidences = [dict(row) for row in (direct_by_requirement.get(req_id) or [])]
        evidence: dict[str, Any] | None = None
        score = 0.0
        match_reason = ""

        if evidences:
            evidence, score, match_reason = _best_requirement_evidence(req, evidences)
            if evidence is None:
                evidence = min(evidences, key=lambda row: len(str(row.get("content_text") or "")))
                score, match_reason = 0.92, "existing_current_domain_evidence_fallback"
            else:
                match_reason = "existing_current_domain_evidence+" + match_reason
        else:
            attrs = req.get("attributes") if isinstance(req.get("attributes"), Mapping) else {}
            briefing_doc_id = str(attrs.get("legacy_briefing_document_id") or "")
            source_asset_id = briefing_asset_by_id.get(briefing_doc_id)
            candidates = (source.get("evidence_by_asset") or {}).get(source_asset_id, []) if source_asset_id else [
                row for row in (source.get("evidence") or []) if str(row.get("source_asset_id") or "") in briefing_assets
            ]
            evidence, score, match_reason = _best_requirement_evidence(req, candidates)
            if source_asset_id:
                match_reason = (match_reason + "+same_source") if evidence else "no_unambiguous_same_source_evidence"

        if not evidence:
            diagnostics.append({
                "origin_route": "legacy_recall", "requirement_id": req_id,
                "title": req.get("title"), "classification": "unresolved",
                "evidence_found": False, "match_reason": match_reason,
            })
            continue

        evidence_id = str(evidence.get("id") or "")
        _candidate_kind, semantic_role, occurrence_role = _classify(
            req, str(evidence.get("content_text") or ""), surrounding.get(evidence_id, "")
        )
        source_role, primary = _source_role(str(evidence.get("source_asset_id") or ""), source)
        observation = _make_observation(
            project_id=project_id,
            observed_name=str(req.get("title") or "Requisito"),
            requirement=req,
            evidence=evidence,
            semantic_role=semantic_role,
            occurrence_role=occurrence_role,
            confidence=score,
            match_reason=match_reason,
            source_role=source_role,
            primary=primary,
            origin_route="legacy_recall",
        )
        observations.append(observation)
        diagnostics.append({
            "origin_route": "legacy_recall", "requirement_id": req_id,
            "legacy_requirement_id": req.get("legacy_source_id"), "title": req.get("title"),
            "classification": semantic_role, "evidence_found": True,
            "evidence_unit_id": evidence.get("id"), "source_role": source_role,
            "match_score": score, "match_reason": match_reason,
        })

    # ------------------------------------------------------------------
    # Route 2: Evidence-first discovery, independent of legacy inventory.
    # ------------------------------------------------------------------
    evidence_first_count = 0
    for aid in sorted(briefing_assets):
        rows = [dict(r) for r in (source.get("evidence_by_asset") or {}).get(aid, []) if r.get("is_current") is True]
        rows.sort(key=lambda r: (int(r.get("ordinal") or 0), str(r.get("id") or "")))
        source_role, primary = _source_role(aid, source)
        previous_text = ""
        for evidence in rows:
            text = str(evidence.get("content_text") or "")
            atoms = _discover_requirement_atoms(text, previous_text=previous_text)
            for atom in atoms:
                observation = _make_observation(
                    project_id=project_id,
                    observed_name=str(atom.get("name") or "Requisito"),
                    requirement=None,
                    evidence=evidence,
                    semantic_role="requirement_candidate",
                    occurrence_role="requirement",
                    confidence=float(atom.get("confidence") or 0.95),
                    match_reason="evidence_first_explicit_obligation",
                    source_role=source_role,
                    primary=primary,
                    origin_route="evidence_first",
                    observed_type=str(atom.get("observed_type") or "other"),
                    attributes={
                        "source_atom": atom.get("source_atom"),
                        "atom_index": atom.get("atom_index"),
                        "polarity": atom.get("polarity") or "positive",
                        "mandatory": True,
                    },
                )
                observations.append(observation)
                evidence_first_count += 1
            previous_text = (previous_text + "\n" + text)[-3600:]

    deduped = {row.observation_hash: row for row in observations}
    legacy_count = sum(1 for row in deduped.values() if row.attributes.get("origin_route") == "legacy_recall")
    evidence_count = sum(1 for row in deduped.values() if row.attributes.get("origin_route") == "evidence_first")
    return {
        "project_id": project_id,
        "observations": [row.to_dict() for row in deduped.values()],
        "diagnostics": diagnostics,
        "summary": {
            "legacy_requirements": len(legacy_requirements),
            "legacy_observations": legacy_count,
            "evidence_first_observations": evidence_count,
            "briefing_assets": len(briefing_assets),
            "total_observations": len(deduped),
            "raw_evidence_first_atoms": evidence_first_count,
        },
    }
