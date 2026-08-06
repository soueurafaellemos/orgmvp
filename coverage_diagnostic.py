from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import fitz
import pandas as pd
from pydantic import BaseModel, Field

from document_io import InputDocument
from gemini_extractor import _structured_call, get_client
from models import ActivationSolution, CatalogProduct, ProjectBriefing, VenueSpace


DiagnosticSeverity = Literal[
    "Crítico",
    "Importante",
    "Melhoria",
]

DiagnosticStatus = Literal[
    "Coberto",
    "Parcialmente coberto",
    "Não estruturado",
    "Sem campo na NAVE",
    "Revisão necessária",
]

DiagnosticAction = Literal[
    "Nenhuma",
    "Aprimorar extração",
    "Adicionar campo",
    "Adicionar área",
    "Reclassificar",
    "Revisar manualmente",
]


class CoverageFinding(BaseModel):
    source_file: str
    source_locator: str | None = None
    detected_information: str
    evidence: str | None = None
    current_treatment: str | None = None
    status: DiagnosticStatus
    severity: DiagnosticSeverity
    suggested_action: DiagnosticAction
    suggested_destination: str | None = None
    rationale: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class SchemaSuggestion(BaseModel):
    suggestion_type: Literal[
        "Novo campo",
        "Nova área",
        "Novo tipo",
        "Nova regra de extração",
        "Melhoria de interface",
    ]
    title: str
    description: str
    applies_to: list[str] = Field(default_factory=list)
    evidence_examples: list[str] = Field(default_factory=list)
    priority: DiagnosticSeverity = "Melhoria"
    confidence: float = Field(default=0.7, ge=0, le=1)


class CoverageDiagnostic(BaseModel):
    mode: str
    summary: str
    coverage_score: int = Field(default=0, ge=0, le=100)
    source_units_total: int = 0
    source_units_meaningful: int = 0
    source_units_covered: int = 0
    structured_records: int = 0
    findings: list[CoverageFinding] = Field(default_factory=list)
    suggested_schema_additions: list[SchemaSuggestion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


MODE_LABELS = {
    "catalog": "Brindes / produtos",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
    "briefing": "Briefing / projeto",
    "memory": "Memória",
}


MEMORY_CAPABILITIES = {
    "sections": [
        "Visão geral",
        "Estratégia",
        "Cenografia & Ambientes",
        "Ativações & Experiências",
        "Brindes & Materiais",
        "Jornada & Operação",
        "Comunicação & Desdobramentos",
        "Conteúdo & Agenda",
        "Parceiros & Cotas",
        "PR, ESG & Legado",
        "Documentos & Versões",
    ],
    "item_fields": [
        "título",
        "tipo",
        "resumo",
        "descrição",
        "status",
        "tags",
        "objetivos",
        "públicos",
        "mecânicas",
        "tecnologias",
        "etapa da jornada",
        "imagem",
        "slide de origem",
        "evidência",
    ],
    "restriction": (
        "O conteúdo da Memória nunca entra na Base de conhecimento "
        "ou nas recomendações."
    ),
}


DIAGNOSTIC_PROMPT = """
Você é o auditor de cobertura da NAVE by VOE.

Compare o conteúdo realmente presente nos arquivos com o resultado que a
plataforma estruturou e com as áreas/campos atualmente suportados.

OBJETIVOS:
1. Identificar conteúdo presente na fonte que não apareceu no resultado.
2. Identificar conteúdo que apareceu apenas parcialmente.
3. Diferenciar falha de extração de uma limitação real do modelo de dados.
4. Sugerir novos campos, tipos, áreas ou regras somente quando a informação
   for recorrente ou claramente útil para consulta futura.
5. Produzir um diagnóstico aplicável a qualquer cliente, evento, fornecedor,
   planilha, catálogo, local ou projeto. Não desenhe uma solução exclusiva
   para o arquivo analisado.

REGRAS:
- Não invente dados ausentes.
- Não trate capa, índice, divisória ou agradecimento como lacuna.
- Uma imagem ou proposta visual relevante conta como conteúdo, mesmo sem
  muito texto.
- Se o conteúdo cabe em um campo ou área existente, recomende aprimorar a
  extração ou reclassificar; não proponha uma nova área desnecessária.
- Use "Sem campo na NAVE" somente quando nenhuma capacidade atual comporta
  adequadamente a informação.
- Para a Memória, nunca sugira mover conteúdo para a Base de conhecimento.
- Evite findings positivos em excesso. Priorize lacunas e melhorias.
- Cite página, slide, aba ou arquivo sempre que possível.
- A cobertura deve refletir o quanto do conteúdo significativo ficou
  consultável, não apenas a quantidade de registros.
"""


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clip(value: Any, limit: int = 1500) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"




def _bounded_json(value: Any, limit: int = 110_000) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        default=str,
    )
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[conteúdo abreviado automaticamente]"

