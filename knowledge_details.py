from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st


ENTITY_TYPE_LABELS = {
    "product": "Brinde",
    "activation": "Solução / ativação",
    "venue": "Local / espaço",
}


PRODUCT_SECTIONS = [
    (
        "Identificação",
        [
            ("name", "Nome"),
            ("sku", "Código / SKU"),
            ("category", "Categoria"),
            ("description", "Descrição"),
            ("development_status", "Status de desenvolvimento"),
            ("origin", "Origem"),
        ],
    ),
    (
        "Fornecedor e catálogo",
        [
            ("supplier_name", "Fornecedor"),
            ("catalog_name", "Catálogo"),
            ("document_year", "Ano do documento"),
            ("source_file", "Arquivo de origem"),
            ("source_page", "Página de origem"),
            ("source_image_url", "Imagem de origem"),
        ],
    ),
    (
        "Valores e condições",
        [
            ("unit_price", "Valor unitário"),
            ("price_min", "Valor mínimo"),
            ("price_max", "Valor máximo"),
            ("currency", "Moeda"),
            ("price_status", "Status do valor"),
            ("price_reference_qty", "Quantidade de referência"),
            ("price_notes", "Observações de valor"),
            ("min_order_qty", "Pedido mínimo"),
        ],
    ),
    (
        "Características técnicas",
        [
            ("capacity", "Capacidade"),
            ("capacity_ml", "Capacidade em ml"),
            ("dimensions_raw", "Dimensões"),
            ("material", "Material"),
            ("finish", "Acabamento"),
            ("decoration", "Personalização / decoração"),
        ],
    ),
    (
        "Personalização e uso",
        [
            ("customizable", "Personalizável"),
            ("licensing_notes", "Licenciamento"),
            ("tags", "Tags"),
        ],
    ),
    (
        "Qualidade da informação",
        [
            ("confidence", "Confiança da leitura"),
            ("missing_fields", "Informações ainda ausentes"),
            ("evidence", "Evidências encontradas"),
        ],
    ),
]

ACTIVATION_SECTIONS = [
    (
        "Identificação",
        [
            ("name", "Nome"),
            ("category", "Categoria"),
            ("record_type", "Tipo de registro"),
            ("description", "Descrição"),
            ("proposal_name", "Proposta"),
            ("document_year", "Ano do documento"),
        ],
    ),
    (
        "Projeto e contexto",
        [
            ("supplier_name", "Fornecedor"),
            ("client_brand", "Marca / cliente"),
            ("project_name", "Projeto"),
            ("event_name", "Evento"),
            ("location", "Localização"),
            ("event_period", "Período do evento"),
        ],
    ),
    (
        "Valores e condições",
        [
            ("base_price", "Valor base"),
            ("currency", "Moeda"),
            ("price_status", "Status do valor"),
            ("pricing_period", "Período de cobrança"),
            ("price_notes", "Observações de valor"),
            ("discount_percent", "Desconto"),
            ("negotiated_benefit", "Benefício negociado"),
            ("validity", "Validade"),
            ("payment_terms", "Condições de pagamento"),
        ],
    ),
    (
        "Execução",
        [
            ("lead_time_days", "Prazo de produção"),
            ("setup_window", "Janela de montagem"),
            ("internet_requirement", "Necessidade de internet"),
            ("staff_included", "Equipe incluída"),
            ("staff_description", "Descrição da equipe"),
            ("customizable", "Personalizável"),
        ],
    ),
    (
        "Escopo e infraestrutura",
        [
            ("included_items", "Itens incluídos"),
            ("excluded_items", "Itens não incluídos"),
            (
                "infrastructure_requirements",
                "Necessidades de infraestrutura",
            ),
        ],
    ),
    (
        "Classificação e origem",
        [
            ("tags", "Tags"),
            ("confidence", "Confiança da leitura"),
            ("missing_fields", "Informações ainda ausentes"),
            ("source_file", "Arquivo de origem"),
            ("source_page", "Página de origem"),
            ("source_image_url", "Imagem de origem"),
            ("evidence", "Evidências encontradas"),
        ],
    ),
]

