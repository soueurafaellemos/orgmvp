from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_batch_ingestion import (
    LABEL_TO_ROLE,
    ROLE_LABELS,
    TARGET_SECTIONS,
    ProjectBatchError,
    fetch_projects,
    infer_project_name,
    prepare_documents,
    rank_project_candidates,
    save_project_bundle,
)
from project_bundle_materializer import reprocess_project_semantically

st.set_page_config(
    page_title="Importar projeto completo | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)

enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Importar projeto completo",
    "Envie briefing, proposta, orçamento, planilha, apresentação, feedbacks e relatórios em um único lote. A NAVE organiza os papéis, evita duplicidade de projeto e prepara cada arquivo para a área correta do workspace.",
    eyebrow="NAVE by VOE · V28.5.0",
)

client = get_nave_client()

# Migrações/reprocessamentos são explícitos. Abrir a página nunca altera dados.
# A rotina legada continua disponível somente quando o usuário solicita correção.

with st.expander("Corrigir um projeto importado por uma versão anterior da V28", expanded=False):
    st.caption(
        "Use quando um projeto já importado precisar de uma nova leitura especializada. "
        "A NAVE preserva os masters e a materialização válida anterior; a nova leitura só substitui a anterior depois de passar pelos gates de cobertura e qualidade."
    )
    try:
        repair_projects = fetch_projects(client)
    except Exception as exc:
        repair_projects = []
        st.warning(f"Não foi possível consultar os projetos agora: {exc}")
    if repair_projects:
        repair_options = {
            f"{row.get('project_name') or 'Projeto sem nome'} · {row.get('client_brand') or 'cliente não informado'}": str(row.get('id'))
            for row in repair_projects if row.get('id')
        }
        repair_label = st.selectbox(
            "Projeto a reprocessar",
            list(repair_options.keys()),
            key="v2815_reprocess_project",
        )
        confirm_reprocess = st.checkbox(
            "Confirmo o reprocessamento sem alterar arquivos originais nem conteúdo manual.",
            key="v2815_reprocess_confirm",
        )
        if st.button(
            "Reprocessar conteúdo com leitura especializada",
            type="primary",
            width="stretch",
            disabled=not confirm_reprocess,
            key="v2815_reprocess_button",
        ):
            with st.spinner("Reprocessando briefing, apresentação e orçamento já preservados..."):
                outcome = reprocess_project_semantically(client, repair_options[repair_label])
            counts = outcome.get("workspace_counts") or {}
            if outcome.get("errors") or outcome.get("incomplete"):
                st.warning(
                    f"Reprocessamento concluído com diagnóstico: {outcome.get('processed', 0)} arquivo(s) materializado(s), "
                    f"{outcome.get('errors', 0)} erro(s). A NAVE não considera a correção concluída enquanto briefing/apresentação esperados continuarem zerados."
                )
            else:
                st.success(f"{outcome.get('processed', 0)} arquivo(s) reprocessado(s) com a leitura especializada da V28.5.0.")
                st.session_state["nave_project_hub_focus_id"] = repair_options[repair_label]

            if counts:
                metric_cols = st.columns(5)
                metric_cols[0].metric("Briefings", counts.get("briefings", 0))
                metric_cols[1].metric("Apresentações", counts.get("presentations", 0))
                metric_cols[2].metric("Conteúdos", counts.get("contents", 0))
                metric_cols[3].metric("Custos", counts.get("cost_documents", 0))
                metric_cols[4].metric("Feedbacks", counts.get("feedbacks", 0))

            diagnostic_rows = []
            for item in outcome.get("results") or []:
                created = item.get("created") or {}
                diagnostic_rows.append({
                    "Arquivo": item.get("file_name") or item.get("source_file_id"),
                    "Papel anterior": item.get("role_before"),
                    "Papel resolvido": item.get("role_after") or item.get("role"),
                    "Status": item.get("status"),
                    "Criado no workspace": ", ".join(f"{key}: {value}" for key, value in created.items()) or "—",
                    "Observação": " | ".join(str(w) for w in (item.get("warnings") or [])[:3]) or "—",
                })
            if diagnostic_rows:
                with st.expander("Diagnóstico arquivo por arquivo", expanded=bool(outcome.get("errors") or outcome.get("incomplete"))):
                    st.dataframe(pd.DataFrame(diagnostic_rows), hide_index=True, width="stretch")

            cross = outcome.get("cross_source_intelligence") or {}
            if cross and str(cross.get("status") or "").startswith("completed"):
                with st.expander("Intelligence Graph · conexões entre arquivos", expanded=False):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Entidades unificadas", int(cross.get("entities_merged") or 0))
                    c2.metric("Solução ↔ custo", int(cross.get("cost_links") or 0))
                    c3.metric("Evidências de execução", int(cross.get("execution_claims") or 0))
                    c4.metric("Revisões sugeridas", int(cross.get("resolution_reviews") or 0) + int(cross.get("cost_link_reviews") or 0))
                    st.caption(
                        "A V28.5.0 preserva conhecimento anterior e transforma a inteligência consolidada em uma experiência mais executiva, visual e rigorosa, sem expor linguagem de backend. "
                        "Vínculos ambíguos não são forçados: viram revisão/finding auditável."
                    )

            warnings = list(dict.fromkeys(str(w) for w in (outcome.get("warnings") or []) if str(w).strip()))
            if warnings:
                with st.expander("Avisos técnicos do reprocessamento", expanded=bool(outcome.get("errors") or outcome.get("incomplete"))):
                    for warning in warnings[:30]:
                        st.caption("• " + warning)

            st.page_link("pages/4_Historico_de_Projetos.py", label="Abrir projeto reprocessado")