def _looks_non_content(text: str, page_number: int | None = None) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if page_number == 1 and len(normalized) < 150:
        return True
    signals = (
        "indice",
        "sumario",
        "obrigado",
        "danke",
        "thank you",
    )
    return len(normalized) < 120 and any(signal in normalized for signal in signals)


def _pdf_inventory(doc: InputDocument) -> list[dict]:
    pdf = fitz.open(stream=doc.data, filetype="pdf")
    rows = []
    try:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            image_count = len(page.get_images(full=True))
            normalized = _normalize_text(text)
            meaningful = (
                not _looks_non_content(text, page_number)
                and (len(normalized) >= 24 or image_count > 0)
            )
            rows.append(
                {
                    "unit_id": f"{doc.name}#page:{page_number}",
                    "source_file": doc.name,
                    "source_locator": f"Página {page_number}",
                    "source_page": page_number,
                    "unit_kind": "Página de PDF",
                    "text": _clip(text, 1800),
                    "image_count": image_count,
                    "meaningful": meaningful,
                }
            )
    finally:
        pdf.close()
    return rows


def _split_text_units(doc: InputDocument) -> list[dict]:
    text = doc.data.decode("utf-8", errors="replace")
    units: list[dict] = []

    slide_pattern = re.compile(r"^=== SLIDE (\d+) ===$", flags=re.MULTILINE)
    slide_matches = list(slide_pattern.finditer(text))
    if slide_matches:
        for index, match in enumerate(slide_matches):
            start = match.end()
            end = (
                slide_matches[index + 1].start()
                if index + 1 < len(slide_matches)
                else len(text)
            )
            slide_number = int(match.group(1))
            content = text[start:end].strip()
            units.append(
                {
                    "unit_id": f"{doc.name}#slide:{slide_number}",
                    "source_file": doc.name,
                    "source_locator": f"Slide {slide_number}",
                    "source_page": slide_number,
                    "unit_kind": "Slide convertido em texto",
                    "text": _clip(content, 1800),
                    "image_count": None,
                    "meaningful": bool(_normalize_text(content)),
                }
            )
        return units

    sheet_pattern = re.compile(r"^=== ABA: (.+?) ===$", flags=re.MULTILINE)
    sheet_matches = list(sheet_pattern.finditer(text))
    if sheet_matches:
        for index, match in enumerate(sheet_matches):
            start = match.end()
            end = (
                sheet_matches[index + 1].start()
                if index + 1 < len(sheet_matches)
                else len(text)
            )
            sheet_name = match.group(1).strip()
            content = text[start:end].strip()
            row_count = max(0, len(content.splitlines()) - 1)
            units.append(
                {
                    "unit_id": f"{doc.name}#sheet:{sheet_name}",
                    "source_file": doc.name,
                    "source_locator": f"Aba {sheet_name}",
                    "source_page": None,
                    "unit_kind": "Aba de planilha",
                    "text": _clip(content, 3500),
                    "image_count": None,
                    "meaningful": row_count > 0,
                    "row_count": row_count,
                }
            )
        return units

    units.append(
        {
            "unit_id": f"{doc.name}#file",
            "source_file": doc.name,
            "source_locator": "Arquivo completo",
            "source_page": None,
            "unit_kind": "Documento textual",
            "text": _clip(text, 7000),
            "image_count": None,
            "meaningful": bool(_normalize_text(text)),
        }
    )
    return units


def build_source_inventory(docs: list[InputDocument]) -> list[dict]:
    inventory: list[dict] = []
    for doc in docs:
        if doc.mime_type == "application/pdf":
            inventory.extend(_pdf_inventory(doc))
        else:
            inventory.extend(_split_text_units(doc))
    return inventory


def _records(value: Any, *, group: str | None = None) -> list[dict]:
    if value is None:
        return []

    if isinstance(value, pd.DataFrame):
        rows = value.where(pd.notna(value), None).to_dict(orient="records")
        if group:
            rows = [{"_record_group": group, **row} for row in rows]
        return rows

    if isinstance(value, BaseModel):
        row = value.model_dump()
        return [{"_record_group": group, **row}] if group else [row]

    if isinstance(value, dict):
        collected: list[dict] = []
        scalar_metadata: dict[str, Any] = {}

        for key, item in value.items():
            if isinstance(item, (pd.DataFrame, BaseModel, list, tuple, dict)):
                nested = _records(item, group=str(key))
                collected.extend(nested)
            elif item not in (None, "", [], {}, ()):
                scalar_metadata[str(key)] = item

        if collected:
            if scalar_metadata:
                collected.insert(
                    0,
                    {
                        "_record_group": group or "metadata",
                        **scalar_metadata,
                    },
                )
            return collected

        row = dict(value)
        return [{"_record_group": group, **row}] if group else [row]

    if isinstance(value, (list, tuple)):
        result: list[dict] = []
        for item in value:
            result.extend(_records(item, group=group))
        return result

    return []


