from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from supabase import Client

from project_analyst import derive_advanced_project_insights, sanitize_semantic_payload


VISUAL_SECTIONS = {"scenography", "activations", "gifts"}
DELIVERY_SECTIONS = {
    "scenography",
    "activations",
    "gifts",
    "journey_operation",
    "communication",
    "content_agenda",
    "partners_sponsorship",
    "pr_esg_legacy",
}

SECTION_LABELS = {
    "strategy": "Estratégia e conceito",
    "scenography": "Cenografia e ambientes",
    "activations": "Ativações e experiências",
    "gifts": "Brindes e press kits",
    "journey_operation": "Jornada e operação",
    "communication": "Comunicação",
    "content_agenda": "Conteúdo e agenda",
    "partners_sponsorship": "Parceiros e patrocínios",
    "pr_esg_legacy": "PR, ESG e legado",
}

SECTION_KEYWORDS = {
    "scenography": {
        "cenografia": 5, "cenografico": 5, "ambientacao": 5,
        "ambiente": 3, "espaco": 2, "estande": 4, "stand": 4,
        "fachada": 4, "palco": 4, "lounge": 4, "arquitetura": 4,
        "mobiliario": 4, "estrutura": 2, "marcenaria": 4,
        "implantacao": 4, "layout": 3, "planta": 3, "render": 4,
        "area externa": 3, "area interna": 3,
        "backdrop": 3, "painel cenografico": 5, "portal": 3,
        "entrada": 2, "balcao": 3, "testeira": 4,
    },
    "activations": {
        "ativacao": 5, "experiencia": 4, "dinamica": 4,
        "game": 5, "jogo": 5, "brincadeira": 5, "oficina": 4,
        "interacao": 4, "gamificacao": 5, "desafio": 4,
        "amarelinha": 7, "pescaria": 7, "jogo da memoria": 7,
        "roleta": 6, "quiz": 6, "photo op": 5, "photopp": 5,
        "foto oportunidade": 4, "karaoke": 5, "simulador": 5,
    },
    "gifts": {
        "brinde": 6, "press kit": 7, "presskit": 7, "gift": 5,
        "giveaway": 5, "mimo": 4, "lembranca": 4, "kit": 2,
        "chaveiro": 7, "adesivo": 6, "tatuagem": 6, "faixa": 4,
        "meia": 6, "sacola": 5, "bone": 5, "camiseta": 5,
        "copo": 5, "caneca": 5, "pulseira": 5, "cordao": 5,
        "asas": 4, "origami": 4, "cadaco": 4, "personalize": 3,
    },
}

GENERIC_TOKENS = {
    "de", "da", "do", "das", "dos", "e", "em", "para", "por",
    "com", "sem", "um", "uma", "ao", "aos", "na", "no", "nas",
    "nos", "projeto", "evento", "item", "servico", "material",
    "fornecimento", "locacao", "producao", "geral", "diversos",
}

RELEVANCE_CLASSIFIER_VERSION = "v27.5"

_HIDDEN_VISIBILITY_VALUES = {
    "hidden",
    "ignored",
    "excluded",
    "do_not_use",
    "nao_usar",
}

_VISIBLE_VISIBILITY_VALUES = {
    "visible",
    "included",
    "force_visible",
}

_STRONG_NON_CONTENT_TITLE_PATTERNS = (
    r"\bconfidential\b",
    r"\bnot\s+for\s+(?:public\s+)?(?:consumption|distribution)\b",
    r"\bdo\s+not\s+distribute\b",
    r"^\s*obrigad[oa]?\b",
    r"^\s*thank(?:s|\s+you)?\b",
    r"^\s*gracias\b",
    r"^\s*merci\b",
    r"^\s*(?:fim|the\s+end)\b",
    r"^\s*(?:contato|contact|fale\s+conosco)\b",
    r"^\s*(?:copyright|direitos\s+reservados)\b",
    r"^\s*(?:aviso\s+legal|legal\s+notice|disclaimer)\b",
)

_GENERIC_NON_CONTENT_TITLES = {
    "agenda",
    "indice",
    "sumario",
    "contents",
    "table of contents",
    "capa",
    "cover",
    "apresentacao",
    "proposta",
    "proposta comercial",
    "introducao",
    "obrigado",
    "obrigada",
    "thank you",
    "contato",
    "contact",
    "quem somos",
    "sobre nos",
    "sobre a voe",
    "portfolio",
    "cases",
    "credenciais",
    "nossos clientes",
}

_SECTION_DIVIDER_TITLES = {
    "estrategia",
    "conceito",
    "estrategia e conceito",
    "cenografia",
    "cenografia e ambientes",
    "ativacoes",
    "ativacoes e experiencias",
    "experiencias",
    "brindes",
    "brindes e press kits",
    "press kits",
    "jornada",
    "jornada e operacao",
    "operacao",
    "orcamento",
    "fornecedores",
}


def _workspace_visibility(record: dict[str, Any]) -> str:
    raw = record.get("raw_data")
    if not isinstance(raw, dict):
        return ""

    for key in (
        "workspace_visibility",
        "nave_visibility",
        "content_visibility",
    ):
        value = normalise_text(raw.get(key))
        if value:
            return value

    relevance = raw.get("relevance")
    if isinstance(relevance, dict):
        return normalise_text(
            relevance.get("visibility")
            or relevance.get("status")
        )

    return ""


def classify_project_record_relevance(
    record: dict[str, Any],
) -> tuple[bool, str | None]:
    """
    Decide se um slide/ficha representa conteúdo útil do projeto.

    O material original continua preservado. Esta função apenas impede
    que capas, encerramentos, avisos legais e divisórias virem entregas,
    recebam custos ou contaminem o diagnóstico.
    """
    visibility = _workspace_visibility(record)
    if visibility in _HIDDEN_VISIBILITY_VALUES:
        return False, "Marcado para não ser usado na NAVE."
    if visibility in _VISIBLE_VISIBILITY_VALUES:
        return True, None

    raw = record.get("raw_data")
    if not isinstance(raw, dict):
        raw = {}

    title = normalise_text(
        record.get("title")
        or record.get("slide_title")
        or raw.get("suggested_title")
        or raw.get("slide_title")
    )
    summary = normalise_text(
        record.get("summary")
        or record.get("slide_summary")
        or record.get("description")
        or raw.get("slide_summary")
    )
    combined = " ".join(
        value for value in (title, summary) if value
    ).strip()

    for pattern in _STRONG_NON_CONTENT_TITLE_PATTERNS:
        if re.search(pattern, title):
            return False, "Slide de fechamento, contato ou confidencialidade."

    # Alguns extratores repetem o aviso no título e no resumo.
    if (
        len(combined.split()) <= 40
        and any(
            token in combined
            for token in (
                "not for public consumption",
                "not for public distribution",
                "do not distribute",
                "direitos reservados",
                "all rights reserved",
            )
        )
    ):
        return False, "Aviso legal ou de confidencialidade."

    if title in _GENERIC_NON_CONTENT_TITLES:
        return False, "Capa, índice, institucional ou encerramento."

    # Divisórias organizam o PPT, mas não são uma entrega do projeto.
    if (
        title in _SECTION_DIVIDER_TITLES
        and len(_tokens(summary)) <= 12
    ):
        return False, "Slide divisório de seção."

    # Página sem conteúdo reconhecível.
    if not combined:
        return False, "Página sem conteúdo identificável."

    positive_score = max(_section_scores(record).values(), default=0.0)
    combined_tokens = _tokens(combined)

    # Evita transformar títulos residuais, rodapés ou capas curtas em fichas.
    if (
        positive_score <= 0
        and len(combined_tokens) <= 3
        and len(combined) <= 70
    ):
        return False, "Conteúdo curto sem entrega identificável."

    return True, None


