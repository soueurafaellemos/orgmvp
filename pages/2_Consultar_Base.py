from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)

from runtime_ui import report_service_error, require_app_access
from media_library import (
    ASSET_TYPE_LABELS,
    DOCUMENT_ASSET_TYPES,
    IMAGE_ASSET_TYPES,
    add_external_media_link,
    create_signed_download_url,
    create_signed_media_url,
    delete_media_asset,
    fetch_media_assets,
    fetch_media_counts,
    fetch_primary_media_urls,
    format_file_size,
    upload_media_asset,
)
from exporters import format_pt_br_number
from knowledge_details import render_complete_record
from supabase_db import (
    database_counts,
    fetch_enrichment_history,
    fetch_knowledge_item,
    fetch_recommendation_candidates,
    get_supabase_client,
)


st.set_page_config(
    page_title="NAVE by VOE | Base de conhecimento",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Base de conhecimento",
    "Explore brindes, soluções e locais já organizados pela NAVE.",
)

try:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )
except Exception:
    url = os.getenv("SUPABASE_URL", "")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

if not url or not key:
    st.error(
        "A base de conhecimento não está disponível. "
        "Consulte a área de Administração."
    )
    st.stop()

try:
    client = get_supabase_client(url, key)
    counts = database_counts(client)
    candidates = fetch_recommendation_candidates(client)
except Exception as exc:
    report_service_error(
        "consulta da base de conhecimento",
        user_message=(
            "Não foi possível consultar a base de conhecimento."
        ),
        exception=exc,
    )
    st.stop()

metric_columns = st.columns(len(counts))
for column, (label, value) in zip(metric_columns, counts.items()):
    column.metric(label, value)

st.divider()

type_labels = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
}

col1, col2, col3, col4 = st.columns(
    [2, 1, 1, 1]
)

with col1:
    search = st.text_input(
        "Buscar",
        placeholder=(
            "Ex.: skate, tecnologia, sustentável, São Paulo..."
        ),
    )

with col2:
    selected_types = st.multiselect(
        "Tipo",
        options=list(type_labels.keys()),
        default=list(type_labels.keys()),
        format_func=lambda value: type_labels[value],
    )

with col3:
    max_price = st.number_input(
        "Valor máximo",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        help="Zero mantém todos os valores.",
    )

with col4:
    media_filter = st.selectbox(
        "Acervo",
        options=[
            "Todos",
            "Com mídia",
            "Sem mídia",
        ],
    )

filtered = candidates.copy()

if selected_types:
    filtered = filtered[
        filtered["item_type"].isin(selected_types)
    ]

if search.strip():
    normalized = search.strip().lower()
    searchable = (
        filtered["name"].fillna("").astype(str)
        + " "
        + filtered["category"].fillna("").astype(str)
        + " "
        + filtered["supplier_name"].fillna("").astype(str)
        + " "
        + filtered["description"].fillna("").astype(str)
        + " "
        + filtered["location"].fillna("").astype(str)
    ).str.lower()
    filtered = filtered[
        searchable.str.contains(
            normalized,
            regex=False,
        )
    ]

if max_price > 0:
    numeric_price = pd.to_numeric(
        filtered["base_price"],
        errors="coerce",
    )
    filtered = filtered[
        numeric_price.isna()
        | (numeric_price <= max_price)
    ]

display = filtered.copy()

if display.empty:
    st.info("Nenhum item corresponde aos filtros.")
    st.stop()

display = display.reset_index(drop=True)

item_keys = [
    (
        str(row.get("item_type")),
        str(row.get("item_id")),
    )
    for _, row in display.iterrows()
]

try:
    media_counts = fetch_media_counts(
        client,
        item_keys,
    )
except Exception:
    media_counts = {}

display["_media_count"] = display.apply(
    lambda row: media_counts.get(
        (
            str(row.get("item_type")),
            str(row.get("item_id")),
        ),
        0,
    ),
    axis=1,
)

if media_filter == "Com mídia":
    display = display[
        display["_media_count"] > 0
    ]
elif media_filter == "Sem mídia":
    display = display[
        display["_media_count"] == 0
    ]

display = display.reset_index(drop=True)