VENUE_SECTIONS = [
    (
        "Identificação",
        [
            ("name", "Nome"),
            ("venue_type", "Tipo de espaço"),
            ("description", "Descrição"),
            ("document_name", "Documento de origem"),
            ("document_year", "Ano do documento"),
            ("supplier_name", "Operador / responsável"),
        ],
    ),
    (
        "Localização e acesso",
        [
            ("address", "Endereço"),
            ("neighborhood", "Bairro"),
            ("city", "Cidade"),
            ("state", "Estado"),
            ("country", "País"),
            ("postal_code", "CEP"),
            ("map_url", "Mapa"),
            ("website_url", "Site"),
            ("loading_access", "Acesso de carga"),
            ("parking", "Estacionamento"),
            ("accessibility", "Acessibilidade"),
        ],
    ),
    (
        "Áreas e dimensões",
        [
            ("total_area_sqm", "Área total"),
            ("indoor_area_sqm", "Área interna"),
            ("outdoor_area_sqm", "Área externa"),
            ("ceiling_height_m", "Pé-direito"),
            ("rooms_or_areas", "Ambientes / áreas"),
        ],
    ),
    (
        "Capacidades",
        [
            ("standing_capacity", "Capacidade em pé"),
            ("seated_capacity", "Capacidade sentada"),
            ("auditorium_capacity", "Capacidade auditório"),
        ],
    ),
    (
        "Infraestrutura",
        [
            ("kitchen_or_catering", "Cozinha / catering"),
            ("power_supply", "Energia"),
            ("internet", "Internet"),
            ("air_conditioning", "Climatização"),
            ("bathrooms", "Banheiros"),
            ("furniture", "Mobiliário"),
            ("audiovisual", "Audiovisual"),
            ("infrastructure", "Infraestrutura disponível"),
            ("included_items", "Itens incluídos"),
            ("excluded_items", "Itens não incluídos"),
        ],
    ),
    (
        "Operação e restrições",
        [
            ("restrictions", "Restrições"),
            ("operating_hours", "Horários de operação"),
            ("event_availability", "Disponibilidade para eventos"),
        ],
    ),
    (
        "Valores e condições",
        [
            ("base_price", "Valor base"),
            ("price_min", "Valor mínimo"),
            ("price_max", "Valor máximo"),
            ("currency", "Moeda"),
            ("price_status", "Status do valor"),
            ("pricing_period", "Período de cobrança"),
            ("price_notes", "Observações de valor"),
        ],
    ),
    (
        "Classificação e origem",
        [
            ("tags", "Tags"),
            ("confidence", "Confiança da leitura"),
            ("missing_fields", "Informações ainda ausentes"),
            ("source_file", "Arquivo de origem"),
            ("source_page", "Página de origem"),
            ("source_image_url", "Imagem de origem"),
            ("evidence", "Evidências encontradas"),
        ],
    ),
]

DETAIL_SCHEMAS = {
    "product": PRODUCT_SECTIONS,
    "activation": ACTIVATION_SECTIONS,
    "venue": VENUE_SECTIONS,
}

INTERNAL_FIELDS = {
    "id",
    "supplier_id",
    "operator_id",
    "project_id",
    "import_id",
    "source_file_id",
    "normalized_name",
    "created_at",
    "updated_at",
    "raw_data",
}

WIDE_FIELDS = {
    "description",
    "price_notes",
    "licensing_notes",
    "staff_description",
    "included_items",
    "excluded_items",
    "infrastructure_requirements",
    "infrastructure",
    "restrictions",
    "rooms_or_areas",
    "missing_fields",
    "evidence",
}

MONEY_FIELDS = {
    "unit_price",
    "price_min",
    "price_max",
    "base_price",
}

INTEGER_FIELDS = {
    "document_year",
    "price_reference_qty",
    "min_order_qty",
    "capacity",
    "capacity_ml",
    "lead_time_days",
    "standing_capacity",
    "seated_capacity",
    "auditorium_capacity",
}

DECIMAL_SUFFIXES = {
    "total_area_sqm": " m²",
    "indoor_area_sqm": " m²",
    "outdoor_area_sqm": " m²",
    "ceiling_height_m": " m",
    "discount_percent": "%",
}

BOOLEAN_FIELDS = {
    "customizable",
    "staff_included",
}

