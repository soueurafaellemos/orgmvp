from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_io import InputDocument
from gemini_extractor import (
    _structured_call,
    get_client,
)
from memory_cost_parser import normalize_text
from memory_learning_models import (
    BriefingExtraction,
    BriefingRequirement,
)


BRIEFING_PROMPT = """
Você analisa o briefing inicial de um projeto de live marketing.

O briefing será comparado posteriormente com a apresentação final,
a planilha de custos, os feedbacks e o resultado comercial.

Extraia somente informações sustentadas pelo documento.

RETORNE:
- file_name;
- title;
- project_name;
- client_brand;
- event_name;
- event_date;
- venue;
- objective;
- audience;
- audience_quantity;
- budget_amount;
- currency;
- requirements;
- warnings.

REQUISITOS:
Crie uma ficha independente para cada demanda relevante.

Tipos permitidos em requirement_type:
- objective;
- deliverable;
- mandatory;
- restriction;
- audience;
- logistics;
- budget;
- kpi;
- operation;
- communication;
- desirable;
- context.

Não agrupe todos os entregáveis em uma única ficha quando o briefing
listar entregas diferentes. Exemplo: geladeiras, depósito, brindes,
sampling, mascote e cobertura devem ser requisitos separados.

Use mandatory=true apenas para obrigatoriedades inequívocas.

Prioridades permitidas:
- critical;
- high;
- medium;
- low;
- not_informed.

Em source_reference, indique página, seção, tabela ou título quando
essa referência estiver disponível.

Em source_quote, preserve um trecho curto do próprio briefing.

Não invente aprovação, execução ou aderência. Esses campos serão
avaliados depois pela NAVE.
"""


def _text_value(
    doc: InputDocument,
) -> str:
    if doc.mime_type.startswith(
        "text/"
    ):
        return doc.data.decode(
            "utf-8",
            errors="replace",
        )

    return ""