if display.empty:
    st.info(
        "Nenhum item corresponde ao filtro de acervo."
    )
    st.stop()

visible_item_keys = [
    (
        str(row.get("item_type")),
        str(row.get("item_id")),
    )
    for _, row in display.iterrows()
]

try:
    primary_urls = fetch_primary_media_urls(
        client,
        visible_item_keys,
    )
except Exception:
    primary_urls = {}

display["Capa"] = display.apply(
    lambda row: primary_urls.get(
        (
            str(row.get("item_type")),
            str(row.get("item_id")),
        ),
        None,
    ),
    axis=1,
)

display["Tipo"] = display["item_type"].map(
    type_labels
)
display["Valor"] = display.apply(
    lambda row: format_pt_br_number(
        row.get("base_price"),
        prefix={
            "BRL": "R$ ",
            "USD": "US$ ",
            "EUR": "€ ",
        }.get(
            str(row.get("currency") or ""),
            "",
        ),
    )
    or "Não informado",
    axis=1,
)
display["Prazo"] = display[
    "lead_time_days"
].apply(
    lambda value: (
        f"{int(value)} dias"
        if pd.notna(value)
        else "Não informado"
    )
)
display["Capacidade"] = display[
    "capacity"
].apply(
    lambda value: (
        f"{int(value):,}".replace(",", ".")
        if pd.notna(value)
        else "Não informado"
    )
)
display["Mídia"] = display[
    "_media_count"
].apply(
    lambda value: f"{int(value)} arquivo(s)"
)

columns = [
    "Capa",
    "Tipo",
    "name",
    "category",
    "supplier_name",
    "Valor",
    "Prazo",
    "Capacidade",
    "location",
    "Mídia",
]

table = display[columns].rename(
    columns={
        "name": "Nome",
        "category": "Categoria",
        "supplier_name": "Fornecedor",
        "location": "Localização",
    }
).fillna("Não informado")

st.caption(
    "Selecione uma linha para abrir a ficha completa, "
    "imagens e documentos."
)

table_event = st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    key="knowledge_base_table",
    on_select="rerun",
    selection_mode="single-row",
    row_height=64,
    column_config={
        "Capa": st.column_config.ImageColumn(
            "Capa",
            width="small",
            help=(
                "Miniatura de 56 × 56 px da imagem "
                "definida como principal."
            ),
        ),
        "Nome": st.column_config.TextColumn(
            "Nome",
            width="medium",
        ),
        "Mídia": st.column_config.TextColumn(
            "Mídia",
            width="small",
        ),
    },
)

st.caption(f"{len(display)} itens encontrados.")


def _selected_row_indexes(event) -> list[int]:
    try:
        return list(event.selection.rows)
    except Exception:
        try:
            return list(
                event.get("selection", {}).get(
                    "rows",
                    [],
                )
            )
        except Exception:
            return []


