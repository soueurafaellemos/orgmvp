from __future__ import annotations

"""NAVE V28.7.3B2.12.2 — Semantic Eligibility & Core Obligation Hardening.

READ ONLY / shadow only.

B2.12.2 is a governed hardening boundary over the B2 response chain. It does four
things before any future Truth-effect phase may be designed:

1) removes semantically ineligible/no-domain Requirement identities from response
   adjudication without mutating their historical records;
2) derives a source-bounded canonical obligation text so truncated display titles do
   not define obligation atoms;
3) recalibrates the B2.10 atom gate against that canonical obligation;
4) applies locality-aware core-obligation guards before machine recommendation.

Nothing in this module creates Human Review, changes Requirement Truth, persists a
response, changes read_mode/canaries, or approves cutover.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import re
import unicodedata

from project_domain_requirement_consumer import adapt_domain_requirements
from project_requirement_response_contract_canary import run_response_contract_canary
from project_requirement_semantic_recall_bridge import run_semantic_recall_bridge
from project_requirement_obligation_atom_gate import (
    _classify as _classify_obligation_candidate,
    _PRIORITY as _OBLIGATION_PRIORITY,
)
from project_requirement_response_recall_review_projection import _project_status
from project_requirement_auto_adjudication_recommendation import (
    recommend_candidate as _b2121_recommend_candidate,
)
from project_requirement_semantic_eligibility import (
    RequirementSemanticEligibility,
    resolve_requirement_semantics,
)

SEMANTIC_HARDENING_VERSION = "V28.7.3B2.12.2"

RECOMMEND_CONFIRM = "recommend_confirm"
RECOMMEND_PARTIAL = "recommend_partial"
RECOMMEND_REJECT = "recommend_reject"
RECOMMEND_VISUAL_REVIEW = "recommend_visual_review"
RECOMMEND_DEFER = "recommend_defer"

_REVIEW_STATUSES = {
    "response_review_high_confidence",
    "response_review_visual_or_structured_evidence",
    "response_review_partial",
    "response_review_existing_evidence",
}


@dataclass(frozen=True)
class SemanticHardenedAdjudication:
    project_id: str
    status: str
    current_requirement_count_before_semantic_gate: int
    semantic_eligible_requirement_count: int
    semantic_excluded_no_domain_count: int
    semantic_unknown_count: int
    queue_count: int
    recommend_confirm_count: int
    recommend_partial_count: int
    recommend_reject_count: int
    recommend_visual_review_count: int
    recommend_defer_count: int
    recommendation_rows: tuple[dict[str, Any], ...]
    semantic_excluded_rows: tuple[dict[str, Any], ...]
    projection_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SEMANTIC_HARDENING_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "current_requirement_count_before_semantic_gate": self.current_requirement_count_before_semantic_gate,
            "semantic_eligible_requirement_count": self.semantic_eligible_requirement_count,
            "semantic_excluded_no_domain_count": self.semantic_excluded_no_domain_count,
            "semantic_unknown_count": self.semantic_unknown_count,
            "queue_count": self.queue_count,
            "recommend_confirm_count": self.recommend_confirm_count,
            "recommend_partial_count": self.recommend_partial_count,
            "recommend_reject_count": self.recommend_reject_count,
            "recommend_visual_review_count": self.recommend_visual_review_count,
            "recommend_defer_count": self.recommend_defer_count,
            "adjudicator_type": "machine_rule_engine_semantic_hardening",
            "human_review_created": False,
            "truth_changed": False,
            "persistence_performed": False,
            "cutover_approved": False,
            "recommendation_rows": list(self.recommendation_rows),
            "semantic_excluded_rows": list(self.semantic_excluded_rows),
            "projection_rows": list(self.projection_rows),
        }


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9$+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_any(text: Any, terms: Sequence[str]) -> bool:
    norm = f" {_norm(text)} "
    return any(f" {_norm(term)} " in norm for term in terms if _norm(term))


def _segments(text: str) -> list[str]:
    """Local semantic segments: no whole-window lexical shortcut."""
    out: list[str] = []
    for line in re.split(r"[\r\n]+", str(text or "")):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?;])\s+", line)
        for part in parts:
            part = re.sub(r"\s+", " ", part).strip(" \t•·-")
            if part:
                out.append(part)
    return out


def _clean_stage_idiom(text: str) -> str:
    # "set the stage for..." is idiomatic and must not satisfy a physical-stage atom.
    return re.sub(r"\bset\s+the\s+stage\b", " ", str(text or ""), flags=re.I)


def _core_obligation_guard(
    canonical_obligation_text: str,
    evidence_text: str,
) -> tuple[str, float, str, str] | None:
    """Locality-aware, domain-generic guards for compound core obligations."""

    requirement = str(canonical_obligation_text or "")
    evidence = str(evidence_text or "")
    segments = _segments(evidence)

    # ------------------------------------------------------------------
    # Financial obligations: a service/item mention is not a budget answer.
    # ------------------------------------------------------------------
    financial_req_terms = (
        "orcamento", "orçamento", "budget", "verba", "custo", "custos", "cost",
        "costs", "price", "preco", "preço", "pagamento", "payment",
        "cotacao", "cotação", "quotation",
    )
    financial_evidence_terms = (
        "orcamento", "orçamento", "budget", "verba", "custo", "custos", "cost",
        "costs", "valor", "valores", "price", "preco", "preço", "pagamento",
        "payment", "cotacao", "cotação", "quotation", "fee", "fees", "$", "r$",
    )
    if _contains_any(requirement, financial_req_terms):
        if not any(_contains_any(seg, financial_evidence_terms) for seg in segments):
            return (
                RECOMMEND_REJECT,
                0.99,
                "missing_core_financial_obligation",
                "A requirement é financeira/orçamentária, mas a evidência não apresenta custo, verba, valor, cotação ou condição de pagamento.",
            )

    # ------------------------------------------------------------------
    # Travel activation: a travel-themed press kit is not an activation.
    # Require the relation locally, never by words in unrelated paragraphs.
    # ------------------------------------------------------------------
    travel_terms = ("viagem", "viagens", "travel", "travelling", "traveling")
    activation_req_terms = (
        "ativacao", "ativação", "activation", "experiencia", "experiência",
        "experience", "experimentacao", "experimentação", "hands-on", "hands on",
    )
    product_req_terms = ("produto", "product", "smartphone", "device", "camera", "câmera")
    if _contains_any(requirement, travel_terms) and (
        _contains_any(requirement, activation_req_terms)
        or _contains_any(requirement, product_req_terms)
    ):
        local_support = False
        travel_activation_without_product = False
        travel_presskit = False
        for seg in segments:
            if not _contains_any(seg, travel_terms):
                continue
            normalized_seg = re.sub(r"\bpr\s+activation\b", " ", seg, flags=re.I)
            is_activation = _contains_any(normalized_seg, activation_req_terms)
            has_product = _contains_any(normalized_seg, product_req_terms) or bool(
                re.search(r"\b[A-Za-z]{1,8}\s*\d{2,}[A-Za-z0-9-]*\b", normalized_seg)
            )
            travel_presskit = travel_presskit or _contains_any(seg, ("press kit", "presskit", "kit de imprensa"))
            if is_activation and has_product:
                local_support = True
                break
            if is_activation:
                travel_activation_without_product = True

        if not local_support:
            if travel_presskit:
                return (
                    RECOMMEND_REJECT,
                    0.99,
                    "travel_presskit_not_product_activation",
                    "A temática de viagem aparece em press kit/comunicação, não em uma ativação localmente ligada à experimentação do produto.",
                )
            if travel_activation_without_product:
                return (
                    RECOMMEND_PARTIAL,
                    0.96,
                    "travel_activation_missing_product_experimentation",
                    "Há ativação com temática de viagem, mas a evidência local não comprova a experimentação de produto exigida.",
                )
            return (
                RECOMMEND_REJECT,
                0.98,
                "missing_core_travel_product_activation",
                "A evidência não apresenta, no mesmo contexto semântico, temática de viagem + ativação/experiência de produto.",
            )

    # ------------------------------------------------------------------
    # Physical stage + LED/screen: "set the stage" is not scenic infrastructure.
    # ------------------------------------------------------------------
    stage_terms = ("palco", "stage")
    screen_terms = ("led", "led screen", "led wall", "tela", "screen")
    if _contains_any(requirement, stage_terms) and _contains_any(requirement, screen_terms):
        local_pair = False
        stage_any = False
        screen_any = False
        for seg in segments:
            clean = _clean_stage_idiom(seg)
            has_stage = _contains_any(clean, stage_terms)
            has_screen = _contains_any(clean, screen_terms)
            stage_any = stage_any or has_stage
            screen_any = screen_any or has_screen
            if has_stage and has_screen:
                local_pair = True
                break
        if not local_pair:
            if stage_any or screen_any:
                return (
                    RECOMMEND_PARTIAL,
                    0.97,
                    "physical_stage_led_not_jointly_supported",
                    "Há menção isolada a palco ou tela/LED, mas a estrutura física de palco + LED exigida não está comprovada no mesmo contexto.",
                )
            return (
                RECOMMEND_REJECT,
                0.98,
                "missing_core_physical_stage_led",
                "A evidência não comprova uma estrutura física de palco com LED/tela; usos idiomáticos como 'set the stage' são ignorados.",
            )

    # ------------------------------------------------------------------
    # Platform-format obligations: explicit horizontal/vertical qualifiers are hard.
    # ------------------------------------------------------------------
    platform_format_req = _contains_any(
        requirement,
        (
            "formato adequado a plataforma",
            "formato adequado à plataforma",
            "platform format",
            "horizontal",
            "vertical",
            "stories",
            "reels",
            "feed",
        ),
    )
    if platform_format_req:
        required_formats = {
            term
            for term in ("horizontal", "vertical")
            if _contains_any(requirement, (term,))
        }
        present_formats = {
            term
            for term in ("horizontal", "vertical")
            if _contains_any(evidence, (term,))
        }
        missing_formats = required_formats - present_formats

        if missing_formats:
            if present_formats:
                return (
                    RECOMMEND_PARTIAL,
                    0.98,
                    "platform_format_qualifier_missing",
                    "A evidência cobre apenas parte dos formatos obrigatórios; faltam: "
                    + ", ".join(sorted(missing_formats))
                    + ".",
                )
            return (
                RECOMMEND_REJECT,
                0.98,
                "missing_core_platform_format_qualifier",
                "A requirement exige formato(s) específico(s), mas a evidência não comprova: "
                + ", ".join(sorted(missing_formats))
                + ".",
            )

        if not required_formats and not _contains_any(
            evidence,
            ("horizontal", "vertical", "feed", "stories", "reels", "shorts", "tiktok", "youtube", "kwai"),
        ):
            return (
                RECOMMEND_REJECT,
                0.97,
                "missing_core_platform_format",
                "A evidência não descreve adaptação concreta do conteúdo ao formato da plataforma.",
            )

    return None


def harden_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Re-evaluate one review candidate against canonical obligation + locality guards."""

    original = dict(row)
    display_title = str(original.get("requirement_title") or original.get("title") or "")
    canonical = str(original.get("canonical_obligation_text") or display_title)
    evidence = str(original.get("evidence_text") or original.get("recall_candidate_text") or "")

    guard = _core_obligation_guard(canonical, evidence)
    if guard is not None:
        rec, conf, rule, rationale = guard
        result = dict(original)
        result.update({
            "machine_recommendation": rec,
            "machine_confidence": round(float(conf), 4),
            "machine_rule_id": rule,
            "machine_rationale": rationale,
        })
    else:
        # Reuse the proven B2.12.1 scorer, but feed it the full canonical obligation
        # instead of a potentially truncated display title.
        scorer_row = dict(original)
        scorer_row["requirement_title"] = canonical
        result = _b2121_recommend_candidate(scorer_row)
        result["requirement_title"] = display_title

    result["canonical_obligation_text"] = canonical
    result["adjudicator_type"] = "machine_rule_engine_semantic_hardening"
    result["human_review_created"] = False
    result["truth_effect_applied"] = False
    result["persistence_performed"] = False
    return result


