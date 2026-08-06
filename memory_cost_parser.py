from __future__ import annotations

import csv
import io
import re
import unicodedata
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from memory_learning_models import (
    CostItem,
    CostWorkbookResult,
)


HEADER_ALIASES = {
    "code": {"#", "codigo", "cod", "item codigo"},
    "category_or_name": {
        "item descricao",
        "item",
        "categoria",
        "grupo",
    },
    "description": {
        "descricao",
        "escopo",
        "especificacao",
        "detalhamento",
    },
    "billing_type": {
        "tipo faturamento",
        "faturamento",
        "tipo de faturamento",
    },
    "quantity": {"quant", "qtd", "qtde", "quantidade"},
    "period": {"periodo", "diarias", "dias", "duracao"},
    "unit_value": {
        "valor unit",
        "valor unitario",
        "unitario",
        "preco unitario",
    },
    "base_value": {
        "valor total",
        "custo base",
        "subtotal",
    },
    "fees_value": {
        "honorarios",
        "honorario",
        "fee",
    },
    "charges_value": {
        "encargos",
        "impostos",
        "taxas",
    },
    "client_total": {
        "total com honorarios e encargos",
        "total cliente",
        "valor final",
        "total final",
    },
}

STATUS_KEYWORDS = {
    "client_responsibility": [
        "responsabilidade cliente",
        "responsabilidade do cliente",
    ],
    "optional": ["opcional"],
    "reserve": [
        "reserva de verba",
        "verba de reserva",
    ],
    "pending": [
        "aguardando",
        "a definir",
        "em definicao",
        "apos visita tecnica",
        "a avaliar",
    ],
}

ESTIMATE_KEYWORDS = {
    "estimated": [
        "estimado",
        "estimativa",
        "pode sofrer alteracao",
        "sujeito a alteracao",
    ],
    "waiting_supplier": [
        "aguardando fornecedor",
        "aguardando lista",
        "fornecedor oficial",
    ],
}


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text.casefold(),
    )
    return re.sub(r"\s+", " ", text).strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = re.sub(
        r"[^\d,.\-]",
        "",
        str(value).strip(),
    )

    if not text:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def _first_line(value: Any) -> str:
    lines = [
        re.sub(r"\s+", " ", line).strip(" -*•\t")
        for line in str(value or "").splitlines()
        if line.strip()
    ]

    if not lines:
        return ""

    result = re.sub(
        r"^(gift|ativacao|ativação)\s*[-:]\s*",
        "",
        lines[0],
        flags=re.IGNORECASE,
    )
    return result[:220]


def _sheet_matrix_xlsx(
    data: bytes,
    *,
    keep_vba: bool,
) -> list[tuple[str, list[list[Any]]]]:
    workbook = load_workbook(
        io.BytesIO(data),
        read_only=True,
        data_only=True,
        keep_vba=keep_vba,
    )
    sheets = []

    try:
        for worksheet in workbook.worksheets:
            matrix = []

            for row in worksheet.iter_rows(
                min_row=1,
                max_row=min(worksheet.max_row or 1, 5000),
                values_only=True,
            ):
                matrix.append(list(row[:60]))

            sheets.append((worksheet.title, matrix))
    finally:
        workbook.close()

    return sheets


def _sheet_matrix_xls(
    data: bytes,
) -> list[tuple[str, list[list[Any]]]]:
    import xlrd

    workbook = xlrd.open_workbook(file_contents=data)
    return [
        (
            sheet.name,
            [
                sheet.row_values(row_index)
                for row_index in range(min(sheet.nrows, 5000))
            ],
        )
        for sheet in workbook.sheets()
    ]


def _sheet_matrix_csv(
    data: bytes,
) -> list[tuple[str, list[list[Any]]]]:
    decoded = data.decode("utf-8-sig", errors="replace")

    try:
        dialect = csv.Sniffer().sniff(
            decoded[:5000],
            delimiters=",;\t|",
        )
    except csv.Error:
        dialect = csv.excel

    return [
        (
            "Planilha",
            list(csv.reader(io.StringIO(decoded), dialect)),
        )
    ]


def _load_sheets(
    file_name: str,
    data: bytes,
) -> list[tuple[str, list[list[Any]]]]:
    suffix = Path(file_name).suffix.casefold()

    if suffix in {".xlsx", ".xlsm"}:
        return _sheet_matrix_xlsx(
            data,
            keep_vba=suffix == ".xlsm",
        )

    if suffix == ".xls":
        return _sheet_matrix_xls(data)

    if suffix == ".csv":
        return _sheet_matrix_csv(data)

    raise ValueError(
        "Formato de planilha não suportado. "
        "Use XLSX, XLSM, XLS ou CSV."
    )