def _render_media_gallery(
    media_df: pd.DataFrame,
) -> None:
    if media_df.empty:
        st.info(
            "Este item ainda não possui imagens ou documentos."
        )
        return

    image_rows = []
    document_rows = []

    for _, media in media_df.iterrows():
        record = media.to_dict()
        mime_type = str(
            record.get("mime_type") or ""
        )
        asset_type = str(
            record.get("asset_type") or ""
        )

        if (
            mime_type.startswith("image/")
            or asset_type in IMAGE_ASSET_TYPES
        ):
            image_rows.append(record)
        else:
            document_rows.append(record)

    if image_rows:
        st.markdown("#### Imagens")
        gallery_columns = st.columns(3)

        for index, media in enumerate(image_rows):
            with gallery_columns[
                index % len(gallery_columns)
            ]:
                try:
                    signed_url = create_signed_media_url(
                        client,
                        media,
                    )
                    download_url = (
                        create_signed_download_url(
                            client,
                            media,
                        )
                    )
                except Exception:
                    signed_url = None
                    download_url = None

                if signed_url:
                    st.image(
                        signed_url,
                        caption=(
                            str(media.get("title") or "")
                            + (
                                " — imagem principal"
                                if media.get("is_primary")
                                else ""
                            )
                        ),
                        use_container_width=True,
                    )
                else:
                    st.warning(
                        "A imagem não pôde ser aberta agora."
                    )

                if media.get("description"):
                    st.caption(
                        str(media.get("description"))
                    )

                if download_url:
                    st.link_button(
                        "Baixar imagem",
                        download_url,
                        use_container_width=True,
                    )

    if document_rows:
        st.markdown("#### Documentos e links")

        for media in document_rows:
            try:
                signed_url = create_signed_media_url(
                    client,
                    media,
                )
                download_url = (
                    create_signed_download_url(
                        client,
                        media,
                    )
                )
            except Exception:
                signed_url = None
                download_url = None

            label = ASSET_TYPE_LABELS.get(
                str(media.get("asset_type")),
                "Arquivo",
            )
            title = str(
                media.get("title")
                or media.get("file_name")
                or label
            )
            size = format_file_size(
                media.get("file_size_bytes")
            )
            is_external_link = bool(
                str(
                    media.get("external_url") or ""
                ).strip()
            )

            col_info, col_open, col_download = st.columns(
                [4, 1, 1]
            )
            with col_info:
                st.write(f"**{title}**")
                details = label
                if size:
                    details += f" · {size}"
                st.caption(details)

                if media.get("description"):
                    st.caption(
                        str(media.get("description"))
                    )

            with col_open:
                if signed_url:
                    st.link_button(
                        "Abrir",
                        signed_url,
                        use_container_width=True,
                    )
                else:
                    st.button(
                        "Indisponível",
                        disabled=True,
                        key=(
                            "unavailable_open_"
                            f"{media.get('id')}"
                        ),
                        use_container_width=True,
                    )

            with col_download:
                if download_url:
                    st.link_button(
                        "Baixar",
                        download_url,
                        use_container_width=True,
                    )
                elif is_external_link:
                    st.button(
                        "Sem arquivo",
                        disabled=True,
                        key=(
                            "external_no_download_"
                            f"{media.get('id')}"
                        ),
                        help=(
                            "Este item é um link externo e "
                            "não possui arquivo armazenado "
                            "na NAVE."
                        ),
                        use_container_width=True,
                    )
                else:
                    st.button(
                        "Indisponível",
                        disabled=True,
                        key=(
                            "unavailable_download_"
                            f"{media.get('id')}"
                        ),
                        use_container_width=True,
                    )


def _entity_noun(
    entity_type: str,
) -> str:
    return {
        "product": "brinde",
        "activation": "solução / ativação",
        "venue": "local",
    }.get(entity_type, "item")


def _asset_options(
    entity_type: str,
) -> list[str]:
    common = [
        "main_image",
        "gallery_image",
        "technical_sheet",
        "presentation",
        "other",
    ]

    if entity_type == "venue":
        return [
            "main_image",
            "gallery_image",
            "floor_plan",
            "elevation",
            "access_map",
            "technical_sheet",
            "commercial_book",
            "presentation",
            "other",
        ]

    return common


