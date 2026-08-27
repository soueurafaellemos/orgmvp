from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re
import unicodedata

from project_domain_requirement_consumer import adapt_domain_requirements
from project_requirement_semantic_recall_bridge import run_semantic_recall_bridge, semantic_bridge_signal

OBLIGATION_ATOM_VERSION = "V28.7.3B2.10"

_EXTRA = {
    "seeding": ("seeding",),
    "options": ("opcao", "opção", "opcoes", "opções", "option", "options"),
    "queue_free": ("sem filas", "nao gere filas", "não gere filas", "no queues", "queue free", "queue-free"),
    "foreign_guests": ("estrangeiro", "estrangeiros", "foreign guests", "international guests"),
    "english_language": ("em ingles", "em inglês", "in english", "english"),
    "next_day": ("dia seguinte", "next day", "following day"),
    "direct_payment": ("pagamento direto", "pago diretamente", "paid directly", "direct payment"),
}
_HARD = {"options", "queue_free", "foreign_guests", "english_language", "next_day", "direct_payment", "vegan", "vegetarian"}
_WEAK = {"guests", "content", "photo", "video", "camera", "live", "gifts", "venue"}
_PRIORITY = {
    "STRICT_SAFE_AUTO_PRESERVED": 0,
    "HIGH_CONFIDENCE_REVIEW_CANDIDATE": 1,
    "PARTIAL_OBLIGATION_COVERAGE": 2,
    "REJECT_GENERIC_OVERLAP": 3,
    "NO_CANDIDATE": 4,
}

@dataclass(frozen=True)
class ObligationAtomGateResult:
    project_id: str
    status: str
    scanned_requirement_count: int
    strict_safe_auto_preserved_count: int
    high_confidence_review_count: int
    partial_obligation_coverage_count: int
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
    return {p.strip() for p in str(value or "").split("|") if p.strip()}


def _atoms(text: str) -> set[str]:
    signal = semantic_bridge_signal(requirement_text=text, evidence_text=text)
    atoms = _pipe(signal.get("requirement_concepts"))
    for atom, aliases in _EXTRA.items():
        if any(_present(text, alias) for alias in aliases):
            atoms.add(atom)
    n = f" {_norm(text)} "
    if any(x in n for x in (" enviar ", " envio ", " send ", " sent ", " delivery ")) and any(x in n for x in (" influenciador", " influencer", " creator")):
        atoms.add("seeding")
    for m in re.finditer(r"\b(\d+)\s*(?:ou mais|or more|\+)", n):
        atoms.add(f"minqty:{m.group(1)}")
    return atoms


def _candidate_text(row: Mapping[str, Any]) -> str:
    return str(row.get("evidence_text") or row.get("window_text") or "")


def _classify(requirement_text: str, row: Mapping[str, Any]) -> dict[str, Any]:
    b29 = str(row.get("b29_class") or "")
    text = _candidate_text(row)
    if b29 == "NO_SEMANTIC_RECALL_CANDIDATE" or not text.strip():
        return {"b210_class": "NO_CANDIDATE", "obligation_atom_coverage": 0.0, "requirement_atoms": "", "candidate_atoms": "", "shared_atoms": "", "missing_atoms": "", "missing_hard_atoms": ""}

    req = _atoms(requirement_text)
    cand = _atoms(text)
    shared = req & cand
    missing = req - cand
    hard_missing = {a for a in missing if a in _HARD or a.startswith("minqty:")}
    coverage = len(shared) / len(req) if req else 0.0
    title_cov = float(row.get("title_anchor_coverage") or 0.0)

    if b29 == "STRICT_SAFE_AUTO_CANDIDATE":
        cls = "STRICT_SAFE_AUTO_PRESERVED"
    elif len(req) >= 2 and coverage >= 0.8 and len(shared) >= 2 and not hard_missing:
        cls = "HIGH_CONFIDENCE_REVIEW_CANDIDATE"
    elif shared or title_cov >= 0.2:
        only_generic = bool(shared) and shared.issubset(_WEAK)
        cls = "REJECT_GENERIC_OVERLAP" if only_generic and coverage < 0.5 and title_cov < 0.2 else "PARTIAL_OBLIGATION_COVERAGE"
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


