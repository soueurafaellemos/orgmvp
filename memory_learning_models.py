from __future__ import annotations

from pydantic import BaseModel, Field


PROCESS_TYPES = {
    "competition": "Concorrência",
    "direct": "Projeto direto",
    "proactive": "Proposta proativa",
    "renewal": "Renovação",
    "not_informed": "Não informado",
}

COMMERCIAL_RESULTS = {
    "in_evaluation": "Em avaliação",
    "won": "Ganho",
    "lost": "Perdido",
    "cancelled": "Cancelado",
    "suspended": "Suspenso",
    "no_return": "Sem retorno",
    "not_applicable": "Não se aplica",
    "not_informed": "Não informado",
}

PROPOSAL_RESULTS = {
    "fully_approved": "Aprovada integralmente",
    "partially_approved": "Aprovada parcialmente",
    "not_approved": "Não aprovada",
    "in_revision": "Em revisão",
    "no_feedback": "Sem feedback",
    "not_informed": "Não informado",
}

EXECUTION_RESULTS = {
    "executed": "Executado",
    "partially_executed": "Executado parcialmente",
    "not_executed": "Não executado",
    "in_progress": "Em andamento",
    "not_applicable": "Não se aplica",
    "not_informed": "Não informado",
}

RESULT_REASONS = {
    "brief_fit": "Adequação ao briefing",
    "concept_strength": "Força do conceito",
    "originality": "Originalidade",
    "brand_fit": "Identificação com a marca",
    "technical_feasibility": "Viabilidade técnica",
    "timeline": "Prazo",
    "budget": "Orçamento",
    "scope": "Escopo",
    "operation": "Operação",
    "venue": "Local",
    "supplier": "Fornecedor",
    "commercial_relationship": "Relacionamento comercial",
    "competitor": "Concorrente",
    "client_internal_change": "Mudança interna do cliente",
    "project_cancelled": "Cancelamento do projeto",
    "not_informed": "Motivo não informado",
    "other": "Outro",
}

CONFIDENCE_LEVELS = {
    "client_confirmed": "Confirmado pelo cliente",
    "voe_confirmed": "Confirmado pela equipe VOE",
    "inferred": "Inferido pela equipe",
    "incomplete": "Informação incompleta",
}

INFORMATION_SOURCES = {
    "client_feedback": "Feedback do cliente",
    "voe_team": "Equipe VOE",
    "email": "E-mail",
    "meeting": "Reunião",
    "document": "Documento",
    "other": "Outro",
    "not_informed": "Não informado",
}

FEEDBACK_SOURCES = {
    "client": "Cliente",
    "procurement": "Compras",
    "marketing": "Marketing",
    "branding": "Branding",
    "partner_agency": "Agência parceira",
    "production": "Produção",
    "public": "Público",
    "internal_team": "Equipe interna",
    "not_informed": "Não informado",
}

FEEDBACK_STAGES = {
    "presentation": "Apresentação",
    "revision": "Revisão",
    "commercial_decision": "Decisão comercial",
    "production": "Produção",
    "post_event": "Pós-evento",
    "not_informed": "Não informado",
}

FEEDBACK_THEMES = {
    "strategy": "Estratégia",
    "creative_concept": "Conceito criativo",
    "kv": "KV",
    "scenography": "Cenografia",
    "activation": "Ativação",
    "gift": "Brinde",
    "journey": "Jornada",
    "operation": "Operação",
    "technology": "Tecnologia",
    "budget": "Orçamento",
    "timeline": "Prazo",
    "presentation": "Apresentação",
    "other": "Outro",
}

FEEDBACK_SENTIMENTS = {
    "positive": "Positivo",
    "negative": "Negativo",
    "neutral": "Neutro",
    "mixed": "Misto",
}

ITEM_OUTCOME_STATUS = {
    "unassessed": "Sem avaliação",
    "approved": "Aprovado",
    "approved_with_changes": "Aprovado com ajustes",
    "not_approved": "Não aprovado",
    "replaced": "Substituído",
    "removed_budget": "Retirado por orçamento",
    "removed_timeline": "Retirado por prazo",
    "executed": "Executado",
    "not_executed": "Não executado",
    "unknown": "Resultado desconhecido",
}

COST_ITEM_STATUS = {
    "included": "Incluído",
    "optional": "Opcional",
    "client_responsibility": "Responsabilidade do cliente",
    "pending": "Pendente de definição",
    "reserve": "Reserva de verba",
    "no_value": "Sem valor informado",
}

ESTIMATE_TYPES = {
    "quoted": "Cotado",
    "estimated": "Estimado",
    "reserve": "Reserva de verba",
    "waiting_supplier": "Aguardando fornecedor",
    "no_value": "Sem valor informado",
}

LINK_STATUS = {
    "suggested": "Sugerida",
    "confirmed": "Confirmada",
    "rejected": "Rejeitada",
    "unlinked": "Sem associação",
}


class CostItem(BaseModel):
    source_sheet: str
    source_row: int
    item_code: str | None = None
    category: str | None = None
    item_name: str
    description: str | None = None
    billing_type: str | None = None
    quantity: float | None = None
    period: float | None = None
    unit_value: float | None = None
    base_value: float | None = None
    fees_value: float | None = None
    charges_value: float | None = None
    client_total: float | None = None
    item_status: str = "included"
    estimate_type: str = "quoted"
    flags: list[str] = Field(default_factory=list)
    raw_data: dict = Field(default_factory=dict)


class CostWorkbookResult(BaseModel):
    file_name: str
    title: str
    sheet_name: str
    header_row: int
    project_name: str | None = None
    event_date: str | None = None
    presentation_date: str | None = None
    macros_present: bool = False
    total_base: float | None = None
    fees_total: float | None = None
    charges_total: float | None = None
    client_total: float | None = None
    currency: str = "BRL"
    items: list[CostItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unknown_columns: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
