from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote_plus
import unicodedata

import pandas as pd
import streamlit as st


ENTITY_TYPE_LABELS = {
    "product": "Brinde",
    "activation": "Solução / ativação",
    "venue": "Local / espaço",
    "supplier": "Fornecedor",
}

PRODUCT_SECTIONS = [
    ("Identificação", [("name", "Nome"), ("sku", "Código / SKU"), ("category", "Categoria"), ("description", "Descrição"), ("development_status", "Status de desenvolvimento"), ("origin", "Origem")]),
    ("Fornecedor e catálogo", [("supplier_name", "Fornecedor"), ("catalog_name", "Catálogo"), ("document_year", "Ano do documento"), ("source_file", "Arquivo de origem"), ("source_page", "Página de origem"), ("source_image_url", "Imagem de origem")]),
    ("Valores e condições", [("unit_price", "Valor unitário"), ("price_min", "Valor mínimo"), ("price_max", "Valor máximo"), ("currency", "Moeda"), ("price_status", "Status do valor"), ("price_reference_qty", "Quantidade de referência"), ("price_notes", "Observações de valor"), ("min_order_qty", "Pedido mínimo")]),
    ("Características técnicas", [("capacity", "Capacidade"), ("capacity_ml", "Capacidade em ml"), ("dimensions_raw", "Dimensões"), ("material", "Material"), ("finish", "Acabamento"), ("decoration", "Personalização / decoração")]),
    ("Personalização e uso", [("customizable", "Personalizável"), ("licensing_notes", "Licenciamento"), ("tags", "Tags")]),
    ("Qualidade da informação", [("confidence", "Confiança da leitura"), ("missing_fields", "Informações ainda ausentes"), ("evidence", "Evidências encontradas")]),
]

ACTIVATION_SECTIONS = [
    ("Identificação", [("name", "Nome"), ("category", "Categoria"), ("record_type", "Tipo de registro"), ("description", "Descrição"), ("proposal_name", "Proposta"), ("document_year", "Ano do documento")]),
    ("Projeto e contexto", [("supplier_name", "Fornecedor"), ("client_brand", "Marca / cliente"), ("project_name", "Projeto"), ("event_name", "Evento"), ("location", "Localização"), ("event_period", "Período do evento")]),
    ("Valores e condições", [("base_price", "Valor base"), ("currency", "Moeda"), ("price_status", "Status do valor"), ("pricing_period", "Período de cobrança"), ("price_notes", "Observações de valor"), ("discount_percent", "Desconto"), ("negotiated_benefit", "Benefício negociado"), ("validity", "Validade"), ("payment_terms", "Condições de pagamento")]),
    ("Execução", [("lead_time_days", "Prazo de produção"), ("setup_window", "Janela de montagem"), ("internet_requirement", "Necessidade de internet"), ("staff_included", "Equipe incluída"), ("staff_description", "Descrição da equipe"), ("customizable", "Personalizável")]),
    ("Escopo e infraestrutura", [("included_items", "Itens incluídos"), ("excluded_items", "Itens não incluídos"), ("infrastructure_requirements", "Necessidades de infraestrutura")]),
    ("Classificação e origem", [("tags", "Tags"), ("confidence", "Confiança da leitura"), ("missing_fields", "Informações ainda ausentes"), ("source_file", "Arquivo de origem"), ("source_page", "Página de origem"), ("source_image_url", "Imagem de origem"), ("evidence", "Evidências encontradas")]),
]

VENUE_SECTIONS = [
    ("Identificação", [("name", "Nome"), ("venue_type", "Tipo de espaço"), ("description", "Descrição"), ("document_name", "Documento de origem"), ("document_year", "Ano do documento"), ("supplier_name", "Operador / responsável")]),
    ("Localização e acesso", [("address", "Endereço"), ("neighborhood", "Bairro"), ("city", "Cidade"), ("state", "Estado"), ("country", "País"), ("postal_code", "CEP"), ("map_url", "Mapa"), ("website_url", "Site"), ("loading_access", "Acesso de carga"), ("parking", "Estacionamento"), ("accessibility", "Acessibilidade")]),
    ("Áreas e dimensões", [("total_area_sqm", "Área total"), ("indoor_area_sqm", "Área interna"), ("outdoor_area_sqm", "Área externa"), ("ceiling_height_m", "Pé-direito"), ("rooms_or_areas", "Ambientes / áreas")]),
    ("Capacidades", [("standing_capacity", "Capacidade em pé"), ("seated_capacity", "Capacidade sentada"), ("auditorium_capacity", "Capacidade auditório")]),
    ("Infraestrutura", [("kitchen_or_catering", "Cozinha / catering"), ("power_supply", "Energia"), ("internet", "Internet"), ("air_conditioning", "Climatização"), ("bathrooms", "Banheiros"), ("furniture", "Mobiliário"), ("audiovisual", "Audiovisual"), ("infrastructure", "Infraestrutura disponível"), ("included_items", "Itens incluídos"), ("excluded_items", "Itens não incluídos")]),
    ("Operação e restrições", [("restrictions", "Restrições"), ("operating_hours", "Horários de operação"), ("event_availability", "Disponibilidade para eventos")]),
    ("Valores e condições", [("base_price", "Valor base"), ("price_min", "Valor mínimo"), ("price_max", "Valor máximo"), ("currency", "Moeda"), ("price_status", "Status do valor"), ("pricing_period", "Período de cobrança"), ("price_notes", "Observações de valor")]),
    ("Classificação e origem", [("tags", "Tags"), ("confidence", "Confiança da leitura"), ("missing_fields", "Informações ainda ausentes"), ("source_file", "Arquivo de origem"), ("source_page", "Página de origem"), ("source_image_url", "Imagem de origem"), ("evidence", "Evidências encontradas")]),
]

