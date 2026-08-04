from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from document_io import (
    InputDocument,
    prepare_documents,
    render_pdf_page,
)
from exporters import (
    activation_json_bytes,
    briefing_dataframe,
    briefing_json_bytes,
    catalog_json_bytes,
    classification_dataframe,
    merge_activation_batches,
    merge_catalog_batches,
    merge_venue_batches,
    normalize_editor_activations,
    normalize_editor_products,
    normalize_editor_venues,
    prepare_activations_for_editor,
    prepare_products_for_editor,
    prepare_venues_for_editor,
    to_xlsx_bytes,
    venue_json_bytes,
)
from gemini_extractor import (
    classify_documents,
    extract_activation,
    extract_briefing,
    extract_catalog,
    extract_venues,
)


st.set_page_config(
    page_title="Organizador Universal de Pré-Produção",
    page_icon="🧩",
    layout="wide",
)

st.title("Organizador universal de pré-produção")
st.caption(
    "Organiza brindes, soluções de ativações, locais e briefings em bases separadas."
)

with st.sidebar:
    st.header("Configuração Gemini")
    try:
        default_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        default_key = os.getenv("GEMINI_API_KEY", "")

    api_key = st.text_input(
        "Gemini API key",
        value=default_key,
        type="password",
    )
    model = st.selectbox(
        "Modelo",
        [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ],
    )
    st.warning(
        "Na faixa gratuita, não use documentos confidenciais."
    )

mode_label = st.radio(
    "Como deseja organizar?",
    [
        "Detecção automática",
        "Catálogo / tabela de brindes",
        "Soluções / ativações",
        "Locais / espaços",
        "Briefing / projeto",
    ],
    horizontal=True,
)

mode_map = {
    "Detecção automática": "auto",
    "Catálogo / tabela de brindes": "catalog",
    "Soluções / ativações": "activation",
    "Locais / espaços": "venue",
    "Briefing / projeto": "briefing",
}
selected_mode = mode_map[mode_label]

uploaded_files = st.file_uploader(
    "Arquivos",
    type=[
        "pdf",
        "txt",
        "md",
        "json",
        "html",
        "xml",
        "docx",
        "pptx",
        "csv",
        "tsv",
        "xls",
        "xlsx",
        "eml",
    ],
    accept_multiple_files=True,
)

pasted_text = st.text_area(
    "Texto colado, e-mail ou observações",
    height=140,
)

start_page, end_page_value, pages_per_batch = 1, 0, 3
if selected_mode != "briefing":
    col1, col2, col3 = st.columns(3)
    with col1:
        start_page = st.number_input(
            "Página inicial", min_value=1, value=1
        )
    with col2:
        end_page_value = st.number_input(
            "Página final (0 = até o fim)",
            min_value=0,
            value=0,
        )
    with col3:
        pages_per_batch = st.slider(
            "Páginas por lote", 1, 8, 3
        )

run = st.button(
    "Identificar e organizar",
    type="primary",
    use_container_width=True,
)


def _clear():
    for key in list(st.session_state.keys()):
        if key.startswith("result_") or key in (
            "classification",
            "source_documents",
        ):
            st.session_state.pop(key, None)


def _find_pdf(
    docs: list[InputDocument],
    source_file: str | None,
) -> InputDocument | None:
    pdfs = [
        doc for doc in docs
        if doc.mime_type == "application/pdf"
    ]
    if not pdfs:
        return None
    if source_file:
        for doc in pdfs:
            if doc.name == source_file:
                return doc
    return pdfs[0]