def _header_key(value: Any) -> str | None:
    raw = str(value or "").strip()
    if raw == "#":
        return "code"

    normalized = normalize_text(value)

    for key, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return key

    return None


def _find_header(
    matrix: list[list[Any]],
) -> tuple[int, dict[str, int]]:
    best_row = -1
    best_map: dict[str, int] = {}

    for row_index, row in enumerate(matrix[:120], start=1):
        mapping: dict[str, int] = {}

        for column_index, value in enumerate(row[:40]):
            key = _header_key(value)

            if key and key not in mapping:
                mapping[key] = column_index

        required_score = sum(
            key in mapping
            for key in {
                "description",
                "quantity",
                "unit_value",
                "base_value",
                "client_total",
                "category_or_name",
            }
        )

        if (
            len(mapping) >= 4
            and required_score >= 2
            and len(mapping) > len(best_map)
        ):
            best_row = row_index
            best_map = mapping

    if best_row < 1:
        raise ValueError(
            "Não foi possível identificar uma "
            "tabela de custos na planilha."
        )

    return best_row, best_map


def _sheet_score(matrix: list[list[Any]]) -> int:
    try:
        _, mapping = _find_header(matrix)
    except ValueError:
        return 0

    return len(mapping) * 10 + min(len(matrix), 200)


def _get(
    row: list[Any],
    mapping: dict[str, int],
    key: str,
) -> Any:
    index = mapping.get(key)

    if index is None or index >= len(row):
        return None

    return row[index]


def _metadata_before_header(
    matrix: list[list[Any]],
    header_row: int,
) -> dict:
    metadata: dict[str, Any] = {}
    title_candidates = []

    for row in matrix[: max(0, header_row - 1)]:
        values = [
            str(value).strip()
            for value in row
            if value not in (None, "")
        ]

        for value in values:
            if ":" in value:
                key, content = value.split(":", 1)

                if content.strip():
                    metadata[normalize_text(key)] = content.strip()
            elif (
                len(value) >= 12
                and not re.fullmatch(r"[\d\s./%-]+", value)
            ):
                title_candidates.append(value)

    metadata["_title_candidates"] = title_candidates
    return metadata


def _status_and_estimate(
    description: str,
    *,
    base_value: float | None,
    client_total: float | None,
) -> tuple[str, str, list[str]]:
    normalized = normalize_text(description)
    flags = []
    status = None

    for status_key, keywords in STATUS_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            status = status_key
            flags.append(status_key)
            break

    if status is None:
        status = (
            "included"
            if (client_total or 0) > 0 or (base_value or 0) > 0
            else "no_value"
        )

    estimate_type = None

    for estimate_key, keywords in ESTIMATE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            estimate_type = estimate_key
            flags.append(estimate_key)
            break

    if estimate_type is None:
        if status == "reserve":
            estimate_type = "reserve"
        elif (client_total or 0) > 0 or (base_value or 0) > 0:
            estimate_type = "quoted"
        else:
            estimate_type = "no_value"

    return status, estimate_type, list(dict.fromkeys(flags))


def _extract_total_row(
    matrix: list[list[Any]],
    header_row: int,
    mapping: dict[str, int],
) -> dict:
    for row in matrix[header_row : min(len(matrix), header_row + 8)]:
        first_values = " ".join(
            normalize_text(value)
            for value in row[:4]
        )

        if re.search(r"\btotal\b", first_values):
            return {
                "total_base": _number(_get(row, mapping, "base_value")),
                "fees_total": _number(_get(row, mapping, "fees_value")),
                "charges_total": _number(_get(row, mapping, "charges_value")),
                "client_total": _number(_get(row, mapping, "client_total")),
            }

    return {}


