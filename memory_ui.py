from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from memory_db import (
    create_memory_signed_url,
    update_memory_item,
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
    item: dict,
    page: dict | None,
    document: dict | None,
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

            st.caption(
                " · ".join(metadata)
            )

            with st.expander(
                "Abrir ficha",
                expanded=False,
            ):
                details_tab, edit_tab = (
                    st.tabs(
                        [
                            "Informações",
                            "Editar",
                        ]
                    )
                )

                with details_tab:
                    _render_item_details(
                        item=item,
                        document=document,
                        slide_url=(
                            slide_url
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
) -> None:
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
            item=item,
            page=page,
            document=document,
            card_key=(
                f"{section_key}_"
                f"{item.get('id')}"
            ),
        )
