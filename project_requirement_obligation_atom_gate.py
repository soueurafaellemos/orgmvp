from __future__ import annotations

"""NAVE V28.7.3B2.10.1 — Canonical Obligation Atom Calibration.

READ ONLY / bugfix to B2.10.

The B2.10 Golden runs exposed two issues:
1) requirement atoms were built from title + description + source_excerpt,
   allowing unrelated surrounding briefing text to contaminate the canonical
   obligation;
2) high-confidence review could be granted from broad/generic atoms with zero
   title-anchor support.

B2.10.1 atomizes the canonical requirement TITLE only, adds explicit obligation
qualifiers, rejects source-role restatements such as BRIEF RECAP, and hardens
the high-confidence review gate.

Nothing is promoted or persisted.
"""

from dataclasses import dataclass
from typing import Any, Mapping
import re
import unicodedata

from project_domain_requirement_consumer import adapt_domain_requirements
from project_requirement_semantic_recall_bridge import (
    run_semantic_recall_bridge,
    semantic_bridge_signal,
)

OBLIGATION_ATOM_VERSION = "V28.7.3B2.10.1"

_EXTRA: dict[str, tuple[str, ...]] = {
    "seeding": ("seeding",),
    "options": ("opcao", "opção", "opcoes", "opções", "option", "options"),
    "queue_free": ("sem filas", "nao gere filas", "não gere filas", "no queues", "queue free", "queue-free"),
    "foreign_guests": ("estrangeiro", "estrangeiros", "foreign guests", "international guests"),
    "english_language": ("em ingles", "em inglês", "in english", "english"),
    "next_day": ("dia seguinte", "next day", "following day"),
    "direct_payment": ("pagamento direto", "pago diretamente", "paid directly", "direct payment"),
    "survey": ("pesquisa", "survey", "questionnaire"),
    "satisfaction": ("satisfacao", "satisfação", "satisfaction"),
    "end_event": ("final do evento", "fim do evento", "event close", "end of the event"),
    "before": ("antes", "before"),
    "report": ("relatorio", "relatório", "report"),
    "results": ("resultado", "resultados", "result", "results"),
    "insights": ("insight", "insights"),
    "kpi": ("kpi", "kpis"),
    "metrics": ("metrica", "métrica", "metricas", "métricas", "metric", "metrics"),
    "creative": ("criativa", "criativo", "creative"),
    "scenario": ("cenario", "cenário", "scenario"),
    "city": ("cidade", "city"),
    "practical_experience": ("na pratica", "na prática", "hands on", "hands-on", "practical experience"),
    "benefits": ("beneficios", "benefícios", "benefit", "benefits", "capabilities"),
    "movement": ("movimento", "movement", "motion"),
    "high_speed": ("alta velocidade", "high speed", "high-speed"),
    "transition": ("transicao", "transição", "transicoes", "transições", "transition", "transitions"),
    "engagement": ("engajamento", "engagement"),
    "publication": ("publicacao", "publicação", "publication", "publish", "publishing", "ready for publication"),
    "visibility": ("visibilidade", "enxergar", "visibility", "visible", "clear view"),
    "seating": ("cadeira", "cadeiras", "banco", "bancos", "assento", "assentos", "seat", "seats", "seating"),
    "flexible": ("flexivel", "flexível", "flexiveis", "flexíveis", "flexible"),
    "communication": ("comunicacao", "comunicação", "communication"),
    "premium": ("premium",),
    "uber": ("uber", "ride voucher", "transport voucher"),
    "product": ("produto", "produtos", "product", "products"),
    "timing": ("timing", "timming", "momento", "momento do gancho"),
    "surprise": ("surpresa", "surprise"),
    "opening": ("abertura", "opening"),
    "experience_area": ("area de experiencias", "área de experiências", "experience area"),
}

_HARD = {
    "options",
    "queue_free",
    "foreign_guests",
    "english_language",
    "next_day",
    "direct_payment",
    "vegan",
    "vegetarian",
}
_WEAK = {
    "guests",
    "content",
    "photo",
    "video",
    "camera",
    "live",
    "gifts",
    "venue",
    "plenary",
    "product",
}
_PRIORITY = {
    "STRICT_SAFE_AUTO_PRESERVED": 0,
    "HIGH_CONFIDENCE_REVIEW_CANDIDATE": 1,
    "PARTIAL_OBLIGATION_COVERAGE": 2,
    "REJECT_SOURCE_ROLE_NON_RESPONSE": 3,
    "REJECT_GENERIC_OVERLAP": 4,
    "NO_CANDIDATE": 5,
}

@dataclass(frozen=True)
class ObligationAtomGateResult:
    project_id: str
    status: str
    scanned_requirement_count: int
    strict_safe_auto_preserved_count: int
    high_confidence_review_count: int
    partial_obligation_coverage_count: int
    source_role_rejected_count: int
    generic_overlap_rejected_count: int
    no_candidate_count: int
    detail_rows: tuple[dict[str, Any], ...]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9$+]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _present(text: str, phrase: str) -> bool:
    return f" {_norm(phrase)} " in f" {_norm(text)} "


