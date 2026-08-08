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
        "area externa": 3, "area interna": 3, "casa chambinho": 6,
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
        for key in ("suggested_title", "suggested_section", "slide_title", "slide_summary"):
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

    stage_key, stage_label = project_stage(snapshot)
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

    matrix: list[dict[str, Any]] = []
    executed_count = 0
    explicit_not_executed = 0
    no_execution_evidence = 0

    for item in items:
        item_id = str(item.get("id") or "")
        outcome = outcomes.get(item_id) or {}
        outcome_status = str(outcome.get("outcome_status") or "unassessed")
        if proposal_stage:
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
            "Evidência / resultado": outcome.get("feedback_summary") or outcome.get("execution_notes") or outcome.get("decision_reason") or "—",
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
    briefing_gaps = []
    for requirement in snapshot.get("briefing_requirements", []):
        req_id = str(requirement.get("id") or "")
        status = str(requirement.get("adherence_status") or "not_assessed")
        if req_id in linked_requirement_ids and status in POSITIVE_ADHERENCE:
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
    if briefing_gaps:
        findings.append({
            "level": "warning",
            "title": "Briefing × evidências",
            "text": f"{len(briefing_gaps)} demanda(s) do briefing ainda não possuem evidência consolidada de atendimento.",
        })
    for key, source in coverage.items():
        if source["state"] == "attached":
            findings.append({
                "level": "warning",
                "title": f"{source['label']} sem estruturação",
                "text": "O arquivo está salvo no projeto, mas seu conteúdo ainda não entrou no cruzamento inteligente.",
            })

    recommendations: list[str] = []
    if cost_only:
        recommendations.append("Revisar as linhas de custo sem correspondência e confirmar se representam entregas adicionais, custos transversais ou itens omitidos da apresentação.")
    if proposed_without_cost:
        recommendations.append("Revisar as propostas sem custo direto: algumas podem estar agrupadas em linhas cenográficas ou operacionais e precisam de confirmação humana.")
    if no_execution_evidence and not proposal_stage:
        recommendations.append("Validar as entregas sem evidência no relatório. Ausência de evidência não significa que o item não foi executado.")
    if report_only:
        recommendations.append("Classificar as entregas identificadas apenas no pós-evento como adaptações de produção, escopo adicional ou substituições da proposta.")
    if briefing_gaps:
        recommendations.append("Revisar a matriz de aderência do briefing e registrar evidência, justificativa ou retirada por budget/prazo para cada lacuna.")
    if budget_amount is not None and cost_total is None and snapshot.get("cost_documents"):
        recommendations.append("Reprocessar ou revisar a estrutura da planilha de custos para transformar o budget do briefing em uma análise financeira comparável.")
    if not snapshot.get("feedback_entries") and stage_key not in {"executed", "lost", "cancelled"}:
        recommendations.append("Quando houver retorno do cliente, registrar o resultado comercial para atualizar automaticamente a leitura do projeto.")
    if not recommendations:
        recommendations.append("Manter o projeto atualizado com novas versões, feedbacks e resultados para preservar o ciclo de aprendizado.")

    latest_report = snapshot.get("report_analyses", [None])[0] if snapshot.get("report_analyses") else None
    result_summary = {
        "executive_summary": (latest_report or {}).get("executive_summary"),
        "highlights": (latest_report or {}).get("highlights") or [],
        "issues": (latest_report or {}).get("issues") or [],
        "learnings": (latest_report or {}).get("learnings") or [],
        "recommendations": (latest_report or {}).get("recommendations") or [],
        "kpis": (latest_report or {}).get("kpis") or [],
        "participants_count": (latest_report or {}).get("participants_count"),
        "planned_cost": (latest_report or {}).get("planned_cost"),
        "actual_cost": (latest_report or {}).get("actual_cost"),
    }

    return {
        "source_signature": _source_signature(snapshot),
        "coverage": coverage,
        "metrics": metrics,
        "matrix": matrix,
        "findings": findings,
        "recommendations": recommendations,
        "discrepancies": {
            "cost_only": cost_only,
            "report_only": report_only,
            "briefing_gaps": briefing_gaps,
            "proposed_without_cost": proposed_without_cost,
        },
        "result_summary": result_summary,
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

    st.subheader("Diagnóstico, recomendações, resultados e aprendizados")
    st.caption(
        "Leitura cumulativa do projeto. O diagnóstico é recalculado sempre que briefing, "
        "apresentação, planilha, relatório ou feedback recebe uma nova informação."
    )

    if new_cost_links or new_brief_links:
        st.success(
            f"A NAVE criou {new_cost_links} nova(s) sugestão(ões) de custo e "
            f"{new_brief_links} nova(s) sugestão(ões) de aderência para revisão."
        )

    st.markdown("#### Cobertura das fontes")
    coverage = intelligence["coverage"]
    columns = st.columns(5)
    for column, key in zip(columns, ("briefing", "presentation", "cost", "report", "feedback")):
        with column:
            st.markdown(_render_source_card(coverage[key]), unsafe_allow_html=True)

    metrics = intelligence["metrics"]
    st.markdown("#### Visão executiva")
    if metrics.get("stage") in {"proposal", "no_return", "won"}:
        metric_columns = st.columns(6)
        metric_columns[0].metric("Situação", metrics.get("stage_label") or "Em proposta")
        metric_columns[1].metric("Demandas do briefing", metrics["briefing_requirements"])
        metric_columns[2].metric("Entregas apresentadas", metrics["presentation_items"])
        metric_columns[3].metric("Com custo direto", metrics["items_with_cost"])
        metric_columns[4].metric("Custos sem proposta", metrics["cost_only_items"])
        metric_columns[5].metric("Lacunas do briefing", metrics["briefing_gaps"])
        st.info("Este projeto ainda não está em etapa de execução. A análise abaixo compara briefing, proposta e custos; execução só entra quando houver evidência posterior.")
    else:
        metric_columns = st.columns(6)
        metric_columns[0].metric("Demandas do briefing", metrics["briefing_requirements"])
        metric_columns[1].metric("Entregas apresentadas", metrics["presentation_items"])
        metric_columns[2].metric("Com custo direto", metrics["items_with_cost"])
        metric_columns[3].metric("Executadas com evidência", metrics["executed_with_evidence"])
        metric_columns[4].metric("Sem evidência de execução", metrics["without_execution_evidence"])
        metric_columns[5].metric("Custos sem proposta", metrics["cost_only_items"])
        st.info(
            "A classificação ‘sem evidência de execução’ não significa que a entrega não aconteceu. "
            "Ela indica apenas que os arquivos atuais ainda não comprovam o resultado."
        )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Diagnóstico")
        for finding in intelligence["findings"]:
            css_class = "nave-diagnostic-alert" if finding.get("level") == "warning" else "nave-diagnostic-callout"
            st.markdown(
                f'<div class="{css_class}"><strong>{finding.get("title")}</strong><br>{finding.get("text")}</div>',
                unsafe_allow_html=True,
            )
    with right:
        st.markdown("#### Recomendações")
        for index, recommendation in enumerate(intelligence["recommendations"], start=1):
            st.markdown(f"**{index}.** {recommendation}")

    st.markdown("#### Matriz integrada do projeto")
    matrix = pd.DataFrame(intelligence["matrix"])
    if matrix.empty:
        st.warning("Ainda não há entregas estruturadas suficientes para montar a matriz.")
    else:
        display = matrix.drop(columns=["item_id", "section_key"], errors="ignore")
        display = _dataframe_money(display, ["Custo direto"])
        st.dataframe(display, hide_index=True, width="stretch", height=min(680, 95 + len(display) * 38))

    discrepancies = intelligence["discrepancies"]
    proposal_view = metrics.get("stage") in {"proposal", "no_return", "won"}
    tabs = st.tabs([
        "Proposta × custos" if proposal_view else "Proposta × execução",
        "Custos sem proposta",
        "Entregas fora da apresentação",
        "Briefing sem evidência",
        "Resultados e aprendizados",
    ])

    with tabs[0]:
        if matrix.empty:
            st.caption("Nenhuma entrega estruturada.")
        elif proposal_view:
            proposal_df = matrix[[
                "Item apresentado", "Área", "Situação na apresentação", "Briefing", "Custo direto", "Correlação do custo"
            ]]
            proposal_df = _dataframe_money(proposal_df, ["Custo direto"])
            st.dataframe(proposal_df, hide_index=True, width="stretch")
        else:
            execution_view = matrix[[
                "Item apresentado", "Área", "Execução", "Evidência / resultado"
            ]]
            st.dataframe(execution_view, hide_index=True, width="stretch")

    with tabs[1]:
        rows = discrepancies["cost_only"]
        if rows:
            df = _dataframe_money(pd.DataFrame(rows), ["Valor"])
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.success("Todas as linhas da planilha possuem alguma correspondência sugerida ou confirmada.")

    with tabs[2]:
        rows = discrepancies["report_only"]
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma entrega adicional foi identificada no relatório atual.")

    with tabs[3]:
        rows = discrepancies["briefing_gaps"]
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.success("Não foram identificadas demandas sem evidência consolidada.")

    with tabs[4]:
        result = intelligence["result_summary"]
        if not result.get("executive_summary"):
            st.caption("O relatório pós-evento ainda não possui leitura estruturada.")
        else:
            result_metrics = st.columns(4)
            result_metrics[0].metric("Participantes", result.get("participants_count") or "—")
            result_metrics[1].metric("Custo previsto", _money(result.get("planned_cost")))
            result_metrics[2].metric("Custo realizado", _money(result.get("actual_cost")))
            variation = _safe_float(result.get("actual_cost")) - _safe_float(result.get("planned_cost"))
            result_metrics[3].metric("Variação", _money(variation) if result.get("actual_cost") is not None and result.get("planned_cost") is not None else "—")
            st.info(str(result.get("executive_summary")))
            two = st.columns(2)
            with two[0]:
                st.markdown("**Destaques**")
                for value in result.get("highlights") or []:
                    st.markdown(f"- {value}")
                st.markdown("**Aprendizados**")
                for value in result.get("learnings") or []:
                    st.markdown(f"- {value}")
            with two[1]:
                st.markdown("**Ocorrências**")
                for value in result.get("issues") or []:
                    st.markdown(f"- {value}")
                st.markdown("**Recomendações do relatório**")
                for value in result.get("recommendations") or []:
                    st.markdown(f"- {value}")
            if result.get("kpis"):
                st.markdown("**KPIs extraídos**")
                st.dataframe(pd.DataFrame(result["kpis"]), hide_index=True, width="stretch")

    history = snapshot.get("recommendation_queries", [])
    if history:
        st.markdown("#### Histórico de análises anteriores")
        for index, row in enumerate(history, start=1):
            title = row.get("query_label") or row.get("project_name") or f"Análise {index}"
            with st.expander(str(title), expanded=False):
                if row.get("objective"):
                    st.markdown(f"**Objetivo:** {row.get('objective')}")
                if row.get("briefing_text"):
                    st.write(row.get("briefing_text"))
                if isinstance(row.get("parsed_brief"), dict):
                    st.json(row.get("parsed_brief"))

    st.caption(
        "Snapshot atualizado a partir da combinação atual de fontes. "
        "Novos arquivos e feedbacks geram uma nova consolidação sem apagar o histórico anterior."
    )
