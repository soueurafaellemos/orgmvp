from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from gemini_extractor import extract_briefing, extract_catalog
from document_io import prepare_documents
from exporters import (
    briefing_dataframe,
    briefing_json_bytes,
    catalog_json_bytes,
    merge_catalog_batches,
    normalize_editor_products,
    prepare_products_for_editor,
    to_xlsx_bytes,
)


st.set_page_config(
    page_title="Organizador de Insumos para Brindes",
    page_icon="🧩",
    layout="wide",
)

st.title("Organizador de insumos para brindes")
st.caption(
    "Envie materiais desorganizados, revise a extração e exporte uma base "
    "padronizada para alimentar o recomendador."
)

with st.sidebar:
    st.header("Configuração Gemini")

    default_key = ""
    try:
        default_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        default_key = os.getenv("GEMINI_API_KEY", "")

    api_key = st.text_input(
        "Gemini API key",
        value=default_key,
        type="password",
        help="A chave fica apenas na sessão atual. Em produção, use secrets.",
    )
    model = st.selectbox(
        "Modelo",
        options=[
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ],
        index=0,
        help=(
            "Comece com Gemini 3.5 Flash. O Flash-Lite é mais econômico, "
            "mas pode ser menos preciso em catálogos muito visuais."
        ),
    )

    st.warning(
        "Na faixa gratuita, os dados enviados podem ser usados pelo Google "
        "para melhorar produtos. Use materiais não confidenciais nesta fase."
    )

mode = st.radio(
    "O que você quer organizar?",
    ["Catálogo de brindes", "Briefing / projeto"],
    horizontal=True,
)

uploaded_files = st.file_uploader(
    "Arquivos",
    type=[
        "pdf",
        "txt",
        "md",
        "json",
        "html",
        "xml",
        "doc",
        "docx",
        "rtf",
        "odt",
        "ppt",
        "pptx",
        "csv",
        "tsv",
        "xls",
        "xlsx",
        "eml",
    ],
    accept_multiple_files=True,
    help=(
        "Para e-mails, exporte como .eml ou cole o texto no campo abaixo. "
        "Anexos compatíveis dentro do .eml também são lidos."
    ),
)

pasted_text = st.text_area(
    "Texto colado, e-mail ou observações adicionais",
    height=160,
    placeholder="Cole aqui o corpo de um e-mail, briefing ou informações soltas...",
)

if mode == "Catálogo de brindes":
    st.subheader("Controle de processamento do PDF")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_page = st.number_input("Página inicial", min_value=1, value=1, step=1)
    with col2:
        end_page_value = st.number_input(
            "Página final (0 = até o fim)",
            min_value=0,
            value=0,
            step=1,
        )
    with col3:
        pages_per_batch = st.slider(
            "Páginas por lote",
            min_value=1,
            max_value=10,
            value=4,
            help="Lotes menores costumam separar melhor produtos e páginas.",
        )

    st.info(
        "Para o primeiro teste, processe algumas páginas de produto. "
        "Depois amplie o intervalo para o catálogo inteiro."
    )

run = st.button("Organizar informações", type="primary", use_container_width=True)

if run:
    if not uploaded_files and not pasted_text.strip():
        st.error("Envie ao menos um arquivo ou cole algum texto.")
        st.stop()

    if not api_key:
        st.error("Informe uma Gemini API key.")
        st.stop()

    raw_uploaded = [
        (file.name, file.getvalue(), file.type or None)
        for file in uploaded_files
    ]

    try:
        docs = prepare_documents(raw_uploaded)
    except Exception as exc:
        st.error(f"Não foi possível preparar os arquivos: {exc}")
        st.stop()

    try:
        if mode == "Catálogo de brindes":
            if pasted_text.strip():
                docs.extend(
                    prepare_documents(
                        [
                            (
                                "observacoes_catalogo.txt",
                                pasted_text.encode("utf-8"),
                                "text/plain",
                            )
                        ]
                    )
                )

            progress = st.progress(0.0)
            status = st.empty()

            def update_progress(done: int, total: int, message: str):
                progress.progress(done / total if total else 1.0)
                status.write(message)

            batches = extract_catalog(
                docs,
                api_key=api_key,
                model=model,
                pages_per_batch=int(pages_per_batch),
                start_page=int(start_page),
                end_page=(
                    None if int(end_page_value) == 0 else int(end_page_value)
                ),
                progress_callback=update_progress,
            )

            products_df, rules_df, warnings_df = merge_catalog_batches(batches)
            st.session_state["catalog_batches"] = batches
            st.session_state["products_df"] = products_df
            st.session_state["products_editor_df"] = (
                prepare_products_for_editor(products_df)
            )
            st.session_state["rules_df"] = rules_df
            st.session_state["warnings_df"] = warnings_df

        else:
            briefing = extract_briefing(
                docs,
                pasted_text=pasted_text,
                api_key=api_key,
                model=model,
            )
            st.session_state["briefing"] = briefing

    except Exception as exc:
        st.exception(exc)