URL_FIELDS = {
    "source_image_url",
    "map_url",
    "website_url",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0

    return False


def _currency_prefix(record: dict) -> str:
    return {
        "BRL": "R$ ",
        "USD": "US$ ",
        "EUR": "€ ",
    }.get(str(record.get("currency") or ""), "")


def _format_number(value: Any, decimals: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")

    formatted = f"{number:,.{decimals}f}"
    return (
        formatted
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _format_value(
    field: str,
    value: Any,
    record: dict,
) -> tuple[str, bool, bool]:
    if _is_missing(value):
        return "Não informado", True, False

    if field in BOOLEAN_FIELDS or isinstance(value, bool):
        return ("Sim" if bool(value) else "Não"), False, False

    if field in MONEY_FIELDS:
        return (
            f"{_currency_prefix(record)}"
            f"{_format_number(value)}",
            False,
            False,
        )

    if field in INTEGER_FIELDS:
        try:
            return _format_number(int(float(value)), 0), False, False
        except (TypeError, ValueError):
            pass

    if field in DECIMAL_SUFFIXES:
        return (
            f"{_format_number(value)}"
            f"{DECIMAL_SUFFIXES[field]}",
            False,
            False,
        )

    if field == "confidence":
        try:
            number = float(value)
            if number <= 1:
                number *= 100
            return f"{_format_number(number, 0)}%", False, False
        except (TypeError, ValueError):
            pass

    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if _is_missing(item):
                continue
            label = str(key).replace("_", " ").strip().capitalize()
            item_text, _, _ = _format_value(
                str(key),
                item,
                record,
            )
            lines.append(f"{label}: {item_text}")
        return (
            "\n".join(lines) or "Não informado",
            not bool(lines),
            False,
        )

    if isinstance(value, (list, tuple, set)):
        lines = []
        for item in value:
            if _is_missing(item):
                continue
            if isinstance(item, dict):
                text, _, _ = _format_value(
                    field,
                    item,
                    record,
                )
                lines.append(text)
            else:
                lines.append(str(item).strip())
        return (
            "\n".join(f"• {line}" for line in lines)
            or "Não informado",
            not bool(lines),
            False,
        )

    text = str(value).strip()
    return text, False, field in URL_FIELDS and text.startswith(
        ("http://", "https://")
    )


def _field_card(
    label: str,
    value: str,
    *,
    missing: bool,
    is_url: bool,
) -> str:
    value_class = (
        "nave-field-value nave-field-empty"
        if missing
        else "nave-field-value"
    )

    if is_url:
        value_html = (
            f'<a href="{escape(value)}" target="_blank" '
            'rel="noopener noreferrer">Abrir link</a>'
        )
    else:
        value_html = escape(value).replace("\n", "<br>")

    return f"""
    <div class="nave-field-card">
        <div class="nave-field-label">{escape(label)}</div>
        <div class="{value_class}">{value_html}</div>
    </div>
    """


def _render_fields(
    fields: list[tuple[str, str]],
    record: dict,
) -> None:
    compact = [
        item
        for item in fields
        if item[0] not in WIDE_FIELDS
    ]
    wide = [
        item
        for item in fields
        if item[0] in WIDE_FIELDS
    ]

    for start in range(0, len(compact), 3):
        row = compact[start:start + 3]
        columns = st.columns(3)

        for column, (field, label) in zip(columns, row):
            value, missing, is_url = _format_value(
                field,
                record.get(field),
                record,
            )
            with column:
                st.markdown(
                    _field_card(
                        label,
                        value,
                        missing=missing,
                        is_url=is_url,
                    ),
                    unsafe_allow_html=True,
                )

    for field, label in wide:
        value, missing, is_url = _format_value(
            field,
            record.get(field),
            record,
        )
        st.markdown(
            _field_card(
                label,
                value,
                missing=missing,
                is_url=is_url,
            ),
            unsafe_allow_html=True,
        )


def _known_fields(
    entity_type: str,
) -> set[str]:
    result = set()

    for _, fields in DETAIL_SCHEMAS.get(
        entity_type,
        [],
    ):
        result.update(field for field, _ in fields)

    return result


def _additional_fields(
    entity_type: str,
    record: dict,
) -> list[tuple[str, str]]:
    known = _known_fields(entity_type)
    raw_data = record.get("raw_data")

    if not isinstance(raw_data, dict):
        return []

    fields = []
    for key in raw_data:
        if key in known or key in INTERNAL_FIELDS:
            continue

        label = str(key).replace("_", " ").strip().capitalize()
        fields.append((str(key), label))

        if key not in record:
            record[key] = raw_data.get(key)

    return fields


def render_complete_record(
    entity_type: str,
    record: dict,
) -> None:
    schema = DETAIL_SCHEMAS.get(entity_type, [])

    if not schema:
        st.info(
            "A ficha detalhada deste tipo de item "
            "ainda não está configurada."
        )
        return

    st.markdown("### Ficha completa")
    st.caption(
        "Campos sem conteúdo aparecem como “Não informado” "
        "para facilitar o enriquecimento da base."
    )

    for section_title, fields in schema:
        st.markdown(
            f'<div class="nave-detail-section-title">'
            f'{escape(section_title)}</div>',
            unsafe_allow_html=True,
        )
        _render_fields(fields, record)

    additional = _additional_fields(
        entity_type,
        record,
    )

    if additional:
        with st.expander(
            "Informações adicionais do material original",
            expanded=False,
        ):
            _render_fields(additional, record)


EXPORT_EXCLUDED_SECTIONS = {
    "Qualidade da informação",
    "Classificação e origem",
}

EXPORT_EXCLUDED_FIELDS = {
    "source_file",
    "source_page",
    "source_image_url",
    "confidence",
    "missing_fields",
    "evidence",
    "raw_data",
}


def formatted_sections_for_export(
    entity_type: str,
    record: dict,
) -> list[tuple[str, list[tuple[str, str]]]]:
    result = []

    for section_title, fields in DETAIL_SCHEMAS.get(
        entity_type,
        [],
    ):
        if section_title in EXPORT_EXCLUDED_SECTIONS:
            continue

        section_values = []

        for field, label in fields:
            if field in EXPORT_EXCLUDED_FIELDS:
                continue

            value, missing, _ = _format_value(
                field,
                record.get(field),
                record,
            )

            if missing:
                continue

            section_values.append((label, value))

        if section_values:
            result.append(
                (section_title, section_values)
            )

    return result