SUPPLIER_SECTIONS = [
    ("Identificação e contato", [("name", "Nome"), ("legal_name", "Razão social"), ("cnpj_normalized", "CNPJ"), ("company_type", "Tipo de empresa"), ("founded_year", "Ano de fundação"), ("website_url", "Site"), ("contact_name", "Contato"), ("contact_role", "Função do contato"), ("email", "E-mail"), ("phone", "Telefone"), ("whatsapp", "WhatsApp"), ("instagram_url", "Instagram"), ("linkedin_url", "LinkedIn"), ("address", "Endereço"), ("notes", "Observações")]),
    ("Classificação e repertório", [("supplier_categories", "Categorias"), ("specialties", "Especialidades"), ("services_offered", "Serviços oferecidos"), ("market_segments", "Segmentos atendidos"), ("client_brands", "Clientes / marcas"), ("differentiators", "Diferenciais"), ("certifications", "Certificações"), ("agency_experience", "Experiência com agências")]),
    ("Base e cobertura", [("base_city", "Cidade-base"), ("base_state", "Estado-base"), ("base_country", "País-base"), ("serves_nationally", "Atende nacionalmente"), ("direct_states", "Estados atendidos diretamente"), ("partner_states", "Estados via parceiros"), ("served_states", "Cobertura estadual consolidada"), ("served_cities", "Cidades atendidas"), ("has_local_teams", "Possui equipes locais"), ("local_team_locations", "Onde possui equipes locais"), ("own_installation_team", "Equipe própria de instalação"), ("rollout_capacity", "Capacidade de rollout simultâneo")]),
    ("Capacidade produtiva", [("production_internal_pct", "Produção interna"), ("production_outsourced_pct", "Produção terceirizada"), ("lead_time", "Lead time"), ("production_bottlenecks", "Gargalos produtivos"), ("facility_total_area", "Área total"), ("facility_ceiling_height", "Pé-direito"), ("team_total", "Colaboradores"), ("technical_structure", "Estrutura técnica")]),
    ("Qualidade, ESG e comercial", [("quality_control", "Controle de qualidade"), ("accepts_technical_visit", "Aceita visita técnica"), ("sustainability_practices", "Práticas de sustentabilidade"), ("has_warranty", "Possui garantia"), ("warranty_terms", "Garantia"), ("emits_invoice", "Emite NF"), ("tax_regime", "Regime tributário"), ("payment_method", "Forma de pagamento"), ("payment_terms", "Prazo de pagamento"), ("large_volume_flexibility", "Flexibilidade para grandes volumes"), ("works_with_contract", "Trabalha com contrato")]),
    ("Logística", [("travel_pricing_mode", "Modelo de deslocamento"), ("default_travel_cost_brl", "Custo padrão de deslocamento"), ("freight_pricing_mode", "Modelo de frete"), ("default_freight_cost_brl", "Custo padrão de frete"), ("travel_lead_days", "Antecedência para deslocamento"), ("equipment_transport_required", "Exige transporte de equipamento"), ("accommodation_required", "Exige hospedagem"), ("coverage_notes", "Observações de cobertura")]),
    ("Repertório associado", [("products_count", "Brindes / produtos"), ("activations_count", "Ativações / soluções"), ("venues_count", "Locais / espaços")]),
]

DETAIL_SCHEMAS = {"product": PRODUCT_SECTIONS, "activation": ACTIVATION_SECTIONS, "venue": VENUE_SECTIONS, "supplier": SUPPLIER_SECTIONS}