def _pipe(value: Any) -> set[str]:
    if value is None:
        return set()
    return {p.strip() for p in str(value).split("|") if p.strip() and p.strip() != "nan"}


def _requirement_atoms(title: str) -> set[str]:
    """Canonical obligation source: TITLE ONLY.

    description/source_excerpt are intentionally excluded because the Golden
    B2.10 run showed that they may contain surrounding briefing context and
    create unrelated atoms.
    """
    signal = semantic_bridge_signal(
        requirement_text=title,
        evidence_text=title,
    )
    atoms = _pipe(signal.get("requirement_concepts"))
    for atom, aliases in _EXTRA.items():
        if any(_present(title, alias) for alias in aliases):
            atoms.add(atom)

    n = f" {_norm(title)} "
    for match in re.finditer(r"\b(\d+)\s*(?:ou mais|or more|\+)", n):
        atoms.add(f"minqty:{match.group(1)}")
    return atoms


def _candidate_atoms(text: str) -> set[str]:
    signal = semantic_bridge_signal(
        requirement_text=text,
        evidence_text=text,
    )
    atoms = _pipe(signal.get("requirement_concepts"))
    for atom, aliases in _EXTRA.items():
        if any(_present(text, alias) for alias in aliases):
            atoms.add(atom)

    n = f" {_norm(text)} "
    if (
        any(x in n for x in (" enviar ", " envio ", " enviado ", " send ", " sent ", " sending ", " delivery ", " deliver "))
        and any(x in n for x in (" influenciador", " influencer", " creator"))
    ):
        atoms.add("seeding")

    for match in re.finditer(r"\b(\d+)\s*(?:ou mais|or more|\+)", n):
        atoms.add(f"minqty:{match.group(1)}")
    return atoms


def _candidate_text(row: Mapping[str, Any]) -> str:
    return str(row.get("evidence_text") or row.get("window_text") or "")


def _source_role_non_response(text: str) -> bool:
    n = _norm(text)
    return (
        "brief recap" in n
        or "our goal" in n
        or "resumo do briefing" in n
    )


def _word_count(text: str) -> int:
    return len(_norm(text).split())


def _classify(requirement_title: str, row: Mapping[str, Any]) -> dict[str, Any]:
    b29 = str(row.get("b29_class") or "")
    text = _candidate_text(row)

    if b29 == "NO_SEMANTIC_RECALL_CANDIDATE" or not text.strip():
        return {
            "b210_class": "NO_CANDIDATE",
            "obligation_atom_coverage": 0.0,
            "requirement_atoms": "",
            "candidate_atoms": "",
            "shared_atoms": "",
            "missing_atoms": "",
            "missing_hard_atoms": "",
        }

    req = _requirement_atoms(requirement_title)
    cand = _candidate_atoms(text)
    shared = req & cand
    missing = req - cand
    hard_missing = {
        atom for atom in missing
        if atom in _HARD or atom.startswith("minqty:")
    }
    coverage = len(shared) / len(req) if req else 0.0
    title_cov = float(row.get("title_anchor_coverage") or 0.0)
    title_words = _word_count(requirement_title)
    specific_shared = shared - _WEAK

    if b29 == "STRICT_SAFE_AUTO_CANDIDATE":
        cls = "STRICT_SAFE_AUTO_PRESERVED"
    elif _source_role_non_response(text):
        cls = "REJECT_SOURCE_ROLE_NON_RESPONSE"
    else:
        single_atom_strong = (
            len(req) == 1
            and coverage >= 1.0
            and title_cov >= 0.40
            and not hard_missing
        )
        short_compound_strong = (
            title_words <= 8
            and len(req) >= 2
            and coverage >= 0.80
            and len(shared) >= 2
            and len(specific_shared) >= 2
            and not hard_missing
        )
        long_compound_strong = (
            title_words > 8
            and len(req) >= 3
            and coverage >= 0.80
            and len(shared) >= 3
            and len(specific_shared) >= 2
            and not hard_missing
        )
        multilingual_complete = (
            len(req) >= 3
            and coverage >= 1.0
            and len(shared) >= 3
            and not hard_missing
        )

        if single_atom_strong or short_compound_strong or long_compound_strong or multilingual_complete:
            cls = "HIGH_CONFIDENCE_REVIEW_CANDIDATE"
        elif shared or title_cov >= 0.20:
            only_generic = bool(shared) and shared.issubset(_WEAK)
            if only_generic and coverage < 0.50 and title_cov < 0.20:
                cls = "REJECT_GENERIC_OVERLAP"
            else:
                cls = "PARTIAL_OBLIGATION_COVERAGE"
        else:
            cls = "REJECT_GENERIC_OVERLAP"

    return {
        "b210_class": cls,
        "requirement_atoms": " | ".join(sorted(req)),
        "candidate_atoms": " | ".join(sorted(cand)),
        "shared_atoms": " | ".join(sorted(shared)),
        "missing_atoms": " | ".join(sorted(missing)),
        "missing_hard_atoms": " | ".join(sorted(hard_missing)),
        "obligation_atom_coverage": round(coverage, 4),
    }


