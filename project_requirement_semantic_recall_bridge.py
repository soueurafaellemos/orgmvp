from __future__ import annotations

"""NAVE V28.7.3B2.9 — Multilingual Semantic Recall Bridge Shadow.

READ ONLY / diagnostic only.

B2.8 exposed two limits:
- one shared atom can incorrectly promote a compound requirement;
- PT briefing requirements vs EN proposal evidence creates systematic under-recall.

B2.9 therefore:
1) hardens automatic acceptance for compound canonical titles;
2) surfaces PT↔EN / paraphrase candidates as REVIEW ONLY;
3) surfaces adjacent-page context windows as REVIEW ONLY.

No response is persisted or promoted by this module.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re
import unicodedata

from project_domain_requirement_consumer import adapt_domain_requirements
from project_requirement_response_contract_canary import run_response_contract_canary

SEMANTIC_RECALL_BRIDGE_VERSION = "V28.7.3B2.9"

# Generic event-production concept bridge. This can only create REVIEW candidates.
_CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "invitation": ("convite", "convites", "invitation", "invitations", "online invitation"),
    "save_the_date": ("save the date", "std"),
    "reminder": ("reminder", "lembrete", "lembretes"),
    "press_kit": ("press kit", "presskit", "kit de imprensa"),
    "seeding": ("seeding", "envio para influenciadores", "enviar para influenciadores", "influencer sendout"),
    "streaming": ("streaming", "transmissao", "transmissão", "livestream", "live stream", "broadcast"),
    "live": ("ao vivo", "live"),
    "recording": ("gravacao", "gravação", "recording", "recorded"),
    "stage": ("palco", "stage"),
    "screen": ("tela", "screen", "led screen", "led wall"),
    "plenary": ("plenaria", "plenária", "plenary"),
    "reception": ("recepcao", "recepção", "reception", "welcome area"),
    "registration": ("credenciamento", "registration", "check in", "check-in"),
    "gifts": ("brinde", "brindes", "gift", "gifts", "giveaway", "giveaways"),
    "guests": ("convidado", "convidados", "guest", "guests"),
    "content": ("conteudo", "conteúdo", "content"),
    "camera": ("camera", "câmera", "cameras", "câmeras"),
    "photo": ("foto", "fotos", "fotografia", "photo", "photos", "photography"),
    "video": ("video", "vídeo", "videos", "vídeos"),
    "travel": ("viagem", "viagens", "travel", "travelling", "traveling"),
    "partnership": ("parceria", "parcerias", "partnership", "partnerships"),
    "budget": ("budget", "orcamento", "orçamento"),
    "direct_payment": ("pagamento direto", "pago diretamente", "paid directly", "direct payment"),
    "food_beverage": ("a&b", "f&b", "alimentacao", "alimentação", "food and beverage", "food & beverage"),
    "vegan": ("vegano", "vegana", "vegan"),
    "vegetarian": ("vegetariano", "vegetariana", "vegetarian"),
    "bilingual": ("bilingue", "bilíngue", "bilingual"),
    "promoter": ("promotor", "promotores", "promoter", "promoters", "promotional staff"),
    "monitor": ("monitor", "monitores", "facilitator", "facilitators"),
    "storytelling": ("storytelling", "narrativa", "narrative"),
    "detailed": ("detalhado", "detalhada", "detailed", "in depth", "in-depth", "deeper"),
    "portrait": ("retrato", "retratos", "portrait", "portraits"),
    "lighting": ("iluminacao", "iluminação", "lighting"),
    "instagrammable": ("instagramavel", "instagramável", "instagrammable"),
    "backstage": ("bastidores", "backstage", "behind the scenes"),
    "vip": ("vip", "a-list", "a list"),
    "show": ("show", "performance", "apresentacao musical", "apresentação musical"),
    "logistics": ("logistica", "logística", "logistics"),
    "storage": ("armazenamento", "storage"),
    "valet": ("valet", "estacionamento com manobrista"),
    "executive_car": ("carro executivo", "executive car", "private car"),
}


@dataclass(frozen=True)
class SemanticRecallBridgeResult:
    project_id: str
    status: str
    current_requirement_count: int
    already_verified_response_count: int
    scanned_requirement_count: int
    old_permissive_auto_count: int
    strict_safe_auto_count: int
    downgraded_compound_atom_count: int
    multilingual_review_requirement_count: int
    context_window_review_requirement_count: int
    remaining_no_candidate_count: int
    detail_rows: tuple[dict[str, Any], ...]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9&+]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _distinctive_tokens(value: str) -> set[str]:
    from project_intelligence_unified import _distinctive_tokens as fn
    return set(fn(value))


def strict_entailment_signal(
    *,
    requirement_title: str,
    evidence_text: str,
) -> dict[str, Any]:
    title_tokens = _distinctive_tokens(requirement_title)
    evidence_tokens = _distinctive_tokens(evidence_text)
    shared = title_tokens & evidence_tokens
    coverage = len(shared) / max(1, len(title_tokens)) if title_tokens else 0.0
    exact = bool(_norm(requirement_title)) and _norm(requirement_title) in _norm(evidence_text)
    evidence_word_count = len(_norm(evidence_text).split())
    heading_like = evidence_word_count <= 4 and len(str(evidence_text or "")) <= 80

    old_permissive_auto = (
        bool(shared)
        and len(title_tokens) <= 2
        and not heading_like
        and (exact or coverage >= 0.5)
    ) or (
        len(shared) >= 2 and coverage >= 0.5 and not heading_like
    )

    # Hardened rule:
    # - one-token canonical title may be explicit-atom safe;
    # - two-token compound title needs full coverage or exact phrase;
    # - longer titles retain the >=50% + >=2-anchor rule.
    if heading_like:
        strict_auto = False
        reason = "heading_only"
    elif len(title_tokens) == 1 and coverage >= 1.0:
        strict_auto = True
        reason = "single_atomic_requirement"
    elif len(title_tokens) == 2 and (coverage >= 1.0 or exact):
        strict_auto = True
        reason = "compound_two_anchor_fully_covered"
    elif len(title_tokens) >= 3 and len(shared) >= 2 and coverage >= 0.5:
        strict_auto = True
        reason = "canonical_anchor_support"
    else:
        strict_auto = False
        reason = "insufficient_strict_canonical_support"

    return {
        "title_anchor_count": len(title_tokens),
        "shared_anchor_count": len(shared),
        "title_anchor_coverage": round(coverage, 4),
        "shared_title_tokens": " | ".join(sorted(shared)),
        "exact_title_phrase": exact,
        "heading_like": heading_like,
        "old_permissive_auto": old_permissive_auto,
        "strict_auto": strict_auto,
        "strict_reason": reason,
    }


def _phrase_present(text: str, phrase: str) -> bool:
    nt = f" {_norm(text)} "
    np = _norm(phrase)
    return bool(np) and f" {np} " in nt


def _concepts(text: str) -> set[str]:
    found: set[str] = set()
    for concept, aliases in _CONCEPT_GROUPS.items():
        if any(_phrase_present(text, alias) for alias in aliases):
            found.add(concept)
    return found


def semantic_bridge_signal(
    *,
    requirement_text: str,
    evidence_text: str,
) -> dict[str, Any]:
    req = _concepts(requirement_text)
    ev = _concepts(evidence_text)
    shared = req & ev
    coverage = len(shared) / len(req) if req else 0.0

    # Review only. One concept is too noisy; require at least two.
    review = len(shared) >= 2 and (coverage >= 0.4 or len(shared) >= 3)

    return {
        "requirement_concepts": " | ".join(sorted(req)),
        "evidence_concepts": " | ".join(sorted(ev)),
        "shared_concepts": " | ".join(sorted(shared)),
        "concept_coverage": round(coverage, 4),
        "review": review,
    }


def _proposal_evidence(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    from project_intelligence_unified import _evidence_ref, _role_maps

    graph = snapshot.get("intelligence_graph") or {}
    roles, assets = _role_maps(graph)
    rows: list[dict[str, Any]] = []
    for raw in graph.get("evidence_units") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        asset_id = str(row.get("source_asset_id") or "")
        if not (
            {"proposal_presentation", "final_presentation"}
            & set(roles.get(asset_id, set()))
        ):
            continue
        if not str(row.get("content_text") or "").strip():
            continue
        ref = _evidence_ref(row, assets, roles)
        ref["ordinal"] = row.get("ordinal")
        rows.append(ref)

    rows.sort(
        key=lambda r: (
            str(r.get("source_name") or "").casefold(),
            int(r.get("ordinal") or 10**9),
            str(r.get("evidence_id") or ""),
        )
    )
    return rows


def _windows(evidence_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for raw in evidence_rows:
        row = dict(raw)
        by_source.setdefault(str(row.get("source_name") or ""), []).append(row)

    output: list[dict[str, Any]] = []
    for source, rows in by_source.items():
        rows.sort(key=lambda r: (int(r.get("ordinal") or 10**9), str(r.get("evidence_id") or "")))
        for i, center in enumerate(rows):
            neighbors = rows[max(0, i - 1): min(len(rows), i + 2)]
            text = "\n".join(
                str(n.get("text") or "").strip()
                for n in neighbors
                if str(n.get("text") or "").strip()
            )
            if text:
                output.append({
                    "source_name": source,
                    "center_evidence_id": center.get("evidence_id"),
                    "center_locator": center.get("locator_text"),
                    "window_text": text,
                    "window_size": len(neighbors),
                })
    return output


def audit_semantic_recall_bridge(
    *,
    project_id: str,
    current_requirement_rows: Sequence[Mapping[str, Any]],
    current_contract_rows: Sequence[Mapping[str, Any]],
    proposal_evidence_rows: Sequence[Mapping[str, Any]],
) -> SemanticRecallBridgeResult:
    requirements = adapt_domain_requirements([dict(r) for r in current_requirement_rows])
    contract = {
        str(r.get("requirement_id") or ""): dict(r)
        for r in current_contract_rows
        if r.get("requirement_id")
    }
    windows = _windows(proposal_evidence_rows)

    details: list[dict[str, Any]] = []
    already_verified = 0
    scanned = 0
    old_auto_reqs: set[str] = set()
    strict_auto_reqs: set[str] = set()
    downgraded_reqs: set[str] = set()
    multilingual_reqs: set[str] = set()
    window_reqs: set[str] = set()
    no_candidate_reqs: set[str] = set()

    for req in requirements:
        req_id = str(req.get("stable_key") or "")
        current_status = str(
            contract.get(req_id, {}).get(
                "response_contract_status",
                "no_verified_response",
            )
        )
        if current_status == "verified_response":
            already_verified += 1
            continue

        scanned += 1
        title = str(req.get("title") or "")
        req_text = " ".join(
            str(req.get(k) or "")
            for k in ("title", "description", "source_excerpt")
        ).strip()

        useful = False
        best_strict: list[dict[str, Any]] = []
        best_bridge: list[dict[str, Any]] = []

        for ev in proposal_evidence_rows:
            ev_text = str(ev.get("text") or "")
            strict = strict_entailment_signal(
                requirement_title=title,
                evidence_text=ev_text,
            )
            bridge = semantic_bridge_signal(
                requirement_text=req_text,
                evidence_text=ev_text,
            )

            if strict["old_permissive_auto"]:
                old_auto_reqs.add(req_id)

            if strict["strict_auto"]:
                strict_auto_reqs.add(req_id)
                useful = True
                best_strict.append({
                    "requirement_id": req_id,
                    "title": title,
                    "current_response_contract_status": current_status,
                    "b29_class": "STRICT_SAFE_AUTO_CANDIDATE",
                    **strict,
                    "shared_concepts": bridge["shared_concepts"],
                    "concept_coverage": bridge["concept_coverage"],
                    "evidence_id": ev.get("evidence_id"),
                    "evidence_source": ev.get("source_name"),
                    "evidence_locator": ev.get("locator_text"),
                    "evidence_text": ev_text,
                })
            elif strict["old_permissive_auto"]:
                downgraded_reqs.add(req_id)
                useful = True
                details.append({
                    "requirement_id": req_id,
                    "title": title,
                    "current_response_contract_status": current_status,
                    "b29_class": "DOWNGRADED_COMPOUND_ATOM_REVIEW",
                    **strict,
                    "shared_concepts": bridge["shared_concepts"],
                    "concept_coverage": bridge["concept_coverage"],
                    "evidence_id": ev.get("evidence_id"),
                    "evidence_source": ev.get("source_name"),
                    "evidence_locator": ev.get("locator_text"),
                    "evidence_text": ev_text,
                })

            if bridge["review"] and not strict["strict_auto"]:
                multilingual_reqs.add(req_id)
                useful = True
                best_bridge.append({
                    "requirement_id": req_id,
                    "title": title,
                    "current_response_contract_status": current_status,
                    "b29_class": "MULTILINGUAL_SEMANTIC_BRIDGE_REVIEW",
                    **strict,
                    "shared_concepts": bridge["shared_concepts"],
                    "concept_coverage": bridge["concept_coverage"],
                    "evidence_id": ev.get("evidence_id"),
                    "evidence_source": ev.get("source_name"),
                    "evidence_locator": ev.get("locator_text"),
                    "evidence_text": ev_text,
                })

        best_strict.sort(
            key=lambda r: (
                -float(r.get("title_anchor_coverage") or 0.0),
                str(r.get("evidence_locator") or ""),
            )
        )
        details.extend(best_strict[:3])

        best_bridge.sort(
            key=lambda r: (
                -float(r.get("concept_coverage") or 0.0),
                -float(r.get("title_anchor_coverage") or 0.0),
                str(r.get("evidence_locator") or ""),
            )
        )
        details.extend(best_bridge[:3])

        # Adjacent-page context is review only.
        window_candidates: list[dict[str, Any]] = []
        for w in windows:
            strict = strict_entailment_signal(
                requirement_title=title,
                evidence_text=str(w.get("window_text") or ""),
            )
            bridge = semantic_bridge_signal(
                requirement_text=req_text,
                evidence_text=str(w.get("window_text") or ""),
            )
            # Adjacent-page context is review-only, so one strong shared concept
            # can be enough to surface a window when it covers at least half of the
            # requirement's controlled concepts (e.g. PRESS KIT heading + next page).
            req_concepts = set(
                part.strip()
                for part in str(bridge.get("requirement_concepts") or "").split("|")
                if part.strip()
            )
            shared_concepts = set(
                part.strip()
                for part in str(bridge.get("shared_concepts") or "").split("|")
                if part.strip()
            )
            window_single_concept_review = (
                len(shared_concepts) >= 1
                and bool(req_concepts)
                and float(bridge.get("concept_coverage") or 0.0) >= 0.5
            )
            if (
                not strict["strict_auto"]
                and not bridge["review"]
                and not window_single_concept_review
            ):
                continue
            window_reqs.add(req_id)
            useful = True
            window_candidates.append({
                "requirement_id": req_id,
                "title": title,
                "current_response_contract_status": current_status,
                "b29_class": "CONTEXT_WINDOW_REVIEW",
                **strict,
                "shared_concepts": bridge["shared_concepts"],
                "concept_coverage": bridge["concept_coverage"],
                "evidence_id": w.get("center_evidence_id"),
                "evidence_source": w.get("source_name"),
                "evidence_locator": w.get("center_locator"),
                "evidence_text": None,
                "window_text": w.get("window_text"),
                "window_size": w.get("window_size"),
            })
        window_candidates.sort(
            key=lambda r: (
                -float(r.get("title_anchor_coverage") or 0.0),
                -float(r.get("concept_coverage") or 0.0),
                str(r.get("evidence_locator") or ""),
            )
        )
        details.extend(window_candidates[:2])

        if not useful:
            no_candidate_reqs.add(req_id)
            details.append({
                "requirement_id": req_id,
                "title": title,
                "current_response_contract_status": current_status,
                "b29_class": "NO_SEMANTIC_RECALL_CANDIDATE",
                "evidence_id": None,
                "evidence_source": None,
                "evidence_locator": None,
                "evidence_text": None,
            })

    if strict_auto_reqs:
        status = "PASS_WITH_STRICT_SAFE_RECALL"
    elif multilingual_reqs or window_reqs or downgraded_reqs:
        status = "PASS_WITH_SEMANTIC_RECALL_REVIEW"
    else:
        status = "PASS_NO_SAFE_SEMANTIC_RECALL"

    details.sort(
        key=lambda r: (
            str(r.get("b29_class") or ""),
            str(r.get("title") or "").casefold(),
            str(r.get("evidence_locator") or ""),
        )
    )

    return SemanticRecallBridgeResult(
        project_id=str(project_id),
        status=status,
        current_requirement_count=len(requirements),
        already_verified_response_count=already_verified,
        scanned_requirement_count=scanned,
        old_permissive_auto_count=len(old_auto_reqs),
        strict_safe_auto_count=len(strict_auto_reqs),
        downgraded_compound_atom_count=len(downgraded_reqs),
        multilingual_review_requirement_count=len(multilingual_reqs),
        context_window_review_requirement_count=len(window_reqs),
        remaining_no_candidate_count=len(no_candidate_reqs),
        detail_rows=tuple(details),
    )


def run_semantic_recall_bridge(
    client: Any,
    *,
    project_id: str,
) -> SemanticRecallBridgeResult:
    from project_domain_reader import read_domain
    from project_workspace_db import fetch_project_workspace_snapshot

    contract = run_response_contract_canary(client, project_id=project_id)

    domain_read = read_domain(
        client,
        project_id,
        "requirements",
        legacy_loader=lambda: [],
        audit=False,
    )
    if str(domain_read.read_mode) != "shadow_compare":
        raise RuntimeError(
            f"B2.9 BLOCKED: requirements read_mode={domain_read.read_mode}"
        )

    snapshot = fetch_project_workspace_snapshot(
        client,
        project_id=project_id,
    )
    evidence = _proposal_evidence(snapshot)

    return audit_semantic_recall_bridge(
        project_id=project_id,
        current_requirement_rows=[
            dict(r)
            for r in (domain_read.domain_candidate or [])
            if isinstance(r, Mapping)
        ],
        current_contract_rows=[
            dict(r) for r in contract.requirement_rows
        ],
        proposal_evidence_rows=evidence,
    )
