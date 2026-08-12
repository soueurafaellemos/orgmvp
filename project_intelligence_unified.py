from __future__ import annotations

"""Unified Project Intelligence Snapshot — NAVE V28.4.

Esta camada não substitui as fontes nem o Intelligence Graph. Ela reconcilia o que
já existe em ambos para produzir UMA verdade operacional consumida por workspace,
Project Analyst e Dossiê Inteligente.
"""

import difflib
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


_STAGE_LABELS = {
    "proposal": "Em proposta / concorrência",
    "won": "Ganho / aprovado",
    "lost": "Concorrência perdida / proposta não aprovada",
    "no_return": "Sem resposta",
    "production": "Em produção",
    "executed": "Executado",
    "cancelled": "Cancelado",
}

_STRATEGY_TERMS = {
    "estrategia", "strategy", "conceito", "concept", "pontos de partida",
    "premissa", "point of view", "pov", "territorio", "territory", "insight",
    "memoria afetiva", "conexao", "presenca", "nostalgia", "racional",
    "desafio", "objetivo", "proposta de valor", "posicionamento",
}
_SCENOGRAPHY_TERMS = {
    "cenografia", "cenografico", "ambientacao", "fachada", "arquitetura",
    "casa", "estande", "stand", "estrutura", "render", "layout", "implantacao",
    "mobiliario", "portal", "backdrop", "ambiente",
}
_ACTIVATION_TERMS = {
    "ativacao", "experiencia", "brincadeira", "jogo", "game", "oficina",
    "amarelinha", "pescaria", "memoria", "origami", "tatuagem", "colorir",
    "mascote", "quiz", "photo op", "interacao", "dinamica",
}
_GIFT_TERMS = {"brinde", "press kit", "presskit", "gift", "chaveiro", "pelucia", "meia", "kit", "seeding"}
_JOURNEY_TERMS = {"jornada", "journey", "cronograma", "timeline", "operacao", "fluxo", "agenda", "recreadores", "uniformes"}
_COMMUNICATION_TERMS = {"comunicacao", "communication", "convite", "save the date", "social", "conteudo", "foto", "video"}
_EXECUTION_MARKERS = {
    "presentes no evento", "produzidas", "distribuidas", "sobras", "fotos",
    "after movie", "realizado", "executado", "visao geral", "recap",
}

_STOP = {
    "de", "da", "do", "das", "dos", "e", "em", "para", "por", "com", "sem",
    "um", "uma", "ao", "aos", "na", "no", "nas", "nos", "the", "and", "for",
    "project", "projeto", "event", "evento", "material", "visual", "sent", "client",
}


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    return {tok for tok in _norm(value).split() if len(tok) >= 3 and tok not in _STOP}


def _clip(value: Any, limit: int = 520) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _role_maps(graph: Mapping[str, Any]) -> tuple[dict[str, set[str]], dict[str, dict[str, Any]]]:
    roles: dict[str, set[str]] = defaultdict(set)
    for row in graph.get("contexts") or []:
        asset_id = str(row.get("source_asset_id") or "")
        if asset_id:
            roles[asset_id].add(str(row.get("context_role") or ""))
    assets = {str(row.get("id")): row for row in graph.get("source_assets") or [] if row.get("id")}
    return roles, assets


def _evidence_ref(row: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]], roles: Mapping[str, set[str]]) -> dict[str, Any]:
    asset_id = str(row.get("source_asset_id") or "")
    asset = assets.get(asset_id) or {}
    locator = row.get("locator") if isinstance(row.get("locator"), Mapping) else {}
    locator_text = ""
    if locator:
        for key in ("page", "slide", "sheet", "row", "paragraph", "section"):
            if locator.get(key) not in (None, ""):
                locator_text = f"{key} {locator.get(key)}"
                break
    return {
        "evidence_id": str(row.get("id") or ""),
        "source_asset_id": asset_id,
        "source_name": asset.get("canonical_file_name") or "Fonte",
        "source_roles": sorted(roles.get(asset_id, set())),
        "unit_type": row.get("unit_type"),
        "ordinal": row.get("ordinal"),
        "locator": dict(locator),
        "locator_text": locator_text,
        "text": _clip(row.get("content_text"), 900),
        "confidence": _safe_float(row.get("extraction_confidence")) or 0.0,
    }