def _render_media_manager(
    entity_type: str,
    entity_id: str,
    item_name: str,
) -> None:
    noun = _entity_noun(entity_type)

    with st.expander(
        f"Adicionar imagens e documentos ao {noun}",
        expanded=False,
    ):
        upload_tab, link_tab = st.tabs(
            ["Enviar arquivos", "Adicionar link"]
        )

        with upload_tab:
            asset_type = st.selectbox(
                "Tipo de material",
                options=_asset_options(entity_type),
                format_func=lambda value: (
                    ASSET_TYPE_LABELS[value]
                ),
                key=(
                    f"asset_type_{entity_type}_{entity_id}"
                ),
            )

            title = st.text_input(
                "Título",
                placeholder=(
                    "Ex.: Imagem de referência, planta "
                    "ou ficha técnica"
                ),
                key=(
                    f"asset_title_{entity_type}_{entity_id}"
                ),
            )

            description = st.text_area(
                "Descrição ou observação",
                key=(
                    f"asset_description_"
                    f"{entity_type}_{entity_id}"
                ),
            )

            uploaded_assets = st.file_uploader(
                "Arquivos",
                type=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                    "gif",
                    "pdf",
                    "docx",
                    "pptx",
                    "xlsx",
                ],
                accept_multiple_files=True,
                key=(
                    f"asset_files_{entity_type}_{entity_id}"
                ),
            )
            st.caption(
                "Formatos aceitos: JPG, JPEG, PNG, WEBP, GIF, "
                "PDF, DOCX, PPTX e XLSX. Limite de 50 MB "
                "por arquivo."
            )

            if asset_type in IMAGE_ASSET_TYPES:
                primary_choice = st.radio(
                    f"Definir como imagem principal do {noun}?",
                    options=["Não", "Sim"],
                    index=(
                        1
                        if asset_type == "main_image"
                        else 0
                    ),
                    horizontal=True,
                    key=(
                        f"asset_primary_{entity_type}_"
                        f"{entity_id}_{asset_type}"
                    ),
                )
                is_primary = primary_choice == "Sim"
            else:
                is_primary = False
                st.caption(
                    "A opção de imagem principal aparece apenas "
                    "para arquivos de imagem."
                )

            if st.button(
                "Adicionar ao acervo",
                type="primary",
                use_container_width=True,
                key=(
                    f"asset_upload_{entity_type}_{entity_id}"
                ),
            ):
                if not uploaded_assets:
                    st.warning(
                        "Selecione ao menos um arquivo."
                    )
                else:
                    try:
                        for index, uploaded in enumerate(
                            uploaded_assets
                        ):
                            item_title = (
                                title.strip()
                                or uploaded.name
                            )
                            if len(uploaded_assets) > 1:
                                item_title = (
                                    f"{item_title} "
                                    f"{index + 1}"
                                )

                            upload_media_asset(
                                client,
                                entity_type=entity_type,
                                entity_id=entity_id,
                                asset_type=asset_type,
                                title=item_title,
                                description=description,
                                file_name=uploaded.name,
                                file_bytes=uploaded.getvalue(),
                                mime_type=uploaded.type,
                                is_primary=(
                                    bool(is_primary)
                                    and index == 0
                                ),
                            )

                        st.success(
                            f"Material adicionado ao acervo "
                            f"de {item_name}."
                        )
                        st.rerun()

                    except Exception as exc:
                        report_service_error(
                            "upload do acervo visual",
                            user_message=(
                                "Não foi possível adicionar "
                                "o material ao acervo."
                            ),
                            exception=exc,
                        )

        with link_tab:
            link_type = st.selectbox(
                "Tipo de link",
                options=[
                    "video",
                    "external_link",
                    "presentation",
                    "commercial_book",
                    "other",
                ],
                format_func=lambda value: (
                    ASSET_TYPE_LABELS[value]
                ),
                key=(
                    f"link_type_{entity_type}_{entity_id}"
                ),
            )

            link_title = st.text_input(
                "Título do link",
                placeholder="Ex.: Tour virtual ou case",
                key=(
                    f"link_title_{entity_type}_{entity_id}"
                ),
            )

            external_url = st.text_input(
                "Endereço",
                placeholder="https://...",
                key=(
                    f"link_url_{entity_type}_{entity_id}"
                ),
            )

            link_description = st.text_area(
                "Descrição",
                key=(
                    f"link_description_"
                    f"{entity_type}_{entity_id}"
                ),
            )

            if st.button(
                "Adicionar link ao acervo",
                type="primary",
                use_container_width=True,
                key=(
                    f"link_add_{entity_type}_{entity_id}"
                ),
            ):
                if not external_url.strip().startswith(
                    ("http://", "https://")
                ):
                    st.warning(
                        "Informe um endereço válido começando "
                        "com http:// ou https://."
                    )
                else:
                    try:
                        add_external_media_link(
                            client,
                            entity_type=entity_type,
                            entity_id=entity_id,
                            asset_type=link_type,
                            title=(
                                link_title.strip()
                                or "Link externo"
                            ),
                            external_url=external_url,
                            description=link_description,
                        )
                        st.success(
                            "Link adicionado ao acervo."
                        )
                        st.rerun()

                    except Exception as exc:
                        report_service_error(
                            "cadastro de link no acervo",
                            user_message=(
                                "Não foi possível adicionar "
                                "este link ao acervo."
                            ),
                            exception=exc,
                        )


