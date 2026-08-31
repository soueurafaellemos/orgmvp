from __future__ import annotations

"""NAVE V28.7.3B2.12.1 — Automated Response Adjudication Recommendations.

READ ONLY / machine recommendation only.

This phase exists because the B2.12 human-by-row workflow is operationally
expensive. It automatically recommends a disposition for every B2.12 review
candidate using the governed B2.11/B2.10.1 signals plus conservative semantic
guards.

IMPORTANT:
- recommendations are MACHINE recommendations, never Human Review;
- they do not change Truth;
- they do not persist anything;
- they do not approve cutover;
- `recommend_confirm` means "the evidence looks sufficient for this shadow
  recommendation layer", not `verified_response`.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re
import unicodedata

AUTO_ADJUDICATION_VERSION = "V28.7.3B2.12.1"

RECOMMEND_CONFIRM = "recommend_confirm"
RECOMMEND_PARTIAL = "recommend_partial"
RECOMMEND_REJECT = "recommend_reject"
RECOMMEND_VISUAL_REVIEW = "recommend_visual_review"
RECOMMEND_DEFER = "recommend_defer"

WEAK_ATOMS = {
    "guests", "content", "photo", "video", "camera", "live",
    "gifts", "venue", "plenary", "product", "show",
}

@dataclass(frozen=True)
class AutomatedAdjudicationRecommendations:
    project_id: str
    status: str
    queue_count: int
    recommend_confirm_count: int
    recommend_partial_count: int
    recommend_reject_count: int
    recommend_visual_review_count: int
    recommend_defer_count: int
    recommendation_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": AUTO_ADJUDICATION_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "queue_count": self.queue_count,
            "recommend_confirm_count": self.recommend_confirm_count,
            "recommend_partial_count": self.recommend_partial_count,
            "recommend_reject_count": self.recommend_reject_count,
            "recommend_visual_review_count": self.recommend_visual_review_count,
            "recommend_defer_count": self.recommend_defer_count,
            "adjudicator_type": "machine_rule_engine",
            "human_review_created": False,
            "truth_changed": False,
            "persistence_performed": False,
            "cutover_approved": False,
            "recommendation_rows": list(self.recommendation_rows),
        }


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9$+]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _atoms(value: Any) -> set[str]:
    return {
        part.strip()
        for part in str(value or "").split("|")
        if part.strip()
    }


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    n = f" {_norm(text)} "
    return any(f" {_norm(term)} " in n for term in terms)


def _semantic_guard(title: str, evidence: str) -> tuple[str, float, str, str] | None:
    """High-precision negative/partial guards for known obligation structures."""
    t = _norm(title)
    e = _norm(evidence)

    # Source-role / context mismatch guards.
    if "competitor landscape" in e and not _contains_any(title, ("concorrente", "competitor", "market")):
        return (
            RECOMMEND_REJECT, 0.99, "source_mismatch_competitor",
            "A evidência é contexto de concorrência/mercado, não uma resposta operacional à requirement.",
        )

    if "gift distribution event close" in e:
        if not _contains_any(title, ("gift", "brinde", "entrega dos brindes", "final do evento")):
            return (
                RECOMMEND_REJECT, 0.98, "source_mismatch_gift_close",
                "A evidência descreve distribuição de brinde/encerramento e não responde à obrigação solicitada.",
            )

    # Core obligations whose absence means there is no substantive response.
    if _contains_any(title, ("pesquisa de satisfacao", "pesquisa curta", "survey")) and not _contains_any(
        evidence, ("pesquisa", "survey", "questionnaire", "satisfaction")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_survey",
            "A requirement exige pesquisa; a evidência não apresenta pesquisa, questionário ou mecanismo equivalente.",
        )

    if _contains_any(title, ("pagamento sera realizado diretamente", "pagamento direto", "pagos diretamente")) and not _contains_any(
        evidence, ("pagamento direto", "paid directly", "direct payment", "jovi pays", "pago diretamente")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_direct_payment",
            "A requirement é sobre pagamento direto; a evidência não comprova essa condição financeira.",
        )

    if _contains_any(title, ("co investimento", "co-investimento", "patrocinio", "compartilhamento de verba")) and not _contains_any(
        evidence, ("co investment", "co-invest", "sponsorship", "patrocinio", "sponsor", "shared investment")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_coinvestment",
            "A menção genérica a partnership não comprova co-investimento, patrocínio ou compartilhamento de verba.",
        )

    if _contains_any(title, ("video memoria", "video resumo", "aftermovie")):
        if not _contains_any(evidence, ("event recap", "recap video", "summary video", "aftermovie", "video resumo", "highlight video")):
            return (
                RECOMMEND_REJECT, 0.99, "missing_core_recap_video",
                "A ocorrência de 'video' não comprova a entrega de um vídeo-resumo/aftermovie do evento.",
            )

    if _contains_any(title, ("promotores bilingues", "promotores bilingues")) and not _contains_any(
        evidence, ("bilingual", "bilingue", "english speaking", "promoter", "promotional staff")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_bilingual_promoters",
            "Não há comprovação de promotores bilíngues na evidência candidata.",
        )

    if _contains_any(title, ("parcerias nao sejam concretizadas", "parcerias não sejam concretizadas", "funcionar de forma independente")) and not _contains_any(
        evidence, ("independent", "standalone", "sem parceria", "without partnership", "independente")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_independence",
            "A evidência menciona partnership, mas não prova que as ativações funcionam sem parceria.",
        )

    if _contains_any(title, ("nao e necessario que as agencias facam qualquer contato", "não é necessário que as agências façam qualquer contato")) and not _contains_any(
        evidence, ("no contact", "do not contact", "negotiation", "negociacao", "marketing team")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_no_contact",
            "A evidência não comprova a instrução de não contato/negociação conduzida pela equipe JOVI.",
        )

    if _contains_any(title, ("hyper mailing", "hyper-mailing", "vip/a-list", "a-list")) and not _contains_any(
        evidence, ("hyper mailing", "vip", "a list", "a-list", "personalities", "celebrit", "kol")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_vip_mailing",
            "A evidência não apresenta ação VIP/A-List ou hyper-mailing.",
        )

    if _contains_any(title, ("dois cenarios de periodos", "dois cenários de períodos", "tanto para o dia quanto para a noite")) and not _contains_any(
        evidence, ("day and night", "daytime", "nighttime", "morning", "evening", "dia", "noite")
    ):
        return (
            RECOMMEND_REJECT, 0.99, "missing_core_day_night",
            "A evidência não apresenta os dois cenários de período solicitados.",
        )

    if _contains_any(title, ("tematica de viagens", "temática de viagens")):
        if _contains_any(evidence, ("travel-inspired press kit", "travel inspired press kit")) and not _contains_any(
            evidence, ("activation", "ativacao", "hands-on", "experience")
        ):
            return (
                RECOMMEND_REJECT, 0.97, "travel_presskit_not_activation",
                "A temática de viagem aparece apenas no press kit; não comprova uma ativação de experimentação de produto.",
            )

    if _contains_any(title, ("performance com muito movimento",)) and not _contains_any(
        evidence, ("movement", "motion", "moving performance", "performance artist", "dance", "show")
    ):
        return (
            RECOMMEND_REJECT, 0.98, "missing_core_movement_performance",
            "A evidência não apresenta uma performance/evento com movimento.",
        )

    if _contains_any(title, ("formato adequado a plataforma", "formato adequado à plataforma")) and not _contains_any(
        evidence, ("feed", "stories", "reels", "tiktok", "youtube", "kwai", "vertical", "horizontal", "platform format")
    ):
        return (
            RECOMMEND_REJECT, 0.96, "missing_core_platform_format",
            "A evidência não descreve adaptação do formato de conteúdo à plataforma.",
        )

    if _contains_any(title, ("backstage",)) and not _contains_any(evidence, ("backstage", "behind the scenes", "bastidores")):
        return (
            RECOMMEND_REJECT, 0.96, "missing_core_backstage",
            "A câmera é mencionada, mas não há conteúdo de backstage/bastidores na evidência.",
        )

    # Known partial structures.
    if _contains_any(title, ("opcoes veganas", "opções veganas", "vegetarianas")) and _contains_any(
        evidence, ("food beverage", "food & beverage", "alimentacao", "a&b", "f&b")
    ) and not _contains_any(evidence, ("vegan", "vegano", "vegetarian", "vegetariano")):
        return (
            RECOMMEND_PARTIAL, 0.98, "food_without_dietary_options",
            "A&B está contemplado, mas não há evidência das opções veganas/vegetarianas exigidas.",
        )

    if _contains_any(title, ("sistema de credenciamento",)) and _contains_any(evidence, ("check-in", "check in", "registration")):
        return (
            RECOMMEND_PARTIAL, 0.90, "checkin_without_registration_system",
            "Há check-in/credenciamento, mas não está comprovado um sistema de credenciamento.",
        )

    if _contains_any(title, ("area de recepcao", "área de recepção")) and _contains_any(evidence, ("receptivo", "reception", "welcome")):
        return (
            RECOMMEND_PARTIAL, 0.88, "reception_area_indicated",
            "A evidência indica receptivo/acolhimento, mas não detalha suficientemente a área de recepção.",
        )

    if _contains_any(title, ("iluminacao premium para retratos", "iluminação premium para retratos")):
        if _contains_any(evidence, ("low light", "limited lighting", "night mode")) and not _contains_any(
            evidence, ("portrait", "retrato", "premium lighting", "studio lighting")
        ):
            return (
                RECOMMEND_REJECT, 0.96, "lowlight_not_premium_portrait",
                "Low-light/Night Mode não comprova iluminação premium dedicada a retratos.",
            )

    return None


def recommend_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    title = str(row.get("requirement_title") or row.get("title") or "")
    evidence = str(row.get("evidence_text") or row.get("recall_candidate_text") or "")
    projected_status = str(row.get("projected_response_status") or "")
    coverage = float(row.get("obligation_atom_coverage") or row.get("recall_obligation_atom_coverage") or 0.0)
    anchor = float(row.get("title_anchor_coverage") or row.get("recall_title_anchor_coverage") or 0.0)
    req_atoms = _atoms(row.get("requirement_atoms") or row.get("recall_requirement_atoms"))
    shared_atoms = _atoms(row.get("shared_atoms") or row.get("recall_shared_atoms"))
    missing_atoms = _atoms(row.get("missing_atoms") or row.get("recall_missing_atoms"))
    missing_hard = _atoms(row.get("missing_hard_atoms") or row.get("recall_missing_hard_atoms"))

    if projected_status == "response_review_visual_or_structured_evidence":
        rec, conf, rule, rationale = (
            RECOMMEND_VISUAL_REVIEW, 0.99, "visual_structured_source",
            "A própria projeção B2.11 exige inspeção visual/estruturada; a máquina não deve forçar conclusão textual.",
        )
    elif not evidence.strip():
        rec, conf, rule, rationale = (
            RECOMMEND_DEFER, 0.99, "no_candidate_evidence",
            "Não há texto de evidência suficiente para uma recomendação automática.",
        )
    else:
        guard = _semantic_guard(title, evidence)
        if guard is not None:
            rec, conf, rule, rationale = guard
        elif projected_status == "response_review_high_confidence":
            if coverage >= 1.0 and not missing_atoms and not missing_hard and (len(shared_atoms) >= 2 or anchor >= 0.4):
                rec, conf, rule, rationale = (
                    RECOMMEND_CONFIRM, 0.94, "high_confidence_full_obligation",
                    "A obrigação canônica está integralmente coberta por âncoras explícitas da evidência.",
                )
            elif coverage >= 1.0 and not missing_atoms and not missing_hard:
                rec, conf, rule, rationale = (
                    RECOMMEND_CONFIRM, 0.87, "high_confidence_single_obligation",
                    "A obrigação canônica principal aparece explicitamente na evidência recuperada.",
                )
            else:
                rec, conf, rule, rationale = (
                    RECOMMEND_PARTIAL, 0.82, "high_confidence_incomplete_atoms",
                    "O recall é forte, mas ainda existem componentes da obrigação sem cobertura completa.",
                )
        else:
            specific_shared = shared_atoms - WEAK_ATOMS
            if not shared_atoms or coverage <= 0.0:
                rec, conf, rule, rationale = (
                    RECOMMEND_REJECT, 0.97, "no_obligation_support",
                    "Nenhum átomo canônico da obrigação é efetivamente sustentado pela evidência candidata.",
                )
            elif missing_hard:
                rec, conf, rule, rationale = (
                    RECOMMEND_PARTIAL, 0.97, "hard_qualifier_missing",
                    "Há resposta parcial, mas faltam qualificadores obrigatórios: " + ", ".join(sorted(missing_hard)) + ".",
                )
            elif len(req_atoms) == 1 and coverage >= 1.0:
                if anchor >= 0.4:
                    rec, conf, rule, rationale = (
                        RECOMMEND_CONFIRM, 0.86, "single_atom_strong_anchor",
                        "A única obrigação canônica está explicitamente ancorada na evidência.",
                    )
                elif anchor >= 0.15:
                    rec, conf, rule, rationale = (
                        RECOMMEND_PARTIAL, 0.82, "single_atom_weak_detail",
                        "O tópico central está presente, mas a implementação/detalhe da requirement não está totalmente comprovado.",
                    )
                else:
                    rec, conf, rule, rationale = (
                        RECOMMEND_REJECT, 0.91, "single_atom_generic_overlap",
                        "Há apenas coincidência temática sem suporte suficiente no título/evidência para considerar resposta.",
                    )
            elif shared_atoms and shared_atoms.issubset(WEAK_ATOMS) and anchor < 0.15:
                rec, conf, rule, rationale = (
                    RECOMMEND_REJECT, 0.95, "generic_atoms_only",
                    "A sobreposição se limita a conceitos genéricos e não responde substantivamente à requirement.",
                )
            elif coverage >= 0.5:
                rec, conf, rule, rationale = (
                    RECOMMEND_PARTIAL, 0.90, "meaningful_partial_coverage",
                    "A evidência responde parte da obrigação, mas ainda faltam: " + ", ".join(sorted(missing_atoms)) + ".",
                )
            else:
                rec, conf, rule, rationale = (
                    RECOMMEND_REJECT, 0.90, "weak_partial_coverage",
                    "A cobertura semântica é insuficiente para tratar o candidato como uma resposta significativa.",
                )

    return {
        **dict(row),
        "machine_recommendation": rec,
        "machine_confidence": round(float(conf), 4),
        "machine_rule_id": rule,
        "machine_rationale": rationale,
        "adjudicator_type": "machine_rule_engine",
        "human_review_created": False,
        "truth_effect_applied": False,
        "persistence_performed": False,
    }


def build_automated_adjudication_recommendations(
    *,
    project_id: str,
    queue_rows: Sequence[Mapping[str, Any]],
) -> AutomatedAdjudicationRecommendations:
    recommendation_rows = [
        recommend_candidate(dict(row))
        for row in queue_rows
    ]
    counts = {
        RECOMMEND_CONFIRM: 0,
        RECOMMEND_PARTIAL: 0,
        RECOMMEND_REJECT: 0,
        RECOMMEND_VISUAL_REVIEW: 0,
        RECOMMEND_DEFER: 0,
    }
    for row in recommendation_rows:
        counts[row["machine_recommendation"]] += 1

    recommendation_rows.sort(
        key=lambda row: (
            0 if row["machine_recommendation"] == RECOMMEND_CONFIRM else
            1 if row["machine_recommendation"] == RECOMMEND_PARTIAL else
            2 if row["machine_recommendation"] == RECOMMEND_VISUAL_REVIEW else
            3 if row["machine_recommendation"] == RECOMMEND_DEFER else 4,
            -float(row.get("machine_confidence") or 0),
            str(row.get("requirement_title") or "").casefold(),
        )
    )

    status = (
        "PASS_MACHINE_RECOMMENDATIONS_READY"
        if recommendation_rows
        else "PASS_NO_REVIEW_CANDIDATES"
    )
    return AutomatedAdjudicationRecommendations(
        project_id=str(project_id),
        status=status,
        queue_count=len(recommendation_rows),
        recommend_confirm_count=counts[RECOMMEND_CONFIRM],
        recommend_partial_count=counts[RECOMMEND_PARTIAL],
        recommend_reject_count=counts[RECOMMEND_REJECT],
        recommend_visual_review_count=counts[RECOMMEND_VISUAL_REVIEW],
        recommend_defer_count=counts[RECOMMEND_DEFER],
        recommendation_rows=tuple(recommendation_rows),
    )


def run_automated_adjudication_recommendations(
    client: Any,
    *,
    project_id: str,
) -> AutomatedAdjudicationRecommendations:
    # Import inside runtime function so the recommendation engine remains
    # independently testable and does not create any persistence dependency.
    from project_requirement_human_response_adjudication_contract import (
        run_human_adjudication_queue,
    )

    queue = run_human_adjudication_queue(
        client,
        project_id=project_id,
    )
    return build_automated_adjudication_recommendations(
        project_id=project_id,
        queue_rows=queue.queue_rows,
    )
