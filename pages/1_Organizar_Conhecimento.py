from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from coverage_diagnostic import (
    diagnose_coverage,
    diagnostic_dataframe,
)
from coverage_diagnostic_ui import render_coverage_diagnostic

from runtime_ui import report_service_error, require_app_access
from enrichment_engine import STRATEGY_LABELS

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
from supabase_db import (
    get_supabase_client,
    save_activations,
    save_briefing,
    save_catalog,
    save_venues,
)


st.set_page_config(
    page_title="NAVE by VOE | Upload de Conhecimento",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Upload de Conhecimento",
    "Envie documentos para estruturar brindes, soluções, locais "
    "e projetos na base da NAVE.",
)

try:
    api_key = st.secrets.get(
        "GEMINI_API_KEY",
        os.getenv("GEMINI_API_KEY", ""),
    )
    model = st.session_state.get(
        "nave_model",
        st.secrets.get(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        ),
    )
    supabase_url = st.secrets.get(
        "SUPABASE_URL",
        os.getenv("SUPABASE_URL", ""),
    )
    supabase_secret_key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get(
            "SUPABASE_SERVICE_ROLE_KEY",
            os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        ),
    )
except Exception:
    api_key = os.getenv("GEMINI_API_KEY", "")
    model = st.session_state.get(
        "nave_model",
        os.getenv(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        ),
    )
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_secret_key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

if supabase_url and supabase_secret_key:
    try:
        database_client = get_supabase_client(
            supabase_url,
            supabase_secret_key,
        )
    except Exception:
        database_client = None
else:
    database_client = None

if not api_key:
    st.warning(
        "O serviço de leitura ainda não está configurado. "
        "Consulte a área de Administração."
    )

if database_client is None:
    st.warning(
        "A base de conhecimento ainda não está disponível. "
        "Consulte a área de Administração."
    )

mode_label = st.radio(
    "O que deseja enviar?",
    [
        "Identificar automaticamente",
        "Brindes / produtos",
        "Soluções / ativações",
        "Locais / espaços",
        "Briefing / projeto",
    ],
    horizontal=True,
)