def audit_obligation_atom_coverage(
    *,
    project_id: str,
    current_requirement_rows,
    b29_detail_rows,
) -> ObligationAtomGateResult:
    reqs = adapt_domain_requirements(
        [dict(row) for row in current_requirement_rows]
    )
    req_by_id = {
        str(row.get("stable_key") or row.get("id") or ""): row
        for row in reqs
    }
    candidates: dict[str, list[dict[str, Any]]] = {}
    for raw in b29_detail_rows:
        row = dict(raw)
        rid = str(row.get("requirement_id") or "")
        if rid:
            candidates.setdefault(rid, []).append(row)

    detail = []
    best = {}

    for rid, req in req_by_id.items():
        rows = candidates.get(rid) or [{
            "requirement_id": rid,
            "b29_class": "NO_SEMANTIC_RECALL_CANDIDATE",
        }]
        title = str(req.get("title") or "")
        classified = []

        for row in rows:
            result = _classify(title, row)
            classified.append({
                "requirement_id": rid,
                "title": title,
                "source_b29_class": row.get("b29_class"),
                **result,
                "title_anchor_coverage": row.get("title_anchor_coverage"),
                "evidence_id": row.get("evidence_id"),
                "evidence_source": row.get("evidence_source"),
                "evidence_locator": row.get("evidence_locator"),
                "candidate_text": _candidate_text(row),
            })

        classified.sort(
            key=lambda item: (
                _PRIORITY.get(item["b210_class"], 99),
                -float(item.get("obligation_atom_coverage") or 0),
                -float(item.get("title_anchor_coverage") or 0),
                str(item.get("evidence_locator") or ""),
            )
        )
        best[rid] = classified[0]["b210_class"]

        # Keep at most two review candidates per requirement to reduce review noise.
        detail.extend(classified[:2])

    strict = sum(v == "STRICT_SAFE_AUTO_PRESERVED" for v in best.values())
    high = sum(v == "HIGH_CONFIDENCE_REVIEW_CANDIDATE" for v in best.values())
    partial = sum(v == "PARTIAL_OBLIGATION_COVERAGE" for v in best.values())
    source_rejected = sum(v == "REJECT_SOURCE_ROLE_NON_RESPONSE" for v in best.values())
    generic_rejected = sum(v == "REJECT_GENERIC_OVERLAP" for v in best.values())
    none = sum(v == "NO_CANDIDATE" for v in best.values())

    status = (
        "PASS_WITH_STRICT_SAFE_RECALL"
        if strict
        else "PASS_WITH_HIGH_CONFIDENCE_REVIEWS"
        if high
        else "PASS_WITH_PARTIAL_REVIEWS"
        if partial
        else "PASS_NO_ACTIONABLE_RECALL"
    )

    detail.sort(
        key=lambda item: (
            _PRIORITY.get(item["b210_class"], 99),
            str(item.get("title") or "").casefold(),
        )
    )

    return ObligationAtomGateResult(
        project_id=str(project_id),
        status=status,
        scanned_requirement_count=len(best),
        strict_safe_auto_preserved_count=strict,
        high_confidence_review_count=high,
        partial_obligation_coverage_count=partial,
        source_role_rejected_count=source_rejected,
        generic_overlap_rejected_count=generic_rejected,
        no_candidate_count=none,
        detail_rows=tuple(detail),
    )


def run_obligation_atom_gate(
    client: Any,
    *,
    project_id: str,
) -> ObligationAtomGateResult:
    from project_domain_reader import read_domain

    b29 = run_semantic_recall_bridge(
        client,
        project_id=project_id,
    )
    domain = read_domain(
        client,
        project_id,
        "requirements",
        legacy_loader=lambda: [],
        audit=False,
    )
    if str(domain.read_mode) != "shadow_compare":
        raise RuntimeError(
            f"B2.10.1 BLOCKED: requirements read_mode={domain.read_mode}"
        )

    ids = {
        str(row.get("requirement_id") or "")
        for row in b29.detail_rows
        if row.get("requirement_id")
    }
    current = [
        dict(row)
        for row in (domain.domain_candidate or [])
        if isinstance(row, Mapping)
        and str(row.get("id") or row.get("stable_key") or "") in ids
    ]

    return audit_obligation_atom_coverage(
        project_id=project_id,
        current_requirement_rows=current,
        b29_detail_rows=[
            dict(row) for row in b29.detail_rows
        ],
    )