def _best_claim(graph: Mapping[str, Any], predicate: str, *, subject_id: str | None = None) -> dict[str, Any] | None:
    candidates = []
    for row in graph.get("claims") or []:
        if str(row.get("predicate") or "") != predicate or str(row.get("status") or "active") not in {"active", "review_required"}:
            continue
        if subject_id and str(row.get("subject_entity_id") or "") != subject_id:
            continue
        authority = _safe_float(row.get("authority_score")) or 0.0
        confidence = _safe_float(row.get("model_confidence")) or 0.0
        candidates.append((authority * 0.65 + confidence * 0.35, row))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _claim_value(row: Mapping[str, Any] | None) -> Any:
    if not row:
        return None
    kind = str(row.get("value_type") or "")
    if kind == "numeric":
        return _safe_float(row.get("value_numeric"))
    if kind == "boolean":
        return row.get("value_boolean")
    if kind == "date":
        return row.get("value_date")
    if kind == "timestamp":
        return row.get("value_timestamp")
    if kind == "json":
        return row.get("value_json")
    if kind == "entity":
        return row.get("object_entity_id")
    return row.get("value_text")


def _legacy_stage(snapshot: Mapping[str, Any]) -> tuple[str, str]:
    project = snapshot.get("project") or {}
    outcome = snapshot.get("outcome") or {}
    status = str(project.get("status") or "")
    commercial = str(outcome.get("commercial_result") or "")
    execution = str(outcome.get("execution_result") or "")
    if execution in {"executed", "partially_executed"} or status == "executado":
        return "executed", _STAGE_LABELS["executed"]
    if execution == "in_progress" or status == "em_producao":
        return "production", _STAGE_LABELS["production"]
    if commercial == "lost" or status == "perdido":
        return "lost", _STAGE_LABELS["lost"]
    if commercial == "cancelled" or status == "cancelado":
        return "cancelled", _STAGE_LABELS["cancelled"]
    if commercial == "no_return":
        return "no_return", _STAGE_LABELS["no_return"]
    if commercial == "won" or status == "aprovado_ganho":
        return "won", _STAGE_LABELS["won"]
    return "proposal", _STAGE_LABELS["proposal"]


