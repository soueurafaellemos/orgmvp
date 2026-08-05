from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


Currency = Literal["BRL", "USD", "EUR", "Outro", "Não informado"]
PriceStatus = Literal[
    "Informado",
    "Faixa de preço",
    "Sob consulta",
    "Não informado",
]


class SupplierContact(BaseModel):
    supplier_name: str | None = None
    website_url: str | None = None
    contact_name: str | None = None
    contact_role: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    instagram_url: str | None = None
    linkedin_url: str | None = None
    address: str | None = None

    base_city: str | None = None
    base_state: str | None = None
    base_country: str | None = None
    serves_nationally: bool | None = None
    served_states: list[str] = Field(default_factory=list)
    served_cities: list[str] = Field(default_factory=list)
    has_local_teams: bool | None = None
    local_team_locations: list[str] = Field(default_factory=list)

    travel_pricing_mode: Literal[
        "Incluído no valor",
        "Adicionar estimativa",
        "Sob consulta",
        "Não informado",
    ] = "Não informado"
    default_travel_cost_brl: float | None = None

    freight_pricing_mode: Literal[
        "Incluído no valor",
        "Adicionar estimativa",
        "Sob consulta",
        "Não informado",
    ] = "Não informado"
    default_freight_cost_brl: float | None = None

    travel_lead_days: int | None = None
    equipment_transport_required: bool | None = None
    accommodation_required: bool | None = None
    coverage_notes: str | None = None

    notes: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class GlobalRule(BaseModel):
    key: str
    value: str
    source_page: int | None = None
    confidence: float = Field(ge=0, le=1)


class DocumentClassification(BaseModel):
    source_files: list[str] = Field(default_factory=list)
    document_type: Literal[
        "Catálogo de brindes",
        "Tabela comercial de produtos",
        "Orçamento de ativação",
        "Catálogo / proposta de local",
        "Briefing de projeto",
        "Documento misto",
        "Outro",
    ]
    suggested_mode: Literal[
        "catalog",
        "activation",
        "venue",
        "briefing",
        "manual_review",
    ]
    destination_base: Literal[
        "Base de brindes",
        "Base de soluções e ativações",
        "Base de locais e espaços",
        "Base de projetos e briefings",
        "Revisão manual",
    ]
    document_title: str | None = None
    supplier_name: str | None = None
    client_brand: str | None = None
    document_year: int | None = None
    contains_products: bool = False
    contains_services_or_activations: bool = False
    contains_venues_or_spaces: bool = False
    contains_prices: bool = False
    contains_project_briefing: bool = False
    summary: str
    classification_signals: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class CatalogProduct(BaseModel):
    source_file: str
    source_page: int | None = None
    supplier_name: str | None = None
    category: str | None = None
    sku: str | None = None
    name: str
    description: str | None = None

    unit_price: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    currency: Currency = "Não informado"
    price_status: PriceStatus = "Não informado"
    price_reference_qty: int | None = None
    price_notes: str | None = None

    capacity: str | None = None
    capacity_ml: float | None = None
    dimensions_raw: str | None = None
    material: str | None = None
    finish: str | None = None
    decoration: str | None = None
    origin: Literal[
        "Brasil", "China", "Outro", "Não informado"
    ] = "Não informado"
    development_status: Literal[
        "Produto regular", "Produto conceito", "Não informado"
    ] = "Não informado"
    min_order_qty: int | None = None
    customizable: bool | None = None
    licensing_notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    evidence: str | None = None


class CatalogBatch(BaseModel):
    supplier_name: str | None = None
    supplier_contact: SupplierContact | None = None
    catalog_name: str | None = None
    document_year: int | None = None
    category_context: str | None = None
    global_rules: list[GlobalRule] = Field(default_factory=list)
    products: list[CatalogProduct] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CostComponent(BaseModel):
    description: str
    amount: float | None = None
    currency: Currency = "Não informado"
    treatment: Literal[
        "Incluído no valor-base",
        "Adicional obrigatório",
        "Opcional",
        "Não incluso sem valor",
        "Não informado",
    ] = "Não informado"
    notes: str | None = None
    source_page: int | None = None
    confidence: float = Field(ge=0, le=1)



