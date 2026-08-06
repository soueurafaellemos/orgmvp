from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field
from models import VisualCrop

MemorySection = Literal[
    "strategy",
    "scenography",
    "activations",
    "gifts",
    "journey_operation",
    "communication",
    "content_agenda",
    "partners_sponsorship",
    "pr_esg_legacy",
]

MemoryItemStatus = Literal[
    "Referência",
    "Proposto",
    "Opção",
    "Recomendado",
    "Aprovado",
    "Descartado",
    "Executado",
    "Não identificado",
]


class MemoryItem(BaseModel):
    section_key: MemorySection
    item_type: str
    title: str
    summary: str | None = None
    description: str | None = None
    status: MemoryItemStatus = "Não identificado"
    tags: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    audiences: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    journey_stage: str | None = None
    visual_crop: VisualCrop | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)
    evidence: str | None = None


class MemorySlide(BaseModel):
    source_file: str
    source_page: int
    slide_title: str | None = None
    slide_summary: str | None = None
    primary_section: MemorySection | None = None
    items: list[MemoryItem] = Field(default_factory=list)


class MemoryBatch(BaseModel):
    source_file: str
    document_title: str | None = None
    client_brand: str | None = None
    project_name: str | None = None
    event_name: str | None = None
    strategic_summary: str | None = None
    creative_concept: str | None = None
    slides: list[MemorySlide] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