INTERNAL_FIELDS = {"id", "supplier_id", "operator_id", "project_id", "import_id", "source_file_id", "normalized_name", "created_at", "updated_at", "raw_data", "profile_data", "recognized_as_supplier"}
WIDE_FIELDS = {"description", "price_notes", "licensing_notes", "staff_description", "included_items", "excluded_items", "infrastructure_requirements", "infrastructure", "restrictions", "rooms_or_areas", "missing_fields", "evidence", "notes", "coverage_notes", "differentiators", "services_offered", "specialties", "client_brands", "market_segments", "certifications", "technical_structure", "production_bottlenecks", "sustainability_practices", "warranty_terms"}
MONEY_FIELDS = {"unit_price", "price_min", "price_max", "base_price", "default_travel_cost_brl", "default_freight_cost_brl"}
INTEGER_FIELDS = {"document_year", "price_reference_qty", "min_order_qty", "lead_time_days", "standing_capacity", "seated_capacity", "auditorium_capacity", "travel_lead_days", "products_count", "activations_count", "venues_count", "founded_year", "team_total"}
DECIMAL_SUFFIXES = {"capacity_ml": " ml", "total_area_sqm": " m²", "indoor_area_sqm": " m²", "outdoor_area_sqm": " m²", "ceiling_height_m": " m", "discount_percent": "%", "production_internal_pct": "%", "production_outsourced_pct": "%"}
BOOLEAN_FIELDS = {"customizable", "staff_included", "serves_nationally", "has_local_teams", "equipment_transport_required", "accommodation_required", "own_installation_team", "quality_control", "accepts_technical_visit", "emits_invoice", "has_warranty", "large_volume_flexibility", "works_with_contract"}
URL_FIELDS = {"source_image_url", "map_url", "website_url", "instagram_url", "linkedin_url"}
ADDRESS_FIELDS = {"address"}

MISSING_SENTINELS = {
    "nao informado", "n a", "na", "none", "null", "sem informacao",
    "nao disponivel", "not informed", "not available", "-", "—",
}


