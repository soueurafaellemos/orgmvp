from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from memory_db import (
    create_memory_signed_url,
    update_memory_item,
)
from memory_learning_db import (
    upsert_item_outcome,
)
from memory_learning_models import (
    CONFIDENCE_LEVELS,
    INFORMATION_SOURCES,
    ITEM_OUTCOME_STATUS,
    COST_ITEM_STATUS,
)
from memory_prompts import (
    MEMORY_SECTION_LABELS,
    MEMORY_SECTION_ORDER,
    MEMORY_STATUS_OPTIONS,
)


DOCUMENT_STATUS_LABELS = {
    "sent_to_client": "Enviada ao cliente",
    "revision": "Revisão",
    "approved": "Aprovada",
    "executed": "Executada",
    "internal_reference": "Referência interna",
}

DOCUMENT_STATUS_OPTIONS = list(
    DOCUMENT_STATUS_LABELS.keys()
)


def _list_value(
    value: Any,
) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    return [
        item.strip()
        for item in str(value)
        .replace("\n", "|")
        .split("|")
        if item.strip()
    ]


def _display_list(
    label: str,
    value: Any,
) -> None:
    items = _list_value(value)

    if items:
        st.markdown(
            f"**{label}:** "
            + ", ".join(items)
        )


def _meaningful_text(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def _money(
    value: Any,
) -> str:
    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return "Não informado"

    formatted = (
        f"{number:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
    return "R$ " + formatted


def section_labels_present(
    items: pd.DataFrame,
) -> list[str]:
    if items.empty:
        return []

    present = {
        str(value)
        for value in items[
            "section_key"
        ].dropna()
    }

    return [
        section
        for section in MEMORY_SECTION_ORDER
        if section in present
    ]


def _render_learning_summary(
    *,
    item_outcome: dict | None,
    linked_costs: list[dict],
) -> None:
    if not item_outcome and not linked_costs:
        st.caption(
            "Ainda não há resultado ou custo "
            "associado a esta ficha."
        )
        return

    if item_outcome:
        st.markdown(
            "### Resultado da proposta"
        )
        st.markdown(
            "**Decisão:** "
            + ITEM_OUTCOME_STATUS.get(
                str(
                    item_outcome.get(
                        "outcome_status"
                    )
                    or ""
                ),
                "Resultado desconhecido",
            )
        )

        if item_outcome.get(
            "decision_reason"
        ):
            st.markdown(
                "**Motivo:** "
                + str(
                    item_outcome[
                        "decision_reason"
                    ]
                )
            )

        if item_outcome.get(
            "feedback_summary"
        ):
            st.markdown(
                "**Feedback relacionado:**"
            )
            st.write(
                item_outcome[
                    "feedback_summary"
                ]
            )

        if item_outcome.get(
            "execution_notes"
        ):
            st.markdown(
                "**Execução:**"
            )
            st.write(
                item_outcome[
                    "execution_notes"
                ]
            )

        st.caption(
            CONFIDENCE_LEVELS.get(
                str(
                    item_outcome.get(
                        "confidence_level"
                    )
                    or ""
                ),
                "Informação incompleta",
            )
            + " · "
            + INFORMATION_SOURCES.get(
                str(
                    item_outcome.get(
                        "information_source"
                    )
                    or ""
                ),
                "Fonte não informada",
            )
        )

    if linked_costs:
        st.markdown(
            "### Custos associados"
        )

        total = sum(
            float(
                cost.get(
                    "client_total"
                )
                or 0
            )
            for cost in linked_costs
        )

        if total > 0:
            st.metric(
                "Valor associado",
                _money(total),
            )

        for cost in linked_costs:
            status = COST_ITEM_STATUS.get(
                str(
                    cost.get(
                        "item_status"
                    )
                    or ""
                ),
                str(
                    cost.get(
                        "item_status"
                    )
                    or "Não informado"
                ),
            )

            with st.container(
                border=True,
            ):
                st.markdown(
                    "**"
                    + str(
                        cost.get(
                            "item_name"
                        )
                        or "Item de custo"
                    )
                    + "**"
                )
                st.caption(
                    status
                    + " · "
                    + _money(
                        cost.get(
                            "client_total"
                        )
                    )
                    + " · linha "
                    + str(
                        cost.get(
                            "source_row"
                        )
                        or ""
                    )
                )

                if cost.get(
                    "description"
                ):
                    st.write(
                        cost[
                            "description"
                        ]
                    )

                link_status = str(
                    cost.get(
                        "link_status"
                    )
                    or ""
                )

                if link_status == "suggested":
                    st.warning(
                        "Correlação sugerida; "
                        "ainda não confirmada."
                    )


def _render_item_details(
    *,
    item: dict,
    document: dict | None,
    slide_url: str | None,
) -> None:
    summary = _meaningful_text(
        item.get("summary")
    )
    description = _meaningful_text(
        item.get("description")
    )

    if (
        description
        and description != summary
    ):
        st.write(description)

    _display_list(
        "Tags",
        item.get("tags"),
    )
    _display_list(
        "Objetivos",
        item.get("objectives"),
    )
    _display_list(
        "Públicos",
        item.get("audiences"),
    )
    _display_list(
        "Mecânicas",
        item.get("mechanics"),
    )
    _display_list(
        "Tecnologias",
        item.get("technologies"),
    )

    if item.get("journey_stage"):
        st.markdown(
            "**Etapa da jornada:** "
            + str(
                item["journey_stage"]
            )
        )

    if item.get("evidence"):
        st.markdown(
            "**Evidência do slide:**"
        )
        st.write(
            item["evidence"]
        )

    if document:
        st.markdown(
            "**Documento de origem:** "
            + str(
                document.get("title")
                or document.get(
                    "file_name"
                )
                or "Apresentação"
            )
        )

    if slide_url:
        st.markdown(
            "**Slide original:**"
        )
        st.image(
            slide_url,
            width="stretch",
        )


def _render_item_outcome_editor(
    client,
    *,
    project_id: str,
    item: dict,
    item_outcome: dict | None,
    card_key: str,
) -> None:
    current = item_outcome or {}
    outcome_options = list(
        ITEM_OUTCOME_STATUS.keys()
    )
    confidence_options = list(
        CONFIDENCE_LEVELS.keys()
    )
    source_options = list(
        INFORMATION_SOURCES.keys()
    )

    def index_of(
        options: list[str],
        value: str,
    ) -> int:
        try:
            return options.index(
                value
            )
        except ValueError:
            return 0

    with st.form(
        "memory_item_outcome_"
        + card_key
    ):
        outcome_status = st.selectbox(
            "Resultado desta ficha",
            outcome_options,
            index=index_of(
                outcome_options,
                str(
                    current.get(
                        "outcome_status"
                    )
                    or "unassessed"
                ),
            ),
            format_func=lambda value: (
                ITEM_OUTCOME_STATUS[
                    value
                ]
            ),
        )

        decision_reason = st.text_area(
            "Motivo da decisão",
            value=str(
                current.get(
                    "decision_reason"
                )
                or ""
            ),
            height=90,
        )
        feedback_summary = st.text_area(
            "Feedback relacionado",
            value=str(
                current.get(
                    "feedback_summary"
                )
                or ""
            ),
            height=100,
        )
        execution_notes = st.text_area(
            "Observações de execução",
            value=str(
                current.get(
                    "execution_notes"
                )
                or ""
            ),
            height=90,
        )

        outcome_cols = st.columns(2)

        with outcome_cols[0]:
            confidence_level = (
                st.selectbox(
                    "Confiança",
                    confidence_options,
                    index=index_of(
                        confidence_options,
                        str(
                            current.get(
                                "confidence_level"
                            )
                            or "incomplete"
                        ),
                    ),
                    format_func=lambda value: (
                        CONFIDENCE_LEVELS[
                            value
                        ]
                    ),
                )
            )

        with outcome_cols[1]:
            information_source = (
                st.selectbox(
                    "Fonte",
                    source_options,
                    index=index_of(
                        source_options,
                        str(
                            current.get(
                                "information_source"
                            )
                            or "not_informed"
                        ),
                    ),
                    format_func=lambda value: (
                        INFORMATION_SOURCES[
                            value
                        ]
                    ),
                )
            )

        submitted = (
            st.form_submit_button(
                "Salvar resultado da ficha",
                type="primary",
                width="stretch",
            )
        )

    if submitted:
        try:
            upsert_item_outcome(
                client,
                project_id=project_id,
                item_id=str(
                    item["id"]
                ),
                values={
                    "outcome_status": (
                        outcome_status
                    ),
                    "decision_reason": (
                        decision_reason.strip()
                        or None
                    ),
                    "feedback_summary": (
                        feedback_summary.strip()
                        or None
                    ),
                    "execution_notes": (
                        execution_notes.strip()
                        or None
                    ),
                    "confidence_level": (
                        confidence_level
                    ),
                    "information_source": (
                        information_source
                    ),
                },
            )
            st.success(
                "Resultado da ficha atualizado."
            )
            st.cache_data.clear()
            st.rerun()
        except Exception as exc:
            st.error(
                "Não foi possível salvar "
                "o resultado desta ficha."
            )
            st.code(
                str(exc)
            )


def _render_item_editor(
    client,
    *,
    item: dict,
    card_key: str,
) -> None:
    section_keys = list(
        MEMORY_SECTION_LABELS.keys()
    )
    current_section = str(
        item.get("section_key")
        or "strategy"
    )
    current_status = str(
        item.get("item_status")
        or "Não identificado"
    )

    with st.form(
        f"memory_item_form_{card_key}"
    ):
        edit_col1, edit_col2 = (
            st.columns(2)
        )

        with edit_col1:
            section_key = st.selectbox(
                "Seção",
                section_keys,
                index=(
                    section_keys.index(
                        current_section
                    )
                    if current_section
                    in section_keys
                    else 0
                ),
                format_func=lambda value: (
                    MEMORY_SECTION_LABELS[
                        value
                    ]
                ),
            )

        with edit_col2:
            item_status = st.selectbox(
                "Status",
                MEMORY_STATUS_OPTIONS,
                index=(
                    MEMORY_STATUS_OPTIONS.index(
                        current_status
                    )
                    if current_status
                    in MEMORY_STATUS_OPTIONS
                    else (
                        len(
                            MEMORY_STATUS_OPTIONS
                        )
                        - 1
                    )
                ),
            )

        item_type = st.text_input(
            "Tipo",
            value=str(
                item.get("item_type")
                or ""
            ),
        )

        title = st.text_input(
            "Título",
            value=str(
                item.get("title")
                or ""
            ),
        )

        summary = st.text_area(
            "Resumo",
            value=str(
                item.get("summary")
                or ""
            ),
            height=85,
        )

        description = st.text_area(
            "Descrição",
            value=str(
                item.get("description")
                or ""
            ),
            height=120,
        )

        tags_text = st.text_input(
            "Tags",
            value=" | ".join(
                _list_value(
                    item.get("tags")
                )
            ),
            help="Separe as tags com |",
        )

        submitted = (
            st.form_submit_button(
                "Salvar alterações",
                type="primary",
                width="stretch",
            )
        )

    if submitted:
        update_memory_item(
            client,
            item_id=str(
                item["id"]
            ),
            section_key=section_key,
            item_type=item_type,
            title=title,
            summary=summary,
            description=description,
            item_status=item_status,
            tags=_list_value(
                tags_text
            ),
        )

        st.success(
            "Ficha atualizada."
        )
        st.cache_data.clear()
        st.rerun()


def render_memory_item_row(
    client,
    *,
    project_id: str,
    item: dict,
    page: dict | None,
    document: dict | None,
    item_outcome: dict | None,
    linked_costs: list[dict],
    card_key: str,
) -> None:
    visual_url = (
        create_memory_signed_url(
            client,
            item.get(
                "visual_storage_path"
            ),
        )
        if item.get(
            "visual_storage_path"
        )
        else None
    )

    slide_url = (
        create_memory_signed_url(
            client,
            (page or {}).get(
                "storage_path"
            ),
        )
        if page
        else None
    )

    preview_url = (
        visual_url
        or slide_url
    )

    with st.container(
        border=True,
    ):
        image_col, content_col = (
            st.columns(
                [1.15, 2.85],
                gap="large",
                vertical_alignment="top",
            )
        )

        with image_col:
            if preview_url:
                st.image(
                    preview_url,
                    width="stretch",
                )
            else:
                st.caption(
                    "Sem imagem disponível"
                )

        with content_col:
            st.markdown(
                "### "
                + str(
                    item.get("title")
                    or "Sem título"
                )
            )

            summary = _meaningful_text(
                item.get("summary")
            )

            if summary:
                st.write(summary)

            metadata = [
                str(
                    item.get(
                        "item_status"
                    )
                    or "Não identificado"
                ),
                str(
                    item.get("item_type")
                    or "Conteúdo"
                ),
                (
                    "Slide "
                    + str(
                        item.get(
                            "source_page"
                        )
                        or ""
                    )
                ),
            ]

            if item_outcome:
                metadata.append(
                    ITEM_OUTCOME_STATUS.get(
                        str(
                            item_outcome.get(
                                "outcome_status"
                            )
                        ),
                        "Resultado registrado",
                    )
                )

            if linked_costs:
                linked_total = sum(
                    float(
                        cost.get(
                            "client_total"
                        )
                        or 0
                    )
                    for cost in linked_costs
                )
                metadata.append(
                    _money(
                        linked_total
                    )
                )

            st.caption(
                " · ".join(metadata)
            )

            with st.expander(
                "Abrir ficha",
                expanded=False,
            ):
                (
                    details_tab,
                    learning_tab,
                    edit_tab,
                ) = st.tabs(
                    [
                        "Informações",
                        "Resultado & custo",
                        "Editar",
                    ]
                )

                with details_tab:
                    _render_item_details(
                        item=item,
                        document=document,
                        slide_url=(
                            slide_url
                        ),
                    )

                with learning_tab:
                    _render_learning_summary(
                        item_outcome=(
                            item_outcome
                        ),
                        linked_costs=(
                            linked_costs
                        ),
                    )
                    st.divider()
                    _render_item_outcome_editor(
                        client,
                        project_id=(
                            project_id
                        ),
                        item=item,
                        item_outcome=(
                            item_outcome
                        ),
                        card_key=(
                            card_key
                        ),
                    )

                with edit_tab:
                    _render_item_editor(
                        client,
                        item=item,
                        card_key=(
                            card_key
                        ),
                    )


def render_memory_section(
    client,
    *,
    project_id: str,
    items: pd.DataFrame,
    pages_by_id: dict[
        str,
        dict,
    ],
    documents_by_id: dict[
        str,
        dict,
    ],
    section_key: str,
    search: str = "",
    item_outcomes_by_id: dict[
        str,
        dict,
    ] | None = None,
    cost_links_by_item_id: dict[
        str,
        list[dict],
    ] | None = None,
) -> None:
    item_outcomes_by_id = (
        item_outcomes_by_id
        or {}
    )
    cost_links_by_item_id = (
        cost_links_by_item_id
        or {}
    )

    section_items = items[
        items["section_key"].eq(
            section_key
        )
    ].copy()

    if search.strip():
        term = search.strip().casefold()

        searchable = (
            section_items["title"]
            .fillna("")
            .astype(str)
            + " "
            + section_items["summary"]
            .fillna("")
            .astype(str)
            + " "
            + section_items[
                "description"
            ]
            .fillna("")
            .astype(str)
            + " "
            + section_items[
                "item_type"
            ]
            .fillna("")
            .astype(str)
            + " "
            + section_items["tags"]
            .fillna("")
            .astype(str)
        ).str.casefold()

        section_items = (
            section_items[
                searchable.str.contains(
                    term,
                    regex=False,
                )
            ]
        )

    if section_items.empty:
        st.info(
            "Nenhum conteúdo corresponde "
            "à busca nesta seção."
        )
        return

    order_columns = [
        column
        for column in [
            "source_page",
            "sort_order",
            "title",
        ]
        if column in section_items.columns
    ]

    if order_columns:
        section_items = (
            section_items.sort_values(
                order_columns,
                kind="stable",
            )
        )

    st.caption(
        f"{len(section_items)} "
        "conteúdo(s) nesta seção"
    )

    for item in section_items.to_dict(
        orient="records"
    ):
        item_id = str(
            item.get("id")
            or ""
        )
        page = pages_by_id.get(
            str(
                item.get("page_id")
                or ""
            )
        )

        document = (
            documents_by_id.get(
                str(
                    item.get(
                        "document_id"
                    )
                    or ""
                )
            )
        )

        render_memory_item_row(
            client,
            project_id=project_id,
            item=item,
            page=page,
            document=document,
            item_outcome=(
                item_outcomes_by_id.get(
                    item_id
                )
            ),
            linked_costs=(
                cost_links_by_item_id.get(
                    item_id,
                    [],
                )
            ),
            card_key=(
                f"{section_key}_"
                f"{item_id}"
            ),
        )
