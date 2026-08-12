from __future__ import annotations

"""NAVE V28.2 — núcleo de inteligência de projeto.

O módulo mantém duas premissas:
1) evidência vem antes da inferência;
2) uma fonte pode gerar várias afirmações relacionadas a entidades diferentes.

Ele não depende de Streamlit ou Supabase e pode ser testado isoladamente.
"""

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field


ALLOWED_FEEDBACK_THEMES = {
    "strategy", "creative_concept", "kv", "scenography", "activation",
    "gift", "journey", "operation", "technology", "budget", "timeline",
    "presentation", "other",
}
ALLOWED_SENTIMENTS = {"positive", "negative", "neutral", "mixed"}
ALLOWED_ITEM_OUTCOMES = {
    "unassessed", "approved", "approved_with_changes", "not_approved",
    "replaced", "removed_budget", "removed_timeline", "executed",
    "not_executed", "unknown",
}
ALLOWED_RESULT_REASONS = {
    "brief_fit", "concept_strength", "originality", "brand_fit",
    "technical_feasibility", "timeline", "budget", "scope", "operation",
    "venue", "supplier", "commercial_relationship", "competitor",
    "client_internal_change", "project_cancelled", "not_informed", "other",
}


class FeedbackClaim(BaseModel):
    title: str
    theme: str = "other"
    sentiment: str = "neutral"
    evidence_quote: str | None = None
    interpretation: str | None = None
    related_entities: list[str] = Field(default_factory=list)
    result_reason: str | None = None
    item_outcome_status: str = "unassessed"
    recommended_learning: str | None = None


class FeedbackAnalysis(BaseModel):
    transcription: str | None = None
    source_type: str = "not_informed"
    process_stage: str = "not_informed"
    process_type: str = "not_informed"
    commercial_result: str = "in_evaluation"
    proposal_result: str = "not_informed"
    execution_result: str = "not_informed"
    confidence_level: str = "incomplete"
    decision_summary: str | None = None
    result_reasons: list[str] = Field(default_factory=list)
    claims: list[FeedbackClaim] = Field(default_factory=list)


class SemanticConnection(BaseModel):
    title: str
    analysis: str
    connection_type: str = "cross_source"
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    recommended_action: str | None = None


class StrategyFramework(BaseModel):
    territory: str | None = None
    tension: str | None = None
    pillars: list[str] = Field(default_factory=list)
    strategic_direction: str | None = None
    concept: str | None = None
    experience_role: str | None = None
    briefing_adherence: str | None = None


class ProjectSemanticSynthesis(BaseModel):
    executive_summary: str
    strategic_reading: str | None = None
    strategy_framework: StrategyFramework | None = None
    diagnostic: list[SemanticConnection] = Field(default_factory=list)
    results: list[SemanticConnection] = Field(default_factory=list)
    strongest_connections: list[SemanticConnection] = Field(default_factory=list)
    discovered_connections: list[SemanticConnection] = Field(default_factory=list)
    contradictions_or_gaps: list[SemanticConnection] = Field(default_factory=list)
    validated_learnings: list[str] = Field(default_factory=list)
    challenged_learnings: list[str] = Field(default_factory=list)
    decision_recommendations: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


PROJECT_ANALYST_PROMPT = r"""
Você é o Project Analyst da NAVE by VOE, especialista sênior em live marketing,
estratégia, criação, produção, experiência, operação e eficiência financeira.

Você receberá um PACOTE DE EVIDÊNCIAS já estruturado. Sua função NÃO é resumir
arquivos isoladamente. Sua função é CONECTAR as evidências e produzir inteligência
acionável sobre o projeto.

PRINCÍPIOS ABSOLUTOS
- Evidência antes de inferência. Não invente nenhuma relação.
- Uma conclusão só pode ser forte quando citar evidence_refs existentes no pacote.
- Diferencie claramente: pedido do briefing, solução proposta, custo orçado, feedback
  do cliente, resultado comercial e execução comprovada.
- Projeto perdido não significa que todas as soluções foram ruins; projeto ganho não
  significa que todas foram boas. Preserve aprendizados por item.
- Orçado/proposto não é gasto real. Só use linguagem de gasto/execução se houver
  fonte de execução.
- Feedback do cliente deve ser ligado, quando houver evidência, à solução específica
  apresentada e ao requisito do briefing correspondente.
- Procure contradições entre intenção estratégica e materialização. Ex.: a estratégia
  promete comportamento nativo de plataforma, mas a ativação apresentada não cumpre.
- Procure concentração financeira, grandes drivers de custo e investimentos relevantes
  que tenham recebido crítica/validação.
- Procure requisitos críticos sem resposta, soluções sem custo, custos sem solução e
  decisões que deveriam ter sido antecipadas.
- Não transforme um feedback isolado em regra universal. Escreva aprendizados como
  evidência histórica contextualizada.
- EXECUÇÃO NÃO É PERFORMANCE: não use “sucesso”, “eficaz”, “alto engajamento”,
  “excelente aceitação”, “principal driver”, “alto índice de participação” ou linguagem
  equivalente sem KPI, feedback ou métrica específica que sustente a afirmação.
- Público do evento/festival NÃO é automaticamente visitante/participante da ativação.
  Nunca calcule custo por participante usando público do evento hospedeiro.
- Quando produzido, distribuído e saldo/sobra não reconciliam, preserve o conflito.
  Não calcule desperdício, sobra implícita ou eficiência a partir de números conflitantes.
- Não escreva linguagem de backend na saída de negócio: evite “Intelligence Graph”,
  “legado”, “links legados”, “pipeline”, “backend”, “fichas canônicas”, “materialização
  pendente” ou frases como “o Project Analyst deve avaliar”. Analise e entregue a conclusão.
- Se não houver evidência suficiente para uma conclusão de performance, diga de forma
  objetiva o que está comprovado e o que não foi mensurado.

CONNECTION TYPES preferidos
brief_to_solution, solution_to_cost, solution_to_feedback, brief_to_feedback,
cost_to_feedback, strategy_to_execution, commercial_decision, cross_project_ready,
cross_source.

CONFIDENCE: high somente quando a relação está explicitamente suportada por duas ou
mais evidências ou por fonte direta do cliente; medium para inferência forte; low para
hipótese útil que deve ser validada.

A resposta deve priorizar aquilo que mudaria uma decisão de pré-produção no próximo
projeto: o que preservar, o que corrigir, onde otimizar, que risco antecipar e que
repertório merece ser reutilizado.

ESTRATÉGIA E CONCEITO
Quando houver camada estratégica explícita, além de strategic_reading preencha strategy_framework:
- territory: território estratégico central;
- tension: problema/tensão que a estratégia resolve;
- pillars: 2 a 6 pilares explícitos ou fortemente sustentados;
- strategic_direction: como a proposta decide responder ao briefing;
- concept: conceito/POV central, se existir;
- experience_role: papel da experiência na vida/jornada do público;
- briefing_adherence: síntese de como a estratégia responde ao briefing.
Não copie blocos de slide. Sintetize sem inventar e preserve os termos relevantes da fonte.

O OURO DA NAVE são cinco saídas diferentes:
1. diagnostic: o que aconteceu e o que isso significa;
2. results: o que está comprovado como resultado/execução/pendência;
3. strongest_connections + discovered_connections: o que só aparece quando fontes são cruzadas;
4. validated_learnings/challenged_learnings: conhecimento reutilizável para a memória VOE;
5. decision_recommendations: decisões melhores e específicas, nunca tarefas burocráticas genéricas.

Não escreva como recomendação "revisar planilha" ou "validar matriz" se você puder
fazer a análise com as evidências recebidas. Só peça ação humana para uma ambiguidade
real que a NAVE não consegue resolver com as fontes atuais.

Se o unified_snapshot disser que há evidência pós-evento, NÃO trate o projeto como
mera proposta. Se uma área possui evidence_found_not_consolidated, NÃO conclua que o
conteúdo não existe: trate como falha de consolidação da NAVE.

Retorne SOMENTE JSON válido no schema solicitado.
""".strip()