def audit_obligation_atom_coverage(*, project_id: str, current_requirement_rows, b29_detail_rows) -> ObligationAtomGateResult:
    reqs = adapt_domain_requirements([dict(r) for r in current_requirement_rows])
    req_by_id = {str(r.get("stable_key") or r.get("id") or ""): r for r in reqs}
    candidates: dict[str, list[dict[str, Any]]] = {}
    for raw in b29_detail_rows:
        row = dict(raw)
        rid = str(row.get("requirement_id") or "")
        if rid:
            candidates.setdefault(rid, []).append(row)

    detail = []
    best = {}
    for rid, req in req_by_id.items():
        rows = candidates.get(rid) or [{"requirement_id": rid, "b29_class": "NO_SEMANTIC_RECALL_CANDIDATE"}]
        requirement_text = " ".join(str(req.get(k) or "") for k in ("title", "description", "source_excerpt"))
        classified = []
        for row in rows:
            result = _classify(requirement_text, row)
            classified.append({
                "requirement_id": rid,
                "title": req.get("title"),
                "source_b29_class": row.get("b29_class"),
                **result,
                "title_anchor_coverage": row.get("title_anchor_coverage"),
                "evidence_id": row.get("evidence_id"),
                "evidence_source": row.get("evidence_source"),
                "evidence_locator": row.get("evidence_locator"),
                "candidate_text": _candidate_text(row),
            })
        classified.sort(key=lambda x: (_PRIORITY.get(x["b210_class"], 99), -float(x.get("obligation_atom_coverage") or 0), str(x.get("evidence_locator") or "")))
        best[rid] = classified[0]["b210_class"]
        detail.extend(classified[:3])

    strict = sum(v == "STRICT_SAFE_AUTO_PRESERVED" for v in best.values())
    high = sum(v == "HIGH_CONFIDENCE_REVIEW_CANDIDATE" for v in best.values())
    partial = sum(v == "PARTIAL_OBLIGATION_COVERAGE" for v in best.values())
    rejected = sum(v == "REJECT_GENERIC_OVERLAP" for v in best.values())
    none = sum(v == "NO_CANDIDATE" for v in best.values())
    status = "PASS_WITH_STRICT_SAFE_RECALL" if strict else "PASS_WITH_HIGH_CONFIDENCE_REVIEWS" if high else "PASS_WITH_PARTIAL_REVIEWS" if partial else "PASS_NO_ACTIONABLE_RECALL"
    detail.sort(key=lambda x: (_PRIORITY.get(x["b210_class"], 99), str(x.get("title") or "").casefold()))
    return ObligationAtomGateResult(str(project_id), status, len(best), strict, high, partial, rejected, none, tuple(detail))


def run_obligation_atom_gate(client: Any, *, project_id: str) -> ObligationAtomGateResult:
    from project_domain_reader import read_domain

    b29 = run_semantic_recall_bridge(client, project_id=project_id)
    domain = read_domain(client, project_id, "requirements", legacy_loader=lambda: [], audit=False)
    if str(domain.read_mode) != "shadow_compare":
        raise RuntimeError(f"B2.10 BLOCKED: requirements read_mode={domain.read_mode}")
    ids = {str(r.get("requirement_id") or "") for r in b29.detail_rows if r.get("requirement_id")}
    current = [dict(r) for r in (domain.domain_candidate or []) if isinstance(r, Mapping) and str(r.get("id") or r.get("stable_key") or "") in ids]
    return audit_obligation_atom_coverage(project_id=project_id, current_requirement_rows=current, b29_detail_rows=[dict(r) for r in b29.detail_rows])