class ActivationFallbackItem(BaseModel):
    source_file: str
    source_page: int | None = None
    supplier_name: str | None = None
    client_brand: str | None = None
    project_name: str | None = None
    event_name: str | None = None
    name: str
    description: str | None = None
    base_price: float | None = None
    currency: Currency = "Não informado"
    price_status: PriceStatus = "Não informado"
    pricing_period: str | None = None
    price_notes: str | None = None
    included_items: list[str] = Field(default_factory=list)
    excluded_items: list[str] = Field(default_factory=list)
    additional_costs_text: list[str] = Field(default_factory=list)
    infrastructure_requirements: list[str] = Field(default_factory=list)
    lead_time_days: int | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)
    evidence: str | None = None


class ActivationFallbackBatch(BaseModel):
    supplier_name: str | None = None
    proposal_name: str | None = None
    client_brand: str | None = None
    project_name: str | None = None
    document_year: int | None = None
    items: list[ActivationFallbackItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ActivationSolution(BaseModel):
    source_file: str
    source_page: int | None = None
    supplier_name: str | None = None
    client_brand: str | None = None
    project_name: str | None = None
    event_name: str | None = None
    category: str | None = None
    record_type: Literal[
        "Ativação tecnológica",
        "Software / aplicativo",
        "Simulador",
        "Equipamento interativo",
        "Cenografia",
        "Operação de evento",
        "Logística",
        "Infraestrutura",
        "Produção audiovisual",
        "Serviço criativo",
        "Outro",
        "Não informado",
    ] = "Não informado"
    name: str
    description: str | None = None

    base_price: float | None = None
    currency: Currency = "Não informado"
    price_status: PriceStatus = "Não informado"
    pricing_period: str | None = None
    price_notes: str | None = None
    additional_costs: list[CostComponent] = Field(default_factory=list)

    included_items: list[str] = Field(default_factory=list)
    excluded_items: list[str] = Field(default_factory=list)
    infrastructure_requirements: list[str] = Field(default_factory=list)
    internet_requirement: str | None = None
    lead_time_days: int | None = None
    setup_window: str | None = None
    event_period: str | None = None
    location: str | None = None
    staff_included: bool | None = None
    staff_description: str | None = None
    validity: str | None = None
    payment_terms: str | None = None
    discount_percent: float | None = None
    negotiated_benefit: str | None = None
    customizable: bool | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    evidence: str | None = None


class ActivationBatch(BaseModel):
    supplier_name: str | None = None
    supplier_contact: SupplierContact | None = None
    proposal_name: str | None = None
    client_brand: str | None = None
    project_name: str | None = None
    document_year: int | None = None
    global_rules: list[GlobalRule] = Field(default_factory=list)
    solutions: list[ActivationSolution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)



class VenueSpace(BaseModel):
    source_file: str
    source_page: int | None = None
    operator_name: str | None = None

    name: str
    venue_type: Literal[
        "Centro de convenções",
        "Pavilhão",
        "Casa de eventos",
        "Hotel",
        "Restaurante / bar",
        "Espaço cultural",
        "Shopping",
        "Área externa",
        "Estádio / arena",
        "Auditório / teatro",
        "Galpão",
        "Outro",
        "Não informado",
    ] = "Não informado"
    description: str | None = None

    address: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    map_url: str | None = None
    website_url: str | None = None

    total_area_sqm: float | None = None
    indoor_area_sqm: float | None = None
    outdoor_area_sqm: float | None = None
    ceiling_height_m: float | None = None
    standing_capacity: int | None = None
    seated_capacity: int | None = None
    auditorium_capacity: int | None = None
    rooms_or_areas: list[str] = Field(default_factory=list)

    parking: str | None = None
    accessibility: str | None = None
    loading_access: str | None = None
    kitchen_or_catering: str | None = None
    power_supply: str | None = None
    internet: str | None = None
    air_conditioning: str | None = None
    bathrooms: str | None = None
    furniture: str | None = None
    audiovisual: str | None = None
    infrastructure: list[str] = Field(default_factory=list)

    included_items: list[str] = Field(default_factory=list)
    excluded_items: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    operating_hours: str | None = None
    event_availability: str | None = None

    base_price: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    currency: Currency = "Não informado"
    price_status: PriceStatus = "Não informado"
    pricing_period: str | None = None
    price_notes: str | None = None

    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    evidence: str | None = None


class VenueBatch(BaseModel):
    operator_name: str | None = None
    venue_contact: SupplierContact | None = None
    document_name: str | None = None
    document_year: int | None = None
    global_rules: list[GlobalRule] = Field(default_factory=list)
    venues: list[VenueSpace] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectBriefing(BaseModel):
    source_files: list[str] = Field(default_factory=list)
    project_name: str | None = None
    client_brand: str | None = None
    event_name: str | None = None
    event_type: str | None = None
    objective: str | None = None
    audience_profile: str | None = None
    audience_quantity: int | None = None
    budget_total_brl: float | None = None
    budget_unit_brl: float | None = None
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None
    event_date: str | None = None
    desired_delivery_date: str | None = None
    available_days: int | None = None
    creative_concept: str | None = None
    desired_attributes: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    differentiations_by_audience: list[str] = Field(default_factory=list)
    products_already_mentioned: list[str] = Field(default_factory=list)
    decisions_already_made: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    source_summary: str
    confidence: float = Field(ge=0, le=1)



class BriefingDiagnosticItem(BaseModel):
    severity: Literal[
        "Crítica",
        "Importante",
        "Enriquecimento",
    ]
    category: Literal[
        "Objetivo",
        "Público",
        "Quantidade",
        "Budget",
        "Prazo",
        "Data",
        "Localização",
        "Distribuição",
        "Logística",
        "Operação",
        "Experiência",
        "Mensuração",
        "Sustentabilidade",
        "Compliance",
        "Escopo",
        "Outro",
    ]
    title: str
    finding: str
    question: str
    responsible: Literal[
        "Atendimento",
        "Cliente",
        "Criação",
        "Produção",
        "Fornecedor",
        "A definir",
    ] = "Atendimento"
    impact: Literal[
        "Budget",
        "Prazo",
        "Logística",
        "Escala",
        "Aderência",
        "Experiência",
        "Mensuração",
        "Risco",
        "Outro",
    ] = "Outro"
    blocks_recommendation: bool = False
    source_support: str | None = None


class AgencyBriefingContext(BaseModel):
    job_code: str | None = None
    job_folder: str | None = None
    account_manager: str | None = None
    client_contacts: list[str] = Field(default_factory=list)
    competition_status: Literal[
        "Sim",
        "Não",
        "Não informado",
    ] = "Não informado"
    competitors: list[str] = Field(default_factory=list)
    campaign_types: list[str] = Field(default_factory=list)
    agency_services: list[str] = Field(default_factory=list)
    production_responsibility: list[str] = Field(
        default_factory=list
    )


class FinancialBriefingContext(BaseModel):
    currency: Literal[
        "BRL",
        "USD",
        "EUR",
        "Outro",
        "Não informado",
    ] = "Não informado"
    budget_status: Literal[
        "Confirmado",
        "Estimado",
        "Parcial / saldo restante",
        "Não necessário",
        "Não informado",
    ] = "Não informado"
    budget_scope: str | None = None
    remaining_budget: float | None = None
    payment_terms: str | None = None
    direct_payment_required: bool | None = None
    advance_payment_required: bool | None = None
    notes: str | None = None


class BriefingProduct(BaseModel):
    name: str
    brand: str | None = None
    role: Literal[
        "Principal",
        "Secundário",
        "Alternativo",
        "Insumo do cliente",
        "Outro",
    ] = "Principal"
    execution_names: list[str] = Field(default_factory=list)
    notes: str | None = None


class BriefingDeliverable(BaseModel):
    name: str
    category: str | None = None
    quantity: float | None = None
    unit: str | None = None
    required: bool = True
    responsible: str | None = None
    execution_names: list[str] = Field(default_factory=list)
    notes: str | None = None


class BriefingMetric(BaseModel):
    name: str
    target: str | None = None
    unit: str | None = None
    status: Literal[
        "Confirmada",
        "Estimada",
        "A definir",
    ] = "A definir"
    execution_names: list[str] = Field(default_factory=list)
    notes: str | None = None


class BriefingExecution(BaseModel):
    name: str
    city: str | None = None
    state: str | None = None
    venue: str | None = None
    institution: str | None = None
    status: Literal[
        "Realizado",
        "Referência",
        "Em pesquisa",
        "Em negociação",
        "Data sugerida",
        "Confirmado",
        "Cancelado",
        "Não informado",
    ] = "Não informado"
    priority: int | None = None
    event_date: str | None = None
    product_name: str | None = None
    audience_quantity: int | None = None
    budget_amount: float | None = None
    currency: str | None = None
    event_format: str | None = None
    notes: str | None = None


class BriefingReference(BaseModel):
    title: str
    reference_type: Literal[
        "Briefing principal",
        "Planilha complementar",
        "Report anterior",
        "Apresentação",
        "KV / identidade visual",
        "Cotação",
        "Link externo",
        "Dependência futura",
        "Outro",
    ] = "Outro"
    status: Literal[
        "Recebido",
        "Pendente",
        "Referência",
        "A atualizar",
        "Não informado",
    ] = "Não informado"
    url_or_location: str | None = None
    notes: str | None = None


class RecommendationBrief(BaseModel):
    source_files: list[str] = Field(default_factory=list)

    briefing_profile: Literal[
        "Entrega simples",
        "Projeto único estruturado",
        "Programa multi-execução",
    ] = "Entrega simples"
    profile_reason: str | None = None

    project_name: str | None = None
    client_brand: str | None = None
    event_name: str | None = None

    agency_context: AgencyBriefingContext = Field(
        default_factory=AgencyBriefingContext
    )

    objective: str | None = None
    audience_profile: str | None = None
    audience_quantity: int | None = None

    budget_total_brl: float | None = None
    budget_unit_brl: float | None = None
    financial_context: FinancialBriefingContext = Field(
        default_factory=FinancialBriefingContext
    )

    location_city: str | None = None
    location_state: str | None = None
    event_date: str | None = None
    desired_delivery_date: str | None = None
    available_days: int | None = None

    key_message: str | None = None
    expected_result: str | None = None
    event_format: str | None = None

    desired_types: list[
        Literal["product", "activation", "venue"]
    ] = Field(default_factory=list)
    desired_attributes: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    products_or_brands: list[BriefingProduct] = Field(
        default_factory=list
    )
    deliverables: list[BriefingDeliverable] = Field(
        default_factory=list
    )
    success_metrics: list[BriefingMetric] = Field(
        default_factory=list
    )
    executions: list[BriefingExecution] = Field(
        default_factory=list
    )
    related_references: list[BriefingReference] = Field(
        default_factory=list
    )

    agenda_items: list[str] = Field(default_factory=list)
    operational_requirements: list[str] = Field(
        default_factory=list
    )
    mandatory_requirements: list[str] = Field(
        default_factory=list
    )
    decisions_already_made: list[str] = Field(
        default_factory=list
    )
    contradictions: list[str] = Field(default_factory=list)

    missing_fields: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    diagnostic_items: list[BriefingDiagnosticItem] = Field(
        default_factory=list
    )
    diagnostic_summary: str | None = None
    recommended_next_step: str | None = None
    source_summary: str
    confidence: float = Field(ge=0, le=1)