mode_map = {
    "Identificar automaticamente": "auto",
    "Brindes / produtos": "catalog",
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

start_page, end_page_value, pages_per_batch = 1, 0, 6
if selected_mode != "briefing":
    analyze_entire_document = st.toggle(
        "Analisar o documento inteiro",
        value=True,
        help=(
            "A NAVE percorre todas as páginas automaticamente, "
            "dividindo o documento em lotes internos."
        ),
    )

    if analyze_entire_document:
        st.caption(
            "Todas as páginas serão analisadas. O documento será "
            "processado em vários lotes automáticos, sem precisar "
            "enviá-lo novamente."
        )
    else:
        range_col1, range_col2 = st.columns(2)
        with range_col1:
            start_page = st.number_input(
                "Página inicial",
                min_value=1,
                value=1,
            )
        with range_col2:
            end_page_value = st.number_input(
                "Página final",
                min_value=1,
                value=8,
            )

    with st.expander(
        "Configurações avançadas de processamento",
        expanded=False,
    ):
        pages_per_batch = st.slider(
            "Páginas processadas por lote",
            min_value=1,
            max_value=8,
            value=6,
            help=(
                "Este número não limita o total de páginas. "
                "Ele define apenas quantas páginas são enviadas "
                "em cada etapa interna da leitura."
            ),
        )
        st.caption(
            "Exemplo: um PDF com 40 páginas será analisado em "
            "vários lotes consecutivos até chegar ao final."
        )

run = st.button(
    "Fazer Upload",
    type="primary",
    use_container_width=True,
)


def _clear():
    for key in list(st.session_state.keys()):
        if key.startswith("result_") or key in (
            "classification",
            "source_documents",
            "coverage_diagnostic",
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
        st.info("Nenhum item disponível.")
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
        if str(source_file or "").lower().endswith(".txt"):
            st.warning(
                "Este item foi criado a partir de texto colado ou e-mail, "
                "sem uma página visual de origem. Para exibir imagens, envie "
                "também o PDF ou PowerPoint original que contenha as fotos."
            )
        else:
            st.warning(
                "O item não possui página de origem. "
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


def _classification_dict():
    item = st.session_state.get("classification")
    payload = item.model_dump() if item else {}

    diagnostic = st.session_state.get(
        "coverage_diagnostic"
    )
    if diagnostic:
        payload["coverage_diagnostic"] = diagnostic

    return payload or None


def _create_coverage_diagnostic(
    *,
    route: str,
    structured_output,
    docs: list[InputDocument],
):
    with st.spinner(
        "Comparando a fonte com o conteúdo estruturado..."
    ):
        diagnostic = diagnose_coverage(
            docs,
            mode=route,
            structured_output=structured_output,
            api_key=api_key,
            model=model,
        )

    st.session_state[
        "coverage_diagnostic"
    ] = diagnostic.model_dump()


def _database_save_controls(
    *,
    key: str,
    label: str,
    save_action,
    allow_enrichment: bool = True,
    allow_visuals: bool = True,
):
    st.divider()
    st.subheader("Adicionar à base de conhecimento")

    if database_client is None:
        st.info(
            "A base de conhecimento está indisponível. "
            "Consulte a área de Administração."
        )
        return

    label_to_strategy = {
        label: strategy
        for strategy, label in STRATEGY_LABELS.items()
    }

    if allow_visuals:
        auto_extract_visuals = st.checkbox(
            "Extrair e associar imagens automaticamente dos PDFs",
            value=True,
            key=f"auto_visuals_{key}",
            help=(
                "A NAVE tenta recortar a imagem representativa de cada item "
                "e adicioná-la ao acervo. Recortes ambíguos ficam pendentes "
                "para revisão manual."
            ),
        )
        if auto_extract_visuals:
            st.caption(
                "A primeira imagem associada ao item será usada como capa. "
                "A NAVE evita adicionar novamente imagens idênticas."
            )
    else:
        auto_extract_visuals = False

    if allow_enrichment:
        selected_label = st.selectbox(
            "Quando a NAVE encontrar um item já cadastrado",
            options=list(label_to_strategy.keys()),
            index=0,
            key=f"existing_strategy_{key}",
        )
        existing_strategy = label_to_strategy[selected_label]

        if existing_strategy == "enrich_safe":
            st.caption(
                "A NAVE preenche campos vazios, une listas e mantém "
                "o valor atual quando encontra uma diferença. "
                "As diferenças ficam registradas para revisão."
            )
        elif existing_strategy == "prefer_new":
            st.warning(
                "As informações diferentes do novo arquivo passarão "
                "a substituir os valores atuais. O histórico anterior "
                "continuará registrado."
            )
        else:
            st.caption(
                "Itens já cadastrados serão mantidos sem alteração. "
                "Somente registros novos serão adicionados."
            )
    else:
        existing_strategy = "enrich_safe"

    if st.button(
        label,
        type="primary",
        use_container_width=True,
        key=f"save_database_{key}",
    ):
        try:
            with st.spinner(
                "Comparando e atualizando a base..."
            ):
                result = save_action(
                    existing_strategy,
                    auto_extract_visuals,
                )

            st.session_state[
                f"database_result_{key}"
            ] = result
            st.success(
                "Base de conhecimento processada."
            )

        except Exception as exc:
            report_service_error(
                "salvamento e enriquecimento da base",
                user_message=(
                    "Não foi possível processar as informações "
                    "na base neste momento."
                ),
                exception=exc,
            )

    result = st.session_state.get(
        f"database_result_{key}"
    )
    if not result:
        return

    metric1, metric2, metric3, metric4, metric5 = st.columns(
        5
    )
    metric1.metric(
        "Itens novos",
        result.get("records_inserted", 0),
    )
    metric2.metric(
        "Itens enriquecidos",
        result.get("records_enriched", 0),
    )
    metric3.metric(
        "Com diferenças",
        result.get(
            "records_with_conflicts",
            0,
        ),
    )
    metric4.metric(
        "Sem alteração",
        result.get("duplicates_skipped", 0),
    )
    metric5.metric(
        "Campos preenchidos",
        result.get("fields_filled", 0),
    )

    if allow_visuals:
        visual1, visual2, visual3 = st.columns(3)
        visual1.metric(
            "Imagens adicionadas",
            result.get("visual_assets_added", 0),
        )
        visual2.metric(
            "Imagens já existentes",
            result.get("visual_assets_duplicate", 0),
        )
        visual3.metric(
            "Recortes para revisar",
            result.get("visual_assets_pending", 0),
        )

        if result.get("visual_assets_pending", 0):
            st.info(
                "Algumas páginas não permitiram isolar a imagem com segurança. "
                "Esses itens podem receber a imagem manualmente na Base de conhecimento."
            )

    possible_duplicates = result.get(
        "possible_duplicate_records",
        0,
    )

    if possible_duplicates:
        st.warning(
            f"{possible_duplicates} item(ns) possuem nomes "
            "semelhantes a cadastros existentes e precisam "
            "de revisão antes de a base ser considerada limpa."
        )
        st.page_link(
            "pages/7_Revisar_Duplicidades.py",
            label="Revisar possíveis duplicidades",
            use_container_width=True,
        )

    if result.get("fields_updated", 0):
        st.caption(
            f"Campos substituídos pelo arquivo mais recente: "
            f"{result.get('fields_updated', 0)}."
        )

    conflicts = result.get("conflicts") or []

    if conflicts:
        st.warning(
            "A NAVE encontrou informações diferentes entre "
            "o cadastro e o novo material."
        )

        conflict_df = pd.DataFrame(conflicts).rename(
            columns={
                "item_name": "Item",
                "field": "Campo",
                "existing_value": "Valor atual",
                "incoming_value": "Novo valor",
                "action": "Tratamento",
            }
        )

        treatment_labels = {
            "kept_existing_value": (
                "Valor atual mantido"
            ),
            "updated_with_new_value": (
                "Atualizado com o novo valor"
            ),
        }
        conflict_df["Tratamento"] = (
            conflict_df["Tratamento"]
            .map(treatment_labels)
            .fillna(conflict_df["Tratamento"])
        )

        with st.expander(
            "Ver diferenças encontradas",
            expanded=True,
        ):
            st.dataframe(
                conflict_df[
                    [
                        "Item",
                        "Campo",
                        "Valor atual",
                        "Novo valor",
                        "Tratamento",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )


if run:
    _clear()
    if not uploaded_files and not pasted_text.strip():
        st.error("Envie um arquivo ou cole um texto.")
        st.stop()
    if not api_key:
        st.error(
            "O serviço de leitura não está disponível. "
            "Consulte a área de Administração."
        )
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
            _create_coverage_diagnostic(
                route="catalog",
                structured_output={
                    "products": products,
                    "suppliers": suppliers,
                    "global_rules": rules,
                    "alerts": alerts,
                },
                docs=docs,
            )

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
            _create_coverage_diagnostic(
                route="activation",
                structured_output={
                    "solutions": records,
                    "costs": costs,
                    "suppliers": suppliers,
                    "global_rules": rules,
                    "alerts": alerts,
                },
                docs=docs,
            )

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
            _create_coverage_diagnostic(
                route="venue",
                structured_output={
                    "venues": records,
                    "contacts": contacts,
                    "global_rules": rules,
                    "alerts": alerts,
                },
                docs=docs,
            )

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
            _create_coverage_diagnostic(
                route="briefing",
                structured_output=briefing,
                docs=docs,
            )

    except Exception as exc:
        report_service_error(
            "organização de documentos",
            user_message=(
                "Não foi possível concluir a organização "
                "destes documentos."
            ),
            exception=exc,
        )


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
diagnostic = st.session_state.get("coverage_diagnostic")

if result_type and diagnostic:
    st.divider()
    render_coverage_diagnostic(
        diagnostic,
        heading="Diagnóstico de cobertura do upload",
        expanded=True,
        download_key=f"upload_{result_type}",
    )

if result_type == "catalog":
    st.divider()
    st.header("Base de brindes")

    records = st.session_state["result_records"]
    rules = st.session_state["result_rules"]
    alerts = st.session_state["result_alerts"]
    suppliers = st.session_state["result_suppliers"]

    if records.empty:
        st.error(
            "A triagem identificou um orçamento de ativação, mas nenhuma "
            "solução foi transformada em linha. Esta versão possui uma "
            "extração de segurança automática; reprocesse o arquivo após "
            "a atualização. Se ainda ocorrer, selecione manualmente "
            "'Soluções / ativações'."
        )
        st.stop()

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
                "visual_crop": None,
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
            "Diagnóstico": diagnostic_dataframe(diagnostic),
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
        "Baixar dados estruturados",
        catalog_json_bytes(
            technical,
            rules,
            alerts,
            suppliers,
            _classification_dict(),
        ),
        "base_brindes_estruturada.json",
        use_container_width=True,
    )

    _database_save_controls(
        key="catalog",
        label="Adicionar brindes à base",
        save_action=lambda strategy, auto_visuals: save_catalog(
            database_client,
            products_df=technical,
            suppliers_df=suppliers,
            rules_df=rules,
            alerts_df=alerts,
            classification=_classification_dict(),
            source_documents=docs,
            existing_strategy=strategy,
            auto_extract_visuals=auto_visuals,
        ),
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
                "visual_crop": None,
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
            "Diagnóstico": diagnostic_dataframe(diagnostic),
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
        "Baixar dados estruturados",
        activation_json_bytes(
            technical,
            costs,
            rules,
            alerts,
            suppliers,
            _classification_dict(),
        ),
        "base_solucoes_ativacoes.json",
        use_container_width=True,
    )

    _database_save_controls(
        key="activation",
        label="Adicionar soluções à base",
        save_action=lambda strategy, auto_visuals: save_activations(
            database_client,
            solutions_df=technical,
            costs_df=costs,
            suppliers_df=suppliers,
            rules_df=rules,
            alerts_df=alerts,
            classification=_classification_dict(),
            source_documents=docs,
            existing_strategy=strategy,
            auto_extract_visuals=auto_visuals,
        ),
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
                "visual_crop": None,
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
            "Diagnóstico": diagnostic_dataframe(diagnostic),
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
        "Baixar dados estruturados",
        venue_json_bytes(
            technical,
            rules,
            alerts,
            contacts,
            _classification_dict(),
        ),
        "base_locais_espacos.json",
        use_container_width=True,
    )

    _database_save_controls(
        key="venue",
        label="Adicionar locais à base",
        save_action=lambda strategy, auto_visuals: save_venues(
            database_client,
            venues_df=technical,
            contacts_df=contacts,
            rules_df=rules,
            alerts_df=alerts,
            classification=_classification_dict(),
            source_documents=docs,
            existing_strategy=strategy,
            auto_extract_visuals=auto_visuals,
        ),
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
    xlsx = to_xlsx_bytes(
        {
            "Briefing": edited,
            "Diagnóstico": diagnostic_dataframe(diagnostic),
        }
    )
    d1, d2 = st.columns(2)
    d1.download_button(
        "Baixar Excel",
        xlsx,
        "briefing_estruturado.xlsx",
        use_container_width=True,
    )
    d2.download_button(
        "Baixar dados estruturados",
        briefing_json_bytes(
            briefing,
            _classification_dict(),
        ),
        "briefing_estruturado.json",
        use_container_width=True,
    )

    _database_save_controls(
        key="briefing",
        label="Adicionar briefing e projeto à base",
        save_action=lambda strategy, auto_visuals: save_briefing(
            database_client,
            briefing=briefing.model_dump(),
            classification=_classification_dict(),
            source_documents=docs,
        ),
        allow_enrichment=False,
        allow_visuals=False,
    )