FEEDBACK_PROMPT = r"""
Você é o módulo de inteligência de feedback da NAVE by VOE, plataforma de
pré-produção de live marketing.

Analise a fonte recebida como EVIDÊNCIA. Se for imagem, leia visualmente o texto.
Não invente nada que não esteja comprovado.

OBJETIVO
Transformar um único feedback em:
1. transcrição fiel;
2. decisão comercial, quando explícita;
3. várias afirmações independentes (claims), uma por assunto/entidade;
4. aprendizados que possam ser ligados ao que foi realmente apresentado.

REGRAS DE TRANSCRIÇÃO
- transcription deve preservar integralmente o conteúdo textual legível da fonte;
- não traduza a transcrição;
- preserve nomes próprios, números, prazos, valores e frases relevantes;
- se uma parte estiver ilegível, omita-a em vez de inventar.

REGRAS DE DECISÃO
process_type permitido: competition, direct, proactive, renewal, not_informed.
commercial_result permitido: in_evaluation, won, lost, cancelled, suspended,
no_return, not_applicable, not_informed.
proposal_result permitido: fully_approved, partially_approved, not_approved,
in_revision, no_feedback, not_informed.
execution_result permitido: executed, partially_executed, not_executed,
in_progress, not_applicable, not_informed.
confidence_level: client_confirmed quando a fonte do cliente explicita a decisão;
inferred somente para inferência clara; incomplete quando não há prova suficiente.

CLAIMS
Separe elogios e críticas diferentes. Não crie um único claim "misto" quando a
fonte fala de conceito, local, ativação, orçamento e prazo separadamente.

Themes permitidos:
strategy, creative_concept, kv, scenography, activation, gift, journey,
operation, technology, budget, timeline, presentation, other.

Sentiment: positive, negative, neutral, mixed.

related_entities deve conter nomes/textos que ajudem a encontrar a solução
apresentada, por exemplo: "JOVI X300 Series On Tour", "Cinemateca",
"YouTube activation", "Instagram activation".

item_outcome_status permitido:
- approved: elogio/validação explícita da solução;
- approved_with_changes: solução aceita conceitualmente, mas com ajuste explícito;
- not_approved: solução explicitamente rejeitada/inadequada;
- removed_budget: retirada explícita por orçamento;
- removed_timeline: retirada explícita por prazo;
- unassessed: quando o texto não permite concluir sobre a solução.
Não use executed/not_executed sem evidência de execução.

result_reason, quando aplicável, deve ser um de:
brief_fit, concept_strength, originality, brand_fit, technical_feasibility,
timeline, budget, scope, operation, venue, supplier, commercial_relationship,
competitor, client_internal_change, project_cancelled, other.

recommended_learning deve ser uma conclusão reutilizável e específica, sem
transformar opinião isolada em regra universal.

Retorne SOMENTE JSON válido no schema solicitado.
""".strip()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    stop = {
        "de", "da", "do", "das", "dos", "e", "em", "para", "por", "com",
        "the", "a", "an", "of", "to", "and", "for", "on", "in", "our",
        "project", "projeto", "event", "evento", "activation", "ativacao",
    }
    return {tok for tok in normalize_text(value).split() if len(tok) >= 3 and tok not in stop}


def _json_object(text: str) -> dict[str, Any]:
    clean = str(text or "").strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.I)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        obj = json.loads(clean)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        start, end = clean.find("{"), clean.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(clean[start:end + 1])
            return obj if isinstance(obj, dict) else {}
        raise