if mode == "Catálogo de brindes" and "products_df" in st.session_state:
    st.divider()
    st.header("Resultado estruturado")

    products_df = st.session_state["products_df"]
    rules_df = st.session_state["rules_df"]
    warnings_df = st.session_state["warnings_df"]
    batches = st.session_state["catalog_batches"]

    tab1, tab2, tab3 = st.tabs(["Produtos", "Regras gerais", "Alertas"])

    with tab1:
        st.write(
            f"**{len(products_df)} registros únicos encontrados.** "
            "Revise os dados antes de importar no MVP."
        )

        missing_price_count = int(
            products_df["price_alert"]
            .astype(str)
            .str.contains("ALERTA", na=False)
            .sum()
        )
        price_quote_count = int(
            products_df["price_alert"]
            .astype(str)
            .str.contains("ATENÇÃO", na=False)
            .sum()
        )
        missing_supplier_count = int(
            products_df["supplier_alert"]
            .astype(str)
            .str.contains("ALERTA", na=False)
            .sum()
        )

        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("Sem preço informado", missing_price_count)
        metric2.metric("Preço sob consulta", price_quote_count)
        metric3.metric("Sem fornecedor", missing_supplier_count)

        if missing_price_count:
            st.warning(
                f"{missing_price_count} produto(s) não possuem preço no "
                "material enviado. A coluna foi mantida vazia e um alerta "
                "foi criado para futura cotação."
            )

        if missing_supplier_count:
            st.warning(
                f"{missing_supplier_count} produto(s) estão sem fornecedor "
                "identificado. O campo deve ser complementado na revisão."
            )
        editor_source = st.session_state.get(
            "products_editor_df",
            prepare_products_for_editor(products_df),
        )

        edited_products = st.data_editor(
            editor_source,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="products_editor",
            column_config={
                "unit_price_formatted": st.column_config.TextColumn(
                    "Valor unitário",
                    help="Use o padrão brasileiro, por exemplo: R$ 32.000,00",
                    width="medium",
                ),
                "price_min_formatted": st.column_config.TextColumn(
                    "Valor mínimo",
                    help="Use o padrão brasileiro, por exemplo: R$ 25.000,00",
                    width="medium",
                ),
                "price_max_formatted": st.column_config.TextColumn(
                    "Valor máximo",
                    help="Use o padrão brasileiro, por exemplo: R$ 40.000,00",
                    width="medium",
                ),
                "price_reference_qty_formatted": st.column_config.TextColumn(
                    "Qtd. de referência",
                    help="Exemplo: 5.000",
                    width="small",
                ),
                "min_order_qty_formatted": st.column_config.TextColumn(
                    "Pedido mínimo",
                    help="Exemplo: 5.000",
                    width="small",
                ),
            },
        )
        st.session_state["products_editor_df"] = edited_products
        st.session_state["edited_products_df"] = (
            normalize_editor_products(edited_products)
        )

    with tab2:
        st.dataframe(rules_df, use_container_width=True, hide_index=True)

    with tab3:
        if warnings_df.empty:
            st.success("Nenhum alerta adicional informado pelo agente.")
        else:
            st.dataframe(warnings_df, use_container_width=True, hide_index=True)

    final_products = st.session_state.get(
        "edited_products_df",
        products_df,
    )
    review_products = prepare_products_for_editor(final_products)

    xlsx = to_xlsx_bytes(
        {
            "Produtos": review_products,
            "Dados técnicos": final_products,
            "Regras gerais": rules_df,
            "Alertas": warnings_df,
        }
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Baixar Excel",
            data=xlsx,
            file_name="catalogo_estruturado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "Baixar CSV",
            data=final_products.to_csv(index=False).encode("utf-8-sig"),
            file_name="produtos_estruturados.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col3:
        st.download_button(
            "Baixar JSON técnico",
            data=catalog_json_bytes(
                final_products,
                rules_df,
                warnings_df,
            ),
            file_name="catalogo_estruturado.json",
            mime="application/json",
            use_container_width=True,
        )

if mode == "Briefing / projeto" and "briefing" in st.session_state:
    st.divider()
    st.header("Briefing consolidado")

    briefing = st.session_state["briefing"]
    briefing_df = briefing_dataframe(briefing)
    edited_briefing = st.data_editor(
        briefing_df,
        use_container_width=True,
        hide_index=True,
        key="briefing_editor",
    )

    xlsx = to_xlsx_bytes({"Briefing": edited_briefing})

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Baixar briefing em Excel",
            data=xlsx,
            file_name="briefing_estruturado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "Baixar briefing em JSON",
            data=briefing_json_bytes(briefing),
            file_name="briefing_estruturado.json",
            mime="application/json",
            use_container_width=True,
        )
