from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class GlobalRule(BaseModel):
    key: str
    value: str
    source_page: int | None = None
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
    currency: Literal[
        "BRL", "USD", "EUR", "Outro", "Não informado"
    ] = "Não informado"
    price_status: Literal[
        "Informado",
        "Faixa de preço",
        "Sob consulta",
        "Não informado",
    ] = "Não informado"
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
    catalog_name: str | None = None
    document_year: int | None = None
    category_context: str | None = None
    global_rules: list[GlobalRule] = Field(default_factory=list)
    products: list[CatalogProduct] = Field(default_factory=list)
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