def normalise_feedback_analysis(value: FeedbackAnalysis) -> FeedbackAnalysis:
    value.source_type = value.source_type if value.source_type in {
        "client", "procurement", "marketing", "branding", "partner_agency",
        "production", "public", "internal_team", "not_informed",
    } else "not_informed"
    value.process_stage = value.process_stage if value.process_stage in {
        "presentation", "revision", "commercial_decision", "production",
        "post_event", "not_informed",
    } else "not_informed"
    value.process_type = value.process_type if value.process_type in {
        "competition", "direct", "proactive", "renewal", "not_informed",
    } else "not_informed"
    value.commercial_result = value.commercial_result if value.commercial_result in {
        "in_evaluation", "won", "lost", "cancelled", "suspended", "no_return",
        "not_applicable", "not_informed",
    } else "not_informed"
    value.proposal_result = value.proposal_result if value.proposal_result in {
        "fully_approved", "partially_approved", "not_approved", "in_revision",
        "no_feedback", "not_informed",
    } else "not_informed"
    value.execution_result = value.execution_result if value.execution_result in {
        "executed", "partially_executed", "not_executed", "in_progress",
        "not_applicable", "not_informed",
    } else "not_informed"
    value.confidence_level = value.confidence_level if value.confidence_level in {
        "client_confirmed", "voe_confirmed", "inferred", "incomplete",
    } else "incomplete"
    value.result_reasons = list(dict.fromkeys(
        reason for reason in value.result_reasons if reason in ALLOWED_RESULT_REASONS
    ))
    cleaned_claims: list[FeedbackClaim] = []
    for claim in value.claims:
        claim.theme = claim.theme if claim.theme in ALLOWED_FEEDBACK_THEMES else "other"
        claim.sentiment = claim.sentiment if claim.sentiment in ALLOWED_SENTIMENTS else "neutral"
        claim.item_outcome_status = (
            claim.item_outcome_status if claim.item_outcome_status in ALLOWED_ITEM_OUTCOMES
            else "unassessed"
        )
        if claim.result_reason not in ALLOWED_RESULT_REASONS:
            claim.result_reason = None
        if claim.title.strip():
            cleaned_claims.append(claim)
    value.claims = cleaned_claims
    return value


def analyze_feedback_bytes(
    *,
    file_name: str,
    mime_type: str,
    file_bytes: bytes,
    api_key: str,
    model: str,
) -> FeedbackAnalysis:
    """Lê feedback textual ou visual com Gemini multimodal.

    Importa google-genai apenas no runtime da chamada para manter o módulo testável
    e desacoplado do ambiente Streamlit.
    """
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não está configurada para leitura do feedback.")
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    client = genai.Client(api_key=api_key)
    part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
    prompt = f"{FEEDBACK_PROMPT}\n\nArquivo: {file_name}"
    try:
        response = client.models.generate_content(
            model=model,
            contents=[part, prompt],
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=FeedbackAnalysis,
            ),
        )
    except Exception:
        # Compatibilidade defensiva: algumas revisões do SDK/modelo aceitam
        # JSON mode, mas não response_schema nesta superfície. O segundo passe
        # mantém a mesma instrução e valida localmente pelo Pydantic.
        schema_text = json.dumps(FeedbackAnalysis.model_json_schema(), ensure_ascii=False)
        response = client.models.generate_content(
            model=model,
            contents=[part, f"{prompt}\n\nSchema JSON obrigatório:\n{schema_text}"],
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
    raw_text = str(getattr(response, "text", "") or "")
    if not raw_text:
        raise RuntimeError("O Gemini não devolveu análise para o feedback.")
    try:
        analysis = FeedbackAnalysis.model_validate_json(raw_text)
    except Exception:
        analysis = FeedbackAnalysis.model_validate(_json_object(raw_text))
    return normalise_feedback_analysis(analysis)


def fallback_feedback_analysis(text: str) -> FeedbackAnalysis:
    """Fallback conservador para feedback já textual quando IA não estiver disponível."""
    raw = str(text or "").strip()
    norm = normalize_text(raw)
    lost = any(term in norm for term in (
        "will not be moving forward", "not moving forward", "nao seguiremos",
        "proposta nao aprovada", "nao aprovado", "perdemos", "declined",
    ))
    won = any(term in norm for term in (
        "proposal approved", "aprovada", "approved proposal", "moving forward with voe",
    )) and not lost
    result = "lost" if lost else "won" if won else "in_evaluation"
    proposal = "not_approved" if lost else "fully_approved" if won else "not_informed"
    stage = "commercial_decision" if lost or won else "presentation"
    reasons: list[str] = []
    for token, reason in (
        ("budget", "budget"), ("orcamento", "budget"), ("deadline", "timeline"),
        ("prazo", "timeline"), ("venue", "venue"), ("local", "venue"),
    ):
        if token in norm and reason not in reasons:
            reasons.append(reason)
    return FeedbackAnalysis(
        transcription=raw or None,
        source_type="client" if raw else "not_informed",
        process_stage=stage,
        process_type="competition" if any(t in norm for t in ("bid", "concorrencia", "bidding")) else "not_informed",
        commercial_result=result,
        proposal_result=proposal,
        execution_result="not_applicable" if lost else "not_informed",
        confidence_level="client_confirmed" if lost or won else "incomplete",
        decision_summary="Decisão comercial explicitada no feedback." if lost or won else None,
        result_reasons=reasons,
        claims=[],
    )


def claim_item_match_score(claim: FeedbackClaim, item: Mapping[str, Any]) -> float:
    """Score genérico claim → solução, sem nomes de clientes/projetos hardcoded."""
    claim_text = " ".join([
        claim.title, claim.evidence_quote or "", claim.interpretation or "",
        " ".join(claim.related_entities),
    ])
    item_text = " ".join(str(item.get(key) or "") for key in (
        "title", "summary", "description", "item_type", "section_key",
    ))
    a, b = _tokens(claim_text), _tokens(item_text)
    if not a or not b:
        return 0.0
    overlap = len(a & b) / max(1, len(a | b))
    containment = len(a & b) / max(1, min(len(a), len(b)))
    score = overlap * 0.55 + containment * 0.45
    item_norm = normalize_text(item_text)
    for entity in claim.related_entities:
        ent = normalize_text(entity)
        if len(ent) >= 5 and ent in item_norm:
            score += 0.35
    theme_sections = {
        "strategy": {"strategy"}, "creative_concept": {"strategy"}, "kv": {"communication"},
        "scenography": {"scenography"}, "activation": {"activations"}, "gift": {"gifts"},
        "journey": {"journey_operation"}, "operation": {"journey_operation"},
        "technology": {"activations", "scenography"}, "presentation": {"content_agenda"},
    }
    if str(item.get("section_key") or "") in theme_sections.get(claim.theme, set()):
        score += 0.12
    return min(1.0, score)


def best_item_for_claim(
    claim: FeedbackClaim,
    items: Sequence[Mapping[str, Any]],
    *,
    min_score: float = 0.24,
) -> tuple[Mapping[str, Any] | None, float]:
    ranked = sorted(
        ((item, claim_item_match_score(claim, item)) for item in items),
        key=lambda pair: pair[1],
        reverse=True,
    )
    if not ranked or ranked[0][1] < min_score:
        return None, 0.0
    return ranked[0]


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_people_quantity(text: Any) -> tuple[float | None, str | None]:
    raw = str(text or "")
    normalized = normalize_text(raw)
    if not raw.strip():
        return None, None

    # Idades são atributos do público, não quantidade de participantes.
    cleaned = re.sub(r"\b(?:entre\s+)?\d{1,3}\s*(?:a|e|ate|[-–])\s*\d{1,3}\s*anos?\b", " ", normalized)
    cleaned = re.sub(r"\b\d{1,3}\s*anos?\b", " ", cleaned)

    scope = None
    if any(token in cleaned for token in ("festival", "publico do evento", "publico do festival")):
        scope = "festival_event"
    elif any(token in cleaned for token in ("convidados", "guest list", "guests", "participantes", "attendees")):
        scope = "project_attendees"
    elif "pessoas" in cleaned or "publico" in cleaned:
        scope = "project_audience"

    # Faixas em milhares: 6 a 8 mil pessoas -> usa o teto como capacidade/audiência
    # de referência, preservando o escopo para não confundir festival com ativação.
    range_mil = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:a|ate|[-–])\s*(\d+(?:[.,]\d+)?)\s*mil\b", cleaned)
    if range_mil:
        high = float(range_mil.group(2).replace(",", ".")) * 1000
        if 10 <= high <= 1000000:
            return high, scope
    single_mil = re.search(r"\b(\d+(?:[.,]\d+)?)\s*mil\s+(?:pessoas|participantes|convidados|visitantes|publico)\b", cleaned)
    if single_mil:
        value = float(single_mil.group(1).replace(",", ".")) * 1000
        if 10 <= value <= 1000000:
            return value, scope

    if not any(token in cleaned for token in ("pessoa", "publico", "convid", "participant", "guest", "attendee")):
        return None, scope
    values = []
    for token in re.findall(r"\b([1-9][0-9]{1,6})\b", cleaned.replace(".", "")):
        value = float(token)
        if 10 <= value <= 1000000:
            values.append(value)
    return (max(values), scope) if values else (None, scope)