def _domain_units(graph: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    roles, assets = _role_maps(graph)
    domains = {key: [] for key in ("strategy", "scenography", "activations", "gifts", "journey_operation", "communication", "execution")}
    term_map = {
        "strategy": _STRATEGY_TERMS,
        "scenography": _SCENOGRAPHY_TERMS,
        "activations": _ACTIVATION_TERMS,
        "gifts": _GIFT_TERMS,
        "journey_operation": _JOURNEY_TERMS,
        "communication": _COMMUNICATION_TERMS,
    }
    for row in graph.get("evidence_units") or []:
        text = str(row.get("content_text") or "")
        if not text.strip():
            continue
        norm = _norm(text)
        asset_id = str(row.get("source_asset_id") or "")
        source_roles = roles.get(asset_id, set())
        ref = _evidence_ref(row, assets, roles)
        for domain, terms in term_map.items():
            score = sum(1 for term in terms if _norm(term) in norm)
            if score:
                # Estratégia deve nascer principalmente de briefing/proposta, não de um relatório que apenas repete o termo.
                if domain == "strategy" and not ({"proposal_presentation", "final_presentation", "briefing_original"} & source_roles):
                    continue
                enriched = dict(ref)
                enriched["semantic_score"] = score
                domains[domain].append(enriched)
        if "post_event_report" in source_roles and any(marker in norm for marker in _EXECUTION_MARKERS):
            enriched = dict(ref)
            enriched["semantic_score"] = sum(1 for marker in _EXECUTION_MARKERS if marker in norm)
            domains["execution"].append(enriched)
    for key, values in domains.items():
        # Dedup por evidência e prioriza densidade sem apagar ordem documental.
        by_id = {row["evidence_id"]: row for row in values}
        domains[key] = sorted(by_id.values(), key=lambda row: (-int(row.get("semantic_score") or 0), int(row.get("ordinal") or 10**9)))[:30]
    return domains


def _distinctive_tokens(value: Any) -> set[str]:
    generic = {
        "2024", "2025", "2026", "2027", "2028", "apresenta", "apresentacao",
        "proposta", "evento", "festival", "projeto", "material", "conteudo",
        "execucao", "relatorio", "marca", "cliente",
    }
    return {
        token for token in _tokens(value)
        if token not in generic and not token.isdigit() and len(token) >= 4
    }


def _match_score(query: Any, candidate: Any) -> float:
    """Similaridade conservadora para vínculos cross-source.

    Ano, número, palavras genéricas ou trechos curtos nunca são evidência de que
    uma solução apresentada é a mesma coisa registrada no pós-evento.
    """
    left = _norm(query)
    right = _norm(candidate)
    if not left or not right:
        return 0.0
    lt, rt = _distinctive_tokens(left), _distinctive_tokens(right)
    shared = lt & rt
    if not shared:
        return 0.0
    if left in right or right in left:
        shorter = left if len(left) <= len(right) else right
        if len(shorter) >= 6 and _distinctive_tokens(shorter):
            return 0.97
    jaccard = len(shared) / max(1, len(lt | rt))
    containment = len(shared) / max(1, min(len(lt), len(rt)))
    sequence = difflib.SequenceMatcher(None, " ".join(sorted(lt)), " ".join(sorted(rt))).ratio()
    # Um token distintivo idêntico (ex.: AMARELINHA) pode ser suficiente quando
    # ele é o nome da solução; termos compartilhados mais genéricos exigem densidade.
    single_name_boost = 0.90 if len(shared) == 1 and next(iter(shared)) in {left, right} else 0.0
    return max(single_name_boost, jaccard, containment * 0.94, sequence * 0.72)


def _execution_matches(snapshot: Mapping[str, Any], domains: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    report_units = domains.get("execution") or []
    # Inclui também headings do pós-evento, mesmo quando não têm marcador de resultado.
    graph = snapshot.get("intelligence_graph") or {}
    roles, assets = _role_maps(graph)
    for row in graph.get("evidence_units") or []:
        asset_id = str(row.get("source_asset_id") or "")
        if "post_event_report" not in roles.get(asset_id, set()) or not row.get("content_text"):
            continue
        ref = _evidence_ref(row, assets, roles)
        if ref["evidence_id"] not in {u["evidence_id"] for u in report_units}:
            report_units.append(ref)

    matches: list[dict[str, Any]] = []
    for item in snapshot.get("memory_items") or []:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        best: tuple[float, dict[str, Any] | None] = (0.0, None)
        for ev in report_units:
            score = _match_score(title, ev.get("text"))
            if score > best[0]:
                best = (score, ev)
        if best[1] and best[0] >= 0.58:
            matches.append({
                "item_id": str(item.get("id") or ""),
                "item_title": title,
                "status": "executed_with_evidence",
                "score": round(best[0], 4),
                "evidence": best[1],
            })
    return matches


def _briefing_matches(snapshot: Mapping[str, Any], domains: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    graph = snapshot.get("intelligence_graph") or {}
    roles, assets = _role_maps(graph)
    proposal_units = []
    for row in graph.get("evidence_units") or []:
        asset_id = str(row.get("source_asset_id") or "")
        if not ({"proposal_presentation", "final_presentation"} & roles.get(asset_id, set())) or not row.get("content_text"):
            continue
        proposal_units.append(_evidence_ref(row, assets, roles))

    matches: list[dict[str, Any]] = []
    for req in snapshot.get("briefing_requirements") or []:
        text = " ".join(str(req.get(key) or "") for key in ("title", "description", "source_quote", "requirement_type"))
        best = (0.0, None)
        for ev in proposal_units:
            score = _match_score(text, ev.get("text"))
            # Broad deliverables benefit from explicit term overlap even when descriptions are long.
            rt = _tokens(text)
            et = _tokens(ev.get("text"))
            if rt and et:
                score = max(score, len(rt & et) / max(1, min(len(rt), 8)) * 0.85)
            if score > best[0]:
                best = (score, ev)
        if best[1] and best[0] >= 0.38:
            matches.append({
                "requirement_id": str(req.get("id") or ""),
                "requirement_title": req.get("title") or "Demanda",
                "score": round(min(best[0], 0.98), 4),
                "evidence": best[1],
                "status": "evidence_found",
            })
    return matches


def _report_results(snapshot: Mapping[str, Any], domains: Mapping[str, list[dict[str, Any]]], execution_matches: list[dict[str, Any]]) -> dict[str, Any]:
    report = (snapshot.get("report_analyses") or [None])[0]
    if report:
        return {
            "executive_summary": report.get("executive_summary"),
            "participants_count": report.get("participants_count"),
            "participants_scope": "event_or_report_scope",
            "highlights": report.get("highlights") or [],
            "issues": report.get("issues") or [],
            "learnings": report.get("learnings") or [],
            "recommendations": report.get("recommendations") or [],
            "kpis": report.get("kpis") or [],
            "activation_results": report.get("activation_results") or [],
            "item_results": report.get("item_results") or [],
            "pending": [],
            "data_quality": [],
            "source": "structured_post_event_report",
        }

    report_units = domains.get("execution") or []
    event_attendance = None
    pending: list[str] = []
    data_quality: list[str] = []
    for ev in report_units:
        text = str(ev.get("text") or "")
        norm = _norm(text)
        match = re.search(r"\b([0-9]{1,3})\s*mil\s+pessoas\s+presentes\s+no\s+evento\b", norm)
        if match:
            event_attendance = float(match.group(1)) * 1000
        if "after movie" in norm and "aguardando" in norm:
            pending.append("After movie registrado como aguardando no relatório pós-evento.")

    # Reconciliação determinística das tabelas de distribuição presentes em PPTX.
    graph = snapshot.get("intelligence_graph") or {}
    roles, _ = _role_maps(graph)
    for row in graph.get("evidence_units") or []:
        if "post_event_report" not in roles.get(str(row.get("source_asset_id") or ""), set()):
            continue
        payload = row.get("content_json") if isinstance(row.get("content_json"), Mapping) else {}
        for table in payload.get("tables") or []:
            if not isinstance(table, list) or len(table) < 2:
                continue
            header = [_norm(cell) for cell in table[0]]
            try:
                prod_idx = next(i for i, v in enumerate(header) if "produz" in v)
                sobra_idx = next(i for i, v in enumerate(header) if "sobra" in v)
                dist_idx = next(i for i, v in enumerate(header) if "distrib" in v)
            except StopIteration:
                continue
            for data_row in table[1:]:
                if not isinstance(data_row, list) or len(data_row) <= max(prod_idx, sobra_idx, dist_idx):
                    continue
                def num(value: Any) -> float | None:
                    m = re.search(r"-?\d+(?:[.,]\d+)?", str(value or ""))
                    return float(m.group(0).replace(",", ".")) if m else None
                produced, leftovers, distributed = num(data_row[prod_idx]), num(data_row[sobra_idx]), num(data_row[dist_idx])
                if produced is None or leftovers is None or distributed is None:
                    continue
                if abs((produced - leftovers) - distributed) > 0.01:
                    item_name = str(data_row[0] or "Item")
                    data_quality.append(
                        f"{item_name}: produzidas ({produced:g}), sobras ({leftovers:g}) e distribuídas ({distributed:g}) não reconciliam."
                    )
    return {
        "executive_summary": None,
        "participants_count": event_attendance,
        "participants_scope": "festival_event" if event_attendance is not None else None,
        "highlights": [f"{row['item_title']} possui evidência posterior de execução." for row in execution_matches[:12]],
        "issues": [],
        "learnings": [],
        "recommendations": [],
        "kpis": [],
        "activation_results": [
            {"name": row["item_title"], "status": "executed", "evidence": row["evidence"].get("text")}
            for row in execution_matches
        ],
        "item_results": [],
        "pending": list(dict.fromkeys(pending)),
        "data_quality": list(dict.fromkeys(data_quality)),
        "source": "graph_post_event_evidence",
    }


def build_unified_project_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    graph = snapshot.get("intelligence_graph") if isinstance(snapshot.get("intelligence_graph"), Mapping) else {}
    roles, assets = _role_maps(graph)
    project_entity = graph.get("project_entity") if isinstance(graph.get("project_entity"), Mapping) else None
    project_entity_id = str((project_entity or {}).get("id") or "") or None

    domains = _domain_units(graph)
    execution_matches = _execution_matches(snapshot, domains)
    briefing_matches = _briefing_matches(snapshot, domains)

    # Truth: fonte pós-evento com marcadores fortes supera estado legado de proposta.
    report_file_present = any(
        str(row.get("file_role") or "") in {"post_execution_report", "closure_report"}
        and not row.get("is_archived")
        for row in snapshot.get("project_files") or []
    ) or any("post_event_report" in values for values in roles.values())
    report_structured = bool(snapshot.get("report_analyses"))
    execution_claim = _best_claim(graph, "execution_result", subject_id=project_entity_id) if project_entity_id else None
    execution_claim_value = str(_claim_value(execution_claim) or "")
    strong_report_evidence = len(domains.get("execution") or []) >= 2

    stage, stage_label = _legacy_stage(snapshot)
    execution_confidence = "legacy"
    if execution_claim_value in {"executed", "partially_executed"}:
        stage, stage_label, execution_confidence = "executed", _STAGE_LABELS["executed"], "graph_claim"
    elif report_structured and str((snapshot.get("report_analyses") or [{}])[0].get("execution_result") or "") in {"executed", "partially_executed"}:
        stage, stage_label, execution_confidence = "executed", _STAGE_LABELS["executed"], "structured_report"
    elif report_file_present and strong_report_evidence:
        stage, stage_label, execution_confidence = "executed", _STAGE_LABELS["executed"], "post_event_evidence"

    budget = None
    budget_source = None
    for doc in snapshot.get("briefing_documents") or []:
        budget = _safe_float(doc.get("budget_amount"))
        if budget is not None:
            budget_source = "briefing_structured"
            break
    if budget is None and project_entity_id:
        claim = _best_claim(graph, "budget_max", subject_id=project_entity_id)
        budget = _safe_float(_claim_value(claim))
        if budget is not None:
            budget_source = "briefing_graph_claim"
    if budget is None:
        budget = _safe_float((snapshot.get("outcome") or {}).get("budget_amount"))
        if budget is not None:
            budget_source = "outcome"

    domain_legacy_counts = defaultdict(int)
    for item in snapshot.get("memory_items") or []:
        section = str(item.get("section_key") or "")
        if section:
            domain_legacy_counts[section] += 1
    coverage = {}
    for domain in ("strategy", "scenography", "activations", "gifts", "journey_operation", "communication"):
        legacy_count = domain_legacy_counts.get(domain, 0)
        evidence_count = len(domains.get(domain) or [])
        if legacy_count:
            state = "structured"
        elif evidence_count:
            state = "evidence_found_not_consolidated"
        else:
            state = "no_evidence"
        coverage[domain] = {"state": state, "legacy_count": legacy_count, "evidence_count": evidence_count}

    results = _report_results(snapshot, domains, execution_matches)

    consistency: list[dict[str, Any]] = []
    legacy_stage, legacy_label = _legacy_stage(snapshot)
    if stage == "executed" and legacy_stage in {"proposal", "won", "no_return"}:
        consistency.append({
            "code": "execution_stage_conflict", "severity": "critical",
            "title": "Status do projeto contradiz evidência de execução",
            "text": f"A leitura legada indica '{legacy_label}', mas há evidência pós-evento suficiente para tratar o projeto como executado.",
            "recommended_action": "Usar a verdade consolidada de execução e sincronizar o estado legado.",
        })
    if report_file_present and not report_structured and strong_report_evidence:
        consistency.append({
            "code": "report_false_unstructured", "severity": "high",
            "title": "Relatório pós-evento possui evidências, mas não está estruturado no legado",
            "text": "O Intelligence Graph já contém conteúdo pós-evento; a interface não deve apresentar esse arquivo como simplesmente 'aguardando leitura'.",
            "recommended_action": "Consolidar automaticamente o relatório e projetar seus resultados no workspace.",
        })
    domain_labels = {
        "strategy": "Estratégia e conceito",
        "scenography": "Cenografia e ambientes",
        "activations": "Ativações e experiências",
        "gifts": "Brindes e press kits",
        "journey_operation": "Jornada e operação",
        "communication": "Comunicação e materiais",
        "execution": "Execução e pós-evento",
    }
    for domain, state in coverage.items():
        if state["state"] == "evidence_found_not_consolidated":
            consistency.append({
                "code": f"false_empty_{domain}", "severity": "high",
                "title": f"Falso vazio em {domain_labels.get(domain, domain)}",
                "text": f"Há {state['evidence_count']} evidência(s) semanticamente relacionadas, embora a estrutura legada esteja vazia.",
                "recommended_action": "Projetar as evidências do Unified Snapshot em vez de exibir estado vazio.",
            })
    if budget is not None and all(_safe_float(doc.get("budget_amount")) is None for doc in snapshot.get("briefing_documents") or []):
        consistency.append({
            "code": "budget_graph_legacy_gap", "severity": "high",
            "title": "Budget comprovado não chegou à estrutura legada",
            "text": f"O Intelligence Graph identifica budget de {budget:.2f}, mas o briefing estruturado não expõe esse valor.",
            "recommended_action": "Usar o claim de maior autoridade no Unified Snapshot e sincronizar o parser do briefing.",
        })

    # Decision Intelligence determinística — conclusões cross-source que já podem ser auditadas.
    diagnostics: list[dict[str, Any]] = []
    results_findings: list[dict[str, Any]] = []
    learnings: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []

    if stage == "executed":
        diagnostics.append({
            "kind": "fact", "importance": "high", "title": "Projeto com evidência de execução",
            "text": "Há fonte pós-evento e evidências posteriores suficientes para analisar o projeto como executado, não apenas como proposta.",
            "evidence": (domains.get("execution") or [])[:4],
        })
    if execution_matches:
        results_findings.append({
            "kind": "fact", "importance": "high", "title": "Proposta materializada em execução",
            "text": f"{len(execution_matches)} entrega(s) estruturada(s) da apresentação possuem correspondência direta em evidências pós-evento.",
            "evidence": [row["evidence"] for row in execution_matches[:8]],
        })
        connections.append({
            "kind": "inference", "importance": "high", "title": "Proposta ↔ execução",
            "text": "A NAVE encontrou continuidade entre soluções apresentadas e registros pós-evento; essas soluções devem alimentar repertório como materializadas, sem assumir resultado de performance não documentado.",
            "evidence": [row["evidence"] for row in execution_matches[:8]],
        })
    if briefing_matches:
        diagnostics.append({
            "kind": "inference", "importance": "high", "title": "Briefing possui respostas identificáveis na proposta",
            "text": f"A NAVE encontrou evidência de resposta para {len(briefing_matches)} demanda(s) do briefing na apresentação, embora os links legados ainda possam estar incompletos.",
            "evidence": [row["evidence"] for row in briefing_matches[:8]],
        })

    # Strategy → execution connection.
    if domains.get("strategy") and execution_matches:
        connections.append({
            "kind": "inference", "importance": "high", "title": "Estratégia ↔ materialização",
            "text": "O projeto contém uma camada estratégica explícita e soluções posteriormente registradas no pós-evento. O Project Analyst deve avaliar se a execução preservou os princípios estratégicos, e não apenas se itens físicos apareceram.",
            "evidence": [*(domains.get("strategy") or [])[:4], *[row["evidence"] for row in execution_matches[:4]]],
        })

    # Financial tension: general rule, not client-specific.
    category_rows = []
    for doc in snapshot.get("cost_documents") or []:
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), Mapping) else {}
        for row in metadata.get("category_breakdown") or []:
            if isinstance(row, Mapping):
                category_rows.append(dict(row))
    if not category_rows:
        # Advanced parser often stores totals in cost items only; rebuild category totals.
        totals = defaultdict(float)
        total = 0.0
        for row in snapshot.get("cost_items") or []:
            value = _safe_float(row.get("client_total")) or 0.0
            category = str(row.get("category") or "Não informada")
            totals[category] += value
            total += value
        category_rows = [{"category": key, "client_total": value, "share": value / total if total else 0.0} for key, value in totals.items()]
    category_rows.sort(key=lambda row: _safe_float(row.get("client_total")) or 0.0, reverse=True)
    proposal_total = sum((_safe_float(row.get("client_total")) or 0.0) for row in snapshot.get("cost_items") or []) or None
    top_category = category_rows[0] if category_rows else None
    if top_category and proposal_total:
        top_value = _safe_float(top_category.get("client_total")) or 0.0
        top_share = top_value / proposal_total if proposal_total else 0.0
        diagnostics.append({
            "kind": "fact", "importance": "medium", "title": "Principal driver de custo",
            "text": f"{top_category.get('category') or 'Categoria principal'} concentra {top_share:.1%} do valor proposto ({top_value:.2f}).",
            "evidence": [],
        })
        brief_text = " ".join(str(row.get("content_text") or "") for row in graph.get("evidence_units") or [] if "briefing_original" in roles.get(str(row.get("source_asset_id") or ""), set()))
        brief_norm = _norm(brief_text)
        reduction_signal = any(term in brief_norm for term in ("menos dinheiro", "menos verba", "reduzir", "menos estrutura", "otimizar", "economia"))
        category_norm = _norm(top_category.get("category"))
        if reduction_signal and top_share >= 0.45 and any(term in category_norm for term in ("infraestrutura", "cenografia", "estrutura", "scenography")):
            connections.append({
                "kind": "inference", "importance": "high", "title": "Restrição financeira ↔ concentração da solução",
                "text": "O briefing contém sinal explícito de redução/otimização, enquanto a maior concentração financeira está justamente em infraestrutura/cenografia. Isso é uma tensão de decisão que deve ser analisada antes de concluir aderência financeira.",
                "evidence": (domains.get("strategy") or [])[:2],
            })
            learnings.append({
                "kind": "learning", "importance": "high", "title": "Criar teto específico para o principal driver",
                "text": "Quando o briefing pede redução estrutural, separar um teto por categoria antes do desenvolvimento criativo ajuda a evitar que a solução concentre o budget justamente no componente mais pressionado.",
                "evidence": [],
            })

    if results.get("participants_count") is not None and results.get("participants_scope") == "festival_event":
        learnings.append({
            "kind": "learning", "importance": "high", "title": "Audiência do evento ≠ impacto da ativação",
            "text": "O relatório informa público do evento/festival. Esse número não deve ser convertido em visitantes ou impactos da ativação sem fonte específica.",
            "evidence": (domains.get("execution") or [])[:2],
        })
    for issue in results.get("data_quality") or []:
        diagnostics.append({"kind": "contradiction", "importance": "high", "title": "Inconsistência de dado pós-evento", "text": issue, "evidence": []})
        learnings.append({"kind": "learning", "importance": "medium", "title": "Não corrigir números conflitantes por inferência", "text": "Quando produzido, sobra e distribuído não reconciliam, a NAVE deve preservar a inconsistência e solicitar validação, não inventar o valor faltante.", "evidence": []})
    for pending in results.get("pending") or []:
        results_findings.append({"kind": "fact", "importance": "medium", "title": "Entrega ainda pendente no pós-evento", "text": pending, "evidence": []})

    direct_payment_signal = any(
        "pagamento direto" in _norm(row.get("content_text"))
        or "forma direta" in _norm(row.get("content_text"))
        for row in graph.get("evidence_units") or []
        if "briefing_original" in roles.get(str(row.get("source_asset_id") or ""), set())
    )
    if proposal_total and budget:
        if proposal_total > budget:
            if direct_payment_signal:
                recommendations.append({
                    "kind": "recommendation", "importance": "high", "title": "Reconciliar envelope antes de chamar de estouro",
                    "text": "O total bruto supera o budget nominal, mas há indicação de pagamento direto pelo cliente. Separar responsabilidades financeiras antes de classificar aderência ou estouro.",
                    "evidence": [],
                })
            else:
                recommendations.append({
                    "kind": "recommendation", "importance": "high", "title": "Atacar os maiores drivers de custo",
                    "text": "A proposta supera o teto identificado. Priorizar negociação/otimização nas categorias de maior concentração preserva mais valor estratégico do que cortes pulverizados.",
                    "evidence": [],
                })
    if execution_matches:
        recommendations.append({
            "kind": "recommendation", "importance": "high", "title": "Fechar resultados por solução",
            "text": "Para cada ativação executada, registrar quantidade prevista, realizada, participação/uso, custo e resultado. Isso transforma comprovação de execução em benchmark de eficiência.",
            "evidence": [],
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_truth": {
            "stage": stage,
            "stage_label": stage_label,
            "execution_confidence_source": execution_confidence,
            "has_post_event_source": report_file_present,
            "report_structured": report_structured,
            "process_type": str((snapshot.get("outcome") or {}).get("process_type") or "not_informed"),
            "budget_amount": budget,
            "budget_source": budget_source,
        },
        "coverage": coverage,
        "domain_evidence": domains,
        "execution_matches": execution_matches,
        "briefing_matches": briefing_matches,
        "results": results,
        "financial_context": {
            "proposal_total": proposal_total,
            "budget_amount": budget,
            "direct_payment_signal": direct_payment_signal,
            "requires_responsibility_reconciliation": bool(direct_payment_signal and proposal_total and budget and proposal_total > budget),
        },
        "consistency_issues": consistency,
        "decision_intelligence": {
            "diagnostic": diagnostics,
            "results": results_findings,
            "learnings": learnings,
            "recommendations": recommendations,
            "connections": connections,
        },
    }