def _stable_candidate_id(project_id: str, row: Mapping[str, Any]) -> str:
    current_ids = ",".join(sorted(
        str(item.get("evidence_id") or "")
        for item in (row.get("current_response_evidence") or [])
        if isinstance(item, Mapping)
    ))
    payload = "|".join([
        str(project_id),
        str(row.get("requirement_id") or ""),
        str(row.get("recall_evidence_id") or ""),
        current_ids,
        str(row.get("projected_response_status") or ""),
        SEMANTIC_HARDENING_VERSION,
    ])
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _best_canonical_recall(
    *,
    eligible_rows: Sequence[Mapping[str, Any]],
    b29_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """B2.10.2: recalibrate B2.9 candidates with full canonical obligations."""

    by_req: dict[str, list[dict[str, Any]]] = {}
    for raw in b29_rows:
        row = dict(raw)
        rid = str(row.get("requirement_id") or "")
        if rid:
            by_req.setdefault(rid, []).append(row)

    best: dict[str, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []

    for raw in eligible_rows:
        row = dict(raw)
        rid = str(row.get("id") or row.get("requirement_id") or "")
        canonical = str(row.get("canonical_obligation_text") or "")
        candidates = by_req.get(rid) or [{
            "requirement_id": rid,
            "b29_class": "NO_SEMANTIC_RECALL_CANDIDATE",
        }]

        classified: list[dict[str, Any]] = []
        for candidate in candidates:
            calibrated = _classify_obligation_candidate(canonical, candidate)
            out = {
                "requirement_id": rid,
                "canonical_obligation_text": canonical,
                "source_b29_class": candidate.get("b29_class"),
                **calibrated,
                "title_anchor_coverage": candidate.get("title_anchor_coverage"),
                "evidence_id": candidate.get("evidence_id"),
                "evidence_source": candidate.get("evidence_source"),
                "evidence_locator": candidate.get("evidence_locator"),
                "candidate_text": candidate.get("evidence_text") or candidate.get("window_text"),
            }
            classified.append(out)

        classified.sort(
            key=lambda item: (
                _OBLIGATION_PRIORITY.get(str(item.get("b210_class") or ""), 99),
                -float(item.get("obligation_atom_coverage") or 0),
                -float(item.get("title_anchor_coverage") or 0),
                str(item.get("evidence_locator") or ""),
            )
        )
        best[rid] = classified[0]
        all_rows.extend(classified[:2])

    return best, all_rows


def _projection_rows(
    *,
    eligible_rows: Sequence[Mapping[str, Any]],
    contract_rows: Sequence[Mapping[str, Any]],
    best_recall: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    contract = {
        str(row.get("requirement_id") or ""): dict(row)
        for row in contract_rows
        if row.get("requirement_id")
    }

    projected: list[dict[str, Any]] = []
    for raw in eligible_rows:
        source = dict(raw)
        adapted = adapt_domain_requirements([source])
        if not adapted:
            continue
        req = adapted[0]
        rid = str(req.get("stable_key") or source.get("id") or "")
        current = dict(contract.get(rid) or {})
        recall = dict(best_recall.get(rid) or {})
        current_status = str(current.get("response_contract_status") or "no_verified_response")
        recall_class = str(recall.get("b210_class") or "NO_CANDIDATE")
        projected_status, reason, origin = _project_status(current_status, recall_class)

        projected.append({
            "requirement_id": rid,
            "title": req.get("title"),
            "canonical_obligation_text": source.get("canonical_obligation_text") or req.get("title"),
            "canonical_obligation_source": source.get("canonical_obligation_source"),
            "canonical_obligation_confidence": source.get("canonical_obligation_confidence"),
            "semantic_role_current": source.get("semantic_role_current"),
            "semantic_observation_id": source.get("semantic_observation_id"),
            "requirement_type": req.get("requirement_type"),
            "mandatory": req.get("mandatory"),
            "priority": req.get("priority"),
            "requirement_truth_status": req.get("truth_status"),
            "current_response_contract_status": current_status,
            "projected_response_status": projected_status,
            "projected_reason": reason,
            "review_origin": origin,
            "current_response_evidence_count": current.get("response_evidence_count", 0),
            "current_response_evidence": current.get("response_evidence") or [],
            "recall_gate_class": recall_class,
            "recall_obligation_atom_coverage": recall.get("obligation_atom_coverage"),
            "recall_title_anchor_coverage": recall.get("title_anchor_coverage"),
            "recall_requirement_atoms": recall.get("requirement_atoms"),
            "recall_shared_atoms": recall.get("shared_atoms"),
            "recall_missing_atoms": recall.get("missing_atoms"),
            "recall_missing_hard_atoms": recall.get("missing_hard_atoms"),
            "recall_evidence_id": recall.get("evidence_id"),
            "recall_evidence_source": recall.get("evidence_source"),
            "recall_evidence_locator": recall.get("evidence_locator"),
            "recall_candidate_text": recall.get("candidate_text"),
        })

    projected.sort(
        key=lambda row: (
            str(row.get("projected_response_status") or ""),
            str(row.get("title") or "").casefold(),
        )
    )
    return projected


def _queue_from_projection(
    *,
    project_id: str,
    projection_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for raw in projection_rows:
        row = dict(raw)
        if str(row.get("projected_response_status") or "") not in _REVIEW_STATUSES:
            continue

        snapshot = {
            "project_id": str(project_id),
            "requirement_id": row.get("requirement_id"),
            "requirement_title": row.get("title"),
            "canonical_obligation_text": row.get("canonical_obligation_text"),
            "canonical_obligation_source": row.get("canonical_obligation_source"),
            "canonical_obligation_confidence": row.get("canonical_obligation_confidence"),
            "semantic_role_current": row.get("semantic_role_current"),
            "semantic_observation_id": row.get("semantic_observation_id"),
            "requirement_type": row.get("requirement_type"),
            "mandatory": row.get("mandatory"),
            "priority": row.get("priority"),
            "requirement_truth_status_at_review": row.get("requirement_truth_status"),
            "current_response_contract_status": row.get("current_response_contract_status"),
            "projected_response_status": row.get("projected_response_status"),
            "projected_reason": row.get("projected_reason"),
            "review_origin": row.get("review_origin"),
            "current_response_evidence_count": row.get("current_response_evidence_count"),
            "current_response_evidence": row.get("current_response_evidence"),
            "evidence_id": row.get("recall_evidence_id"),
            "evidence_source": row.get("recall_evidence_source"),
            "evidence_locator": row.get("recall_evidence_locator"),
            "evidence_text": row.get("recall_candidate_text"),
            "recall_gate_class": row.get("recall_gate_class"),
            "obligation_atom_coverage": row.get("recall_obligation_atom_coverage"),
            "title_anchor_coverage": row.get("recall_title_anchor_coverage"),
            "requirement_atoms": row.get("recall_requirement_atoms"),
            "shared_atoms": row.get("recall_shared_atoms"),
            "missing_atoms": row.get("recall_missing_atoms"),
            "missing_hard_atoms": row.get("recall_missing_hard_atoms"),
            "source_projection_version": "V28.7.3B2.11/B2.12.2 projection",
            "source_atom_gate_version": "V28.7.3B2.10.2 canonical recalibration",
            "source_response_contract_version": "V28.7.3B2.7.1",
        }
        snapshot["candidate_id"] = _stable_candidate_id(project_id, {
            **snapshot,
            "recall_evidence_id": snapshot.get("evidence_id"),
        })
        queue.append(snapshot)

    queue.sort(
        key=lambda row: (
            0 if row["projected_response_status"] == "response_review_high_confidence" else
            1 if row["projected_response_status"] == "response_review_visual_or_structured_evidence" else
            2 if row["projected_response_status"] == "response_review_partial" else 3,
            str(row.get("requirement_title") or "").casefold(),
        )
    )
    return queue


def build_semantic_hardened_adjudication(
    *,
    project_id: str,
    semantics: RequirementSemanticEligibility,
    contract_rows: Sequence[Mapping[str, Any]],
    b29_rows: Sequence[Mapping[str, Any]],
) -> SemanticHardenedAdjudication:
    best_recall, _calibration_rows = _best_canonical_recall(
        eligible_rows=semantics.eligible_rows,
        b29_rows=b29_rows,
    )
    projection = _projection_rows(
        eligible_rows=semantics.eligible_rows,
        contract_rows=contract_rows,
        best_recall=best_recall,
    )
    queue = _queue_from_projection(
        project_id=project_id,
        projection_rows=projection,
    )
    recommendations = [harden_candidate(row) for row in queue]

    counts = {
        RECOMMEND_CONFIRM: 0,
        RECOMMEND_PARTIAL: 0,
        RECOMMEND_REJECT: 0,
        RECOMMEND_VISUAL_REVIEW: 0,
        RECOMMEND_DEFER: 0,
    }
    for row in recommendations:
        counts[str(row.get("machine_recommendation") or RECOMMEND_DEFER)] += 1

    recommendations.sort(
        key=lambda row: (
            0 if row.get("machine_recommendation") == RECOMMEND_CONFIRM else
            1 if row.get("machine_recommendation") == RECOMMEND_PARTIAL else
            2 if row.get("machine_recommendation") == RECOMMEND_VISUAL_REVIEW else
            3 if row.get("machine_recommendation") == RECOMMEND_DEFER else 4,
            -float(row.get("machine_confidence") or 0),
            str(row.get("requirement_title") or "").casefold(),
        )
    )

    status = (
        "BLOCKED_SEMANTIC_ELIGIBILITY_UNKNOWN"
        if semantics.unknown_count
        else "PASS_SEMANTIC_HARDENING_READY"
    )

    return SemanticHardenedAdjudication(
        project_id=str(project_id),
        status=status,
        current_requirement_count_before_semantic_gate=semantics.input_count,
        semantic_eligible_requirement_count=semantics.eligible_count,
        semantic_excluded_no_domain_count=semantics.excluded_no_domain_count,
        semantic_unknown_count=semantics.unknown_count,
        queue_count=len(recommendations),
        recommend_confirm_count=counts[RECOMMEND_CONFIRM],
        recommend_partial_count=counts[RECOMMEND_PARTIAL],
        recommend_reject_count=counts[RECOMMEND_REJECT],
        recommend_visual_review_count=counts[RECOMMEND_VISUAL_REVIEW],
        recommend_defer_count=counts[RECOMMEND_DEFER],
        recommendation_rows=tuple(recommendations),
        semantic_excluded_rows=tuple(semantics.excluded_rows),
        projection_rows=tuple(projection),
    )


def run_semantic_hardened_adjudication(
    client: Any,
    *,
    project_id: str,
) -> SemanticHardenedAdjudication:
    """Run B2.12.2 without writes or cutover side effects."""

    from project_domain_reader import read_domain

    domain = read_domain(
        client,
        project_id,
        "requirements",
        legacy_loader=lambda: [],
        audit=False,
    )
    if str(domain.read_mode) != "shadow_compare":
        raise RuntimeError(
            f"B2.12.2 BLOCKED: requirements read_mode={domain.read_mode}"
        )

    semantics = resolve_requirement_semantics(
        client,
        project_id=project_id,
        current_requirement_rows=[
            dict(row)
            for row in (domain.domain_candidate or [])
            if isinstance(row, Mapping)
        ],
    )

    contract = run_response_contract_canary(
        client,
        project_id=project_id,
    )
    b29 = run_semantic_recall_bridge(
        client,
        project_id=project_id,
    )

    return build_semantic_hardened_adjudication(
        project_id=project_id,
        semantics=semantics,
        contract_rows=[
            dict(row) for row in contract.requirement_rows
        ],
        b29_rows=[
            dict(row) for row in b29.detail_rows
        ],
    )