def is_project_relevant_record(record: dict[str, Any]) -> bool:
    return classify_project_record_relevance(record)[0]

EXECUTED_STATUSES = {"executed"}
NO_EXECUTION_STATUSES = {"not_executed"}
POSITIVE_ADHERENCE = {"fulfilled", "partially_fulfilled", "exceeded", "changed_justified"}

DIAGNOSTIC_CSS = """
<style>
.nave-source-card {
    background: #FFFFFF;
    border: 1px solid #E1E6EF;
    border-radius: 13px;
    min-height: 118px;
    padding: 0.85rem 0.9rem;
}
.nave-source-label {
    color: #18AFC9;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.nave-source-title {
    color: #121B42;
    font-size: 0.92rem;
    font-weight: 800;
    margin-top: 0.3rem;
}
.nave-source-status {
    color: #667188;
    font-size: 0.75rem;
    line-height: 1.35;
    margin-top: 0.4rem;
}
.nave-diagnostic-callout {
    background: #F0FAFC;
    border-left: 4px solid #18CDEA;
    border-radius: 9px;
    color: #34405D;
    font-size: 0.84rem;
    line-height: 1.5;
    margin: 0.45rem 0;
    padding: 0.75rem 0.85rem;
}
.nave-diagnostic-alert {
    background: #FFF8E7;
    border-left: 4px solid #E0A11B;
    border-radius: 9px;
    color: #5E4A1B;
    font-size: 0.84rem;
    line-height: 1.5;
    margin: 0.45rem 0;
    padding: 0.75rem 0.85rem;
}
</style>
"""


def normalise_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold().replace("&", " e ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    return {
        token for token in normalise_text(value).split()
        if len(token) > 2 and token not in GENERIC_TOKENS
    }


def _record_text(record: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "title", "slide_title", "summary", "slide_summary", "description",
        "item_type", "evidence", "category", "item_name", "source_sheet",
    ):
        if record.get(key):
            values.append(str(record.get(key)))
    for key in ("tags", "objectives", "mechanics", "technologies"):
        value = record.get(key)
        if isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value)
    raw = record.get("raw_data")
    if isinstance(raw, dict):
        for key in ("suggested_title", "suggested_section", "slide_title", "slide_summary", "summary", "text", "normalized_text"):
            if raw.get(key):
                values.append(str(raw.get(key)))
    return normalise_text(" ".join(values))


def _section_scores(record: dict[str, Any]) -> dict[str, float]:
    text = _record_text(record)
    scores = {section: 0.0 for section in VISUAL_SECTIONS}
    for section, keywords in SECTION_KEYWORDS.items():
        for phrase, weight in keywords.items():
            if normalise_text(phrase) in text:
                scores[section] += float(weight)
    return scores


def infer_section_from_record(
    record: dict[str, Any],
    *,
    explicit_section: str | None = None,
) -> str | None:
    explicit = str(explicit_section or record.get("section_key") or record.get("primary_section") or "").strip()
    scores = _section_scores(record)
    best = max(scores, key=scores.get)
    best_score = scores[best]

    if explicit in VISUAL_SECTIONS:
        # A classificação já revisada tem prioridade, salvo evidência textual muito forte.
        if best != explicit and best_score >= scores.get(explicit, 0) + 8:
            return best
        return explicit

    if best_score >= 3:
        return best
    return explicit or None


def infer_cost_section(cost: dict[str, Any]) -> str | None:
    return infer_section_from_record(
        {
            "title": cost.get("item_name"),
            "summary": cost.get("description"),
            "category": cost.get("category"),
            "item_type": cost.get("billing_type"),
            "raw_data": cost.get("raw_data"),
        }
    )


def _similarity(left: Any, right: Any) -> float:
    left_text = normalise_text(left)
    right_text = normalise_text(right)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    left_tokens = _tokens(left_text)
    right_tokens = _tokens(right_text)
    union = left_tokens | right_tokens
    overlap = len(left_tokens & right_tokens) / max(len(union), 1)
    containment = 0.0
    if left_text in right_text or right_text in left_text:
        containment = 0.94
    sequence = difflib.SequenceMatcher(None, left_text, right_text).ratio()
    return max(sequence * 0.82, overlap, containment)


def _item_cost_score(item: dict[str, Any], cost: dict[str, Any]) -> tuple[float, str]:
    title = item.get("title") or item.get("slide_title")
    item_body = " ".join(
        str(value or "")
        for value in (
            title, item.get("summary"), item.get("description"),
            " ".join(item.get("tags") or []) if isinstance(item.get("tags"), list) else item.get("tags"),
        )
    )
    cost_title = cost.get("item_name")
    cost_body = " ".join(
        str(value or "")
        for value in (cost_title, cost.get("category"), cost.get("description"))
    )
    title_score = _similarity(title, cost_title)
    body_score = _similarity(item_body, cost_body)
    item_section = infer_section_from_record(item)
    cost_section = infer_cost_section(cost)
    section_bonus = 0.10 if item_section and item_section == cost_section else 0.0
    score = min(1.0, max(title_score, body_score * 0.88) + section_bonus)
    reason = (
        f"Título {title_score:.0%}; conteúdo {body_score:.0%}"
        + (f"; mesma seção {SECTION_LABELS.get(item_section, item_section)}" if section_bonus else "")
    )
    return score, reason


def _requirement_item_score(requirement: dict[str, Any], item: dict[str, Any]) -> tuple[float, str]:
    requirement_text = " ".join(
        str(value or "")
        for value in (
            requirement.get("title"), requirement.get("description"),
            requirement.get("source_quote"),
            " ".join(requirement.get("tags") or []) if isinstance(requirement.get("tags"), list) else requirement.get("tags"),
        )
    )
    item_text = " ".join(
        str(value or "")
        for value in (
            item.get("title"), item.get("summary"), item.get("description"),
            item.get("evidence"),
            " ".join(item.get("tags") or []) if isinstance(item.get("tags"), list) else item.get("tags"),
        )
    )
    title_score = _similarity(requirement.get("title"), item.get("title"))
    body_score = _similarity(requirement_text, item_text)
    score = max(title_score, body_score * 0.92)
    return score, f"Demanda × ficha: título {title_score:.0%}; conteúdo {body_score:.0%}"