def _briefing_audience_reference(snapshot: Mapping[str, Any]) -> tuple[float | None, str | None, str | None]:
    # 1. Claim explícito do Intelligence Graph.
    graph = snapshot.get("intelligence_graph") if isinstance(snapshot.get("intelligence_graph"), Mapping) else {}
    project_entity = graph.get("project_entity") if isinstance(graph.get("project_entity"), Mapping) else {}
    project_entity_id = str(project_entity.get("id") or "")
    claims = [
        row for row in (graph.get("claims") or [])
        if str(row.get("predicate") or "") == "expected_attendees"
        and (not project_entity_id or str(row.get("subject_entity_id") or "") == project_entity_id)
        and str(row.get("status") or "active") in {"active", "review_required"}
    ]
    claims.sort(key=lambda row: (float(row.get("authority_score") or 0), float(row.get("model_confidence") or 0)), reverse=True)
    for row in claims:
        value = _safe_float(row.get("value_numeric"))
        if value and 10 <= value <= 1000000:
            return value, str((row.get("value_json") or {}).get("scope") or "project_audience") if isinstance(row.get("value_json"), Mapping) else "project_audience", "graph_claim"

    # 2. Requisitos do briefing preservam o contexto semântico melhor do que um
    # número isolado em metadata (que pode ser idade, capacidade parcial etc.).
    scoped_candidates: list[tuple[float, str | None, str]] = []
    for req in snapshot.get("briefing_requirements", []) or []:
        text = " ".join(str(req.get(key) or "") for key in ("title", "description", "source_quote", "requirement_type"))
        value, scope = _parse_people_quantity(text)
        if value is not None:
            scoped_candidates.append((value, scope, "briefing_requirement"))
    if scoped_candidates:
        # Preferimos escopo específico de participantes; em empate, a maior
        # quantidade explícita é a referência operacional mais conservadora.
        rank = {"project_attendees": 3, "project_audience": 2, "festival_event": 1, None: 0}
        scoped_candidates.sort(key=lambda row: (rank.get(row[1], 0), row[0]), reverse=True)
        return scoped_candidates[0]

    # 3. Campos estruturados do documento somente depois da validação contextual.
    for doc in snapshot.get("briefing_documents", []) or []:
        for value in (doc.get("audience"), (doc.get("metadata") or {}).get("audience_quantity") if isinstance(doc.get("metadata"), Mapping) else None):
            parsed, scope = _parse_people_quantity(value)
            if parsed is not None:
                return parsed, scope, "briefing_document"
    return None, None, None


def _briefing_audience_quantity(snapshot: Mapping[str, Any]) -> float | None:
    return _briefing_audience_reference(snapshot)[0]


def _compact_text(value: Any, limit: int = 900) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else None


