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



class RecommendationBrief(BaseModel):
    project_name: str | None = None
    objective: str | None = None
    audience_profile: str | None = None
    audience_quantity: int | None = None
    budget_total_brl: float | None = None
    budget_unit_brl: float | None = None
    location_city: str | None = None
    location_state: str | None = None
    event_date: str | None = None
    available_days: int | None = None
    desired_types: list[
        Literal["product", "activation", "venue"]
    ] = Field(default_factory=list)
    desired_attributes: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source_summary: str
    confidence: float = Field(ge=0, le=1)