def ensure_automatic_cost_links(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> int:
    items = [
        row for row in snapshot.get("memory_items", [])
        if row.get("id") and is_project_relevant_record(row)
    ]
    costs = [row for row in proposal_cost_items(snapshot) if row.get("id")]
    if not items or not costs:
        return 0

    existing_pairs = {
        (str(row.get("cost_item_id")), str(row.get("memory_item_id")))
        for row in snapshot.get("cost_links", [])
        if row.get("cost_item_id") and row.get("memory_item_id")
    }
    inserted_count = 0
    new_rows: list[dict[str, Any]] = []

    for cost in costs:
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for item in items:
            pair = (str(cost.get("id")), str(item.get("id")))
            if pair in existing_pairs:
                continue
            score, reason = _item_cost_score(item, cost)
            if score >= 0.58:
                candidates.append((score, reason, item))
        candidates.sort(key=lambda row: row[0], reverse=True)
        if not candidates:
            continue
        best_score = candidates[0][0]
        selected = [row for row in candidates[:2] if row[0] >= max(0.58, best_score - 0.06)]
        for score, reason, item in selected:
            payload = {
                "project_id": project_id,
                "cost_item_id": cost.get("id"),
                "memory_item_id": item.get("id"),
                "match_score": round(score, 4),
                "match_reason": "Correlação automática V27.2 — " + reason,
                "link_status": "suggested",
            }
            try:
                response = client.table("memory_cost_links").insert(payload).execute()
                saved = dict(response.data[0]) if response.data else payload
                new_rows.append(saved)
                existing_pairs.add((str(cost.get("id")), str(item.get("id"))))
                inserted_count += 1
            except Exception:
                continue

    if new_rows:
        snapshot.setdefault("cost_links", []).extend(new_rows)
    return inserted_count


def ensure_automatic_briefing_links(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> int:
    requirements = [row for row in snapshot.get("briefing_requirements", []) if row.get("id")]
    items = [
        row for row in snapshot.get("memory_items", [])
        if row.get("id") and is_project_relevant_record(row)
    ]
    if not requirements or not items:
        return 0

    existing_pairs = {
        (str(row.get("requirement_id")), str(row.get("memory_item_id")))
        for row in snapshot.get("briefing_links", [])
        if row.get("requirement_id") and row.get("memory_item_id")
    }
    inserted_count = 0
    new_rows: list[dict[str, Any]] = []

    for requirement in requirements:
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for item in items:
            pair = (str(requirement.get("id")), str(item.get("id")))
            if pair in existing_pairs:
                continue
            score, reason = _requirement_item_score(requirement, item)
            if score >= 0.55:
                candidates.append((score, reason, item))
        candidates.sort(key=lambda row: row[0], reverse=True)
        if not candidates:
            continue
        best_score = candidates[0][0]
        selected = [row for row in candidates[:2] if row[0] >= max(0.55, best_score - 0.05)]
        for score, reason, item in selected:
            payload = {
                "project_id": project_id,
                "requirement_id": requirement.get("id"),
                "memory_item_id": item.get("id"),
                "match_score": round(score, 4),
                "match_reason": "Correlação automática V27.2 — " + reason,
                "link_status": "suggested",
                "adherence_status": "not_assessed",
                "evidence": None,
                "notes": None,
            }
            try:
                response = client.table("memory_briefing_links").insert(payload).execute()
                saved = dict(response.data[0]) if response.data else payload
                new_rows.append(saved)
                existing_pairs.add((str(requirement.get("id")), str(item.get("id"))))
                inserted_count += 1
            except Exception:
                continue

    if new_rows:
        snapshot.setdefault("briefing_links", []).extend(new_rows)
    return inserted_count


def section_cost_context(snapshot: dict[str, Any], section: str) -> dict[str, Any]:
    relevant_item_ids = {
        str(row.get("id"))
        for row in snapshot.get("memory_items", [])
        if row.get("id") and is_project_relevant_record(row)
    }
    active_links = [
        row
        for row in snapshot.get("cost_links", [])
        if row.get("link_status") != "rejected"
        and str(row.get("memory_item_id") or "") in relevant_item_ids
    ]
    linked_cost_ids = {str(row.get("cost_item_id")) for row in active_links if row.get("cost_item_id")}
    section_costs = [row for row in proposal_cost_items(snapshot) if infer_cost_section(row) == section]
    unallocated = [row for row in section_costs if str(row.get("id")) not in linked_cost_ids]
    return {
        "section_costs": section_costs,
        "unallocated": unallocated,
        "section_total": sum(_safe_float(row.get("client_total")) for row in section_costs),
        "unallocated_total": sum(_safe_float(row.get("client_total")) for row in unallocated),
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _money(value: Any) -> str:
    number = _safe_float(value)
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _best_item_match(name: str, items: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best = None
    best_score = 0.0
    for item in items:
        score = _similarity(name, item.get("title"))
        if score > best_score:
            best = item
            best_score = score
    return best, best_score


def _coverage_state(structured: int, attached: int, label: str) -> dict[str, Any]:
    if structured > 0:
        return {"state": "structured", "label": label, "detail": f"{structured} registro(s) estruturado(s)"}
    if attached > 0:
        return {"state": "attached", "label": label, "detail": "Arquivo anexado, ainda sem leitura estruturada"}
    return {"state": "missing", "label": label, "detail": "Pendente"}


def _active_links(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("link_status") != "rejected"]


def _source_signature(snapshot: dict[str, Any]) -> str:
    keys = (
        "briefing_documents", "briefing_requirements", "memory_documents",
        "memory_pages", "memory_items", "cost_documents", "cost_items",
        "cost_links", "item_outcomes", "briefing_links", "feedback_entries",
        "project_files", "report_analyses",
    )
    compact: dict[str, Any] = {}
    for key in keys:
        rows = []
        for row in snapshot.get(key, []):
            rows.append({
                "id": row.get("id") or row.get("item_id"),
                "updated_at": row.get("updated_at"),
                "created_at": row.get("created_at"),
                "status": row.get("link_status") or row.get("outcome_status") or row.get("analysis_status"),
                "value": row.get("client_total") or row.get("actual_cost") or row.get("adherence_status"),
            })
        compact[key] = rows
    compact["outcome"] = snapshot.get("outcome") or {}
    graph = snapshot.get("intelligence_graph") if isinstance(snapshot.get("intelligence_graph"), dict) else {}
    compact["intelligence_graph"] = {
        "evidence": [
            (row.get("id"), row.get("source_asset_id"), row.get("content_sha256"), row.get("created_at"))
            for row in (graph.get("evidence_units") or [])
        ],
        "claims": [
            (row.get("id"), row.get("predicate"), row.get("value_text"), row.get("value_numeric"), row.get("status"), row.get("updated_at"))
            for row in (graph.get("claims") or [])
        ],
        "relations": [
            (row.get("id"), row.get("relation_type"), row.get("source_entity_id"), row.get("target_entity_id"), row.get("status"), row.get("updated_at"))
            for row in (graph.get("relations") or [])
        ],
    }
    compact["relevance_classifier_version"] = RELEVANCE_CLASSIFIER_VERSION
    payload = json.dumps(compact, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def project_stage(snapshot: dict[str, Any]) -> tuple[str, str]:
    """Traduz o estado técnico para a situação de negócio que faz sentido no projeto."""
    project = snapshot.get("project") or {}
    outcome = snapshot.get("outcome") or {}
    status = str(project.get("status") or "")
    commercial = str(outcome.get("commercial_result") or "")
    execution = str(outcome.get("execution_result") or "")
    client_decision = (
        str(outcome.get("information_source") or "") == "client_feedback"
        and str(outcome.get("confidence_level") or "") == "client_confirmed"
    )

    if client_decision and commercial == "lost":
        return (
            "lost",
            "Concorrência perdida / proposta não aprovada"
            if str(outcome.get("process_type") or "") == "competition"
            else "Perdido / proposta não aprovada",
        )
    if client_decision and commercial == "cancelled":
        return "cancelled", "Cancelado"
    if execution in {"executed", "partially_executed"} or status == "executado":
        return "executed", "Executado"
    if execution == "in_progress" or status == "em_producao":
        return "production", "Em produção"
    if commercial == "lost" or status == "perdido":
        return "lost", "Perdido"
    if commercial == "cancelled" or status == "cancelado":
        return "cancelled", "Cancelado"
    if commercial == "no_return":
        return "no_return", "Sem resposta"
    if commercial == "won" or status == "aprovado_ganho":
        return "won", "Ganho / aprovado"
    return "proposal", "Em proposta / concorrência"


def _numeric_values(rows: Iterable[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        raw = row.get(field)
        if raw in (None, ""):
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def cost_document_kind(document: dict[str, Any]) -> str:
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    kind = str(metadata.get("document_role") or metadata.get("cost_kind") or "").strip()
    if kind in {"detailed_costs", "preliminary_budget"}:
        return kind
    file_name = normalise_text(document.get("file_name") or document.get("title"))
    if "estudo de verba" in file_name or "verba preliminar" in file_name:
        return "preliminary_budget"
    return "detailed_costs"


def proposal_cost_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    documents = snapshot.get("cost_documents", [])
    detailed_ids = {
        str(row.get("id"))
        for row in documents
        if row.get("id") and cost_document_kind(row) == "detailed_costs"
    }
    if not detailed_ids:
        preliminary_ids = {
            str(row.get("id"))
            for row in documents
            if row.get("id") and cost_document_kind(row) == "preliminary_budget"
        }
        return [
            row for row in snapshot.get("cost_items", [])
            if str(row.get("cost_document_id") or "") not in preliminary_ids
        ]
    return [
        row for row in snapshot.get("cost_items", [])
        if str(row.get("cost_document_id") or "") in detailed_ids
    ]


def _first_document_total(documents: list[dict[str, Any]], kind: str) -> float | None:
    for row in documents:
        if cost_document_kind(row) != kind:
            continue
        raw = row.get("client_total")
        if raw in (None, ""):
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _financial_scope(snapshot: dict[str, Any]) -> dict[str, Any]:
    documents = list(snapshot.get("cost_documents", []))
    detailed_documents = [row for row in documents if cost_document_kind(row) == "detailed_costs"]
    preliminary_documents = [row for row in documents if cost_document_kind(row) == "preliminary_budget"]
    proposal_items = proposal_cost_items(snapshot)

    proposal_total = _first_document_total(detailed_documents, "detailed_costs")
    if proposal_total is None:
        values = _numeric_values(proposal_items, "client_total")
        proposal_total = sum(values) if values else None

    preliminary_total = _first_document_total(preliminary_documents, "preliminary_budget")
    preliminary_items = [
        row for row in snapshot.get("cost_items", [])
        if str(row.get("cost_document_id") or "") in {str(doc.get("id")) for doc in preliminary_documents if doc.get("id")}
    ]

    category_totals: dict[str, float] = defaultdict(float)
    for item in proposal_items:
        value = item.get("client_total")
        if value in (None, ""):
            continue
        category = str(item.get("category") or "Sem categoria").strip() or "Sem categoria"
        category_totals[category] += _safe_float(value)
    category_breakdown = [
        {"category": category, "total": total}
        for category, total in sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True)
    ]

    additional_sheets: list[dict[str, Any]] = []
    for document in detailed_documents:
        metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
        for row in metadata.get("additional_sheet_totals") or []:
            if not isinstance(row, dict) or row.get("client_total") in (None, ""):
                continue
            additional_sheets.append(dict(row))

    return {
        "documents": documents,
        "detailed_documents": detailed_documents,
        "preliminary_documents": preliminary_documents,
        "proposal_items": proposal_items,
        "preliminary_items": preliminary_items,
        "proposal_total": proposal_total,
        "preliminary_total": preliminary_total,
        "category_breakdown": category_breakdown,
        "additional_sheets": additional_sheets,
    }


def build_project_intelligence(snapshot: dict[str, Any]) -> dict[str, Any]:
    from project_intelligence_unified import build_unified_project_snapshot

    unified = snapshot.get("unified_intelligence")
    if not isinstance(unified, dict):
        unified = build_unified_project_snapshot(snapshot)
        snapshot["unified_intelligence"] = unified
    current_signature = _source_signature(snapshot)
    prior_semantic: dict[str, Any] | None = None
    for stored in snapshot.get("intelligence_snapshots", []) or []:
        if str(stored.get("source_signature") or "") != current_signature:
            continue
        stored_metrics = stored.get("metrics") if isinstance(stored.get("metrics"), dict) else {}
        candidate = stored_metrics.get("semantic_synthesis")
        if isinstance(candidate, dict) and candidate.get("executive_summary"):
            prior_semantic = candidate
            break

    project_files = [row for row in snapshot.get("project_files", []) if not row.get("is_archived")]
    role_count = defaultdict(int)
    for row in project_files:
        role_count[str(row.get("file_role"))] += 1

    coverage = {
        "briefing": _coverage_state(len(snapshot.get("briefing_documents", [])), role_count["briefing_original"], "Briefing"),
        "presentation": _coverage_state(len(snapshot.get("memory_documents", [])), role_count["final_presentation"], "Apresentação"),
        "cost": _coverage_state(len(snapshot.get("cost_documents", [])), role_count["cost_sheet"], "Planilha de custos"),
        "report": _coverage_state(len(snapshot.get("report_analyses", [])), role_count["post_execution_report"] + role_count["closure_report"], "Pós-evento / encerramento"),
        "feedback": _coverage_state(len(snapshot.get("feedback_entries", [])), role_count["feedback"] + role_count["approval"], "Feedbacks"),
    }
    unified_truth = unified.get("project_truth") or {}
    if unified_truth.get("has_post_event_source") and (unified.get("domain_evidence") or {}).get("execution"):
        coverage["report"] = {
            "state": "structured" if unified_truth.get("report_structured") else "evidence_found",
            "label": "Pós-evento / encerramento",
            "detail": (
                f"{len(snapshot.get('report_analyses', []))} leitura(s) estruturada(s)"
                if unified_truth.get("report_structured")
                else f"{len((unified.get('domain_evidence') or {}).get('execution') or [])} evidência(s) pós-evento no Intelligence Graph"
            ),
        }

    stage_key = str(unified_truth.get("stage") or "") or project_stage(snapshot)[0]
    stage_label = str(unified_truth.get("stage_label") or "") or project_stage(snapshot)[1]
    proposal_stage = stage_key in {"proposal", "no_return", "won"}

    items = []
    for row in snapshot.get("memory_items", []):
        if not is_project_relevant_record(row):
            continue
        section = infer_section_from_record(
            row,
            explicit_section=row.get("section_key"),
        )
        enriched = dict(row)
        enriched["inferred_section"] = section
        if section in DELIVERY_SECTIONS:
            items.append(enriched)

    financial_scope = _financial_scope(snapshot)
    analysis_cost_items = financial_scope["proposal_items"]
    cost_by_id = {str(row.get("id")): row for row in analysis_cost_items if row.get("id")}
    req_by_id = {str(row.get("id")): row for row in snapshot.get("briefing_requirements", []) if row.get("id")}
    outcomes = {str(row.get("item_id")): row for row in snapshot.get("item_outcomes", []) if row.get("item_id")}

    relevant_item_ids = {
        str(row.get("id"))
        for row in items
        if row.get("id")
    }

    costs_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    active_cost_links = [
        row
        for row in _active_links(snapshot.get("cost_links", []))
        if str(row.get("memory_item_id") or "") in relevant_item_ids
        and str(row.get("cost_item_id") or "") in cost_by_id
    ]
    for link in active_cost_links:
        cost = cost_by_id.get(str(link.get("cost_item_id")))
        if cost:
            costs_by_item[str(link.get("memory_item_id"))].append({"link": link, "cost": cost})

    requirements_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    active_brief_links = [
        row
        for row in _active_links(snapshot.get("briefing_links", []))
        if str(row.get("memory_item_id") or "") in relevant_item_ids
    ]
    for link in active_brief_links:
        requirement = req_by_id.get(str(link.get("requirement_id")))
        if requirement:
            requirements_by_item[str(link.get("memory_item_id"))].append({"link": link, "requirement": requirement})

    execution_match_by_item = {
        str(row.get("item_id") or ""): row
        for row in (unified.get("execution_matches") or [])
        if row.get("item_id")
    }
    matrix: list[dict[str, Any]] = []
    executed_count = 0
    explicit_not_executed = 0
    no_execution_evidence = 0

    for item in items:
        item_id = str(item.get("id") or "")
        outcome = outcomes.get(item_id) or {}
        outcome_status = str(outcome.get("outcome_status") or "unassessed")
        unified_execution = execution_match_by_item.get(item_id)
        if unified_execution:
            execution_reading = "Executado com evidência pós-evento"
            executed_count += 1
        elif proposal_stage:
            execution_reading = "Ainda não aplicável — projeto em proposta"
        elif outcome_status in EXECUTED_STATUSES:
            execution_reading = "Executado com evidência"
            executed_count += 1
        elif outcome_status in NO_EXECUTION_STATUSES:
            execution_reading = "Não executado — evidência explícita"
            explicit_not_executed += 1
        else:
            execution_reading = "Sem evidência de execução"
            no_execution_evidence += 1

        linked_costs = costs_by_item.get(item_id, [])
        direct_cost = sum(_safe_float(row["cost"].get("client_total")) for row in linked_costs)
        confirmed = any(row["link"].get("link_status") == "confirmed" for row in linked_costs)
        best_cost_score = max((_safe_float(row["link"].get("match_score")) for row in linked_costs), default=0)

        briefing_links = requirements_by_item.get(item_id, [])
        adherence_values = [
            str(row["link"].get("adherence_status") or row["requirement"].get("adherence_status") or "not_assessed")
            for row in briefing_links
        ]
        if any(value in {"not_fulfilled"} for value in adherence_values):
            adherence = "Não cumprida"
        elif any(value in POSITIVE_ADHERENCE for value in adherence_values):
            adherence = "Com evidência de aderência"
        elif briefing_links:
            adherence = "Relacionada, ainda não avaliada"
        else:
            adherence = "Sem demanda relacionada"

        matrix.append({
            "Item apresentado": item.get("title") or "Sem título",
            "Área": SECTION_LABELS.get(item.get("inferred_section"), item.get("inferred_section") or "Não classificada"),
            "Situação na apresentação": item.get("item_status") or "Não informada",
            "Briefing": adherence,
            "Custo direto": direct_cost,
            "Correlação do custo": (
                "Confirmada" if confirmed else
                f"Sugerida · {best_cost_score:.0%}" if linked_costs else
                "Sem linha direta"
            ),
            "Execução": execution_reading,
            "Evidência / resultado": (
                (unified_execution or {}).get("evidence", {}).get("text")
                or outcome.get("feedback_summary") or outcome.get("execution_notes") or outcome.get("decision_reason") or "—"
            ),
            "item_id": item_id,
            "section_key": item.get("inferred_section"),
        })

    linked_cost_ids = {str(row.get("cost_item_id")) for row in active_cost_links if row.get("cost_item_id")}
    cost_only = []
    for cost in analysis_cost_items:
        if str(cost.get("id")) in linked_cost_ids:
            continue
        cost_only.append({
            "Linha da planilha": cost.get("item_name") or "Sem nome",
            "Categoria": cost.get("category") or "Não informada",
            "Valor": _safe_float(cost.get("client_total")),
            "Situação": cost.get("item_status") or "Não informada",
            "Leitura": "Custo sem correspondência direta na apresentação",
        })

    report_results: list[dict[str, Any]] = []
    for report in snapshot.get("report_analyses", []):
        for key in ("activation_results", "item_results"):
            for row in report.get(key) or []:
                if isinstance(row, dict):
                    report_results.append(row)
    report_only = []
    matched_report_names: set[str] = set()
    for result in report_results:
        name = str(result.get("name") or result.get("item_name") or "").strip()
        if not name:
            continue
        item, score = _best_item_match(name, items)
        if item and score >= 0.56:
            matched_report_names.add(normalise_text(name))
            continue
        report_only.append({
            "Entrega no relatório": name,
            "Resultado": result.get("result") or result.get("feedback") or "Não detalhado",
            "Situação": result.get("status") or result.get("outcome_status") or "Não informada",
            "Evidência": result.get("evidence") or "—",
            "Leitura": "Entrega registrada no pós-evento sem correspondência clara na apresentação",
        })

    linked_requirement_ids = {str(row.get("requirement_id")) for row in active_brief_links if row.get("requirement_id")}
    unified_requirement_matches = {
        str(row.get("requirement_id") or ""): row
        for row in (unified.get("briefing_matches") or [])
        if row.get("requirement_id")
    }
    briefing_unconsolidated = []
    briefing_gaps = []
    for requirement in snapshot.get("briefing_requirements", []):
        req_id = str(requirement.get("id") or "")
        status = str(requirement.get("adherence_status") or "not_assessed")
        if req_id in linked_requirement_ids and status in POSITIVE_ADHERENCE:
            continue
        unified_match = unified_requirement_matches.get(req_id)
        if unified_match:
            briefing_unconsolidated.append({
                "Demanda do briefing": requirement.get("title") or "Sem título",
                "Tipo": requirement.get("requirement_type") or "Não informado",
                "Obrigatória": "Sim" if requirement.get("mandatory") else "Não",
                "Aderência": "Evidência encontrada",
                "Leitura": "A proposta contém evidência semanticamente relacionada, mas o vínculo ainda não foi consolidado numa solução estruturada.",
                "Confiança": f"{float(unified_match.get('score') or 0):.0%}",
            })
            continue
        briefing_gaps.append({
            "Demanda do briefing": requirement.get("title") or "Sem título",
            "Tipo": requirement.get("requirement_type") or "Não informado",
            "Obrigatória": "Sim" if requirement.get("mandatory") else "Não",
            "Aderência": status.replace("_", " ").title(),
            "Leitura": "Sem evidência consolidada de atendimento" if req_id not in linked_requirement_ids else "Relacionada, mas sem conclusão positiva",
        })

    proposed_without_cost = [row for row in matrix if row["Custo direto"] <= 0]

    cost_total = financial_scope.get("proposal_total")
    preliminary_budget_total = financial_scope.get("preliminary_total")
    linked_values = [
        _safe_float(cost_by_id.get(str(cost_id), {}).get("client_total"))
        for cost_id in linked_cost_ids
        if cost_by_id.get(str(cost_id), {}).get("client_total") not in (None, "")
    ]
    linked_cost_total = sum(linked_values) if linked_values else None
    outcome_project = snapshot.get("outcome") or {}
    budget_amount = outcome_project.get("budget_amount")
    try:
        budget_amount = float(budget_amount) if budget_amount not in (None, "") else None
    except (TypeError, ValueError):
        budget_amount = None
    unified_budget = _safe_float((unified.get("project_truth") or {}).get("budget_amount"))
    if unified_budget is not None:
        budget_amount = unified_budget
    if budget_amount is None:
        briefing_budgets = []
        for document in snapshot.get("briefing_documents", []):
            value = document.get("budget_amount")
            try:
                if value not in (None, "") and float(value) > 0:
                    briefing_budgets.append(float(value))
            except (TypeError, ValueError):
                continue
        if briefing_budgets:
            # A versão mais recente vem primeiro no snapshot; o primeiro valor
            # comprovado é a melhor evidência disponível do teto do briefing.
            budget_amount = briefing_budgets[0]
    if budget_amount is None and preliminary_budget_total is not None:
        budget_amount = preliminary_budget_total
    budget_delta = (budget_amount - cost_total) if budget_amount is not None and cost_total is not None else None
    budget_usage_pct = (cost_total / budget_amount) if budget_amount and cost_total is not None else None

    metrics = {
        "briefing_requirements": len(snapshot.get("briefing_requirements", [])),
        "presentation_items": len(items),
        "cost_items": len(analysis_cost_items),
        "preliminary_cost_items": len(financial_scope.get("preliminary_items") or []),
        "items_with_cost": len(matrix) - len(proposed_without_cost),
        "executed_with_evidence": executed_count,
        "explicit_not_executed": explicit_not_executed,
        "without_execution_evidence": no_execution_evidence,
        "cost_only_items": len(cost_only),
        "report_only_items": len(report_only),
        "briefing_gaps": len(briefing_gaps),
        "briefing_evidence_unconsolidated": len(briefing_unconsolidated),
        "cost_total": cost_total,
        "linked_cost_total": linked_cost_total,
        "budget_amount": budget_amount,
        "budget_delta": budget_delta,
        "budget_usage_pct": budget_usage_pct,
        "preliminary_budget_total": preliminary_budget_total,
        "cost_category_breakdown": financial_scope.get("category_breakdown") or [],
        "additional_cost_sheets": financial_scope.get("additional_sheets") or [],
        "stage": stage_key,
        "stage_label": stage_label,
    }

    findings: list[dict[str, str]] = []
    technical_health: list[dict[str, Any]] = []
    if items and proposal_stage:
        findings.append({
            "level": "info",
            "title": "Projeto ainda em proposta",
            "text": (
                f"A apresentação contém {len(items)} entrega(s) estruturada(s). "
                "Como o projeto ainda não foi ganho/executado, a NAVE não cobra nem infere evidência de execução."
            ),
        })
    elif items:
        findings.append({
            "level": "info",
            "title": "Proposta × execução",
            "text": (
                f"A apresentação contém {len(items)} entrega(s) estruturada(s). "
                f"{executed_count} possuem evidência de execução; "
                f"{explicit_not_executed} foram registradas explicitamente como não executadas; "
                f"{no_execution_evidence} ainda não possuem evidência suficiente."
            ),
        })
    if analysis_cost_items or financial_scope.get("detailed_documents"):
        total_text = _money(cost_total) if cost_total is not None else "total ainda não identificado"
        findings.append({
            "level": "warning" if cost_only or cost_total is None else "info",
            "title": "Proposta × planilha",
            "text": (
                f"A proposta detalhada contém {len(analysis_cost_items)} linha(s) estruturada(s), com {total_text}. "
                f"{len(cost_only)} linha(s) ainda não têm correspondência direta na apresentação."
            ),
        })
    if preliminary_budget_total is not None:
        findings.append({
            "level": "info",
            "title": "Estudo de verba",
            "text": f"O estudo preliminar foi reconstruído em {_money(preliminary_budget_total)} e é tratado como referência de alocação, sem ser somado novamente ao total da proposta.",
        })
    if budget_amount is not None:
        if cost_total is None:
            findings.append({
                "level": "warning",
                "title": "Budget identificado, total da planilha pendente",
                "text": f"O briefing registra budget de {_money(budget_amount)}, mas a leitura atual da planilha ainda não permite calcular a aderência financeira.",
            })
        else:
            relation = "abaixo" if budget_delta is not None and budget_delta >= 0 else "acima"
            direct_payment = bool((unified.get("financial_context") or {}).get("direct_payment_signal"))
            if budget_delta is not None and budget_delta < 0 and direct_payment:
                findings.append({
                    "level": "warning",
                    "title": "Diferença bruta a reconciliar",
                    "text": f"O total bruto da proposta ({_money(cost_total)}) supera o budget nominal ({_money(budget_amount)}) em {_money(abs(budget_delta or 0))}, mas há indicação de pagamento direto pelo cliente. A aderência final depende da separação de responsabilidades financeiras.",
                })
            else:
                findings.append({
                    "level": "warning" if budget_delta is not None and budget_delta < 0 else "info",
                    "title": "Aderência financeira",
                    "text": f"Budget: {_money(budget_amount)} · planilha: {_money(cost_total)} · diferença: {_money(abs(budget_delta or 0))} {relation} do budget.",
                })
    additional_cost_sheets = financial_scope.get("additional_sheets") or []
    if additional_cost_sheets:
        readable = ", ".join(
            f"{row.get('sheet_name') or 'Aba adicional'}: {_money(row.get('client_total'))}"
            for row in additional_cost_sheets[:3]
        )
        findings.append({
            "level": "info",
            "title": "Escopos financeiros apartados",
            "text": f"A planilha detalhada possui aba(s) adicional(is) não somada(s) ao total principal: {readable}.",
        })

    if report_only:
        findings.append({
            "level": "warning",
            "title": "Entregas adicionais",
            "text": f"O relatório registra {len(report_only)} entrega(s) sem correspondência clara na apresentação final.",
        })
    if briefing_unconsolidated:
        findings.append({
            "level": "info",
            "title": "Briefing × proposta · evidências ainda não consolidadas",
            "text": f"A NAVE encontrou evidência de resposta para {len(briefing_unconsolidated)} demanda(s) do briefing na proposta. Essas demandas devem aparecer como respostas identificadas, ainda que algumas relações exijam confirmação adicional.",
        })
    if briefing_gaps:
        findings.append({
            "level": "warning",
            "title": "Briefing × evidências",
            "text": f"{len(briefing_gaps)} demanda(s) do briefing ainda não possuem evidência identificada de atendimento nas fontes atuais.",
        })
    for key, source in coverage.items():
        if source["state"] == "attached":
            technical_health.append({
                "level": "warning",
                "code": f"attached_not_structured_{key}",
                "title": f"{source['label']} sem estruturação",
                "text": "O arquivo está salvo no projeto, mas seu conteúdo ainda não entrou na leitura estruturada principal.",
            })

    # Unified Decision Intelligence entra antes das recomendações legadas. O
    # workspace deixa de depender apenas das tabelas memory_* para saber o que o
    # projeto realmente contém.
    for issue in unified.get("consistency_issues") or []:
        technical_health.append({
            "level": "warning",
            "code": issue.get("code") or "consistency_issue",
            "title": issue.get("title") or "Inconsistência da leitura NAVE",
            "text": issue.get("text") or "",
            "source": "consistency_engine",
            "severity": issue.get("severity"),
            "recommended_action": issue.get("recommended_action"),
        })
    decision = unified.get("decision_intelligence") or {}
    for row in decision.get("diagnostic") or []:
        findings.append({
            "level": "warning" if row.get("kind") in {"contradiction", "risk"} else "info",
            "title": row.get("title") or "Leitura NAVE",
            "text": row.get("text") or "",
            "source": "unified_diagnostic",
            "kind": row.get("kind"),
            "importance": row.get("importance"),
            "evidence": row.get("evidence") or [],
        })

    # Recomendações exibidas ao usuário devem ser decisões de projeto, não tarefas
    # de manutenção do pipeline. Os avisos de estruturação vivem em technical_health.
    recommendations: list[str] = [
        str(row.get("text") or "").strip()
        for row in decision.get("recommendations") or []
        if str(row.get("text") or "").strip()
    ]
    advanced = derive_advanced_project_insights(
        snapshot,
        proposal_total=cost_total,
        budget_amount=budget_amount,
    )
    # O Project Analyst adiciona conexões de segunda ordem: concentração
    # financeira, feedback → solução, custo → solução e briefing → feedback.
    existing_finding_signatures = {
        (str(row.get("title") or ""), str(row.get("text") or ""))
        for row in findings
    }
    for row in advanced.get("findings") or []:
        signature = (str(row.get("title") or ""), str(row.get("text") or ""))
        if signature not in existing_finding_signatures:
            findings.append(row)
            existing_finding_signatures.add(signature)
    recommendations.extend(advanced.get("recommendations") or [])
    recommendations = list(dict.fromkeys(recommendations))
    if not recommendations:
        recommendations.append("Manter o projeto atualizado com novas versões, feedbacks e resultados para preservar o ciclo de aprendizado.")

    metrics.update({
        "cost_per_attendee": advanced.get("cost_per_attendee"),
        "audience_quantity": advanced.get("audience_quantity"),
        "audience_scope": advanced.get("audience_scope"),
        "audience_source": advanced.get("audience_source"),
        "top4_category_share": advanced.get("top4_category_share"),
        "top5_item_share": advanced.get("top5_item_share"),
        "validated_items_count": len(advanced.get("validated_items") or []),
        "challenged_items_count": len(advanced.get("challenged_items") or []),
    })

    # A síntese semântica é gerada após materialização e fica presa à assinatura
    # das fontes. Recalcular a parte determinística não apaga o raciocínio já
    # validado para exatamente o mesmo conjunto de evidências.
    if prior_semantic:
        safe_semantic = sanitize_semantic_payload(prior_semantic, snapshot)
        metrics["semantic_synthesis"] = safe_semantic
        semantic_rows = []
        for group_name, level in (
            ("diagnostic", "info"),
            ("strongest_connections", "info"),
            ("discovered_connections", "info"),
            ("contradictions_or_gaps", "warning"),
        ):
            for row in safe_semantic.get(group_name) or []:
                if not isinstance(row, dict):
                    continue
                semantic_rows.append({
                    "level": level,
                    "title": row.get("title") or "Conexão inteligente",
                    "text": row.get("analysis") or "",
                    "source": "semantic_project_analyst",
                    "connection_type": row.get("connection_type") or "cross_source",
                    "evidence_refs": row.get("evidence_refs") or [],
                    "confidence": row.get("confidence") or "medium",
                    "recommended_action": row.get("recommended_action"),
                })
        existing = {(str(r.get("title") or ""), str(r.get("text") or "")) for r in findings}
        for row in semantic_rows:
            key = (str(row.get("title") or ""), str(row.get("text") or ""))
            if row.get("text") and key not in existing:
                findings.append(row)
                existing.add(key)
        recommendations.extend(
            str(value).strip()
            for value in safe_semantic.get("decision_recommendations") or []
            if str(value).strip()
        )
        recommendations = list(dict.fromkeys(recommendations))

    latest_report = snapshot.get("report_analyses", [None])[0] if snapshot.get("report_analyses") else None
    unified_results = unified.get("results") or {}
    result_summary = {
        "executive_summary": (latest_report or {}).get("executive_summary") or unified_results.get("executive_summary"),
        "highlights": (latest_report or {}).get("highlights") or unified_results.get("highlights") or [],
        "issues": list(dict.fromkeys([*((latest_report or {}).get("issues") or []), *(unified_results.get("issues") or []), *(unified_results.get("data_quality") or [])])),
        "learnings": (latest_report or {}).get("learnings") or unified_results.get("learnings") or [],
        "recommendations": list(dict.fromkeys([*((latest_report or {}).get("recommendations") or []), *(unified_results.get("recommendations") or [])])),
        "kpis": (latest_report or {}).get("kpis") or unified_results.get("kpis") or [],
        "participants_count": (latest_report or {}).get("participants_count") or unified_results.get("participants_count"),
        "participants_scope": unified_results.get("participants_scope"),
        "planned_cost": (latest_report or {}).get("planned_cost"),
        "actual_cost": (latest_report or {}).get("actual_cost"),
        "activation_results": (latest_report or {}).get("activation_results") or unified_results.get("activation_results") or [],
        "pending": unified_results.get("pending") or [],
    }

    return {
        "source_signature": current_signature,
        "coverage": coverage,
        "metrics": metrics,
        "matrix": matrix,
        "findings": findings,
        "recommendations": recommendations,
        "discrepancies": {
            "cost_only": cost_only,
            "report_only": report_only,
            "briefing_gaps": briefing_gaps,
            "briefing_evidence_unconsolidated": briefing_unconsolidated,
            "proposed_without_cost": proposed_without_cost,
        },
        "result_summary": result_summary,
        "advanced_insights": advanced,
        "technical_health": technical_health,
        "unified": unified,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def persist_project_intelligence(
    client: Client,
    *,
    project_id: str,
    intelligence: dict[str, Any],
) -> None:
    payload = {
        "project_id": project_id,
        "source_signature": intelligence.get("source_signature"),
        "coverage": intelligence.get("coverage") or {},
        "metrics": intelligence.get("metrics") or {},
        "matrix": intelligence.get("matrix") or [],
        "findings": intelligence.get("findings") or [],
        "recommendations": intelligence.get("recommendations") or [],
        "discrepancies": intelligence.get("discrepancies") or {},
    }
    try:
        client.table("project_intelligence_snapshots").upsert(
            payload,
            on_conflict="project_id,source_signature",
        ).execute()
    except Exception:
        # A página continua funcionando mesmo antes da execução do SQL.
        pass


def _render_source_card(source: dict[str, Any]) -> str:
    state_label = {
        "structured": "Estruturado e cruzado",
        "evidence_found": "Evidência encontrada no Intelligence Graph",
        "attached": "Anexado, aguardando leitura",
        "missing": "Pendente",
    }.get(source.get("state"), "Pendente")
    return f"""
    <div class="nave-source-card">
        <div class="nave-source-label">Fonte do diagnóstico</div>
        <div class="nave-source-title">{source.get('label')}</div>
        <div class="nave-source-status"><strong>{state_label}</strong><br>{source.get('detail')}</div>
    </div>
    """


def _dataframe_money(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    copy = df.copy()
    for column in columns:
        if column in copy.columns:
            copy[column] = pd.to_numeric(copy[column], errors="coerce").fillna(0).map(_money)
    return copy


def render_project_intelligence(
    client: Client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
) -> None:
    """Projeção executiva da inteligência do projeto.

    A tela principal mostra CONCLUSÕES. Cobertura de fonte, links automáticos,
    matriz detalhada e saúde de processamento permanecem auditáveis, mas ficam
    fora do caminho principal do usuário.
    """
    st.markdown(DIAGNOSTIC_CSS, unsafe_allow_html=True)

    with st.spinner("Cruzando briefing, apresentação, custos e resultados..."):
        new_cost_links = ensure_automatic_cost_links(
            client, project_id=project_id, snapshot=snapshot
        )
        new_brief_links = ensure_automatic_briefing_links(
            client, project_id=project_id, snapshot=snapshot
        )
        intelligence = build_project_intelligence(snapshot)
        persist_project_intelligence(
            client, project_id=project_id, intelligence=intelligence
        )

    st.subheader("Diagnóstico e recomendações")
    st.caption(
        "Leitura executiva do projeto: aderência, riscos, oportunidades e decisões. "
        "Resultados pós-evento e aprendizados permanecem em uma área própria do workspace."
    )

    metrics = intelligence["metrics"]
    semantic = metrics.get("semantic_synthesis") if isinstance(metrics.get("semantic_synthesis"), dict) else {}
    if semantic.get("executive_summary"):
        st.markdown("#### Leitura executiva")
        st.info(str(semantic.get("executive_summary")))

    # Cards próprios evitam labels truncados do st.metric em grids estreitos.
    if metrics.get("stage") in {"proposal", "no_return", "won"}:
        metric_rows = [
            ("Situação", metrics.get("stage_label") or "Em proposta"),
            ("Demandas do briefing", metrics.get("briefing_requirements", 0)),
            ("Entregas apresentadas", metrics.get("presentation_items", 0)),
            ("Entregas com custo direto", metrics.get("items_with_cost", 0)),
            ("Custos sem correspondência", metrics.get("cost_only_items", 0)),
            ("Demandas sem evidência", metrics.get("briefing_gaps", 0)),
        ]
    else:
        metric_rows = [
            ("Demandas do briefing", metrics.get("briefing_requirements", 0)),
            ("Entregas apresentadas", metrics.get("presentation_items", 0)),
            ("Entregas com custo direto", metrics.get("items_with_cost", 0)),
            ("Executadas com evidência", metrics.get("executed_with_evidence", 0)),
            ("Ainda sem evidência de execução", metrics.get("without_execution_evidence", 0)),
            ("Custos sem correspondência", metrics.get("cost_only_items", 0)),
        ]
    cards = "".join(
        f'<div class="nave-exec-metric"><div class="nave-exec-metric-label">{str(label)}</div><div class="nave-exec-metric-value">{str(value)}</div></div>'
        for label, value in metric_rows
    )
    st.markdown(
        """
        <style>
        .nave-exec-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:.55rem 0 1rem}
        .nave-exec-metric{background:#F7F9FC;border:1px solid #E1E6EF;border-radius:14px;padding:14px 15px;min-width:0}
        .nave-exec-metric-label{font-size:.78rem;line-height:1.25;color:#58647B;font-weight:700;white-space:normal;overflow-wrap:anywhere;min-height:2.0em}
        .nave-exec-metric-value{font-size:1.75rem;line-height:1.1;color:#121B42;font-weight:850;margin-top:.35rem;overflow-wrap:anywhere}
        @media(max-width:900px){.nave-exec-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
        </style>
        <div class="nave-exec-metrics">""" + cards + "</div>",
        unsafe_allow_html=True,
    )

    unified = intelligence.get("unified") or {}
    decision = unified.get("decision_intelligence") or {}
    diagnostics = [row for row in decision.get("diagnostic") or [] if str(row.get("text") or "").strip()]
    recommendations = [row for row in decision.get("recommendations") or [] if str(row.get("text") or "").strip()]
    connections = [row for row in decision.get("connections") or [] if str(row.get("text") or "").strip()]

    if diagnostics or recommendations or connections:
        st.markdown("#### Inteligência de decisão")
        tabs = st.tabs(["Diagnóstico", "Recomendações", "Conexões descobertas"])
        with tabs[0]:
            if diagnostics:
                for row in diagnostics[:8]:
                    title = str(row.get("title") or "Leitura NAVE")
                    text = str(row.get("text") or "")
                    if str(row.get("kind") or "") in {"contradiction", "risk"}:
                        st.warning(f"**{title}**\n\n{text}")
                    else:
                        st.info(f"**{title}**\n\n{text}")
            else:
                st.caption("Nenhum diagnóstico adicional consolidado com as fontes atuais.")
        with tabs[1]:
            if recommendations:
                for index, row in enumerate(recommendations[:8], start=1):
                    title = str(row.get("title") or f"Recomendação {index}")
                    st.success(f"**{title}**\n\n{str(row.get('text') or '')}")
            else:
                for index, value in enumerate((intelligence.get("recommendations") or [])[:8], start=1):
                    st.markdown(f"**{index}.** {value}")
        with tabs[2]:
            if connections:
                for row in connections[:8]:
                    st.info(f"**{row.get('title') or 'Conexão'}**\n\n{row.get('text') or ''}")
            else:
                st.caption("Nenhuma conexão adicional consolidada com segurança.")

    # Insights financeiros determinísticos continuam úteis, sem duplicar frases
    # de saúde técnica ou pedir que o usuário faça o trabalho do motor.
    advanced = intelligence.get("advanced_insights") or {}
    business_findings = [
        row for row in (advanced.get("findings") or [])
        if str(row.get("title") or "") not in {"Custo por participante"}
    ]
    if business_findings:
        st.markdown("#### Leituras objetivas")
        for row in business_findings[:5]:
            if row.get("level") == "warning":
                st.warning(f"**{row.get('title')}**\n\n{row.get('text')}")
            else:
                st.info(f"**{row.get('title')}**\n\n{row.get('text')}")

    # Auditoria detalhada existe, mas não compete visualmente com o ouro da NAVE.
    with st.expander("Detalhes e auditoria do projeto", expanded=False):
        st.markdown("**Cobertura das fontes**")
        coverage = intelligence["coverage"]
        columns = st.columns(5)
        for column, key in zip(columns, ("briefing", "presentation", "cost", "report", "feedback")):
            with column:
                st.markdown(_render_source_card(coverage[key]), unsafe_allow_html=True)
        if new_cost_links or new_brief_links:
            st.caption(
                f"Nesta leitura, a NAVE criou {new_cost_links} nova(s) sugestão(ões) de custo e "
                f"{new_brief_links} nova(s) sugestão(ões) de aderência."
            )

        matrix = pd.DataFrame(intelligence["matrix"])
        st.markdown("**Matriz integrada do projeto**")
        if matrix.empty:
            st.caption("Ainda não há entregas estruturadas suficientes para montar a matriz.")
        else:
            display = matrix.drop(columns=["item_id", "section_key"], errors="ignore")
            display = _dataframe_money(display, ["Custo direto"])
            st.dataframe(display, hide_index=True, width="stretch", height=min(680, 95 + len(display) * 38))

        discrepancies = intelligence["discrepancies"]
        proposal_view = metrics.get("stage") in {"proposal", "no_return", "won"}
        tabs = st.tabs([
            "Proposta × custos" if proposal_view else "Proposta × execução",
            "Custos sem correspondência",
            "Entregas adicionais",
            "Briefing ainda sem evidência",
        ])
        with tabs[0]:
            if matrix.empty:
                st.caption("Nenhuma entrega estruturada.")
            elif proposal_view:
                proposal_df = matrix[["Item apresentado", "Área", "Situação na apresentação", "Briefing", "Custo direto", "Correlação do custo"]]
                proposal_df = _dataframe_money(proposal_df, ["Custo direto"])
                st.dataframe(proposal_df, hide_index=True, width="stretch")
            else:
                execution_view = matrix[["Item apresentado", "Área", "Execução", "Evidência / resultado"]]
                st.dataframe(execution_view, hide_index=True, width="stretch")
        with tabs[1]:
            rows = discrepancies["cost_only"]
            if rows:
                st.dataframe(_dataframe_money(pd.DataFrame(rows), ["Valor"]), hide_index=True, width="stretch")
            else:
                st.caption("Todas as linhas possuem alguma correspondência sugerida ou confirmada.")
        with tabs[2]:
            rows = discrepancies["report_only"]
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            else:
                st.caption("Nenhuma entrega adicional foi identificada no relatório atual.")
        with tabs[3]:
            evidence_rows = discrepancies.get("briefing_evidence_unconsolidated") or []
            gap_rows = discrepancies["briefing_gaps"]
            if evidence_rows:
                st.markdown("**Demandas com resposta identificada, ainda aguardando confirmação de vínculo**")
                st.dataframe(pd.DataFrame(evidence_rows), hide_index=True, width="stretch")
            if gap_rows:
                st.markdown("**Demandas ainda sem evidência identificada**")
                st.dataframe(pd.DataFrame(gap_rows), hide_index=True, width="stretch")
            if not evidence_rows and not gap_rows:
                st.caption("Não foram identificadas demandas sem evidência.")

    technical_health = intelligence.get("technical_health") or []
    if technical_health:
        with st.expander("Saúde da leitura NAVE", expanded=False):
            st.caption("Diagnóstico técnico do processamento; não faz parte da análise de negócio.")
            for row in technical_health[:20]:
                severity = str(row.get("severity") or row.get("level") or "warning")
                message = f"**{row.get('title') or 'Aviso técnico'}** — {row.get('text') or ''}"
                if severity in {"critical", "high", "error"}:
                    st.error(message)
                else:
                    st.warning(message)

    history = snapshot.get("recommendation_queries", [])
    if history:
        with st.expander("Histórico de análises anteriores", expanded=False):
            for index, row in enumerate(history, start=1):
                title = row.get("query_label") or row.get("project_name") or f"Análise {index}"
                st.markdown(f"**{title}**")
                if row.get("objective"):
                    st.caption(str(row.get("objective")))

    st.caption(
        "A análise é atualizada quando novas fontes entram no projeto. "
        "Ausência de evidência não é tratada como prova de ausência."
    )