# Imported lazily in _records to avoid adding BaseModel to the public API.
from pydantic import BaseModel  # noqa: E402


def summarize_structured_output(value: Any, *, limit: int = 500) -> list[dict]:
    rows = _records(value)
    result = []
    for row in rows[:limit]:
        source_page = row.get("source_page") or row.get("page")
        source_file = row.get("source_file") or row.get("file_name")
        name = (
            row.get("name")
            or row.get("title")
            or row.get("project_name")
            or row.get("document_title")
            or row.get("item_type")
            or "Registro"
        )
        non_empty_fields = [
            str(key)
            for key, item in row.items()
            if item not in (None, "", [], {}, ())
            and not str(key).startswith("_")
        ]
        result.append(
            {
                "source_file": source_file,
                "source_page": int(source_page) if str(source_page or "").isdigit() else None,
                "name": _clip(name, 200),
                "summary": _clip(
                    row.get("summary")
                    or row.get("description")
                    or row.get("objective")
                    or row.get("evidence"),
                    600,
                ),
                "non_empty_fields": non_empty_fields[:80],
            }
        )
    return result


def supported_capabilities(mode: str) -> dict:
    if mode == "memory":
        return MEMORY_CAPABILITIES

    model_by_mode = {
        "catalog": CatalogProduct,
        "activation": ActivationSolution,
        "venue": VenueSpace,
        "briefing": ProjectBriefing,
    }
    schema = model_by_mode.get(mode)
    if not schema:
        return {"fields": []}

    return {
        "fields": list(schema.model_fields.keys()),
        "mode_label": MODE_LABELS.get(mode, mode),
    }


def _covered_unit_ids(inventory: list[dict], records: list[dict]) -> set[str]:
    covered: set[str] = set()
    pages_by_file: dict[str, set[int]] = {}
    files_with_records: set[str] = set()

    for record in records:
        source_file = str(record.get("source_file") or "")
        source_page = record.get("source_page")
        if source_file:
            files_with_records.add(source_file)
        if source_file and isinstance(source_page, int):
            pages_by_file.setdefault(source_file, set()).add(source_page)

    for unit in inventory:
        source_file = str(unit.get("source_file") or "")
        source_page = unit.get("source_page")
        if isinstance(source_page, int):
            if source_page in pages_by_file.get(source_file, set()):
                covered.add(str(unit["unit_id"]))
        elif source_file in files_with_records:
            covered.add(str(unit["unit_id"]))

    return covered


def _fallback_diagnostic(
    *,
    mode: str,
    inventory: list[dict],
    records: list[dict],
    warning: str | None = None,
) -> CoverageDiagnostic:
    meaningful = [row for row in inventory if row.get("meaningful")]
    covered_ids = _covered_unit_ids(inventory, records)
    covered = [row for row in meaningful if row["unit_id"] in covered_ids]
    uncovered = [row for row in meaningful if row["unit_id"] not in covered_ids]
    score = round(len(covered) / len(meaningful) * 100) if meaningful else 100
    findings = []

    for row in uncovered[:40]:
        findings.append(
            CoverageFinding(
                source_file=str(row["source_file"]),
                source_locator=str(row.get("source_locator") or ""),
                detected_information=(
                    _clip(row.get("text"), 180)
                    or "Conteúdo visual presente na fonte"
                ),
                evidence=_clip(row.get("text"), 400),
                current_treatment="Nenhum registro relacionado foi localizado pelo diagnóstico determinístico.",
                status="Não estruturado",
                severity="Importante",
                suggested_action="Aprimorar extração",
                suggested_destination=MODE_LABELS.get(mode, mode),
                rationale=(
                    "A unidade contém texto ou imagem, mas não possui um registro com a mesma origem."
                ),
                confidence=0.62,
            )
        )

    warnings = [warning] if warning else []
    return CoverageDiagnostic(
        mode=mode,
        summary=(
            f"Cobertura estimada de {score}%. "
            f"Foram identificadas {len(meaningful)} unidade(s) com conteúdo e "
            f"{len(records)} registro(s) estruturado(s)."
        ),
        coverage_score=score,
        source_units_total=len(inventory),
        source_units_meaningful=len(meaningful),
        source_units_covered=len(covered),
        structured_records=len(records),
        findings=findings,
        warnings=warnings,
    )