def _normalized_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().strip().replace("/", " ").split())


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        clean = value.strip()
        return not clean or _normalized_text(clean) in MISSING_SENTINELS
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0 or all(_is_missing(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_missing(item) for item in value.values())
    return False


def record_value(record: dict, field: str) -> Any:
    if field in record and not _is_missing(record.get(field)):
        return record.get(field)
    raw_data = record.get("raw_data")
    if isinstance(raw_data, dict) and field in raw_data:
        return raw_data.get(field)
    return record.get(field)


def visible_fields(fields: list[tuple[str, str]], record: dict) -> list[tuple[str, str]]:
    return [(field, label) for field, label in fields if not _is_missing(record_value(record, field))]


def visible_sections(entity_type: str, record: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    result = []
    for section_title, fields in DETAIL_SCHEMAS.get(entity_type, []):
        available = visible_fields(fields, record)
        if available:
            result.append((section_title, available))
    return result


def _currency_prefix(record: dict) -> str:
    return {"BRL": "R$ ", "USD": "US$ ", "EUR": "€ "}.get(str(record.get("currency") or ""), "")


def _format_number(value: Any, decimals: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")
    formatted = f"{number:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_value(field: str, value: Any, record: dict) -> tuple[str, bool, bool]:
    if _is_missing(value):
        return "", True, False
    if field in BOOLEAN_FIELDS or isinstance(value, bool):
        return ("Sim" if bool(value) else "Não"), False, False
    if field == "cnpj_normalized":
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if len(digits) == 14:
            return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}", False, False
    if field in MONEY_FIELDS:
        return f"{_currency_prefix(record)}{_format_number(value)}", False, False
    if field in INTEGER_FIELDS:
        try:
            return _format_number(int(float(value)), 0), False, False
        except (TypeError, ValueError):
            pass
    if field in DECIMAL_SUFFIXES:
        return f"{_format_number(value)}{DECIMAL_SUFFIXES[field]}", False, False
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
            item_text, _, _ = _format_value(str(key), item, record)
            if item_text:
                lines.append(f"{label}: {item_text}")
        return "\n".join(lines), not bool(lines), False
    if isinstance(value, (list, tuple, set)):
        lines = []
        for item in value:
            if _is_missing(item):
                continue
            if isinstance(item, dict):
                text, _, _ = _format_value(field, item, record)
                if text:
                    lines.append(text)
            else:
                lines.append(str(item).strip())
        return "\n".join(f"• {line}" for line in lines), not bool(lines), False
    text = str(value).strip()
    return text, False, field in URL_FIELDS and text.startswith(("http://", "https://"))


def _field_card(
    label: str,
    value: str,
    *,
    missing: bool,
    is_url: bool,
    field: str | None = None,
) -> str:
    if missing:
        return ""
    if field in ADDRESS_FIELDS:
        href = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(value)
        value_html = (
            f'<a href="{escape(href, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{escape(value)}</a>'
        )
    elif is_url:
        link_label = {
            "website_url": "Abrir site",
            "map_url": "Abrir mapa",
            "instagram_url": "Abrir Instagram",
            "linkedin_url": "Abrir LinkedIn",
            "source_image_url": "Abrir imagem",
        }.get(field or "", "Abrir link")
        value_html = (
            f'<a href="{escape(value, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{escape(link_label)}</a>'
        )
    else:
        value_html = escape(value).replace("\n", "<br>")
    return (
        f'<div class="nave-field-card">'
        f'<div class="nave-field-label">{escape(label)}</div>'
        f'<div class="nave-field-value">{value_html}</div>'
        f'</div>'
    )

def _render_fields(fields: list[tuple[str, str]], record: dict) -> None:
    fields = visible_fields(fields, record)
    compact = [item for item in fields if item[0] not in WIDE_FIELDS]
    wide = [item for item in fields if item[0] in WIDE_FIELDS]
    for start in range(0, len(compact), 3):
        row = compact[start:start + 3]
        columns = st.columns(3)
        for column, (field, label) in zip(columns, row):
            value, missing, is_url = _format_value(field, record_value(record, field), record)
            if not missing:
                with column:
                    st.markdown(_field_card(label, value, missing=False, is_url=is_url, field=field), unsafe_allow_html=True)
    for field, label in wide:
        value, missing, is_url = _format_value(field, record_value(record, field), record)
        if not missing:
            st.markdown(_field_card(label, value, missing=False, is_url=is_url, field=field), unsafe_allow_html=True)


def _known_fields(entity_type: str) -> set[str]:
    result = set()
    for _, fields in DETAIL_SCHEMAS.get(entity_type, []):
        result.update(field for field, _ in fields)
    return result


def _additional_fields(entity_type: str, record: dict) -> list[tuple[str, str]]:
    known = _known_fields(entity_type)
    raw_data = record.get("raw_data")
    if not isinstance(raw_data, dict):
        return []
    fields = []
    for key, value in raw_data.items():
        if key in known or key in INTERNAL_FIELDS or _is_missing(value):
            continue
        label = str(key).replace("_", " ").strip().capitalize()
        fields.append((str(key), label))
        if key not in record:
            record[key] = value
    return fields


def render_complete_record(
    entity_type: str,
    record: dict,
    *,
    show_related_projects: bool = True,
) -> None:
    sections = visible_sections(entity_type, record)
    if entity_type not in DETAIL_SCHEMAS:
        st.info("A ficha detalhada deste tipo de item ainda não está configurada.")
        return

    st.markdown("### Ficha completa")
    st.caption(
        "A ficha mostra apenas informações disponíveis. Campos vazios continuam "
        "disponíveis na edição e aparecem automaticamente quando forem preenchidos."
    )

    if not sections:
        st.info("Este cadastro ainda não possui informações de ficha para exibir.")
    for section_title, fields in sections:
        st.markdown(
            f'<div class="nave-detail-section-title">{escape(section_title)}</div>',
            unsafe_allow_html=True,
        )
        _render_fields(fields, record)

    # Dados brutos de ingestão são rastreabilidade para a inteligência da NAVE,
    # não conteúdo de apresentação. Em fornecedores, uma planilha pode carregar
    # dezenas de colunas, URLs técnicas e payloads ainda não normalizados. Tudo
    # permanece preservado em raw_data, mas a ficha exibe apenas campos canônicos.
    additional = [] if entity_type == "supplier" else _additional_fields(entity_type, record)
    if additional:
        with st.expander("Informações adicionais do material original", expanded=False):
            _render_fields(additional, record)

    entity_id = record.get("id")
    if show_related_projects and entity_id:
        try:
            from knowledge_project_links import render_related_projects_panel
            render_related_projects_panel(entity_type, str(entity_id), allow_edit=False)
        except Exception:
            pass


# Aliases públicos de compatibilidade com módulos anteriores da NAVE.
# Mantêm a ficha evolutiva sem obrigar exportadores/PDFs legados a importar
# helpers privados pelo nome antigo.
is_missing = _is_missing
format_value = _format_value
field_card = _field_card
render_fields = _render_fields
known_fields = _known_fields
additional_fields = _additional_fields
get_visible_fields = visible_fields
get_visible_sections = visible_sections