st.markdown("### 1. Arquivos do projeto")
st.caption(
    "Você pode enviar vários arquivos de uma vez. Nesta etapa a NAVE lê sinais do nome e do conteúdo, sugere o papel de cada documento e sempre permite revisar antes de salvar."
)

uploaded = st.file_uploader(
    "Documentos do projeto",
    type=["pdf", "docx", "pptx", "ppt", "xlsx", "xlsm", "xls", "csv", "txt", "md", "eml", "msg", "jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Limite da NAVE: 300 MB por arquivo. Prints e imagens aceitos: JPG, JPEG, PNG e WEBP.",
)

current_signature = tuple(
    (item.name, getattr(item, "size", None), getattr(item, "type", None))
    for item in (uploaded or [])
)

if current_signature != st.session_state.get("v281_upload_signature"):
    for state_key in (
        "v281_documents",
        "v281_review",
        "v281_project_name",
        "v281_project_name_input",
        "v281_client_brand",
        "v281_event_name",
        "v281_role_editor",
        "v281_destination",
    ):
        st.session_state.pop(state_key, None)
    st.session_state["v281_upload_signature"] = current_signature

if uploaded and st.button("Analisar conjunto de documentos", type="primary", width="stretch"):
    with st.spinner("Lendo e organizando o conjunto de documentos..."):
        try:
            source = []
            for item in uploaded:
                data = item.getvalue()
                source.append((item.name, data, getattr(item, "type", None)))
            documents = prepare_documents(source)
            st.session_state["v281_documents"] = documents
            st.session_state["v281_project_name"] = infer_project_name(documents)
            st.session_state["v281_review"] = None
        except ProjectBatchError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"A NAVE não conseguiu analisar o conjunto. Detalhe técnico: {exc}")

documents = st.session_state.get("v281_documents") or []