def diagnose_coverage(
    docs: list[InputDocument],
    *,
    mode: str,
    structured_output: Any,
    api_key: str | None,
    model: str,
    source_inventory: list[dict] | None = None,
) -> CoverageDiagnostic:
    inventory = source_inventory or build_source_inventory(docs)
    records = summarize_structured_output(structured_output)
    meaningful = [row for row in inventory if row.get("meaningful")]
    covered_ids = _covered_unit_ids(inventory, records)
    deterministic_covered = sum(
        1
        for row in meaningful
        if row["unit_id"] in covered_ids
    )
    deterministic_score = (
        round(deterministic_covered / len(meaningful) * 100)
        if meaningful
        else 100
    )

    inventory_payload = [
        {
            "source_file": row.get("source_file"),
            "source_locator": row.get("source_locator"),
            "unit_kind": row.get("unit_kind"),
            "text": _clip(row.get("text"), 1200),
            "image_count": row.get("image_count"),
            "meaningful": row.get("meaningful"),
        }
        for row in inventory[:220]
    ]

    prompt = (
        DIAGNOSTIC_PROMPT
        + "\n\nMODO ATUAL: "
        + MODE_LABELS.get(mode, mode)
        + "\n\nCAPACIDADES ATUAIS DA NAVE:\n"
        + _bounded_json(supported_capabilities(mode), 30_000)
        + "\n\nINVENTÁRIO DA FONTE:\n"
        + _bounded_json(inventory_payload, 110_000)
        + "\n\nRESULTADO ESTRUTURADO ATUAL:\n"
        + _bounded_json(records[:500], 110_000)
    )

    try:
        client = get_client(api_key)
        diagnostic = _structured_call(
            client,
            model=model,
            prompt=prompt,
            docs=[],
            schema=CoverageDiagnostic,
            context=f"diagnóstico de cobertura — {mode}",
        )
        diagnostic.mode = mode
        diagnostic.source_units_total = len(inventory)
        diagnostic.source_units_meaningful = len(meaningful)
        diagnostic.source_units_covered = deterministic_covered
        diagnostic.structured_records = len(records)
        diagnostic.coverage_score = max(
            0,
            min(
                100,
                round((diagnostic.coverage_score + deterministic_score) / 2),
            ),
        )
        return diagnostic
    except Exception as exc:
        return _fallback_diagnostic(
            mode=mode,
            inventory=inventory,
            records=records,
            warning=(
                "O diagnóstico semântico não pôde ser concluído; a NAVE exibiu a auditoria determinística. "
                f"Detalhe técnico: {exc}"
            ),
        )


def diagnostic_dataframe(value: CoverageDiagnostic | dict | None) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    diagnostic = (
        value
        if isinstance(value, CoverageDiagnostic)
        else CoverageDiagnostic.model_validate(value)
    )
    rows = []
    for finding in diagnostic.findings:
        rows.append(
            {
                "Prioridade": finding.severity,
                "Situação": finding.status,
                "Arquivo": finding.source_file,
                "Origem": finding.source_locator or "Não informada",
                "Informação detectada": finding.detected_information,
                "Tratamento atual": finding.current_treatment or "Não informado",
                "Ação sugerida": finding.suggested_action,
                "Destino sugerido": finding.suggested_destination or "Não informado",
                "Motivo": finding.rationale or "",
                "Confiança": round(finding.confidence * 100, 1),
            }
        )
    return pd.DataFrame(rows)


def suggestions_dataframe(value: CoverageDiagnostic | dict | None) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    diagnostic = (
        value
        if isinstance(value, CoverageDiagnostic)
        else CoverageDiagnostic.model_validate(value)
    )
    return pd.DataFrame(
        [
            {
                "Prioridade": suggestion.priority,
                "Tipo": suggestion.suggestion_type,
                "Sugestão": suggestion.title,
                "Descrição": suggestion.description,
                "Aplicação": " | ".join(suggestion.applies_to),
                "Evidências": " | ".join(suggestion.evidence_examples),
                "Confiança": round(suggestion.confidence * 100, 1),
            }
            for suggestion in diagnostic.suggested_schema_additions
        ]
    )


def diagnostic_json_bytes(value: CoverageDiagnostic | dict) -> bytes:
    diagnostic = (
        value
        if isinstance(value, CoverageDiagnostic)
        else CoverageDiagnostic.model_validate(value)
    )
    return diagnostic.model_dump_json(indent=2).encode("utf-8")