def parse_cost_workbook(
    file_name: str,
    data: bytes,
) -> CostWorkbookResult:
    sheets = _load_sheets(file_name, data)

    if not sheets:
        raise ValueError("A planilha não possui abas legíveis.")

    selected_sheet_name, matrix = max(
        sheets,
        key=lambda item: _sheet_score(item[1]),
    )
    header_row, mapping = _find_header(matrix)
    metadata = _metadata_before_header(matrix, header_row)
    totals = _extract_total_row(matrix, header_row, mapping)

    header_values = (
        matrix[header_row - 1]
        if header_row - 1 < len(matrix)
        else []
    )
    mapped_columns = set(mapping.values())
    unknown_columns = [
        str(value).strip()
        for index, value in enumerate(header_values)
        if (
            value not in (None, "")
            and index not in mapped_columns
        )
    ]

    items = []
    current_category = None
    blank_streak = 0

    for source_row, row in enumerate(
        matrix[header_row:],
        start=header_row + 1,
    ):
        row_text = " ".join(
            str(value or "").strip()
            for value in row
        ).strip()

        if not row_text:
            blank_streak += 1

            if blank_streak >= 5 and items:
                break
            continue

        blank_streak = 0

        code = _get(row, mapping, "code")
        category_or_name = _get(row, mapping, "category_or_name")
        description = _get(row, mapping, "description")
        billing_type = _get(row, mapping, "billing_type")
        quantity = _number(_get(row, mapping, "quantity"))
        period = _number(_get(row, mapping, "period"))
        unit_value = _number(_get(row, mapping, "unit_value"))
        base_value = _number(_get(row, mapping, "base_value"))
        fees_value = _number(_get(row, mapping, "fees_value"))
        charges_value = _number(_get(row, mapping, "charges_value"))
        client_total = _number(_get(row, mapping, "client_total"))

        normalized_first = normalize_text(
            " ".join(str(value or "") for value in row[:4])
        )

        if re.search(r"\btotal\b", normalized_first):
            continue

        is_category = (
            bool(str(category_or_name or "").strip())
            and not str(description or "").strip()
            and not str(billing_type or "").strip()
            and all(
                value in (None, 0)
                for value in [
                    quantity,
                    unit_value,
                    base_value,
                    client_total,
                ]
            )
        )

        if is_category:
            current_category = str(category_or_name).strip()
            continue

        full_description = str(
            description
            or category_or_name
            or ""
        ).strip()

        if not full_description:
            continue

        item_name = _first_line(full_description)

        if not item_name:
            continue

        status, estimate_type, flags = _status_and_estimate(
            full_description,
            base_value=base_value,
            client_total=client_total,
        )

        items.append(
            CostItem(
                source_sheet=selected_sheet_name,
                source_row=source_row,
                item_code=(
                    str(code).strip()
                    if code not in (None, "")
                    else None
                ),
                category=(
                    current_category
                    or (
                        str(category_or_name).strip()
                        if category_or_name and description
                        else None
                    )
                ),
                item_name=item_name,
                description=full_description,
                billing_type=(
                    str(billing_type).strip()
                    if billing_type not in (None, "")
                    else None
                ),
                quantity=quantity,
                period=period,
                unit_value=unit_value,
                base_value=base_value,
                fees_value=fees_value,
                charges_value=charges_value,
                client_total=client_total,
                item_status=status,
                estimate_type=estimate_type,
                flags=flags,
                raw_data={"row": list(row)},
            )
        )

    if not items:
        raise ValueError(
            "A tabela foi localizada, mas nenhum "
            "item de custo pôde ser estruturado."
        )

    title_candidates = metadata.pop("_title_candidates", [])
    project_name = (
        title_candidates[0]
        if title_candidates
        else Path(file_name).stem
    )

    warnings = []

    if Path(file_name).suffix.casefold() == ".xlsm":
        warnings.append(
            "O arquivo contém suporte a macros. "
            "A NAVE leu somente valores e células; "
            "nenhuma macro foi executada."
        )

    if unknown_columns:
        warnings.append(
            "Algumas colunas não fazem parte da "
            "estrutura atual e foram preservadas "
            "apenas no arquivo original."
        )

    calculated_total = sum(
        float(item.client_total or 0)
        for item in items
    )
    stated_total = totals.get("client_total")

    if (
        stated_total
        and abs(calculated_total - stated_total)
        > max(1.0, stated_total * 0.01)
    ):
        warnings.append(
            "O total das linhas estruturadas não "
            "reconciliou exatamente com o total "
            "informado na planilha."
        )

    return CostWorkbookResult(
        file_name=file_name,
        title=Path(file_name).stem,
        sheet_name=selected_sheet_name,
        header_row=header_row,
        project_name=project_name,
        event_date=metadata.get("data do evento"),
        presentation_date=metadata.get("data de apresentacao"),
        macros_present=(
            Path(file_name).suffix.casefold() == ".xlsm"
        ),
        total_base=totals.get("total_base"),
        fees_total=totals.get("fees_total"),
        charges_total=totals.get("charges_total"),
        client_total=(
            stated_total
            if stated_total is not None
            else calculated_total
        ),
        items=items,
        warnings=warnings,
        unknown_columns=unknown_columns,
        metadata=metadata,
    )