def _render_media_management(
    entity_type: str,
    entity_id: str,
    media_df: pd.DataFrame,
) -> None:
    if (
        media_df.empty
        or not st.session_state.get(
            "nave_admin_authenticated",
            False,
        )
    ):
        return

    with st.expander(
        "Gerenciar itens do acervo",
        expanded=False,
    ):
        options = {
            (
                f"{ASSET_TYPE_LABELS.get(
                    str(row.get('asset_type')),
                    'Arquivo',
                )} — "
                f"{row.get('title')}"
            ): index
            for index, row in media_df.iterrows()
        }

        selected_media_label = st.selectbox(
            "Material",
            list(options.keys()),
            key=(
                f"delete_media_select_"
                f"{entity_type}_{entity_id}"
            ),
        )

        if st.button(
            "Excluir material selecionado",
            key=(
                f"delete_media_"
                f"{entity_type}_{entity_id}"
            ),
        ):
            try:
                media_record = media_df.loc[
                    options[selected_media_label]
                ].to_dict()

                delete_media_asset(
                    client,
                    media_record,
                )
                st.success(
                    "Material removido do acervo."
                )
                st.rerun()

            except Exception as exc:
                report_service_error(
                    "exclusão do acervo visual",
                    user_message=(
                        "Não foi possível remover "
                        "este material."
                    ),
                    exception=exc,
                )


selected_indexes = _selected_row_indexes(
    table_event
)

if selected_indexes:
    selected = display.iloc[
        selected_indexes[0]
    ].to_dict()

    entity_type = str(
        selected.get("item_type") or ""
    )
    entity_id = str(
        selected.get("item_id") or ""
    )
    item_name = str(
        selected.get("name") or "Item"
    )

    st.divider()
    st.subheader(item_name)

    try:
        complete_record = fetch_knowledge_item(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except Exception as exc:
        report_service_error(
            "consulta da ficha completa",
            user_message=(
                "Não foi possível carregar todos os detalhes "
                "deste item."
            ),
            exception=exc,
        )
        complete_record = {}

    complete_record = {
        **selected,
        **complete_record,
    }

    if not complete_record.get("supplier_name"):
        complete_record["supplier_name"] = selected.get(
            "supplier_name"
        )

    render_complete_record(
        entity_type,
        complete_record,
    )

    try:
        enrichment_history = fetch_enrichment_history(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except Exception:
        enrichment_history = pd.DataFrame()

    if not enrichment_history.empty:
        with st.expander(
            "Histórico de enriquecimento",
            expanded=False,
        ):
            for _, event in enrichment_history.iterrows():
                strategy_label = {
                    "enrich_safe": (
                        "Lacunas preenchidas e diferenças "
                        "preservadas"
                    ),
                    "prefer_new": (
                        "Arquivo mais recente priorizado"
                    ),
                }.get(
                    str(event.get("strategy")),
                    str(event.get("strategy") or ""),
                )

                st.write(
                    f"**{strategy_label}**"
                )
                source = str(
                    event.get("source_file")
                    or "Fonte não informada"
                )
                page = event.get("source_page")
                source_text = source
                if pd.notna(page):
                    source_text += f" · página {int(page)}"

                st.caption(source_text)

                history_metrics = st.columns(4)
                history_metrics[0].metric(
                    "Preenchidos",
                    len(
                        event.get("fields_filled")
                        or []
                    ),
                )
                history_metrics[1].metric(
                    "Atualizados",
                    len(
                        event.get("fields_updated")
                        or []
                    ),
                )
                history_metrics[2].metric(
                    "Listas unidas",
                    len(
                        event.get("fields_merged")
                        or []
                    ),
                )
                history_metrics[3].metric(
                    "Diferenças",
                    len(
                        event.get("conflict_fields")
                        or []
                    ),
                )
                st.divider()

    st.markdown("### Imagens e arquivos")

    try:
        media_df = fetch_media_assets(
            client,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except Exception as exc:
        report_service_error(
            "consulta do acervo visual",
            user_message=(
                "Não foi possível carregar as imagens "
                "e documentos deste item."
            ),
            exception=exc,
        )
        media_df = pd.DataFrame()

    _render_media_gallery(media_df)
    _render_media_manager(
        entity_type,
        entity_id,
        item_name,
    )
    _render_media_management(
        entity_type,
        entity_id,
        media_df,
    )

