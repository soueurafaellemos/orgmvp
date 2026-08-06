from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import fitz
import openpyxl
import pandas as pd
from google import genai
from google.genai import types


DEFAULT_REPORT_MODEL = "gemini-3.5-flash"

REPORT_SCHEMA_EXAMPLE = {
    "document_type": "post_execution_report",
    "event_date": "2026-08-01",
    "participants_count": 6500,
    "planned_cost": 400000.0,
    "actual_cost": 392500.0,
    "client_satisfaction": "Cliente satisfeito com a operação.",
    "executive_summary": "Resumo objetivo do que aconteceu.",
    "objectives_result": "Avaliação dos objetivos e entregáveis.",
    "commercial_result": "won",
    "execution_result": "executed",
    "competitor": None,
    "loss_reasons": [],
    "highlights": ["Destaque comprovado pelo documento."],
    "issues": ["Ocorrência ou ponto de atenção comprovado."],
    "learnings": ["Aprendizado explícito ou sustentado por evidência."],
    "recommendations": ["Recomendação para projetos futuros."],
    "client_feedback": [
        {
            "text": "Feedback literal ou fiel ao documento.",
            "sentiment": "positive",
            "theme": "activation",
            "evidence": "Trecho ou contexto de origem."
        }
    ],
    "kpis": [
        {
            "name": "Participantes",
            "target": "6.000",
            "actual": "6.500",
            "unit": "pessoas",
            "status": "exceeded",
            "evidence": "Trecho ou tabela de origem."
        }
    ],
    "activation_results": [
        {
            "name": "Amarelinha",
            "result": "Descrição do resultado.",
            "participants": 900,
            "status": "executed",
            "evidence": "Trecho ou contexto."
        }
    ],
    "supplier_evaluations": [
        {
            "supplier": "Fornecedor",
            "scope": "Escopo executado",
            "evaluation": "Avaliação objetiva",
            "issues": [],
            "recommended": True,
            "evidence": "Trecho ou contexto."
        }
    ],
    "media_results": [
        {
            "channel": "Instagram",
            "metric": "Alcance",
            "value": "120000",
            "unit": "pessoas",
            "evidence": "Trecho ou tabela."
        }
    ],
    "item_results": [
        {
            "item_name": "Pescaria",
            "item_type": "Ativação",
            "outcome_status": "executed",
            "feedback": "Resultado e decisão observados.",
            "evidence": "Trecho ou contexto."
        }
    ],
    "confidence_level": "voe_confirmed"
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _xml_text(data: bytes) -> str:
    try:
        root = ET.fromstring(data)
    except Exception:
        return ""
    chunks: list[str] = []
    for node in root.iter():
        if node.text and node.text.strip():
            chunks.append(node.text.strip())
    return "\n".join(chunks)


def _extract_docx(file_bytes: bytes) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        names = set(archive.namelist())
        for name in (
            "word/document.xml",
            "word/footnotes.xml",
            "word/endnotes.xml",
            "word/comments.xml",
        ):
            if name in names:
                chunks.append(_xml_text(archive.read(name)))
        headers = sorted(
            name for name in names
            if name.startswith("word/header") and name.endswith(".xml")
        )
        footers = sorted(
            name for name in names
            if name.startswith("word/footer") and name.endswith(".xml")
        )
        for name in [*headers, *footers]:
            chunks.append(_xml_text(archive.read(name)))
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _extract_pptx(file_bytes: bytes) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        slide_names = sorted(
            (
                item for item in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", item)
            ),
            key=lambda value: int(re.search(r"(\d+)", value).group(1)),
        )
        for index, name in enumerate(slide_names, start=1):
            text = _xml_text(archive.read(name))
            if text:
                chunks.append(f"[Página {index}]\n{text}")
    return "\n\n".join(chunks)


def _extract_pdf(file_bytes: bytes) -> str:
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        chunks = []
        for index, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if text:
                chunks.append(f"[Página {index}]\n{text}")
        return "\n\n".join(chunks)
    finally:
        pdf.close()


def _extract_spreadsheet(file_name: str, file_bytes: bytes) -> str:
    suffix = Path(file_name).suffix.casefold()
    if suffix in {".xlsx", ".xlsm"}:
        workbook = openpyxl.load_workbook(
            io.BytesIO(file_bytes),
            read_only=True,
            data_only=True,
            keep_vba=False,
        )
        chunks = []
        try:
            for worksheet in workbook.worksheets:
                chunks.append(f"[Aba: {worksheet.title}]")
                for row in worksheet.iter_rows(values_only=True):
                    values = [_clean_text(value) for value in row]
                    if any(values):
                        chunks.append(" | ".join(values))
        finally:
            workbook.close()
        return "\n".join(chunks)
    if suffix == ".xls":
        sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)
        chunks = []
        for sheet_name, dataframe in sheets.items():
            chunks.append(f"[Aba: {sheet_name}]")
            safe = dataframe.fillna("").astype(str)
            for row in safe.itertuples(index=False, name=None):
                values = [_clean_text(value) for value in row]
                if any(values):
                    chunks.append(" | ".join(values))
        return "\n".join(chunks)
    if suffix == ".csv":
        decoded = file_bytes.decode("utf-8-sig", errors="replace")
        rows = csv.reader(io.StringIO(decoded))
        return "\n".join(" | ".join(row) for row in rows)
    return ""