def _extract_money(
    text: str,
) -> float | None:
    patterns = [
        r"(?:budget|orçamento|orcamento)\D{0,40}"
        r"R?\$?\s*([\d.]+,\d{2})",
        r"R\$\s*([\d.]+,\d{2})",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = (
            match.group(1)
            .replace(".", "")
            .replace(",", ".")
        )

        try:
            return float(value)
        except ValueError:
            continue

    return None


def _after_heading(
    text: str,
    headings: list[str],
    *,
    max_chars: int = 900,
) -> str | None:
    normalized = text.replace(
        "\r\n",
        "\n",
    )

    for heading in headings:
        pattern = (
            r"(?:^|\n)"
            + re.escape(heading)
            + r"\s*:?\s*\n?"
            + r"(.{1,"
            + str(max_chars)
            + r"})"
        )
        match = re.search(
            pattern,
            normalized,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if not match:
            continue

        content = match.group(1)
        next_heading = re.search(
            r"\n[A-ZÁÉÍÓÚÇ0-9][A-ZÁÉÍÓÚÇ0-9 "
            r"/&_-]{4,}\s*:?\s*\n",
            content,
        )

        if next_heading:
            content = content[
                : next_heading.start()
            ]

        cleaned = re.sub(
            r"\s+",
            " ",
            content,
        ).strip()

        if cleaned:
            return cleaned[:max_chars]

    return None


def _bullet_lines(
    text: str,
    heading: str,
) -> list[str]:
    normalized = text.replace(
        "\r\n",
        "\n",
    )
    match = re.search(
        r"(?:^|\n)"
        + re.escape(heading)
        + r"\s*:?\s*\n"
        + r"(.{1,4000})",
        normalized,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        return []

    section = match.group(1)
    next_heading = re.search(
        r"\n[A-ZÁÉÍÓÚÇ0-9][A-ZÁÉÍÓÚÇ0-9 "
        r"/&_-]{4,}\s*:?\s*\n",
        section,
    )

    if next_heading:
        section = section[
            : next_heading.start()
        ]

    lines = []

    for line in section.splitlines():
        clean = re.sub(
            r"^[\s•\-–—\d.)]+",
            "",
            line,
        ).strip()

        if (
            len(clean) >= 3
            and not clean.endswith(":")
        ):
            lines.append(clean)

    return list(
        dict.fromkeys(lines)
    )


def _fallback_extraction(
    doc: InputDocument,
    *,
    warning: str | None = None,
) -> BriefingExtraction:
    text = _text_value(doc)
    file_title = Path(
        doc.name
    ).stem
    normalized = normalize_text(
        text
    )

    requirements = []

    objective = _after_heading(
        text,
        [
            "OBJETIVO E DESAFIO",
            "OBJETIVO",
        ],
    )
    audience = _after_heading(
        text,
        [
            "PUBLICO ALVO",
            "PÚBLICO ALVO",
        ],
    )

    for item in _bullet_lines(
        text,
        "ENTREGAVEIS",
    ) + _bullet_lines(
        text,
        "ENTREGÁVEIS",
    ):
        requirements.append(
            BriefingRequirement(
                requirement_type=(
                    "deliverable"
                ),
                title=item[:180],
                description=item,
                priority="high",
                mandatory=False,
                source_reference=(
                    "Entregáveis"
                ),
                source_quote=item[:300],
            )
        )

    for item in _bullet_lines(
        text,
        "OBRIGATORIEDADES",
    ):
        requirements.append(
            BriefingRequirement(
                requirement_type=(
                    "mandatory"
                ),
                title=item[:180],
                description=item,
                priority="critical",
                mandatory=True,
                source_reference=(
                    "Obrigatoriedades"
                ),
                source_quote=item[:300],
            )
        )

    restriction = _after_heading(
        text,
        [
            "IMPUTS DA AREA DE NEGÓCIO",
            "INPUTS DA AREA DE NEGÓCIO",
            "INPUTS DA ÁREA DE NEGÓCIO",
        ],
    )

    if restriction:
        requirements.append(
            BriefingRequirement(
                requirement_type=(
                    "restriction"
                ),
                title=(
                    "Restrição de verba e estrutura"
                    if "menos dinheiro"
                    in normalize_text(
                        restriction
                    )
                    else "Restrição do projeto"
                ),
                description=restriction,
                priority="critical",
                mandatory=True,
                source_reference=(
                    "Inputs da área de negócio"
                ),
                source_quote=(
                    restriction[:300]
                ),
            )
        )

    budget_amount = _extract_money(
        text
    )

    if budget_amount is not None:
        requirements.append(
            BriefingRequirement(
                requirement_type="budget",
                title=(
                    "Respeitar o budget informado"
                ),
                description=(
                    f"Budget identificado: "
                    f"R$ {budget_amount:,.2f}"
                ),
                priority="critical",
                mandatory=True,
                source_reference="Budget",
                source_quote=(
                    "Budget identificado "
                    "no briefing."
                ),
            )
        )

    if objective:
        requirements.append(
            BriefingRequirement(
                requirement_type="objective",
                title="Objetivo principal",
                description=objective,
                priority="critical",
                mandatory=True,
                source_reference=(
                    "Objetivo e desafio"
                ),
                source_quote=objective[:300],
            )
        )

    if audience:
        requirements.append(
            BriefingRequirement(
                requirement_type="audience",
                title="Público-alvo",
                description=audience,
                priority="high",
                mandatory=False,
                source_reference=(
                    "Público-alvo"
                ),
                source_quote=audience[:300],
            )
        )

    client_brand = None
    event_name = None

    if "chambinho" in normalized:
        client_brand = "Chambinho"

    if "festivalzinho" in normalized:
        event_name = "Festivalzinho"

    warnings = []

    if warning:
        warnings.append(warning)

    if not requirements:
        warnings.append(
            "A leitura de segurança não conseguiu "
            "separar demandas individuais. Revise "
            "o documento manualmente."
        )

    return BriefingExtraction(
        file_name=doc.name,
        title=file_title,
        project_name=file_title,
        client_brand=client_brand,
        event_name=event_name,
        objective=objective,
        audience=audience,
        budget_amount=budget_amount,
        requirements=requirements,
        warnings=warnings,
    )


def analyze_briefing_document(
    doc: InputDocument,
    *,
    api_key: str | None,
    model: str,
) -> BriefingExtraction:
    client = get_client(
        api_key
    )

    try:
        result = _structured_call(
            client,
            model=model,
            prompt=(
                BRIEFING_PROMPT
                + "\n\nARQUIVO ORIGINAL: "
                + doc.name
            ),
            docs=[doc],
            schema=BriefingExtraction,
            context=(
                "análise do briefing "
                + doc.name
            ),
        )
        result.file_name = doc.name

        if not result.requirements:
            fallback = _fallback_extraction(
                doc,
                warning=(
                    "A IA não devolveu demandas "
                    "individuais. A NAVE aplicou "
                    "uma leitura de segurança."
                ),
            )
            result.requirements = (
                fallback.requirements
            )
            result.warnings = list(
                dict.fromkeys(
                    [
                        *result.warnings,
                        *fallback.warnings,
                    ]
                )
            )

        return result

    except Exception as exc:
        return _fallback_extraction(
            doc,
            warning=(
                "A análise estruturada não foi "
                "concluída. A NAVE aplicou uma "
                "leitura de segurança. "
                f"Detalhe técnico: {exc}"
            ),
        )
