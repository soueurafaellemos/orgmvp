from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from coverage_diagnostic import diagnose_coverage
from coverage_diagnostic_ui import render_coverage_diagnostic
from document_io import prepare_documents, render_pdf_page
from memory_db import (
    create_memory_signed_url,
    delete_memory_document,
    delete_memory_project,
    create_memory_project,
    MemorySaveError,
    fetch_memory_documents,
    fetch_memory_items,
    fetch_memory_pages,
    fetch_memory_projects_overview,
    save_memory_presentation,
    update_memory_document_metadata,
    update_memory_project_metadata,
)
from memory_extractor import (
    extract_memory,
    memory_editor_dataframe,
    memory_section_counts,
    merge_memory_batches,
    selected_memory_items,
)
from memory_prompts import (
    MEMORY_SECTION_LABELS,
    MEMORY_STATUS_OPTIONS,
)
from memory_ui import (
    DOCUMENT_STATUS_LABELS,
    DOCUMENT_STATUS_OPTIONS,
    render_memory_section,
    section_labels_present,
)
from runtime_ui import (
    report_service_error,
    require_admin_access,
    require_app_access,
)
from supabase_db import get_supabase_client


st.set_page_config(
    page_title="NAVE by VOE | Memória",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Memória",
    "Arquivo vivo do repertório criativo e estratégico "
    "dos projetos da VOE.",
)

st.info(
    "A Memória é um módulo isolado. Nada armazenado aqui "
    "entra na Base de conhecimento, nas recomendações ou "
    "em cadastros comerciais."
)


def _setting(name: str, default: str = "") -> str:
    try:
        return str(
            st.secrets.get(
                name,
                os.getenv(name, default),
            )
        )
    except Exception:
        return str(os.getenv(name, default))


api_key = _setting("GEMINI_API_KEY")
model = st.session_state.get(
    "nave_model",
    _setting("GEMINI_MODEL", "gemini-3.5-flash-lite"),
)
supabase_url = _setting("SUPABASE_URL")
supabase_key = (
    _setting("SUPABASE_SECRET_KEY")
    or _setting("SUPABASE_SERVICE_ROLE_KEY")
)

if not supabase_url or not supabase_key:
    st.error(
        "A Memória não está disponível. "
        "Consulte a área de Administração."
    )
    st.stop()

client = get_supabase_client(supabase_url, supabase_key)

consult_tab, upload_tab = st.tabs(
    [
        "Consultar Memória",
        "Adicionar novo projeto",
    ]
)


def _selected_rows(event) -> list[int]:
    try:
        return list(event.selection.rows)
    except Exception:
        try:
            return list(
                event.get("selection", {}).get("rows", [])
            )
        except Exception:
            return []