def _source_image_tab(
    records_df: pd.DataFrame,
    docs: list[InputDocument],
    label: str,
):
    if records_df.empty:
        st.info("Nenhum registro disponível.")
        return

    options = {
        f"{index + 1}. {row.get('name', 'Sem nome')}": index
        for index, row in records_df.iterrows()
    }
    selected_label = st.selectbox(
        f"Selecione um {label}",
        list(options.keys()),
    )
    row = records_df.loc[options[selected_label]]
    page = row.get("source_page")
    source_file = row.get("source_file")

    st.write(
        f"**Fonte:** {source_file or 'não informada'}"
        + (
            f" — **Página:** {int(page)}"
            if pd.notna(page)
            else ""
        )
    )

    if pd.isna(page):
        st.warning(
            "O registro não possui página de origem. "
            "A imagem não pode ser exibida automaticamente."
        )
        return

    pdf = _find_pdf(docs, source_file)
    if not pdf:
        st.warning("O arquivo de origem não é um PDF disponível.")
        return

    try:
        image = render_pdf_page(pdf, int(page), zoom=1.5)
        st.image(
            image,
            caption=(
                "Página de origem. O recorte exato do produto será "
                "uma evolução posterior."
            ),
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Não foi possível renderizar a página: {exc}")


if run:
    _clear()
    if not uploaded_files and not pasted_text.strip():
        st.error("Envie um arquivo ou cole um texto.")
        st.stop()
    if not api_key:
        st.error("Informe uma Gemini API key.")
        st.stop()

    raw = [
        (file.name, file.getvalue(), file.type or None)
        for file in uploaded_files
    ]
    if pasted_text.strip() and selected_mode != "briefing":
        raw.append(
            (
                "texto_colado_usuario.txt",
                pasted_text.encode("utf-8"),
                "text/plain",
            )
        )

    try:
        docs = prepare_documents(raw)
        st.session_state["source_documents"] = docs

        route = selected_mode
        classification = None

        if route == "auto":
            with st.spinner("Identificando o documento..."):
                classification = classify_documents(
                    docs,
                    api_key=api_key,
                    model=model,
                )
            st.session_state["classification"] = classification
            route = classification.suggested_mode

            if route == "manual_review":
                st.warning(
                    "Documento misto ou inconclusivo. "
                    "Escolha manualmente um modo."
                )
                st.stop()

        progress = st.progress(0.0)
        status = st.empty()

        def update(done, total, message):
            progress.progress(done / total if total else 1)
            status.write(message)

        end_page = (
            None
            if int(end_page_value) == 0
            else int(end_page_value)
        )

        if route == "catalog":
            batches = extract_catalog(
                docs,
                api_key=api_key,
                model=model,
                pages_per_batch=int(pages_per_batch),
                start_page=int(start_page),
                end_page=end_page,
                progress_callback=update,
            )
            products, rules, alerts, suppliers = (
                merge_catalog_batches(batches)
            )
            st.session_state["result_type"] = "catalog"
            st.session_state["result_records"] = products
            st.session_state["result_editor"] = (
                prepare_products_for_editor(products)
            )
            st.session_state["result_rules"] = rules
            st.session_state["result_alerts"] = alerts
            st.session_state["result_suppliers"] = suppliers

        elif route == "activation":
            batches = extract_activation(
                docs,
                api_key=api_key,
                model=model,
                pages_per_batch=int(pages_per_batch),
                start_page=int(start_page),
                end_page=end_page,
                progress_callback=update,
            )
            records, costs, rules, alerts, suppliers = (
                merge_activation_batches(batches)
            )
            st.session_state["result_type"] = "activation"
            st.session_state["result_records"] = records
            st.session_state["result_editor"] = (
                prepare_activations_for_editor(records)
            )
            st.session_state["result_costs"] = costs
            st.session_state["result_rules"] = rules
            st.session_state["result_alerts"] = alerts
            st.session_state["result_suppliers"] = suppliers



        elif route == "venue":
            batches = extract_venues(
                docs,
                api_key=api_key,
                model=model,
                pages_per_batch=int(pages_per_batch),
                start_page=int(start_page),
                end_page=end_page,
                progress_callback=update,
            )
            records, rules, alerts, contacts = merge_venue_batches(
                batches
            )
            st.session_state["result_type"] = "venue"
            st.session_state["result_records"] = records
            st.session_state["result_editor"] = (
                prepare_venues_for_editor(records)
            )
            st.session_state["result_rules"] = rules
            st.session_state["result_alerts"] = alerts
            st.session_state["result_contacts"] = contacts

        elif route == "briefing":
            briefing = extract_briefing(
                docs,
                pasted_text=(
                    pasted_text if selected_mode == "briefing" else ""
                ),
                api_key=api_key,
                model=model,
            )
            st.session_state["result_type"] = "briefing"
            st.session_state["result_briefing"] = briefing

    except Exception as exc:
        st.exception(exc)


classification = st.session_state.get("classification")
if classification:
    st.divider()
    st.header("Triagem")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tipo", classification.document_type)
    c2.metric("Destino", classification.destination_base)
    c3.metric(
        "Confiança", f"{classification.confidence * 100:.0f}%"
    )
    st.write(classification.summary)

result_type = st.session_state.get("result_type")
docs = st.session_state.get("source_documents", [])

if result_type == "catalog":
    st.divider()
    st.header("Base de brindes")

    records = st.session_state["result_records"]
    rules = st.session_state["result_rules"]
    alerts = st.session_state["result_alerts"]
    suppliers = st.session_state["result_suppliers"]

    tabs = st.tabs(
        [
            "Produtos",
            "Imagem / fonte",
            "Fornecedores",
            "Regras gerais",
            "Alertas",
        ]
    )

    with tabs[0]:
        edited = st.data_editor(
            st.session_state["result_editor"],
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="catalog_editor_v4",
            column_config={
                "supplier_website": st.column_config.LinkColumn(
                    "Site do fornecedor"
                ),
                "unit_price_formatted": st.column_config.TextColumn(
                    "Valor unitário"
                ),
                "price_min_formatted": st.column_config.TextColumn(
                    "Valor mínimo"
                ),
                "price_max_formatted": st.column_config.TextColumn(
                    "Valor máximo"
                ),
            },
        )
        st.session_state["result_editor"] = edited
        technical = normalize_editor_products(edited)

    with tabs[1]:
        _source_image_tab(records, docs, "produto")

    with tabs[2]:
        edited_suppliers = st.data_editor(
            suppliers,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="supplier_editor_catalog_v4",
            column_config={
                "website_url": st.column_config.LinkColumn("Site"),
                "instagram_url": st.column_config.LinkColumn(
                    "Instagram"
                ),
                "linkedin_url": st.column_config.LinkColumn(
                    "LinkedIn"
                ),
            },
        )
        suppliers = edited_suppliers

    with tabs[3]:
        st.dataframe(rules, use_container_width=True)
    with tabs[4]:
        if alerts.empty:
            st.success("Nenhum alerta adicional.")
        else:
            st.dataframe(alerts, use_container_width=True)

    classification_df = (
        classification_dataframe(classification)
        if classification
        else pd.DataFrame()
    )
    xlsx = to_xlsx_bytes(
        {
            "Produtos": edited,
            "Dados técnicos": technical,
            "Fornecedores": suppliers,
            "Regras gerais": rules,
            "Alertas": alerts,
            "Classificação": classification_df,
        }
    )
    d1, d2 = st.columns(2)
    d1.download_button(
        "Baixar Excel",
        xlsx,
        "base_brindes_estruturada.xlsx",
        use_container_width=True,
    )
    d2.download_button(
        "Baixar JSON",
        catalog_json_bytes(
            technical,
            rules,
            alerts,
            suppliers,
            classification,
        ),
        "base_brindes_estruturada.json",
        use_container_width=True,
    )


if result_type == "activation":
    st.divider()
    st.header("Base de soluções e ativações")

    records = st.session_state["result_records"]
    costs = st.session_state["result_costs"]
    rules = st.session_state["result_rules"]
    alerts = st.session_state["result_alerts"]
    suppliers = st.session_state["result_suppliers"]

    tabs = st.tabs(
        [
            "Soluções",
            "Imagem / fonte",
            "Fornecedores",
            "Custos adicionais",
            "Regras gerais",
            "Alertas",
        ]
    )

    with tabs[0]:
        edited = st.data_editor(
            st.session_state["result_editor"],
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="activation_editor_v4",
            column_config={
                "supplier_website": st.column_config.LinkColumn(
                    "Site do fornecedor"
                ),
                "base_price_formatted": st.column_config.TextColumn(
                    "Valor-base"
                ),
                "additional_costs_total_formatted":
                    st.column_config.TextColumn("Adicionais"),
                "estimated_total_formatted":
                    st.column_config.TextColumn(
                        "Total estimado derivado"
                    ),
            },
        )
        st.session_state["result_editor"] = edited
        technical = normalize_editor_activations(edited)

    with tabs[1]:
        _source_image_tab(records, docs, "solução")

    with tabs[2]:
        edited_suppliers = st.data_editor(
            suppliers,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="supplier_editor_activation_v4",
            column_config={
                "website_url": st.column_config.LinkColumn("Site"),
                "instagram_url": st.column_config.LinkColumn(
                    "Instagram"
                ),
                "linkedin_url": st.column_config.LinkColumn(
                    "LinkedIn"
                ),
            },
        )
        suppliers = edited_suppliers

    with tabs[3]:
        st.dataframe(costs, use_container_width=True)
    with tabs[4]:
        st.dataframe(rules, use_container_width=True)
    with tabs[5]:
        if alerts.empty:
            st.success("Nenhum alerta adicional.")
        else:
            st.dataframe(alerts, use_container_width=True)

    classification_df = (
        classification_dataframe(classification)
        if classification
        else pd.DataFrame()
    )
    xlsx = to_xlsx_bytes(
        {
            "Soluções": edited,
            "Dados técnicos": technical,
            "Fornecedores": suppliers,
            "Custos adicionais": costs,
            "Regras gerais": rules,
            "Alertas": alerts,
            "Classificação": classification_df,
        }
    )
    d1, d2 = st.columns(2)
    d1.download_button(
        "Baixar Excel",
        xlsx,
        "base_solucoes_ativacoes.xlsx",
        use_container_width=True,
    )
    d2.download_button(
        "Baixar JSON",
        activation_json_bytes(
            technical,
            costs,
            rules,
            alerts,
            suppliers,
            classification,
        ),
        "base_solucoes_ativacoes.json",
        use_container_width=True,
    )



if result_type == "venue":
    st.divider()
    st.header("Base de locais e espaços")

    records = st.session_state["result_records"]
    rules = st.session_state["result_rules"]
    alerts = st.session_state["result_alerts"]
    contacts = st.session_state["result_contacts"]

    tabs = st.tabs(
        [
            "Locais",
            "Imagem / fonte",
            "Contatos",
            "Regras gerais",
            "Alertas",
        ]
    )

    with tabs[0]:
        edited = st.data_editor(
            st.session_state["result_editor"],
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="venue_editor_v5",
            column_config={
                "contact_website": st.column_config.LinkColumn(
                    "Site do local"
                ),
                "map_url": st.column_config.LinkColumn(
                    "Mapa"
                ),
                "base_price_formatted": st.column_config.TextColumn(
                    "Valor-base"
                ),
                "price_min_formatted": st.column_config.TextColumn(
                    "Valor mínimo"
                ),
                "price_max_formatted": st.column_config.TextColumn(
                    "Valor máximo"
                ),
                "standing_capacity_formatted":
                    st.column_config.TextColumn(
                        "Capacidade em pé"
                    ),
                "seated_capacity_formatted":
                    st.column_config.TextColumn(
                        "Capacidade sentada"
                    ),
                "auditorium_capacity_formatted":
                    st.column_config.TextColumn(
                        "Capacidade auditório"
                    ),
                "total_area_sqm_formatted":
                    st.column_config.TextColumn(
                        "Área total (m²)"
                    ),
            },
        )
        st.session_state["result_editor"] = edited
        technical = normalize_editor_venues(edited)

    with tabs[1]:
        _source_image_tab(records, docs, "local")

    with tabs[2]:
        edited_contacts = st.data_editor(
            contacts,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="venue_contacts_editor_v5",
            column_config={
                "website_url": st.column_config.LinkColumn("Site"),
                "instagram_url": st.column_config.LinkColumn(
                    "Instagram"
                ),
                "linkedin_url": st.column_config.LinkColumn(
                    "LinkedIn"
                ),
            },
        )
        contacts = edited_contacts

    with tabs[3]:
        st.dataframe(rules, use_container_width=True)

    with tabs[4]:
        if alerts.empty:
            st.success("Nenhum alerta adicional.")
        else:
            st.dataframe(alerts, use_container_width=True)

    classification_df = (
        classification_dataframe(classification)
        if classification
        else pd.DataFrame()
    )

    xlsx = to_xlsx_bytes(
        {
            "Locais": edited,
            "Dados técnicos": technical,
            "Contatos": contacts,
            "Regras gerais": rules,
            "Alertas": alerts,
            "Classificação": classification_df,
        }
    )

    d1, d2 = st.columns(2)

    d1.download_button(
        "Baixar Excel",
        xlsx,
        "base_locais_espacos.xlsx",
        use_container_width=True,
    )

    d2.download_button(
        "Baixar JSON",
        venue_json_bytes(
            technical,
            rules,
            alerts,
            contacts,
            classification,
        ),
        "base_locais_espacos.json",
        use_container_width=True,
    )


if result_type == "briefing":
    st.divider()
    st.header("Base de projetos e briefings")
    briefing = st.session_state["result_briefing"]
    df = briefing_dataframe(briefing)
    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
    )
    xlsx = to_xlsx_bytes({"Briefing": edited})
    d1, d2 = st.columns(2)
    d1.download_button(
        "Baixar Excel",
        xlsx,
        "briefing_estruturado.xlsx",
        use_container_width=True,
    )
    d2.download_button(
        "Baixar JSON",
        briefing_json_bytes(briefing, classification),
        "briefing_estruturado.json",
        use_container_width=True,
    )