if documents:
    st.success(f"{len(documents)} arquivo(s) lido(s). Revise a organização antes de importar.")

    st.markdown("### 2. Revisar o papel de cada documento")
    review_rows = []
    for document in documents:
        review_rows.append({
            "Incluir": True,
            "Arquivo": document.name,
            "Papel do documento": document.role_label,
            "Confiança": f"{round(document.role_confidence * 100)}%",
            "Sinais encontrados": "; ".join(document.role_reasons) or "revisão manual",
            "Destino no workspace": " · ".join(document.target_sections),
            "_sha256": document.sha256,
        })
    base_review = pd.DataFrame(review_rows)

    edited = st.data_editor(
        base_review,
        hide_index=True,
        width="stretch",
        disabled=["Arquivo", "Confiança", "Sinais encontrados", "Destino no workspace", "_sha256"],
        column_config={
            "Incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
            "Arquivo": st.column_config.TextColumn("Arquivo", width="large"),
            "Papel do documento": st.column_config.SelectboxColumn(
                "Papel do documento",
                options=list(ROLE_LABELS.values()),
                required=True,
                width="medium",
            ),
            "Confiança": st.column_config.TextColumn("Confiança", width="small"),
            "Sinais encontrados": st.column_config.TextColumn("Sinais encontrados", width="large"),
            "Destino no workspace": st.column_config.TextColumn("Destino no workspace", width="large"),
            "_sha256": None,
        },
        key="v281_role_editor",
    )
    st.caption(
        "Ao alterar o papel do documento, o destino definitivo é recalculado no momento da importação. A coluna acima mostra o destino sugerido na análise inicial."
    )

    st.markdown("### 3. Identidade do projeto")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        project_name = st.text_input(
            "Nome do projeto",
            value=st.session_state.get("v281_project_name", ""),
            key="v281_project_name_input",
        )
    with c2:
        client_brand = st.text_input("Cliente / marca", key="v281_client_brand")
    with c3:
        event_name = st.text_input("Evento", key="v281_event_name")

    try:
        projects = fetch_projects(client)
    except Exception as exc:
        projects = []
        st.warning(f"A lista de projetos existentes não pôde ser consultada agora: {exc}")

    candidates = rank_project_candidates(
        projects,
        project_name=project_name,
        client_brand=client_brand,
        event_name=event_name,
        limit=5,
    )

    if candidates:
        st.markdown("#### Projetos existentes parecidos")
        candidate_rows = []
        for candidate in candidates:
            candidate_rows.append({
                "Projeto": candidate.project_name,
                "Cliente": candidate.client_brand or "",
                "Evento": candidate.event_name or "",
                "Confiança": candidate.confidence.capitalize(),
                "Aderência": f"{round(candidate.score * 100)}%",
                "Leitura": "; ".join(candidate.reasons) or "sem sinal adicional",
                "Conflitos": "; ".join(candidate.conflicts) or "—",
            })
        st.dataframe(pd.DataFrame(candidate_rows), hide_index=True, width="stretch")
        top = candidates[0]
        if top.confidence == "alta" and not top.conflicts:
            st.info(
                f"Correspondência forte encontrada: **{top.project_name}**. A NAVE não associa automaticamente: confirme o destino abaixo."
            )

    st.markdown("### 4. Destino")
    strong_match = bool(
        candidates
        and candidates[0].confidence == "alta"
        and not candidates[0].conflicts
    )
    destination = st.radio(
        "Este conjunto pertence a:",
        ["Um novo projeto", "Um projeto que já existe"],
        horizontal=True,
        index=1 if strong_match else 0,
        key="v281_destination",
    )

    force_new_confirmed = True
    if destination == "Um novo projeto" and strong_match:
        force_new_confirmed = st.checkbox(
            f"Confirmo criar um novo projeto mesmo com forte correspondência a **{candidates[0].project_name}**.",
            value=False,
            help="Esta confirmação existe para evitar duplicatas como projetos com o mesmo cliente, nome e edição.",
        )
        if not force_new_confirmed:
            st.caption(
                "A NAVE recomenda associar o lote ao projeto existente. O novo cadastro só será liberado após a confirmação acima."
            )

    existing_project_id = None
    selected_existing = None
    if destination == "Um projeto que já existe":
        if not projects:
            st.warning("Nenhum projeto existente está disponível para seleção.")
        else:
            project_options = []
            option_to_id = {}
            for row in projects:
                label = str(row.get("project_name") or "Projeto sem nome")
                project_client_label = str(row.get("client_brand") or "").strip()
                event = str(row.get("event_name") or "").strip()
                suffix = " · ".join(item for item in (project_client_label, event) if item)
                display = f"{label} — {suffix}" if suffix else label
                # Evita colisão visual sem mostrar UUID ao usuário.
                if display in option_to_id:
                    display = f"{display} · registro {len(project_options) + 1}"
                project_options.append(display)
                option_to_id[display] = str(row.get("id"))
            default_index = 0
            if candidates:
                candidate_id = candidates[0].project_id
                for index, option in enumerate(project_options):
                    if option_to_id[option] == candidate_id:
                        default_index = index
                        break
            selected_existing = st.selectbox(
                "Projeto existente",
                project_options,
                index=default_index,
            )
            existing_project_id = option_to_id.get(selected_existing)

    selected_rows = edited[edited["Incluir"] == True]  # noqa: E712
    include_sha256 = set(selected_rows["_sha256"].astype(str).tolist())
    role_overrides = {
        str(row["_sha256"]): LABEL_TO_ROLE.get(
            str(row["Papel do documento"]),
            "complementary_document",
        )
        for _, row in selected_rows.iterrows()
    }

    if include_sha256:
        destination_preview: dict[str, int] = {}
        for sha, role in role_overrides.items():
            for section in TARGET_SECTIONS.get(role, ("Documentos",)):
                destination_preview[section] = destination_preview.get(section, 0) + 1
        with st.expander("Ver distribuição prevista no workspace"):
            preview = pd.DataFrame([
                {"Área": section, "Arquivo(s) relacionado(s)": count}
                for section, count in destination_preview.items()
            ])
            st.dataframe(preview, hide_index=True, width="stretch")

    can_save = (
        bool(include_sha256)
        and bool(project_name.strip() or existing_project_id)
        and bool(force_new_confirmed)
    )
    if st.button(
        "Importar projeto completo",
        type="primary",
        width="stretch",
        disabled=not can_save,
    ):
        match_context = {}
        if candidates:
            top = candidates[0]
            match_context = {
                "top_candidate_project_id": top.project_id,
                "top_candidate_score": top.score,
                "top_candidate_confidence": top.confidence,
                "top_candidate_reasons": top.reasons,
                "top_candidate_conflicts": top.conflicts,
                "user_destination": destination,
            }
        with st.spinner("Preservando arquivos no Cloudflare R2 e criando o lote do projeto..."):
            try:
                result = save_project_bundle(
                    client,
                    documents=documents,
                    role_overrides=role_overrides,
                    include_sha256=include_sha256,
                    project_name=project_name,
                    client_brand=client_brand,
                    event_name=event_name,
                    existing_project_id=existing_project_id,
                    match_context=match_context,
                )
            except ProjectBatchError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"A importação não pôde ser concluída. Detalhe técnico: {exc}")
            else:
                st.session_state["v281_last_result"] = result
                workspace_ok = int(result.get("workspace_materialized") or 0)
                workspace_errors = int(result.get("workspace_errors") or 0)
                st.success(
                    f"Projeto importado: {result['documents_saved']} arquivo(s) preservado(s) e {workspace_ok} incorporado(s) ao workspace."
                )
                if result.get("duplicates_reused"):
                    st.info(
                        f"{result['duplicates_reused']} arquivo(s) já existiam no projeto e foram reaproveitados sem duplicar o arquivo físico."
                    )
                if workspace_errors:
                    st.warning(
                        f"{workspace_errors} arquivo(s) tiveram alguma etapa de incorporação incompleta. O original continua preservado para nova tentativa, sem perda do lote."
                    )
                cols = st.columns(4)
                cols[0].metric("Arquivos", result["documents_saved"])
                cols[1].metric("No workspace", workspace_ok)
                cols[2].metric("Reaproveitados", result.get("duplicates_reused", 0))
                cols[3].metric("Projeto", "Novo" if result.get("created_project") else "Existente")
                st.caption(
                    "Os masters ficam preservados no Cloudflare R2; briefing, custos, apresentações, feedbacks e relatórios alimentam as estruturas que a Visão geral e as abas do projeto realmente consultam."
                )
                materialization_rows = []
                role_labels_by_key = ROLE_LABELS
                source_name_by_sha = {document.sha256: document.name for document in documents}
                source_id_to_name = {}
                # O resultado técnico vem por source_file_id; o nome é recuperado
                # do lote quando disponível e, caso contrário, o papel ainda deixa
                # claro qual pipeline falhou.
                for item in result.get("materialization_results") or []:
                    created = item.get("created") or {}
                    materialization_rows.append({
                        "Papel": role_labels_by_key.get(str(item.get("role") or ""), str(item.get("role") or "Documento")),
                        "Status": "OK" if str(item.get("status") or "") != "error" else "Erro",
                        "Estruturas criadas": ", ".join(f"{key}: {value}" for key, value in created.items() if int(value or 0) > 0) or "arquivo preservado",
                        "Observações": " | ".join(str(w) for w in (item.get("warnings") or [])[:4]) or "—",
                    })
                if materialization_rows:
                    with st.expander("Ver diagnóstico da incorporação ao workspace", expanded=bool(workspace_errors)):
                        st.dataframe(pd.DataFrame(materialization_rows), hide_index=True, width="stretch")
                        st.caption(
                            "Um arquivo pode estar preservado e ainda assim ter falha na leitura estruturada. Este quadro separa as duas situações."
                        )
                cross = result.get("cross_source_intelligence") or {}
                if cross and str(cross.get("status") or "").startswith("completed"):
                    with st.expander("Intelligence Graph · conexões entre arquivos", expanded=False):
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Entidades unificadas", int(cross.get("entities_merged") or 0))
                        c2.metric("Solução ↔ custo", int(cross.get("cost_links") or 0))
                        c3.metric("Evidências de execução", int(cross.get("execution_claims") or 0))
                        c4.metric("Revisões sugeridas", int(cross.get("resolution_reviews") or 0) + int(cross.get("cost_link_reviews") or 0))
                        st.caption(
                            "A NAVE conecta o mesmo conceito/solução/local ao longo dos diferentes documentos sem fazer merge silencioso quando a identidade é ambígua."
                        )
                st.page_link(
                    "pages/4_Historico_de_Projetos.py",
                    label="Abrir Projetos",
                )

else:
    st.markdown("### Como esta etapa funciona")
    st.markdown(
        """
        1. envie todos os documentos que já pertencem ao mesmo job;
        2. a NAVE sugere o papel de cada arquivo;
        3. você revisa a classificação;
        4. a plataforma compara o conjunto com projetos existentes;
        5. você confirma **novo projeto** ou **projeto existente**;
        6. os arquivos são preservados no acervo privado do projeto com papel, confiança e origem;
        7. briefing, custos, apresentações, feedbacks e relatórios são incorporados às estruturas reais do workspace.
        """
    )
    st.info(
        "O Upload de Conhecimento continua existindo para alimentar o repertório transversal. Esta tela é específica para documentos que, juntos, formam um projeto."
    )
