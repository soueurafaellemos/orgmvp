from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from runtime_ui import (
    report_service_error,
    require_admin_access,
)
from taxonomy import taxonomy_options
from supabase_db import (
    delete_knowledge_entity,
    fetch_curation_history,
    fetch_curation_state,
    knowledge_entity_dependency_counts,
    update_curated_entity,
)


VALIDATION_LABELS = {
    "not_reviewed": "Não revisado",
    "in_review": "Em revisão",
    "validated": "Validado",
    "needs_update": "Precisa de atualização",
    "archived": "Arquivado",
}

VALIDATION_VALUES = list(VALIDATION_LABELS.keys())

REVIEW_SOURCES = [
    "Não informado",
    "Revisão manual",
    "Documento",
    "Fornecedor",
    "Site oficial",
    "Visita técnica",
    "Histórico de projeto",
    "Outro",
]


EDIT_SCHEMAS = {
    "product": [
        (
            "Identificação",
            [
                {"field": "name", "label": "Nome", "type": "text"},
                {"field": "sku", "label": "Código / SKU", "type": "text"},
                {"field": "category", "label": "Categoria NAVE", "type": "taxonomy"},
                {
                    "field": "supplier_id",
                    "label": "Fornecedor",
                    "type": "supplier",
                },
                {
                    "field": "description",
                    "label": "Descrição",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Valores e condições",
            [
                {
                    "field": "unit_price",
                    "label": "Valor unitário",
                    "type": "decimal",
                },
                {
                    "field": "price_min",
                    "label": "Valor mínimo",
                    "type": "decimal",
                },
                {
                    "field": "price_max",
                    "label": "Valor máximo",
                    "type": "decimal",
                },
                {
                    "field": "currency",
                    "label": "Moeda",
                    "type": "select",
                    "options": ["", "BRL", "USD", "EUR"],
                },
                {
                    "field": "price_status",
                    "label": "Status do valor",
                    "type": "text",
                },
                {
                    "field": "price_reference_qty",
                    "label": "Quantidade de referência",
                    "type": "integer",
                },
                {
                    "field": "min_order_qty",
                    "label": "Pedido mínimo",
                    "type": "integer",
                },
                {
                    "field": "price_notes",
                    "label": "Observações de valor",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Características",
            [
                {
                    "field": "capacity",
                    "label": "Capacidade",
                    "type": "integer",
                },
                {
                    "field": "capacity_ml",
                    "label": "Capacidade em ml",
                    "type": "integer",
                },
                {
                    "field": "dimensions_raw",
                    "label": "Dimensões",
                    "type": "text",
                },
                {"field": "material", "label": "Material", "type": "text"},
                {
                    "field": "finish",
                    "label": "Acabamento",
                    "type": "text",
                },
                {
                    "field": "decoration",
                    "label": "Personalização / decoração",
                    "type": "textarea",
                },
                {
                    "field": "customizable",
                    "label": "Personalizável",
                    "type": "boolean",
                },
                {
                    "field": "licensing_notes",
                    "label": "Licenciamento",
                    "type": "textarea",
                },
                {
                    "field": "tags",
                    "label": "Tags",
                    "type": "list",
                },
            ],
        ),
    ],
    "activation": [
        (
            "Identificação",
            [
                {"field": "name", "label": "Nome", "type": "text"},
                {"field": "category", "label": "Categoria NAVE", "type": "taxonomy"},
                {
                    "field": "record_type",
                    "label": "Tipo de registro",
                    "type": "text",
                },
                {
                    "field": "supplier_id",
                    "label": "Fornecedor",
                    "type": "supplier",
                },
                {
                    "field": "description",
                    "label": "Descrição",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Projeto e contexto",
            [
                {
                    "field": "client_brand",
                    "label": "Marca / cliente",
                    "type": "text",
                },
                {
                    "field": "project_name",
                    "label": "Projeto",
                    "type": "text",
                },
                {
                    "field": "event_name",
                    "label": "Evento",
                    "type": "text",
                },
                {
                    "field": "location",
                    "label": "Localização",
                    "type": "text",
                },
                {
                    "field": "event_period",
                    "label": "Período",
                    "type": "text",
                },
            ],
        ),
        (
            "Valores e execução",
            [
                {
                    "field": "base_price",
                    "label": "Valor base",
                    "type": "decimal",
                },
                {
                    "field": "currency",
                    "label": "Moeda",
                    "type": "select",
                    "options": ["", "BRL", "USD", "EUR"],
                },
                {
                    "field": "price_status",
                    "label": "Status do valor",
                    "type": "text",
                },
                {
                    "field": "pricing_period",
                    "label": "Período de cobrança",
                    "type": "text",
                },
                {
                    "field": "lead_time_days",
                    "label": "Prazo de produção em dias",
                    "type": "integer",
                },
                {
                    "field": "setup_window",
                    "label": "Janela de montagem",
                    "type": "text",
                },
                {
                    "field": "payment_terms",
                    "label": "Condições de pagamento",
                    "type": "textarea",
                },
                {
                    "field": "validity",
                    "label": "Validade",
                    "type": "text",
                },
                {
                    "field": "price_notes",
                    "label": "Observações de valor",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Escopo",
            [
                {
                    "field": "included_items",
                    "label": "Itens incluídos",
                    "type": "list",
                },
                {
                    "field": "excluded_items",
                    "label": "Itens não incluídos",
                    "type": "list",
                },
                {
                    "field": "infrastructure_requirements",
                    "label": "Necessidades de infraestrutura",
                    "type": "list",
                },
                {
                    "field": "internet_requirement",
                    "label": "Necessidade de internet",
                    "type": "text",
                },
                {
                    "field": "staff_included",
                    "label": "Equipe incluída",
                    "type": "boolean",
                },
                {
                    "field": "staff_description",
                    "label": "Descrição da equipe",
                    "type": "textarea",
                },
                {
                    "field": "customizable",
                    "label": "Personalizável",
                    "type": "boolean",
                },
                {
                    "field": "tags",
                    "label": "Tags",
                    "type": "list",
                },
            ],
        ),
    ],
    "venue": [
        (
            "Identificação",
            [
                {"field": "name", "label": "Nome", "type": "text"},
                {
                    "field": "venue_type",
                    "label": "Tipo de espaço NAVE",
                    "type": "taxonomy",
                },
                {
                    "field": "operator_id",
                    "label": "Operador / responsável",
                    "type": "supplier",
                },
                {
                    "field": "venue_scope",
                    "label": "Nível do cadastro",
                    "type": "select",
                    "options": ["venue", "subspace"],
                },
                {
                    "field": "subspace_name",
                    "label": "Nome do ambiente / subespaço",
                    "type": "text",
                },
                {
                    "field": "description",
                    "label": "Descrição",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Localização e acesso",
            [
                {"field": "address", "label": "Endereço", "type": "text"},
                {
                    "field": "neighborhood",
                    "label": "Bairro",
                    "type": "text",
                },
                {"field": "city", "label": "Cidade", "type": "text"},
                {"field": "state", "label": "Estado", "type": "text"},
                {"field": "country", "label": "País", "type": "text"},
                {"field": "postal_code", "label": "CEP", "type": "text"},
                {"field": "map_url", "label": "Mapa", "type": "text"},
                {
                    "field": "website_url",
                    "label": "Site",
                    "type": "text",
                },
                {
                    "field": "loading_access",
                    "label": "Acesso de carga",
                    "type": "textarea",
                },
                {
                    "field": "parking",
                    "label": "Estacionamento",
                    "type": "textarea",
                },
                {
                    "field": "accessibility",
                    "label": "Acessibilidade",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Áreas e capacidades",
            [
                {
                    "field": "total_area_sqm",
                    "label": "Área total em m²",
                    "type": "decimal",
                },
                {
                    "field": "indoor_area_sqm",
                    "label": "Área interna em m²",
                    "type": "decimal",
                },
                {
                    "field": "outdoor_area_sqm",
                    "label": "Área externa em m²",
                    "type": "decimal",
                },
                {
                    "field": "ceiling_height_m",
                    "label": "Pé-direito em metros",
                    "type": "decimal",
                },
                {
                    "field": "standing_capacity",
                    "label": "Capacidade em pé",
                    "type": "integer",
                },
                {
                    "field": "seated_capacity",
                    "label": "Capacidade sentada",
                    "type": "integer",
                },
                {
                    "field": "auditorium_capacity",
                    "label": "Capacidade auditório",
                    "type": "integer",
                },
                {
                    "field": "rooms_or_areas",
                    "label": "Ambientes / áreas",
                    "type": "list",
                },
            ],
        ),
        (
            "Infraestrutura e operação",
            [
                {
                    "field": "kitchen_or_catering",
                    "label": "Cozinha / catering",
                    "type": "textarea",
                },
                {
                    "field": "power_supply",
                    "label": "Energia",
                    "type": "textarea",
                },
                {
                    "field": "internet",
                    "label": "Internet",
                    "type": "textarea",
                },
                {
                    "field": "air_conditioning",
                    "label": "Climatização",
                    "type": "textarea",
                },
                {
                    "field": "bathrooms",
                    "label": "Banheiros",
                    "type": "textarea",
                },
                {
                    "field": "furniture",
                    "label": "Mobiliário",
                    "type": "textarea",
                },
                {
                    "field": "audiovisual",
                    "label": "Audiovisual",
                    "type": "textarea",
                },
                {
                    "field": "infrastructure",
                    "label": "Infraestrutura disponível",
                    "type": "list",
                },
                {
                    "field": "restrictions",
                    "label": "Restrições",
                    "type": "list",
                },
                {
                    "field": "operating_hours",
                    "label": "Horários de operação",
                    "type": "textarea",
                },
                {
                    "field": "event_availability",
                    "label": "Disponibilidade para eventos",
                    "type": "textarea",
                },
            ],
        ),
        (
            "Valores",
            [
                {
                    "field": "base_price",
                    "label": "Valor base",
                    "type": "decimal",
                },
                {
                    "field": "price_min",
                    "label": "Valor mínimo",
                    "type": "decimal",
                },
                {
                    "field": "price_max",
                    "label": "Valor máximo",
                    "type": "decimal",
                },
                {
                    "field": "currency",
                    "label": "Moeda",
                    "type": "select",
                    "options": ["", "BRL", "USD", "EUR"],
                },
                {
                    "field": "price_status",
                    "label": "Status do valor",
                    "type": "text",
                },
                {
                    "field": "pricing_period",
                    "label": "Período de cobrança",
                    "type": "text",
                },
                {
                    "field": "price_notes",
                    "label": "Observações de valor",
                    "type": "textarea",
                },
                {
                    "field": "tags",
                    "label": "Tags",
                    "type": "list",
                },
            ],
        ),
    ],
    "supplier": [
        (
            "Identificação e contato",
            [
                {"field": "name", "label": "Nome", "type": "text"},
                {
                    "field": "contact_name",
                    "label": "Contato",
                    "type": "text",
                },
                {
                    "field": "contact_role",
                    "label": "Cargo",
                    "type": "text",
                },
                {"field": "email", "label": "E-mail", "type": "text"},
                {"field": "phone", "label": "Telefone", "type": "text"},
                {
                    "field": "whatsapp",
                    "label": "WhatsApp",
                    "type": "text",
                },
                {
                    "field": "website_url",
                    "label": "Site",
                    "type": "text",
                },
                {
                    "field": "instagram_url",
                    "label": "Instagram",
                    "type": "text",
                },
                {
                    "field": "linkedin_url",
                    "label": "LinkedIn",
                    "type": "text",
                },
                {
                    "field": "address",
                    "label": "Endereço",
                    "type": "textarea",
                },
                {
                    "field": "notes",
                    "label": "Observações gerais",
                    "type": "textarea",
                },
            ],
        ),
    ],
}


FIELD_LABELS = {
    field["field"]: field["label"]
    for sections in EDIT_SCHEMAS.values()
    for _, fields in sections
    for field in fields
}

FIELD_LABELS.update(
    {
        "review_source": "Fonte da informação",
        "internal_notes": "Observações internas",
        "is_archived": "Situação do cadastro",
    }
)


def _text_value(value: Any) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    if isinstance(value, (list, tuple, set)):
        return " | ".join(
            str(item).strip()
            for item in value
            if str(item).strip()
        )

    return str(value)


def _boolean_label(value: Any) -> str:
    if value is True:
        return "Sim"
    if value is False:
        return "Não"
    return "Não informado"


def _parse_decimal(value: str) -> float | None:
    text = value.strip()

    if not text:
        return None

    text = text.replace("R$", "").replace(" ", "")

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    return float(text)


def _parse_integer(value: str) -> int | None:
    text = value.strip()

    if not text:
        return None

    return int(float(text.replace(",", ".")))


def _parse_list(value: str) -> list[str]:
    normalized = value.replace("\n", "|")

    return [
        item.strip()
        for item in normalized.split("|")
        if item.strip()
    ]


def _parse_date(value: str) -> str | None:
    text = value.strip()

    if not text:
        return None

    parsed = pd.to_datetime(
        text,
        dayfirst=True,
        errors="raise",
    )
    return parsed.date().isoformat()


def _render_widget(
    field: dict,
    *,
    record: dict,
    entity_type: str,
    entity_id: str,
    supplier_options: dict[str, str],
) -> Any:
    name = field["field"]
    label = field["label"]
    field_type = field["type"]
    value = record.get(name)
    key = f"curation_{entity_type}_{entity_id}_{name}"

    if field_type == "textarea":
        return st.text_area(
            label,
            value=_text_value(value),
            height=105,
            key=key,
        )

    if field_type in {"decimal", "integer"}:
        return st.text_input(
            label,
            value=_text_value(value),
            placeholder=(
                "Deixe em branco quando não informado"
            ),
            key=key,
        )

    if field_type == "boolean":
        options = [
            "Não informado",
            "Sim",
            "Não",
        ]
        current = _boolean_label(value)
        return st.selectbox(
            label,
            options,
            index=options.index(current),
            key=key,
        )

    if field_type == "select":
        options = list(field.get("options") or [""])
        current = _text_value(value)

        if current not in options:
            options.append(current)

        return st.selectbox(
            label,
            options,
            index=options.index(current),
            format_func=lambda item: (
                item or "Não informado"
            ),
            key=key,
        )

    if field_type == "taxonomy":
        options = [
            "",
            *taxonomy_options(entity_type),
        ]
        current = _text_value(value)

        if current and current not in options:
            options.append(current)

        return st.selectbox(
            label,
            options,
            index=(
                options.index(current)
                if current in options
                else 0
            ),
            format_func=lambda item: (
                item or "Não informado"
            ),
            key=key,
        )

    if field_type == "supplier":
        options = ["", *supplier_options.keys()]
        current = _text_value(value)

        if current and current not in options:
            options.append(current)

        return st.selectbox(
            label,
            options,
            index=(
                options.index(current)
                if current in options
                else 0
            ),
            format_func=lambda item: (
                supplier_options.get(
                    item,
                    "Não informado"
                    if not item
                    else "Fornecedor não localizado",
                )
            ),
            key=key,
        )

    if field_type == "list":
        return st.text_area(
            label,
            value=_text_value(value),
            height=90,
            help="Separe os itens com | ou use uma linha por item.",
            key=key,
        )

    return st.text_input(
        label,
        value=_text_value(value),
        key=key,
    )


def _normalize_value(
    field: dict,
    value: Any,
) -> Any:
    field_type = field["type"]

    if field_type == "decimal":
        return _parse_decimal(str(value))

    if field_type == "integer":
        return _parse_integer(str(value))

    if field_type == "boolean":
        return {
            "Sim": True,
            "Não": False,
            "Não informado": None,
        }[str(value)]

    if field_type == "list":
        return _parse_list(str(value))

    text = str(value).strip()
    return text or None


def render_curation_status(
    state: dict | None,
) -> None:
    state = state or {}

    if state.get("is_archived"):
        st.warning(
            "Este cadastro está arquivado e não participa "
            "das recomendações."
        )

    if state.get("internal_notes"):
        st.info(
            "Observações internas: "
            + str(state.get("internal_notes"))
        )


def render_curation_editor(
    client,
    *,
    entity_type: str,
    entity_id: str,
    record: dict,
    supplier_options: dict[str, str] | None = None,
    title: str = "Editar cadastro",
    expanded: bool = False,
) -> None:
    supplier_options = supplier_options or {}

    try:
        state = fetch_curation_state(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except Exception:
        state = {}

    render_curation_status(state)

    with st.expander(
        title,
        expanded=expanded,
    ):
        st.caption(
            "Toda alteração fica registrada no histórico "
            "de curadoria da NAVE."
        )

        schema = EDIT_SCHEMAS[entity_type]
        raw_values = {}

        with st.form(
            f"curation_form_{entity_type}_{entity_id}"
        ):
            for section_title, fields in schema:
                st.markdown(f"#### {section_title}")

                for start in range(0, len(fields), 2):
                    row_fields = fields[start:start + 2]
                    columns = st.columns(2)

                    for column, field in zip(
                        columns,
                        row_fields,
                    ):
                        with column:
                            raw_values[
                                field["field"]
                            ] = _render_widget(
                                field,
                                record=record,
                                entity_type=entity_type,
                                entity_id=entity_id,
                                supplier_options=supplier_options,
                            )

            st.markdown("#### Informações internas")

            meta1, meta2 = st.columns(2)

            with meta1:
                current_source = str(
                    state.get("review_source")
                    or "Não informado"
                )
                source_options = list(REVIEW_SOURCES)

                if current_source not in source_options:
                    source_options.append(current_source)

                review_source = st.selectbox(
                    "Fonte da informação",
                    source_options,
                    index=source_options.index(
                        current_source
                    ),
                    key=(
                        f"review_source_"
                        f"{entity_type}_{entity_id}"
                    ),
                )

                is_archived = st.checkbox(
                    "Arquivar este cadastro",
                    value=bool(
                        state.get("is_archived")
                        or False
                    ),
                    help=(
                        "O cadastro continua na base e no histórico, "
                        "mas deixa de participar das recomendações."
                    ),
                    key=(
                        f"is_archived_"
                        f"{entity_type}_{entity_id}"
                    ),
                )

            with meta2:
                internal_notes = st.text_area(
                    "Observações internas",
                    value=str(
                        state.get("internal_notes")
                        or ""
                    ),
                    height=130,
                    key=(
                        f"internal_notes_"
                        f"{entity_type}_{entity_id}"
                    ),
                )

            edit_notes = st.text_area(
                "Motivo ou observação sobre esta edição",
                placeholder=(
                    "Ex.: preço atualizado pelo fornecedor; "
                    "capacidade confirmada em visita técnica."
                ),
                height=80,
                key=(
                    f"edit_notes_"
                    f"{entity_type}_{entity_id}"
                ),
            )

            submitted = st.form_submit_button(
                "Salvar alterações",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            try:
                updates = {}

                for _, fields in schema:
                    for field in fields:
                        updates[field["field"]] = (
                            _normalize_value(
                                field,
                                raw_values.get(
                                    field["field"]
                                ),
                            )
                        )

                with st.spinner(
                    "Salvando alterações e histórico..."
                ):
                    result = update_curated_entity(
                        client,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        updates=updates,
                        editor_name="Usuário da NAVE",
                        edit_notes=edit_notes.strip()
                        or None,
                        field_labels=FIELD_LABELS,
                        curation_payload={
                            "validation_status": (
                                "archived"
                                if is_archived
                                else "not_reviewed"
                            ),
                            "reviewed_by": None,
                            "review_source": (
                                None
                                if review_source
                                == "Não informado"
                                else review_source
                            ),
                            "next_review_date": None,
                            "internal_notes": (
                                internal_notes.strip()
                                or None
                            ),
                            "is_archived": is_archived,
                        },
                    )

                changed = int(
                    result.get("fields_changed")
                    or 0
                )
                st.success(
                    f"Cadastro atualizado. "
                    f"{changed} campo(s) alterado(s)."
                )
                st.cache_data.clear()
                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except Exception as exc:
                report_service_error(
                    "edição manual do cadastro",
                    user_message=(
                        "Não foi possível salvar as alterações."
                    ),
                    exception=exc,
                )

    render_curation_history(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    render_delete_control(
        client,
        entity_type=entity_type,
        entity_id=entity_id,
        item_name=str(record.get("name") or "Cadastro"),
    )


def render_curation_history(
    client,
    *,
    entity_type: str,
    entity_id: str,
) -> None:
    try:
        history = fetch_curation_history(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except Exception:
        history = pd.DataFrame()

    if history.empty:
        return

    with st.expander(
        "Histórico de alterações manuais",
        expanded=False,
    ):
        display = history.copy()

        display["Data"] = display[
            "created_at"
        ].astype(str).str.slice(0, 19)
        display["Campo"] = display[
            "field_label"
        ].fillna(display["field_name"])
        display["Valor anterior"] = display[
            "old_value"
        ].apply(_text_value)
        display["Novo valor"] = display[
            "new_value"
        ].apply(_text_value)
        display["Observação"] = display[
            "edit_notes"
        ].fillna("")

        st.dataframe(
            display[
                [
                    "Data",
                    "Campo",
                    "Valor anterior",
                    "Novo valor",
                    "Observação",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            height=330,
            column_config={
                "Valor anterior": st.column_config.TextColumn(
                    "Valor anterior",
                    width="large",
                ),
                "Novo valor": st.column_config.TextColumn(
                    "Novo valor",
                    width="large",
                ),
            },
        )


def render_delete_control(
    client,
    *,
    entity_type: str,
    entity_id: str,
    item_name: str,
) -> None:
    with st.expander(
        "Excluir cadastro definitivamente",
        expanded=False,
    ):
        st.error(
            "A exclusão definitiva não pode ser desfeita. "
            "Use o arquivamento sempre que houver dúvida."
        )

        if not require_admin_access():
            return

        try:
            dependencies = knowledge_entity_dependency_counts(
                client,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        except Exception:
            dependencies = {}

        total_dependencies = sum(
            int(value or 0)
            for value in dependencies.values()
        )

        if total_dependencies:
            st.warning(
                "Este cadastro possui vínculos e não pode ser "
                "excluído com segurança. Arquive-o."
            )
            st.json(dependencies)
            return

        confirmation_text = st.text_input(
            f'Digite EXCLUIR para remover "{item_name}"',
            key=(
                f"delete_entity_text_"
                f"{entity_type}_{entity_id}"
            ),
        )

        delete_clicked = st.button(
            "Excluir cadastro",
            disabled=(
                confirmation_text.strip().upper()
                != "EXCLUIR"
            ),
            key=(
                f"delete_entity_button_"
                f"{entity_type}_{entity_id}"
            ),
            use_container_width=True,
        )

        if delete_clicked:
            try:
                delete_knowledge_entity(
                    client,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    editor_name="Administrador da NAVE",
                )
                st.success(
                    "Cadastro excluído definitivamente."
                )
                st.session_state.pop(
                    "nave_curation_focus",
                    None,
                )
                st.cache_data.clear()
                st.rerun()

            except Exception as exc:
                report_service_error(
                    "exclusão definitiva do cadastro",
                    user_message=(
                        "Não foi possível excluir este cadastro. "
                        "Arquive-o ou verifique seus vínculos."
                    ),
                    exception=exc,
                )
