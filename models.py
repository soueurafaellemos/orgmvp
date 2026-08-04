from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


class GlobalRule(BaseModel):
    key: str
    value: str
    source_page: int | None
    confidence: float


class CatalogProduct(BaseModel):
    source_file: str
    source_page: int | None
    category: str | None
    sku: str | None
    name: str
    description: str | None
    capacity: str | None
    capacity_ml: float | None
    dimensions_raw: str | None
    material: str | None
    finish: str | None
    decoration: str | None
    origin: Literal["Brasil", "China", "Outro", "Não informado"]
    development_status: Literal[
        "Produto regular", "Produto conceito", "Não informado"
    ]
    min_order_qty: int | None
    customizable: bool | None
    licensing_notes: str | None
    tags: list[str]
    confidence: float
    missing_fields: list[str]
    evidence: str | None


class CatalogBatch(BaseModel):
    supplier_name: str | None
    catalog_name: str | None
    document_year: int | None
    category_context: str | None
    global_rules: list[GlobalRule]
    products: list[CatalogProduct]
    warnings: list[str]


class ProjectBriefing(BaseModel):
    source_files: list[str]
    project_name: str | None
    client_brand: str | None
    event_name: str | None
    event_type: str | None
    objective: str | None
    audience_profile: str | None
    audience_quantity: int | None
    budget_total_brl: float | None
    budget_unit_brl: float | None
    location_city: str | None
    location_state: str | None
    location_country: str | None
    event_date: str | None
    desired_delivery_date: str | None
    available_days: int | None
    creative_concept: str | None
    desired_attributes: list[str]
    restrictions: list[str]
    differentiations_by_audience: list[str]
    products_already_mentioned: list[str]
    decisions_already_made: list[str]
    open_questions: list[str]
    missing_fields: list[str]
    contradictions: list[str]
    source_summary: str
    confidence: float