with consult_tab:
    try:
        overview = fetch_memory_projects_overview(client)
    except Exception as exc:
        report_service_error(
            "consulta da Memória",
            user_message=(
                "Não foi possível carregar os projetos da Memória."
            ),
            exception=exc,
        )
        overview = pd.DataFrame()

    if overview.empty:
        st.info(
            "Nenhuma apresentação foi adicionada à Memória ainda."
        )
    else:
        filter1, filter2 = st.columns([3, 1])

        with filter1:
            project_search = st.text_input(
                "Buscar projeto, cliente ou evento",
                placeholder=(
                    "Ex.: Creator Lab, Nissin, Oktoberfest..."
                ),
                key="memory_project_search",
            )

        with filter2:
            page_size = st.selectbox(
                "Projetos por página",
                [25, 50, 100],
                key="memory_project_page_size",
            )

        visible_projects = overview.copy()

        if project_search.strip():
            term = project_search.strip().casefold()
            searchable = (
                visible_projects["project_name"]
                .fillna("")
                .astype(str)
                + " "
                + visible_projects["client_brand"]
                .fillna("")
                .astype(str)
                + " "
                + visible_projects["event_name"]
                .fillna("")
                .astype(str)
            ).str.casefold()

            visible_projects = visible_projects[
                searchable.str.contains(term, regex=False)
            ]

        visible_projects = visible_projects.reset_index(drop=True)
        total_projects = len(visible_projects)

        if total_projects == 0:
            st.warning("Nenhum projeto corresponde à busca.")
        else:
            total_pages = max(
                1,
                math.ceil(total_projects / page_size),
            )
            page_col, summary_col = st.columns([1, 4])

            with page_col:
                current_page = st.number_input(
                    "Página",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    key="memory_projects_page",
                )

            with summary_col:
                st.caption(
                    f"{total_projects} projeto(s) com Memória · "
                    f"página {int(current_page)} de {total_pages}"
                )

            start = (int(current_page) - 1) * page_size
            end = min(start + page_size, total_projects)

            project_page = (
                visible_projects.iloc[start:end]
                .copy()
                .reset_index(drop=True)
            )

            project_page["Projeto"] = project_page[
                "project_name"
            ].fillna("Projeto sem nome")
            project_page["Cliente"] = project_page[
                "client_brand"
            ].fillna("Não informado")
            project_page["Evento"] = project_page[
                "event_name"
            ].fillna("Não informado")
            project_page["Apresentações"] = pd.to_numeric(
                project_page["memory_documents_count"],
                errors="coerce",
            ).fillna(0).astype(int)
            project_page["Conteúdos"] = pd.to_numeric(
                project_page["memory_items_count"],
                errors="coerce",
            ).fillna(0).astype(int)
            project_page["Última atualização"] = project_page[
                "latest_memory_activity"
            ].apply(
                lambda value: (
                    str(value)[:10]
                    if value
                    else "Não informada"
                )
            )

            project_event = st.dataframe(
                project_page[
                    [
                        "Projeto",
                        "Cliente",
                        "Evento",
                        "Apresentações",
                        "Conteúdos",
                        "Última atualização",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                row_height=52,
                on_select="rerun",
                selection_mode="single-row",
                key=f"memory_project_table_{int(current_page)}",
            )

            selected_rows = _selected_rows(project_event)
            focused_project = st.session_state.get(
                "nave_memory_focus_project"
            )

            selected_project = None

            if selected_rows:
                selected_project = project_page.iloc[
                    selected_rows[0]
                ].to_dict()
            elif focused_project:
                matches = overview[
                    overview["project_id"]
                    .astype(str)
                    .eq(str(focused_project))
                ]
                if not matches.empty:
                    selected_project = matches.iloc[0].to_dict()

            if not selected_project:
                st.info(
                    "Selecione um projeto para abrir sua Memória."
                )
            else:
                project_id = str(selected_project["project_id"])
                st.session_state[
                    "nave_memory_focus_project"
                ] = project_id

                st.divider()
                st.subheader(
                    selected_project.get("project_name")
                    or selected_project.get("Projeto")
                    or "Projeto"
                )

                m1, m2, m3, m4 = st.columns(4)
                m1.metric(
                    "Cliente",
                    selected_project.get("client_brand")
                    or selected_project.get("Cliente")
                    or "Não informado",
                )
                m2.metric(
                    "Apresentações",
                    int(
                        selected_project.get("memory_documents_count")
                        or selected_project.get("Apresentações")
                        or 0
                    ),
                )
                m3.metric(
                    "Conteúdos",
                    int(
                        selected_project.get("memory_items_count")
                        or selected_project.get("Conteúdos")
                        or 0
                    ),
                )
                m4.metric(
                    "Slides preservados",
                    int(
                        selected_project.get("memory_pages_count")
                        or 0
                    ),
                )

                try:
                    documents = fetch_memory_documents(
                        client,
                        project_id=project_id,
                    )
                except Exception as exc:
                    report_service_error(
                        "consulta dos documentos da Memória",
                        user_message=(
                            "Não foi possível abrir este projeto."
                        ),
                        exception=exc,
                    )
                    documents = pd.DataFrame()

                if documents.empty:
                    st.info(
                        "Este projeto ainda não possui apresentações."
                    )
                else:
                    document_labels = {
                        (
                            str(
                                row.get("title")
                                or row.get("file_name")
                            )
                            + (
                                " · " + str(row.get("version_label"))
                                if row.get("version_label")
                                else ""
                            )
                        ): str(row["id"])
                        for _, row in documents.iterrows()
                    }

                    filter_col1, filter_col2 = st.columns([1.5, 2.5])

                    with filter_col1:
                        selected_document = st.selectbox(
                            "Versão",
                            ["Todas", *document_labels.keys()],
                            key="memory_document_filter",
                        )

                    with filter_col2:
                        item_search = st.text_input(
                            "Buscar dentro do projeto",
                            placeholder=(
                                "Ex.: photo-op, KV, sampling, palco..."
                            ),
                            key="memory_item_search",
                        )

                    selected_document_ids = (
                        None
                        if selected_document == "Todas"
                        else [document_labels[selected_document]]
                    )

                    try:
                        pages = fetch_memory_pages(
                            client,
                            project_id=project_id,
                            document_ids=selected_document_ids,
                        )
                        items = fetch_memory_items(
                            client,
                            project_id=project_id,
                            document_ids=selected_document_ids,
                        )
                    except Exception as exc:
                        report_service_error(
                            "consulta dos itens da Memória",
                            user_message=(
                                "Não foi possível carregar as galerias."
                            ),
                            exception=exc,
                        )
                        pages = pd.DataFrame()
                        items = pd.DataFrame()

                    documents_by_id = {
                        str(row["id"]): row.to_dict()
                        for _, row in documents.iterrows()
                    }
                    pages_by_id = {
                        str(row["id"]): row.to_dict()
                        for _, row in pages.iterrows()
                    }

                    sections = section_labels_present(items)
                    tab_keys = [
                        "overview",
                        *sections,
                        "documents",
                    ]
                    tab_labels = [
                        "Visão geral",
                        *[
                            MEMORY_SECTION_LABELS[section]
                            for section in sections
                        ],
                        "Documentos & Versões",
                    ]
                    tabs = st.tabs(tab_labels)

                    for tab, tab_key in zip(tabs, tab_keys):
                        with tab:
                            if tab_key == "overview":
                                latest = documents.iloc[0].to_dict()
                                cover_page = pages[
                                    pages["document_id"]
                                    .astype(str)
                                    .eq(str(latest["id"]))
                                    & pages["page_number"].eq(1)
                                ]

                                overview_col1, overview_col2 = st.columns(
                                    [1.35, 2]
                                )

                                with overview_col1:
                                    if not cover_page.empty:
                                        cover_url = (
                                            create_memory_signed_url(
                                                client,
                                                cover_page.iloc[0].get(
                                                    "storage_path"
                                                ),
                                            )
                                        )
                                        if cover_url:
                                            st.image(
                                                cover_url,
                                                use_container_width=True,
                                            )

                                with overview_col2:
                                    st.markdown("### Síntese estratégica")
                                    st.write(
                                        latest.get("strategic_summary")
                                        or (
                                            "A apresentação ainda não "
                                            "possui uma síntese."
                                        )
                                    )
                                    if latest.get("creative_concept"):
                                        st.markdown("**Conceito criativo:**")
                                        st.write(latest["creative_concept"])
                                    st.caption(
                                        "Documento mais recente: "
                                        + str(
                                            latest.get("title")
                                            or latest.get("file_name")
                                        )
                                    )

                                if not items.empty:
                                    counts = (
                                        items.groupby("section_key")
                                        .size()
                                        .reset_index(name="Itens")
                                    )
                                    counts["Seção"] = counts[
                                        "section_key"
                                    ].map(MEMORY_SECTION_LABELS)

                                    st.subheader("Conteúdo organizado")
                                    st.dataframe(
                                        counts[["Seção", "Itens"]],
                                        use_container_width=True,
                                        hide_index=True,
                                    )

                                latest_raw_data = (
                                    latest.get("raw_data")
                                    or {}
                                )
                                if isinstance(
                                    latest_raw_data,
                                    dict,
                                ):
                                    render_coverage_diagnostic(
                                        latest_raw_data.get(
                                            "coverage_diagnostic"
                                        ),
                                        heading=(
                                            "Diagnóstico do documento mais recente"
                                        ),
                                        expanded=False,
                                        download_key=(
                                            "memory_saved_"
                                            + str(latest.get("id"))
                                        ),
                                    )

                                with st.expander(
                                    "Editar informações do projeto",
                                    expanded=False,
                                ):
                                    with st.form(
                                        "memory_project_metadata_"
                                        + project_id
                                    ):
                                        edit_project_name = st.text_input(
                                            "Nome do projeto",
                                            value=str(
                                                selected_project.get(
                                                    "project_name"
                                                )
                                                or selected_project.get(
                                                    "Projeto"
                                                )
                                                or ""
                                            ),
                                        )

                                        edit_meta1, edit_meta2 = (
                                            st.columns(2)
                                        )

                                        with edit_meta1:
                                            edit_client_brand = st.text_input(
                                                "Cliente / marca",
                                                value=str(
                                                    selected_project.get(
                                                        "client_brand"
                                                    )
                                                    or selected_project.get(
                                                        "Cliente"
                                                    )
                                                    or ""
                                                ),
                                            )

                                        with edit_meta2:
                                            edit_event_name = st.text_input(
                                                "Evento",
                                                value=str(
                                                    selected_project.get(
                                                        "event_name"
                                                    )
                                                    or selected_project.get(
                                                        "Evento"
                                                    )
                                                    or ""
                                                ),
                                            )

                                        save_project_meta = (
                                            st.form_submit_button(
                                                "Salvar informações do projeto",
                                                type="primary",
                                                use_container_width=True,
                                            )
                                        )

                                    if save_project_meta:
                                        try:
                                            update_memory_project_metadata(
                                                client,
                                                project_id=project_id,
                                                project_name=edit_project_name,
                                                client_brand=edit_client_brand,
                                                event_name=edit_event_name,
                                            )
                                            st.success(
                                                "Informações do projeto atualizadas."
                                            )
                                            st.cache_data.clear()
                                            st.rerun()
                                        except Exception as exc:
                                            report_service_error(
                                                "edição do projeto na Memória",
                                                user_message=(
                                                    "Não foi possível atualizar "
                                                    "as informações do projeto."
                                                ),
                                                exception=exc,
                                            )

                            elif tab_key == "documents":
                                for _, document_row in documents.iterrows():
                                    document = document_row.to_dict()
                                    doc_id = str(document["id"])

                                    with st.container(border=True):
                                        col1, col2 = st.columns([3, 1])

                                        with col1:
                                            st.markdown(
                                                "### "
                                                + str(
                                                    document.get("title")
                                                    or document.get("file_name")
                                                )
                                            )
                                            st.caption(
                                                (
                                                    document.get("version_label")
                                                    or "Sem versão informada"
                                                )
                                                + " · "
                                                + DOCUMENT_STATUS_LABELS.get(
                                                    str(
                                                        document.get(
                                                            "document_status"
                                                        )
                                                    ),
                                                    str(
                                                        document.get(
                                                            "document_status"
                                                        )
                                                    ),
                                                )
                                            )
                                            st.write(
                                                document.get(
                                                    "strategic_summary"
                                                )
                                                or "Sem síntese."
                                            )

                                        with col2:
                                            st.metric(
                                                "Slides",
                                                int(
                                                    document.get("page_count")
                                                    or 0
                                                ),
                                            )
                                            st.metric(
                                                "Itens",
                                                int(
                                                    document.get("items_count")
                                                    or 0
                                                ),
                                            )

                                        original_url = (
                                            create_memory_signed_url(
                                                client,
                                                document.get("storage_path"),
                                                download=True,
                                            )
                                        )
                                        if original_url:
                                            st.link_button(
                                                "Abrir apresentação original",
                                                original_url,
                                                use_container_width=True,
                                            )

                                        with st.expander(
                                            "Editar informações da apresentação",
                                            expanded=False,
                                        ):
                                            with st.form(
                                                "memory_document_metadata_"
                                                + doc_id
                                            ):
                                                edit_document_title = (
                                                    st.text_input(
                                                        "Título da apresentação",
                                                        value=str(
                                                            document.get(
                                                                "title"
                                                            )
                                                            or document.get(
                                                                "file_name"
                                                            )
                                                            or ""
                                                        ),
                                                    )
                                                )

                                                document_meta1, document_meta2 = (
                                                    st.columns(2)
                                                )

                                                with document_meta1:
                                                    edit_version_label = (
                                                        st.text_input(
                                                            "Versão",
                                                            value=str(
                                                                document.get(
                                                                    "version_label"
                                                                )
                                                                or ""
                                                            ),
                                                        )
                                                    )

                                                with document_meta2:
                                                    current_document_status = str(
                                                        document.get(
                                                            "document_status"
                                                        )
                                                        or "sent_to_client"
                                                    )
                                                    edit_document_status = (
                                                        st.selectbox(
                                                            "Situação do documento",
                                                            DOCUMENT_STATUS_OPTIONS,
                                                            index=(
                                                                DOCUMENT_STATUS_OPTIONS.index(
                                                                    current_document_status
                                                                )
                                                                if current_document_status
                                                                in DOCUMENT_STATUS_OPTIONS
                                                                else 0
                                                            ),
                                                            format_func=lambda value: (
                                                                DOCUMENT_STATUS_LABELS[
                                                                    value
                                                                ]
                                                            ),
                                                        )
                                                    )

                                                save_document_meta = (
                                                    st.form_submit_button(
                                                        "Salvar informações da apresentação",
                                                        type="primary",
                                                        use_container_width=True,
                                                    )
                                                )

                                            if save_document_meta:
                                                try:
                                                    update_memory_document_metadata(
                                                        client,
                                                        document_id=doc_id,
                                                        title=edit_document_title,
                                                        version_label=edit_version_label,
                                                        document_status=edit_document_status,
                                                    )
                                                    st.success(
                                                        "Informações da apresentação atualizadas."
                                                    )
                                                    st.cache_data.clear()
                                                    st.rerun()
                                                except Exception as exc:
                                                    report_service_error(
                                                        "edição da apresentação",
                                                        user_message=(
                                                            "Não foi possível atualizar "
                                                            "esta apresentação."
                                                        ),
                                                        exception=exc,
                                                    )

                                        with st.expander(
                                            "Excluir esta apresentação",
                                            expanded=False,
                                        ):
                                            st.error(
                                                "A exclusão remove o documento, "
                                                "os slides e todos os itens "
                                                "ligados a ele."
                                            )

                                            if require_admin_access():
                                                confirmation = st.text_input(
                                                    "Digite EXCLUIR",
                                                    key=f"memory_delete_{doc_id}",
                                                )
                                                if st.button(
                                                    "Excluir apresentação",
                                                    disabled=(
                                                        confirmation
                                                        .strip()
                                                        .upper()
                                                        != "EXCLUIR"
                                                    ),
                                                    key=(
                                                        "memory_delete_button_"
                                                        + doc_id
                                                    ),
                                                    use_container_width=True,
                                                ):
                                                    delete_memory_document(
                                                        client,
                                                        document_id=doc_id,
                                                    )
                                                    st.success(
                                                        "Apresentação excluída."
                                                    )
                                                    st.cache_data.clear()
                                                    st.rerun()

                            else:
                                render_memory_section(
                                    client,
                                    items=items,
                                    pages_by_id=pages_by_id,
                                    documents_by_id=documents_by_id,
                                    section_key=tab_key,
                                    search=item_search,
                                )


with upload_tab:
    st.subheader(
        "Adicionar novo projeto"
    )
    st.caption(
        "Envie a apresentação final já enviada ao cliente. "
        "Cada envio cria um novo projeto na Memória; "
        "nenhum projeto existente será alterado."
    )

    if not api_key:
        st.warning(
            "O serviço de leitura não está configurado."
        )
    else:
        st.info(
            "Nenhum preenchimento inicial é necessário. "
            "A NAVE identificará projeto, cliente, evento, "
            "título e versão a partir do PDF. Tudo poderá "
            "ser revisado antes e depois de salvar."
        )

        uploaded = st.file_uploader(
            "Apresentação final em PDF",
            type=["pdf"],
            accept_multiple_files=False,
            key="memory_pdf_upload",
            help=(
                "Todos os slides serão analisados automaticamente "
                "e consolidados como um único projeto."
            ),
        )

        analyze_clicked = st.button(
            "Analisar projeto completo",
            type="primary",
            use_container_width=True,
            disabled=(
                uploaded is None
                or not api_key
            ),
            key="memory_analyze_button",
        )

        if analyze_clicked:
            raw = [
                (
                    uploaded.name,
                    uploaded.getvalue(),
                    uploaded.type
                    or "application/pdf",
                )
            ]

            try:
                docs = prepare_documents(raw)
                progress = st.progress(0.0)
                status = st.empty()

                def update(
                    done,
                    total,
                    message,
                ):
                    progress.progress(
                        done / total
                        if total
                        else 1
                    )
                    status.write(message)

                batches = extract_memory(
                    docs,
                    api_key=api_key,
                    model=model,
                    progress_callback=update,
                )
                extraction = (
                    merge_memory_batches(
                        batches
                    )
                )
                memory_source_inventory = [
                    {
                        "unit_id": (
                            str(row.get("source_file") or docs[0].name)
                            + "#page:"
                            + str(row.get("page_number") or 0)
                        ),
                        "source_file": (
                            row.get("source_file")
                            or docs[0].name
                        ),
                        "source_locator": (
                            "Página "
                            + str(row.get("page_number") or 0)
                        ),
                        "source_page": int(
                            row.get("page_number") or 0
                        ),
                        "unit_kind": "Slide de apresentação",
                        "text": row.get("text"),
                        "image_count": row.get("image_count"),
                        "meaningful": bool(
                            row.get("is_meaningful")
                        ),
                    }
                    for row in extraction.get(
                        "page_inventory",
                        [],
                    )
                    if int(row.get("page_number") or 0) > 0
                ]
                coverage_diagnostic = (
                    diagnose_coverage(
                        docs,
                        mode="memory",
                        structured_output=(
                            extraction.get(
                                "items",
                                [],
                            )
                        ),
                        api_key=api_key,
                        model=model,
                        source_inventory=(
                            memory_source_inventory
                        ),
                    )
                )
                extraction[
                    "coverage_diagnostic"
                ] = coverage_diagnostic.model_dump()
                editor = (
                    memory_editor_dataframe(
                        extraction
                    )
                )

                file_title = Path(
                    uploaded.name
                ).stem

                detected_project_name = (
                    extraction.get(
                        "project_name"
                    )
                    or extraction.get(
                        "document_title"
                    )
                    or file_title
                )
                detected_client_brand = (
                    extraction.get(
                        "client_brand"
                    )
                    or ""
                )
                detected_event_name = (
                    extraction.get(
                        "event_name"
                    )
                    or ""
                )
                detected_document_title = (
                    extraction.get(
                        "document_title"
                    )
                    or file_title
                )
                detected_version = (
                    extraction.get(
                        "version_label"
                    )
                    or ""
                )

                st.session_state[
                    "memory_source_document"
                ] = docs[0]
                st.session_state[
                    "memory_extraction"
                ] = extraction
                st.session_state[
                    "memory_editor"
                ] = editor
                st.session_state[
                    "memory_document_meta"
                ] = {
                    "creates_new_project": True,
                }

                st.session_state[
                    "memory_review_project_name"
                ] = str(
                    detected_project_name
                )
                st.session_state[
                    "memory_review_client_brand"
                ] = str(
                    detected_client_brand
                )
                st.session_state[
                    "memory_review_event_name"
                ] = str(
                    detected_event_name
                )
                st.session_state[
                    "memory_review_document_title"
                ] = str(
                    detected_document_title
                )
                st.session_state[
                    "memory_review_version_label"
                ] = str(
                    detected_version
                )
                st.session_state[
                    "memory_review_document_status"
                ] = "sent_to_client"

                st.success(
                    "Projeto completo decupado. "
                    "Revise os dados, o diagnóstico e os conteúdos abaixo."
                )

            except Exception as exc:
                report_service_error(
                    "leitura do projeto completo",
                    user_message=(
                        "Não foi possível analisar "
                        "esta apresentação."
                    ),
                    exception=exc,
                )

        extraction = st.session_state.get("memory_extraction")
        editor = st.session_state.get("memory_editor")
        source_document = st.session_state.get(
            "memory_source_document"
        )
        saved_meta = (
            st.session_state.get("memory_document_meta")
            or {}
        )

        if (
            extraction
            and editor is not None
            and source_document is not None
        ):
            st.divider()
            st.subheader("Revisão antes de salvar")

            st.markdown("### Informações identificadas")
            st.caption(
                "Todos os campos abaixo foram preenchidos "
                "automaticamente e podem ser corrigidos."
            )

            st.text_input(
                "Nome do projeto",
                key="memory_review_project_name",
            )

            review_meta1, review_meta2 = st.columns(2)

            with review_meta1:
                st.text_input(
                    "Cliente / marca",
                    key="memory_review_client_brand",
                )

            with review_meta2:
                st.text_input(
                    "Evento",
                    key="memory_review_event_name",
                )

            review_doc1, review_doc2, review_doc3 = (
                st.columns(
                    [2, 1, 1.35]
                )
            )

            with review_doc1:
                st.text_input(
                    "Título da apresentação",
                    key="memory_review_document_title",
                )

            with review_doc2:
                st.text_input(
                    "Versão",
                    key="memory_review_version_label",
                )

            with review_doc3:
                st.selectbox(
                    "Situação do documento",
                    DOCUMENT_STATUS_OPTIONS,
                    format_func=lambda value: (
                        DOCUMENT_STATUS_LABELS[
                            value
                        ]
                    ),
                    key="memory_review_document_status",
                )

            st.divider()

            preview_items = selected_memory_items(
                extraction,
                editor,
            )
            counts = memory_section_counts(preview_items)

            memory_coverage = extraction.get(
                "coverage"
            ) or {}
            metric1, metric2, metric3, metric4 = (
                st.columns(4)
            )
            metric1.metric(
                "Itens encontrados",
                len(extraction.get("items", [])),
            )
            metric2.metric(
                "Itens selecionados",
                len(preview_items),
            )
            metric3.metric(
                "Slides relevantes cobertos",
                (
                    f"{memory_coverage.get('pages_with_items', 0)}/"
                    f"{memory_coverage.get('meaningful_pages', 0)}"
                ),
            )
            metric4.metric(
                "Cobertura",
                (
                    f"{float(memory_coverage.get('coverage_percent', 0)):.1f}%"
                ),
            )

            if memory_coverage.get(
                "automatic_repair_items",
                0,
            ):
                st.info(
                    "A cobertura automática preservou "
                    f"{memory_coverage.get('automatic_repair_items', 0)} "
                    "item(ns) que não vieram completos na resposta da IA. "
                    "Eles aparecem marcados como Cobertura automática e "
                    "podem ser revisados antes do salvamento."
                )

            if not counts.empty:
                st.dataframe(
                    counts,
                    use_container_width=True,
                    hide_index=True,
                )

            render_coverage_diagnostic(
                extraction.get(
                    "coverage_diagnostic"
                ),
                heading=(
                    "Diagnóstico de cobertura do projeto"
                ),
                expanded=True,
                download_key="memory_review",
            )

            if editor.empty:
                st.warning(
                    "A apresentação foi compreendida, mas nenhum "
                    "conteúdo individual foi estruturado. A NAVE "
                    "não salvará uma tabela vazia nem interromperá "
                    "a página."
                )

                if extraction.get(
                    "strategic_summary"
                ):
                    st.markdown(
                        "### Síntese identificada"
                    )
                    st.write(
                        extraction[
                            "strategic_summary"
                        ]
                    )

                if extraction.get(
                    "warnings"
                ):
                    with st.expander(
                        "Detalhes da leitura",
                        expanded=False,
                    ):
                        for warning in (
                            extraction["warnings"]
                        ):
                            st.write(
                                "• " + str(
                                    warning
                                )
                            )

                if st.button(
                    "Limpar análise e tentar novamente",
                    use_container_width=True,
                    key="memory_empty_retry",
                ):
                    for state_key in [
                        "memory_source_document",
                        "memory_extraction",
                        "memory_editor",
                        "memory_document_meta",
                        "memory_review_project_name",
                        "memory_review_client_brand",
                        "memory_review_event_name",
                        "memory_review_document_title",
                        "memory_review_version_label",
                        "memory_review_document_status",
                    ]:
                        st.session_state.pop(
                            state_key,
                            None,
                        )
                    st.rerun()

                st.stop()

            edited = st.data_editor(
                editor,
                use_container_width=True,
                hide_index=True,
                height=520,
                key="memory_extraction_editor",
                column_config={
                    "_row_id": None,
                    "Incluir": st.column_config.CheckboxColumn(
                        "Incluir"
                    ),
                    "Seção": st.column_config.SelectboxColumn(
                        "Seção",
                        options=list(
                            MEMORY_SECTION_LABELS.values()
                        ),
                    ),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=MEMORY_STATUS_OPTIONS,
                    ),
                    "Resumo": st.column_config.TextColumn(
                        "Resumo",
                        width="large",
                    ),
                    "Origem": st.column_config.TextColumn(
                        "Origem",
                        help=(
                            "IA: item estruturado pelo modelo. "
                            "Cobertura automática: item preservado "
                            "porque o slide não poderia desaparecer."
                        ),
                    ),
                    "Confiança": st.column_config.ProgressColumn(
                        "Confiança",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    ),
                },
                disabled=[
                    "Página",
                    "Arquivo",
                    "Origem",
                    "Confiança",
                ],
            )
            st.session_state["memory_editor"] = edited

            if (
                "Incluir" in edited.columns
                and not edited.empty
            ):
                included_rows = edited[
                    edited["Incluir"].fillna(
                        False
                    ).eq(True)
                ]
            else:
                included_rows = edited.iloc[
                    0:0
                ]

            preview_options = {
                (
                    f"Slide {int(row.get('Página') or 0)} · "
                    f"{row.get('Título')}"
                ): str(row.get("_row_id"))
                for _, row in included_rows.iterrows()
            }

            if preview_options:
                selected_preview = st.selectbox(
                    "Visualizar item no slide",
                    list(preview_options.keys()),
                    key="memory_preview_item",
                )
                preview_row_id = preview_options[selected_preview]

                original_item = next(
                    (
                        item
                        for item in extraction.get("items", [])
                        if str(item.get("_row_id")) == preview_row_id
                    ),
                    None,
                )

                if original_item:
                    try:
                        slide_bytes = render_pdf_page(
                            source_document,
                            int(original_item["source_page"]),
                            zoom=1.2,
                        )
                        st.image(
                            slide_bytes,
                            caption=(
                                "Slide original — página "
                                f"{original_item['source_page']}"
                            ),
                            use_container_width=True,
                        )
                    except Exception:
                        pass

            if extraction.get("warnings"):
                with st.expander("Alertas da leitura", expanded=False):
                    for warning in extraction["warnings"]:
                        st.write("• " + str(warning))

            save_clicked = st.button(
                "Salvar na Memória",
                type="primary",
                use_container_width=True,
                key="memory_save_button",
            )

            if save_clicked:
                final_items = selected_memory_items(
                    extraction,
                    st.session_state["memory_editor"],
                )

                if not final_items:
                    st.warning(
                        "Mantenha pelo menos um item selecionado."
                    )
                else:
                    project_id = None
                    try:
                        review_project_name = str(
                            st.session_state.get(
                                "memory_review_project_name"
                            )
                            or ""
                        ).strip()
                        review_client_brand = str(
                            st.session_state.get(
                                "memory_review_client_brand"
                            )
                            or ""
                        ).strip()
                        review_event_name = str(
                            st.session_state.get(
                                "memory_review_event_name"
                            )
                            or ""
                        ).strip()
                        review_document_title = str(
                            st.session_state.get(
                                "memory_review_document_title"
                            )
                            or source_document.name
                        ).strip()
                        review_version_label = str(
                            st.session_state.get(
                                "memory_review_version_label"
                            )
                            or ""
                        ).strip()
                        review_document_status = str(
                            st.session_state.get(
                                "memory_review_document_status"
                            )
                            or "sent_to_client"
                        )

                        if not review_project_name:
                            st.warning(
                                "A NAVE não conseguiu identificar "
                                "o nome do projeto. Corrija esse campo "
                                "antes de salvar."
                            )
                            st.stop()

                        project_id = (
                            create_memory_project(
                                client,
                                project_name=(
                                    review_project_name
                                ),
                                client_brand=(
                                    review_client_brand
                                    or None
                                ),
                                event_name=(
                                    review_event_name
                                    or None
                                ),
                            )
                        )

                        extraction_for_save = {
                            **extraction,
                            "project_name": (
                                review_project_name
                            ),
                            "client_brand": (
                                review_client_brand
                                or None
                            ),
                            "event_name": (
                                review_event_name
                                or None
                            ),
                            "document_title": (
                                review_document_title
                            ),
                            "version_label": (
                                review_version_label
                                or None
                            ),
                        }

                        save_progress = st.progress(0.0)
                        save_status = st.empty()

                        def update_save_progress(
                            done,
                            total,
                            message,
                        ):
                            save_progress.progress(
                                done / total
                                if total
                                else 1.0
                            )
                            save_status.write(message)

                        result = save_memory_presentation(
                            client,
                            project_id=str(project_id),
                            source_document=source_document,
                            extraction=extraction_for_save,
                            selected_items=final_items,
                            document_title=(
                                review_document_title
                            ),
                            version_label=(
                                review_version_label
                                or None
                            ),
                            document_status=(
                                review_document_status
                            ),
                            progress_callback=(
                                update_save_progress
                            ),
                        )

                        if result.get("status") == "duplicate":
                            st.warning(
                                "Esta mesma apresentação já está "
                                "na Memória do projeto."
                            )
                        else:
                            st.success(
                                f"{result.get('items_saved', 0)} item(ns) "
                                f"e {result.get('pages_saved', 0)} slide(s) "
                                "preservados."
                            )

                        if result.get("warnings"):
                            with st.expander(
                                "Avisos do salvamento",
                                expanded=False,
                            ):
                                for warning in result[
                                    "warnings"
                                ]:
                                    st.write(
                                        "• " + str(warning)
                                    )

                        st.session_state[
                            "nave_memory_focus_project"
                        ] = str(project_id)

                        for key in [
                            "memory_source_document",
                            "memory_extraction",
                            "memory_editor",
                            "memory_document_meta",
                            "memory_review_project_name",
                            "memory_review_client_brand",
                            "memory_review_event_name",
                            "memory_review_document_title",
                            "memory_review_version_label",
                            "memory_review_document_status",
                        ]:
                            st.session_state.pop(key, None)

                        st.cache_data.clear()
                        st.rerun()

                    except MemorySaveError as exc:
                        if project_id:
                            delete_memory_project(
                                client,
                                project_id=str(project_id),
                            )

                        st.error(exc.safe_message)
                        st.caption(
                            "Etapa interrompida: "
                            + str(exc.stage)
                            + ". A análise permanece na tela "
                            "para uma nova tentativa."
                        )

                        report_service_error(
                            "salvamento da Memória — "
                            + str(exc.stage),
                            user_message=(
                                "O salvamento não foi concluído, "
                                "mas o diagnóstico técnico foi registrado."
                            ),
                            exception=(
                                exc.original
                                or exc
                            ),
                        )

                    except Exception as exc:
                        if project_id:
                            delete_memory_project(
                                client,
                                project_id=str(project_id),
                            )

                        report_service_error(
                            "salvamento da Memória",
                            user_message=(
                                "Não foi possível salvar esta apresentação."
                            ),
                            exception=exc,
                        )