def extract_report_text(*, file_name: str, mime_type: str | None, file_bytes: bytes) -> str:
    suffix = Path(file_name).suffix.casefold()
    mime = str(mime_type or "").casefold()
    if suffix == ".pdf" or mime == "application/pdf":
        return _extract_pdf(file_bytes)
    if suffix == ".docx":
        return _extract_docx(file_bytes)
    if suffix == ".pptx":
        return _extract_pptx(file_bytes)
    if suffix in {".xlsx", ".xlsm", ".xls", ".csv"}:
        return _extract_spreadsheet(file_name, file_bytes)
    if suffix in {".txt", ".md"} or mime.startswith("text/"):
        return file_bytes.decode("utf-8-sig", errors="replace")
    raise ValueError(
        "Formato não suportado para análise do relatório. "
        "Use PDF, DOCX, PPTX, XLSX, XLSM, XLS, CSV, TXT ou MD."
    )


def _json_from_response(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("A análise não retornou conteúdo.")
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("A resposta do modelo não contém um objeto JSON válido.")
    return json.loads(text[start:end + 1])


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_text_list(value: Any) -> list[str]:
    return [_clean_text(item) for item in _as_list(value) if _clean_text(item)]


def _as_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,.\-]", "", str(value))
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def _as_int(value: Any) -> int | None:
    number = _as_number(value)
    return int(round(number)) if number is not None else None


def _normalise_status(value: Any, *, allowed: set[str], default: str) -> str:
    text = _clean_text(value).casefold().replace(" ", "_")
    return text if text in allowed else default