def build_project_evidence_packet(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Monta pacote compacto, rastreável e seguro para raciocínio semântico."""
    project = dict(snapshot.get("project") or {})
    outcome = dict(snapshot.get("outcome") or {})

    requirements = []
    for row in (snapshot.get("briefing_requirements") or [])[:60]:
        requirements.append({
            "ref": f"REQ:{row.get('id')}",
            "title": row.get("title"),
            "type": row.get("requirement_type"),
            "mandatory": row.get("mandatory"),
            "priority": row.get("priority"),
            "description": _compact_text(row.get("description") or row.get("original_text"), 700),
            "adherence_status": row.get("adherence_status"),
        })

    items = []
    for row in (snapshot.get("memory_items") or [])[:100]:
        items.append({
            "ref": f"ITEM:{row.get('id')}",
            "title": row.get("title"),
            "section": row.get("section_key"),
            "type": row.get("item_type"),
            "summary": _compact_text(row.get("summary") or row.get("description"), 900),
            "source_page": row.get("source_page"),
            "source_document_id": row.get("document_id"),
        })

    costs = []
    sorted_costs = sorted(
        list(snapshot.get("cost_items") or []),
        key=lambda row: _safe_float(row.get("client_total")) or 0.0,
        reverse=True,
    )
    for row in sorted_costs[:80]:
        costs.append({
            "ref": f"COST:{row.get('id')}",
            "category": row.get("category"),
            "item": row.get("item_name"),
            "description": _compact_text(row.get("description"), 500),
            "value": _safe_float(row.get("client_total")),
            "quantity": _safe_float(row.get("quantity")),
            "unit_value": _safe_float(row.get("unit_value")),
        })

    feedback = []
    for row in (snapshot.get("feedback_entries") or [])[:50]:
        raw = str(row.get("original_feedback") or "")
        feedback.append({
            "ref": f"FB:{row.get('id')}",
            "theme": row.get("theme"),
            "sentiment": row.get("sentiment"),
            "feedback": _compact_text(raw, 1600),
            "interpretation": _compact_text(row.get("internal_interpretation"), 900),
            "confidence": row.get("confidence_level"),
        })

    brief_links = [
        {
            "ref": f"BLINK:{row.get('id')}",
            "requirement_ref": f"REQ:{row.get('requirement_id')}",
            "item_ref": f"ITEM:{row.get('memory_item_id')}",
            "status": row.get("link_status"),
            "adherence": row.get("adherence_status"),
            "evidence": _compact_text(row.get("evidence"), 500),
        }
        for row in (snapshot.get("briefing_links") or [])[:120]
    ]
    cost_links = [
        {
            "ref": f"CLINK:{row.get('id')}",
            "item_ref": f"ITEM:{row.get('memory_item_id')}",
            "cost_ref": f"COST:{row.get('cost_item_id')}",
            "status": row.get("link_status"),
            "score": row.get("match_score"),
        }
        for row in (snapshot.get("cost_links") or [])[:120]
    ]
    item_outcomes = [
        {
            "ref": f"OUT:{row.get('id')}",
            "item_ref": f"ITEM:{row.get('item_id')}",
            "status": row.get("outcome_status"),
            "feedback": _compact_text(row.get("feedback_summary"), 900),
            "reason": _compact_text(row.get("decision_reason"), 500),
            "source": row.get("information_source"),
            "confidence": row.get("confidence_level"),
        }
        for row in (snapshot.get("item_outcomes") or [])[:100]
    ]

    briefing_docs = []
    for row in (snapshot.get("briefing_documents") or [])[:5]:
        briefing_docs.append({
            "ref": f"BRIEF:{row.get('id')}",
            "title": row.get("title") or row.get("file_name"),
            "budget_amount": _safe_float(row.get("budget_amount")),
            "audience": _compact_text(row.get("audience"), 600),
            "objective": _compact_text(row.get("objective") or row.get("summary"), 1200),
        })

    graph = snapshot.get("intelligence_graph") if isinstance(snapshot.get("intelligence_graph"), Mapping) else {}
    unified = snapshot.get("unified_intelligence") if isinstance(snapshot.get("unified_intelligence"), Mapping) else {}
    assets = {str(row.get("id")): row for row in (graph.get("source_assets") or []) if row.get("id")}
    contexts = graph.get("contexts") or []
    roles_by_asset: dict[str, list[str]] = defaultdict(list)
    for row in contexts:
        asset_id = str(row.get("source_asset_id") or "")
        role = str(row.get("context_role") or "")
        if asset_id and role and role not in roles_by_asset[asset_id]:
            roles_by_asset[asset_id].append(role)
    graph_evidence = []
    for row in (graph.get("evidence_units") or [])[:220]:
        asset_id = str(row.get("source_asset_id") or "")
        asset = assets.get(asset_id) or {}
        graph_evidence.append({
            "ref": f"EVID:{row.get('id')}",
            "source": asset.get("canonical_file_name"),
            "source_roles": roles_by_asset.get(asset_id, []),
            "unit_type": row.get("unit_type"),
            "ordinal": row.get("ordinal"),
            "locator": row.get("locator") or {},
            "text": _compact_text(row.get("content_text"), 1500),
            "confidence": row.get("extraction_confidence"),
        })
    graph_claims = []
    for row in (graph.get("claims") or [])[:180]:
        value = row.get("value_text")
        if value in (None, ""):
            value = row.get("value_numeric")
        if value in (None, ""):
            value = row.get("value_boolean")
        if value in (None, ""):
            value = row.get("value_date")
        graph_claims.append({
            "ref": f"CLAIM:{row.get('id')}",
            "subject_entity_id": row.get("subject_entity_id"),
            "predicate": row.get("predicate"),
            "value": value,
            "kind": row.get("claim_kind"),
            "confidence": row.get("model_confidence"),
            "authority": row.get("authority_score"),
            "status": row.get("status"),
        })
    graph_relations = [
        {
            "ref": f"REL:{row.get('id')}",
            "source_entity_id": row.get("source_entity_id"),
            "relation_type": row.get("relation_type"),
            "target_entity_id": row.get("target_entity_id"),
            "confidence": row.get("confidence"),
            "status": row.get("status"),
        }
        for row in (graph.get("relations") or [])[:180]
    ]

    return {
        "unified_snapshot": unified,
        "graph_evidence": graph_evidence,
        "graph_claims": graph_claims,
        "graph_relations": graph_relations,
        "project": {
            "ref": f"PROJECT:{project.get('id')}",
            "name": project.get("project_name"),
            "client": project.get("client_brand"),
            "event": project.get("event_name"),
            "status": project.get("status"),
            "event_date": project.get("event_date"),
        },
        "outcome": {
            "process_type": outcome.get("process_type"),
            "commercial_result": outcome.get("commercial_result"),
            "proposal_result": outcome.get("proposal_result"),
            "execution_result": outcome.get("execution_result"),
            "result_reasons": outcome.get("result_reasons"),
            "result_context": _compact_text(outcome.get("result_context"), 900),
            "source": outcome.get("information_source"),
            "confidence": outcome.get("confidence_level"),
        },
        "briefing_documents": briefing_docs,
        "requirements": requirements,
        "proposal_items": items,
        "cost_items": costs,
        "feedback_claims": feedback,
        "brief_to_solution_links": brief_links,
        "solution_to_cost_links": cost_links,
        "solution_outcomes": item_outcomes,
    }


def project_evidence_signature(snapshot: Mapping[str, Any]) -> str:
    packet = build_project_evidence_packet(snapshot)
    payload = json.dumps(packet, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



_BACKEND_LANGUAGE = (
    "intelligence graph", "links legados", "link legado", "estrutura legada",
    "pipeline", "backend", "fichas canonicas", "fichas canônicas",
    "materializacao pendente", "materialização pendente", "project analyst deve",
    "nao esta estruturado no legado", "não está estruturado no legado",
)
_UNSUPPORTED_PERFORMANCE_LANGUAGE = (
    "realizado com sucesso", "realizada com sucesso", "executado com sucesso",
    "executada com sucesso", "altamente eficaz", "alto engajamento",
    "excelente aceitacao", "excelente aceitação", "alto indice de participacao",
    "alto índice de participação", "principal driver de interacao",
    "principal driver de interação", "principal driver de engajamento",
    "valor percebido superior", "92% de sobra", "92% sobra",
    "sucesso do engajamento", "alto nivel de engajamento", "alto nível de engajamento",
    "alta participacao", "alta participação", "excelente performance", "principal fator de engajamento",
)
_UNSUPPORTED_BLAME_LANGUAGE = (
    "a agencia ignorou", "a agência ignorou", "voe ignorou", "desconsiderou a restricao",
    "desconsiderou a restrição", "sobra massiva", "descompasso severo",
)


def _semantic_support_flags(snapshot: Mapping[str, Any]) -> dict[str, bool]:
    feedback = bool(snapshot.get("feedback_entries"))
    reports = snapshot.get("report_analyses") or []
    performance_kpi = False
    activation_participation = False
    data_conflict = False
    for report in reports:
        for kpi in report.get("kpis") or []:
            name_blob = normalize_text(kpi.get("name"))
            blob = normalize_text(" ".join(str(kpi.get(k) or "") for k in ("name", "unit", "evidence")))
            specific_activation_metric = any(token in blob for token in (
                "participacao por ativacao", "visitantes da ativacao", "visitantes casa",
                "interacoes", "conversao", "satisfacao", "nps", "tempo medio",
                "engajamento da ativacao", "conteudo gerado",
            ))
            generic_attendance = any(token in name_blob for token in ("publico", "público", "presentes", "participantes do evento", "attendance"))
            if specific_activation_metric:
                performance_kpi = True
                activation_participation = True
            elif blob and not generic_attendance and any(token in blob for token in ("meta", "target", "atingido", "resultado", "conversao", "satisfacao", "engajamento")):
                performance_kpi = True
        if report.get("client_feedback"):
            feedback = True
        if report.get("issues"):
            for issue in report.get("issues") or []:
                blob = normalize_text(issue)
                if "nao reconc" in blob or "não reconc" in str(issue).casefold():
                    data_conflict = True
    unified = snapshot.get("unified_intelligence") if isinstance(snapshot.get("unified_intelligence"), Mapping) else {}
    for issue in (unified.get("results") or {}).get("data_quality") or []:
        if "reconc" in normalize_text(issue):
            data_conflict = True
    return {
        "feedback": feedback,
        "performance_kpi": performance_kpi,
        "activation_participation": activation_participation,
        "data_conflict": data_conflict,
    }


def _semantic_sentence_supported(text: str, flags: Mapping[str, bool]) -> bool:
    norm = normalize_text(text)
    if any(normalize_text(term) in norm for term in _BACKEND_LANGUAGE):
        return False
    if any(normalize_text(term) in norm for term in _UNSUPPORTED_BLAME_LANGUAGE):
        return False
    strong = any(normalize_text(term) in norm for term in _UNSUPPORTED_PERFORMANCE_LANGUAGE)
    if strong and not (flags.get("feedback") or flags.get("performance_kpi") or flags.get("activation_participation")):
        return False
    if flags.get("data_conflict") and ("sobra" in norm or "desperdicio" in norm or "desperdício" in text.casefold()) and "%" in text:
        return False
    # Público do evento não pode virar participação/impacto da ativação sem métrica própria.
    if ("8 mil" in norm or "8000" in norm or "8.000" in text) and any(token in norm for token in ("participacao", "engajamento", "visitantes da ativacao", "impacto da ativacao")) and not flags.get("activation_participation"):
        return False
    return True


def _sanitize_semantic_text(text: Any, flags: Mapping[str, bool]) -> str:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if not raw:
        return ""
    # Mantém somente sentenças sustentáveis; evita descartar um parágrafo inteiro
    # quando apenas uma frase ultrapassa a evidência disponível.
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", raw) if part.strip()]
    kept = [part for part in sentences if _semantic_sentence_supported(part, flags)]
    return " ".join(kept).strip()


def sanitize_semantic_payload(payload: Mapping[str, Any] | None, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Projection guard: evita que linguagem convincente ultrapasse a evidência.

    Não altera a fonte nem inventa correções. Apenas retira da projeção executiva
    afirmações de performance/aceitação sem sustentação e vazamentos de backend.
    """
    if not isinstance(payload, Mapping):
        return {}
    data = json.loads(json.dumps(dict(payload), ensure_ascii=False, default=str))
    flags = _semantic_support_flags(snapshot)
    for key in ("executive_summary", "strategic_reading"):
        if key in data:
            data[key] = _sanitize_semantic_text(data.get(key), flags)
    framework = data.get("strategy_framework") if isinstance(data.get("strategy_framework"), dict) else {}
    for key, value in list(framework.items()):
        if isinstance(value, str):
            framework[key] = _sanitize_semantic_text(value, flags)
    data["strategy_framework"] = framework
    for group in ("diagnostic", "results", "strongest_connections", "discovered_connections", "contradictions_or_gaps"):
        clean_rows = []
        for row in data.get(group) or []:
            if not isinstance(row, dict):
                continue
            title_norm = normalize_text(row.get("title"))
            if group == "diagnostic" and title_norm in {
                "projeto com evidencia de execucao",
                "projeto executado",
                "status de execucao",
            }:
                continue
            if any(normalize_text(term) in title_norm for term in _BACKEND_LANGUAGE):
                continue
            text = _sanitize_semantic_text(row.get("analysis"), flags)
            action = _sanitize_semantic_text(row.get("recommended_action"), flags) if row.get("recommended_action") else None
            if not text:
                continue
            row["analysis"] = text
            row["recommended_action"] = action or None
            clean_rows.append(row)
        data[group] = clean_rows
    for group in ("validated_learnings", "challenged_learnings", "decision_recommendations", "unknowns"):
        clean = []
        for value in data.get(group) or []:
            text = _sanitize_semantic_text(value, flags)
            if text:
                clean.append(text)
        data[group] = clean
    return data


def analyze_project_snapshot(
    *,
    snapshot: Mapping[str, Any],
    api_key: str,
    model: str,
) -> ProjectSemanticSynthesis:
    """Executa raciocínio semântico sobre o PROJETO, não sobre um arquivo isolado."""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não está configurada para o Project Analyst.")
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    packet = build_project_evidence_packet(snapshot)
    evidence_json = json.dumps(packet, ensure_ascii=False, default=str)
    prompt = f"{PROJECT_ANALYST_PROMPT}\n\nPACOTE DE EVIDÊNCIAS:\n{evidence_json}"
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=ProjectSemanticSynthesis,
            ),
        )
    except Exception:
        schema_text = json.dumps(ProjectSemanticSynthesis.model_json_schema(), ensure_ascii=False)
        response = client.models.generate_content(
            model=model,
            contents=f"{prompt}\n\nSchema JSON obrigatório:\n{schema_text}",
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
    raw_text = str(getattr(response, "text", "") or "")
    if not raw_text:
        raise RuntimeError("O Gemini não devolveu a síntese semântica do projeto.")
    try:
        parsed = ProjectSemanticSynthesis.model_validate_json(raw_text)
    except Exception:
        parsed = ProjectSemanticSynthesis.model_validate(_json_object(raw_text))
    safe_payload = sanitize_semantic_payload(parsed.model_dump(), snapshot)
    return ProjectSemanticSynthesis.model_validate(safe_payload)


def semantic_synthesis_findings(synthesis: ProjectSemanticSynthesis) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = [
        (synthesis.diagnostic, "info", "diagnostic"),
        (synthesis.results, "info", "result"),
        (synthesis.strongest_connections, "info", "connection"),
        (synthesis.discovered_connections, "info", "discovered_connection"),
        (synthesis.contradictions_or_gaps, "warning", "contradiction"),
    ]
    for values, level, default_type in groups:
        for connection in values:
            rows.append({
                "level": level,
                "title": connection.title,
                "text": connection.analysis,
                "source": "semantic_project_analyst",
                "connection_type": connection.connection_type or default_type,
                "evidence_refs": list(connection.evidence_refs),
                "confidence": connection.confidence,
                "recommended_action": connection.recommended_action,
            })
    return rows


def derive_advanced_project_insights(
    snapshot: Mapping[str, Any],
    *,
    proposal_total: float | None,
    budget_amount: float | None,
) -> dict[str, Any]:
    """Gera inteligência cruzada baseada apenas nos dados estruturados/provados.

    Esta camada é determinística. A futura camada LLM pode sintetizar linguagem,
    mas os números e relações centrais permanecem auditáveis.
    """
    cost_items = list(snapshot.get("cost_items", []) or [])
    cost_links = list(snapshot.get("cost_links", []) or [])
    item_outcomes = list(snapshot.get("item_outcomes", []) or [])
    memory_items = list(snapshot.get("memory_items", []) or [])
    feedback_entries = list(snapshot.get("feedback_entries", []) or [])
    briefing_links = list(snapshot.get("briefing_links", []) or [])
    requirements = list(snapshot.get("briefing_requirements", []) or [])

    categories: dict[str, float] = defaultdict(float)
    valid_costs: list[dict[str, Any]] = []
    for item in cost_items:
        value = _safe_float(item.get("client_total"))
        if value is None:
            continue
        categories[str(item.get("category") or "Sem categoria")] += value
        if value > 0:
            valid_costs.append({
                "id": item.get("id"), "name": item.get("item_name") or "Item sem nome",
                "category": item.get("category") or "Sem categoria", "value": value,
            })
    top_categories = [
        {"category": k, "value": v, "share": (v / proposal_total if proposal_total else None)}
        for k, v in sorted(categories.items(), key=lambda pair: pair[1], reverse=True)
    ]
    top_items = sorted(valid_costs, key=lambda row: row["value"], reverse=True)
    top5_share = (
        sum(row["value"] for row in top_items[:5]) / proposal_total
        if proposal_total and top_items else None
    )
    top4_category_share = (
        sum(row["value"] for row in top_categories[:4]) / proposal_total
        if proposal_total and top_categories else None
    )
    audience, audience_scope, audience_source = _briefing_audience_reference(snapshot)
    # Uma claim antiga pode ter marcado o número como participants mesmo quando o
    # pós-evento comprova que ele é público do evento hospedeiro. A verdade
    # consolidada mais específica prevalece sobre o rótulo genérico da claim.
    unified = snapshot.get("unified_intelligence") if isinstance(snapshot.get("unified_intelligence"), Mapping) else {}
    unified_results = unified.get("results") if isinstance(unified.get("results"), Mapping) else {}
    report_audience = _safe_float(unified_results.get("participants_count"))
    report_scope = str(unified_results.get("participants_scope") or "")
    if (
        audience is not None
        and report_audience is not None
        and abs(float(audience) - float(report_audience)) < 0.01
        and report_scope in {"festival_event", "event_or_report_scope"}
    ):
        audience_scope = "festival_event"
        audience_source = "unified_post_event_scope"

    # Público de festival/evento hospedeiro não é automaticamente público da ativação.
    # Só calculamos custo por participante quando a fonte prova uma contagem
    # específica de participantes/convidados da própria ativação/projeto. Público
    # genérico ou audiência do evento hospedeiro não é denominador válido.
    cost_per_attendee = (
        proposal_total / audience
        if proposal_total and audience and audience_scope == "project_attendees"
        else None
    )

    item_by_id = {str(row.get("id")): row for row in memory_items if row.get("id")}
    cost_by_id = {str(row.get("id")): row for row in cost_items if row.get("id")}
    outcome_by_item = {str(row.get("item_id")): row for row in item_outcomes if row.get("item_id")}
    costs_by_memory_item: dict[str, float] = defaultdict(float)
    for link in cost_links:
        if str(link.get("link_status") or "suggested") == "rejected":
            continue
        cost = cost_by_id.get(str(link.get("cost_item_id") or ""))
        if not cost:
            continue
        value = _safe_float(cost.get("client_total")) or 0.0
        costs_by_memory_item[str(link.get("memory_item_id") or "")] += value

    validated: list[dict[str, Any]] = []
    challenged: list[dict[str, Any]] = []
    for item_id, outcome in outcome_by_item.items():
        item = item_by_id.get(item_id)
        if not item:
            continue
        row = {
            "item_id": item_id,
            "title": item.get("title") or "Solução",
            "section": item.get("section_key"),
            "status": outcome.get("outcome_status"),
            "feedback": outcome.get("feedback_summary") or outcome.get("decision_reason"),
            "linked_cost": costs_by_memory_item.get(item_id) or None,
        }
        if outcome.get("outcome_status") in {"approved", "approved_with_changes"}:
            validated.append(row)
        elif outcome.get("outcome_status") in {"not_approved", "removed_budget", "removed_timeline", "replaced"}:
            challenged.append(row)

    # Briefing crítico cujo item ligado recebeu feedback negativo.
    req_by_id = {str(row.get("id")): row for row in requirements if row.get("id")}
    challenged_item_ids = {row["item_id"] for row in challenged}
    requirement_risks: list[dict[str, Any]] = []
    for link in briefing_links:
        if str(link.get("memory_item_id") or "") not in challenged_item_ids:
            continue
        req = req_by_id.get(str(link.get("requirement_id") or ""))
        if not req:
            continue
        if bool(req.get("mandatory")) or str(req.get("priority") or "") in {"critical", "high"}:
            requirement_risks.append({
                "requirement": req.get("title"),
                "item": item_by_id.get(str(link.get("memory_item_id") or ""), {}).get("title"),
                "adherence": link.get("adherence_status"),
            })

    feedback_theme_counts = Counter(str(row.get("theme") or "other") for row in feedback_entries)
    feedback_sentiment_counts = Counter(str(row.get("sentiment") or "neutral") for row in feedback_entries)

    findings: list[dict[str, Any]] = []
    recommendations: list[str] = []
    if budget_amount is not None and proposal_total is not None and budget_amount > 0:
        delta = proposal_total - budget_amount
        if delta > 0:
            unified_financial = unified.get("financial_context") if isinstance(unified.get("financial_context"), Mapping) else {}
            direct_payment_signal = bool(unified_financial.get("direct_payment_signal"))
            if direct_payment_signal:
                findings.append({
                    "level": "warning", "title": "Diferença bruta a reconciliar",
                    "text": (
                        f"A proposta bruta supera o budget nominal em R$ {delta:,.2f} ({delta / budget_amount:.1%}), "
                        "mas há indicação de pagamento direto pelo cliente. A aderência financeira só pode ser "
                        "classificada após separar responsabilidades de pagamento."
                    ),
                })
            else:
                findings.append({
                    "level": "warning", "title": "Aderência financeira",
                    "text": f"A proposta excede o budget comprovado em R$ {delta:,.2f} ({delta / budget_amount:.1%}).",
                })
            recommendations.append("Atacar primeiro os maiores drivers de custo depois de reconciliar quais parcelas pertencem ao envelope efetivamente administrado pela agência.")
    if top_categories:
        lead = top_categories[0]
        share = lead.get("share")
        findings.append({
            "level": "info", "title": "Principal driver de custo",
            "text": f"{lead['category']} concentra R$ {lead['value']:,.2f}" + (f" ({share:.1%} da proposta)." if share is not None else "."),
        })
    if top4_category_share is not None and top4_category_share >= 0.65:
        findings.append({
            "level": "info", "title": "Concentração do orçamento",
            "text": f"As quatro maiores categorias concentram {top4_category_share:.1%} da proposta; são o melhor ponto de partida para otimização.",
        })
    if top_items:
        lead_item = top_items[0]
        findings.append({
            "level": "info", "title": "Maior item individual",
            "text": f"{lead_item['name']} ({lead_item['category']}) representa R$ {lead_item['value']:,.2f}.",
        })
    if cost_per_attendee is not None:
        findings.append({
            "level": "info", "title": "Custo por participante",
            "text": f"Com audiência de referência de {audience:,.0f} pessoas, a proposta equivale a aproximadamente R$ {cost_per_attendee:,.2f} por participante.",
        })
    if validated:
        titles = ", ".join(str(row["title"]) for row in validated[:3])
        findings.append({
            "level": "info", "title": "Soluções validadas pelo cliente",
            "text": f"Há validação positiva vinculada a {titles}. O resultado geral do projeto não deve apagar esses aprendizados específicos.",
        })
    if challenged:
        expensive = [row for row in challenged if row.get("linked_cost") and proposal_total and float(row["linked_cost"]) / proposal_total >= 0.05]
        if expensive:
            row = max(expensive, key=lambda r: float(r.get("linked_cost") or 0))
            findings.append({
                "level": "warning", "title": "Crítica em investimento relevante",
                "text": f"{row['title']} recebeu feedback desfavorável e está ligado a aproximadamente R$ {float(row['linked_cost']):,.2f} do orçamento.",
            })
            recommendations.append("Revisar cedo soluções de alto peso financeiro que tenham risco de aderência ao briefing ou histórico de feedback negativo.")
    if requirement_risks:
        findings.append({
            "level": "warning", "title": "Briefing × feedback",
            "text": f"{len(requirement_risks)} requisito(s) crítico(s)/alto(s) estão ligados a soluções posteriormente questionadas pelo cliente.",
        })
    if feedback_entries and not validated and not challenged:
        recommendations.append("Vincular os feedbacks às soluções apresentadas para transformar opinião do cliente em aprendizado reutilizável por item.")

    return {
        "top_categories": top_categories,
        "top_items": top_items,
        "top5_item_share": top5_share,
        "top4_category_share": top4_category_share,
        "audience_quantity": audience,
        "audience_scope": audience_scope,
        "audience_source": audience_source,
        "cost_per_attendee": cost_per_attendee,
        "validated_items": validated,
        "challenged_items": challenged,
        "requirement_risks": requirement_risks,
        "feedback_theme_counts": dict(feedback_theme_counts),
        "feedback_sentiment_counts": dict(feedback_sentiment_counts),
        "findings": findings,
        "recommendations": list(dict.fromkeys(recommendations)),
    }