def normalise_report_analysis(raw: dict[str, Any], *, report_type: str) -> dict[str, Any]:
    confidence = _normalise_status(
        raw.get("confidence_level"),
        allowed={"client_confirmed", "voe_confirmed", "inferred", "incomplete"},
        default="incomplete",
    )
    commercial_result = _normalise_status(
        raw.get("commercial_result"),
        allowed={"in_evaluation", "won", "lost", "cancelled", "suspended", "no_return", "not_applicable", "not_informed"},
        default="lost" if report_type == "closure" else "not_informed",
    )
    execution_result = _normalise_status(
        raw.get("execution_result"),
        allowed={"executed", "partially_executed", "not_executed", "in_progress", "not_applicable", "not_informed"},
        default="executed" if report_type == "post_execution" else "not_applicable",
    )
    return {
        "document_type": _clean_text(raw.get("document_type")) or ("closure_report" if report_type == "closure" else "post_execution_report"),
        "event_date": _clean_text(raw.get("event_date")) or None,
        "participants_count": _as_int(raw.get("participants_count")),
        "planned_cost": _as_number(raw.get("planned_cost")),
        "actual_cost": _as_number(raw.get("actual_cost")),
        "client_satisfaction": _clean_text(raw.get("client_satisfaction")) or None,
        "executive_summary": _clean_text(raw.get("executive_summary")) or "Resumo não identificado.",
        "objectives_result": _clean_text(raw.get("objectives_result")) or None,
        "commercial_result": commercial_result,
        "execution_result": execution_result,
        "competitor": _clean_text(raw.get("competitor")) or None,
        "loss_reasons": _as_text_list(raw.get("loss_reasons")),
        "highlights": _as_text_list(raw.get("highlights")),
        "issues": _as_text_list(raw.get("issues")),
        "learnings": _as_text_list(raw.get("learnings")),
        "recommendations": _as_text_list(raw.get("recommendations")),
        "client_feedback": [item for item in _as_list(raw.get("client_feedback")) if isinstance(item, (dict, str))],
        "kpis": [item for item in _as_list(raw.get("kpis")) if isinstance(item, dict)],
        "activation_results": [item for item in _as_list(raw.get("activation_results")) if isinstance(item, dict)],
        "supplier_evaluations": [item for item in _as_list(raw.get("supplier_evaluations")) if isinstance(item, dict)],
        "media_results": [item for item in _as_list(raw.get("media_results")) if isinstance(item, dict)],
        "item_results": [item for item in _as_list(raw.get("item_results")) if isinstance(item, dict)],
        "confidence_level": confidence,
    }


def analyze_project_report(
    *,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    report_type: str,
    api_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("A chave GEMINI_API_KEY não está configurada nos Secrets.")
    text = extract_report_text(file_name=file_name, mime_type=mime_type, file_bytes=file_bytes)
    prompt = f"""
Você é o módulo de encerramento e aprendizado da NAVE by VOE,
plataforma de inteligência para projetos de live marketing.

Analise o arquivo como:
- relatório pós-execução, quando report_type = post_execution;
- relatório de encerramento de concorrência, quando report_type = closure.

report_type: {report_type}
arquivo: {file_name}

REGRAS OBRIGATÓRIAS
1. Não invente números, datas, resultados, feedbacks ou fornecedores.
2. Use null ou lista vazia quando a informação não estiver comprovada.
3. Diferencie meta de resultado realizado.
4. Extraia resultados por ativação, ambiente, brinde, press kit ou entrega sempre que o documento permitir.
5. Preserve feedbacks do cliente e ocorrências operacionais.
6. Extraia custos planejados e realizados separadamente.
7. Identifique aprendizados e recomendações reutilizáveis.
8. item_results deve usar nomes próximos aos itens apresentados no projeto para permitir correlação com as fichas da Memória.
9. Não use o número do slide como informação de negócio.
10. Retorne somente JSON válido, sem markdown.

FORMATO EXATO
{json.dumps(REPORT_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2)}

TEXTO EXTRAÍDO
{text[:120000]}
""".strip()
    client = genai.Client(api_key=api_key)
    resolved_model = str(model or DEFAULT_REPORT_MODEL).strip()
    contents: list[Any] = [prompt]
    if str(mime_type or "").casefold() == "application/pdf" or Path(file_name).suffix.casefold() == ".pdf":
        contents = [types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"), prompt]
    response = client.models.generate_content(
        model=resolved_model,
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"),
    )
    raw = _json_from_response(response.text)
    normalised = normalise_report_analysis(raw, report_type=report_type)
    normalised["_raw_model_response"] = raw
    normalised["_extracted_text_length"] = len(text)
    return normalised
