from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from memory_learning_db import (
    delete_memory_project,
)
from project_hub import (
    fetch_unified_projects,
    selected_rows,
    unified_project_table,
)
from runtime_ui import (
    report_service_error,
    require_admin_access,
    require_app_access,
)
from supabase_db import (
    get_supabase_client,
)


st.set_page_config(
    page_title="NAVE by VOE | Projetos",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Projetos",
    "Acesse briefing, recomendações, apresentação final, "
    "custos, feedbacks e aprendizados em um único lugar.",
)


def _setting(
    name: str,
    default: str = "",
) -> str:
    try:
        return str(
            st.secrets.get(
                name,
                os.getenv(
                    name,
                    default,
                ),
            )
        )
    except Exception:
        return str(
            os.getenv(
                name,
                default,
            )
        )


supabase_url = _setting(
    "SUPABASE_URL"
)
supabase_key = (
    _setting(
        "SUPABASE_SECRET_KEY"
    )
    or _setting(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
)

if not supabase_url or not supabase_key:
    st.error(
        "A área de Projetos não está disponível. "
        "Consulte a Administração."
    )
    st.stop()

client = get_supabase_client(
    supabase_url,
    supabase_key,
)

try:
    projects = fetch_unified_projects(
        client
    )
except Exception as exc:
    report_service_error(
        "consulta unificada de projetos",
        user_message=(
            "Não foi possível carregar os projetos."
        ),
        exception=exc,
    )
    st.stop()

if projects.empty:
    st.info(
        "Ainda não existem projetos salvos."
    )

    if st.button(
        "Criar projeto por uma nova análise",
        type="primary",
        width="stretch",
    ):
        st.switch_page(
            "pages/3_Nova_Recomendacao.py"
        )

    st.stop()

metric1, metric2, metric3, metric4 = (
    st.columns(4)
)
metric1.metric(
    "Projetos",
    len(projects),
)
metric2.metric(
    "Versões de recomendação",
    int(
        pd.to_numeric(
            projects[
                "recommendation_versions"
            ],
            errors="coerce",
        ).fillna(0).sum()
    ),
)
metric3.metric(
    "Apresentações finais",
    int(
        pd.to_numeric(
            projects[
                "memory_documents_count"
            ],
            errors="coerce",
        ).fillna(0).sum()
    ),
)
metric4.metric(
    "Conteúdos preservados",
    int(
        pd.to_numeric(
            projects[
                "memory_items_count"
            ],
            errors="coerce",
        ).fillna(0).sum()
    ),
)

st.divider()

filter_col, size_col = st.columns(
    [3, 1]
)

with filter_col:
    search = st.text_input(
        "Buscar projeto, cliente ou evento",
        placeholder=(
            "Ex.: Chambinho, CCXP, Oktoberfest..."
        ),
    )

with size_col:
    page_size = st.selectbox(
        "Projetos por página",
        [
            25,
            50,
            100,
        ],
        index=0,
    )

page_number = st.session_state.get(
    "project_hub_page",
    1,
)

project_page, total_projects, total_pages = (
    unified_project_table(
        projects,
        search=search,
        page_size=page_size,
        current_page=page_number,
    )
)

pagination_col, summary_col = st.columns(
    [1, 4]
)

with pagination_col:
    current_page = st.number_input(
        "Página",
        min_value=1,
        max_value=total_pages,
        value=min(
            int(page_number),
            total_pages,
        ),
        step=1,
        key="project_hub_page",
    )

if int(current_page) != int(
    page_number
):
    project_page, total_projects, total_pages = (
        unified_project_table(
            projects,
            search=search,
            page_size=page_size,
            current_page=(
                int(current_page)
            ),
        )
    )

with summary_col:
    st.caption(
        f"{total_projects} projeto(s) encontrado(s) · "
        f"página {int(current_page)} de {total_pages}"
    )

if project_page.empty:
    st.warning(
        "Nenhum projeto corresponde à busca."
    )
    st.stop()

st.caption(
    "Selecione uma linha para abrir o hub do projeto."
)

project_event = st.dataframe(
    project_page[
        [
            "Projeto",
            "Cliente",
            "Evento",
            "Briefings / recomendações",
            "Apresentações",
            "Conteúdos",
            "Última atualização",
        ]
    ],
    hide_index=True,
    row_height=52,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    key=(
        "project_hub_table_"
        + str(
            int(current_page)
        )
        + "_"
        + str(page_size)
    ),
)

rows = selected_rows(
    project_event
)

if not rows:
    st.info(
        "Selecione um projeto para acessar briefing, "
        "recomendações, Memória, custos e resultados."
    )
    st.stop()

selected_project = (
    project_page.iloc[
        rows[0]
    ].to_dict()
)
project_id = str(
    selected_project[
        "project_id"
    ]
)
project_name = str(
    selected_project.get(
        "Projeto"
    )
    or "Projeto sem nome"
)

st.session_state[
    "nave_project_hub_focus_id"
] = project_id
st.session_state[
    "nave_project_hub_focus_name"
] = project_name

st.divider()

title_col, delete_col = st.columns(
    [4, 1],
    vertical_alignment="center",
)

with title_col:
    st.subheader(
        project_name
    )
    st.caption(
        "Cliente: "
        + str(
            selected_project.get(
                "Cliente"
            )
            or "Não informado"
        )
        + " · Evento: "
        + str(
            selected_project.get(
                "Evento"
            )
            or "Não informado"
        )
    )

delete_state_key = (
    "project_hub_delete_"
    + project_id
)

with delete_col:
    if st.button(
        "Excluir projeto",
        key=(
            "project_hub_delete_button_"
            + project_id
        ),
        width="stretch",
    ):
        st.session_state[
            delete_state_key
        ] = True

if st.session_state.get(
    delete_state_key,
    False,
):
    with st.container(
        border=True,
    ):
        st.error(
            "A exclusão é permanente e remove briefing, "
            "recomendações, apresentações, imagens, custos, "
            "feedbacks e resultados associados."
        )

        if require_admin_access():
            confirmation = st.text_input(
                "Digite EXCLUIR para confirmar",
                key=(
                    "project_hub_delete_text_"
                    + project_id
                ),
            )
            cancel_col, confirm_col = (
                st.columns(2)
            )

            with cancel_col:
                if st.button(
                    "Cancelar",
                    key=(
                        "project_hub_delete_cancel_"
                        + project_id
                    ),
                    width="stretch",
                ):
                    st.session_state.pop(
                        delete_state_key,
                        None,
                    )
                    st.rerun()

            with confirm_col:
                if st.button(
                    "Excluir definitivamente",
                    type="primary",
                    disabled=(
                        confirmation
                        .strip()
                        .upper()
                        != "EXCLUIR"
                    ),
                    key=(
                        "project_hub_delete_confirm_"
                        + project_id
                    ),
                    width="stretch",
                ):
                    try:
                        with st.spinner(
                            "Excluindo projeto e arquivos..."
                        ):
                            delete_memory_project(
                                client,
                                project_id=(
                                    project_id
                                ),
                            )

                        st.session_state.pop(
                            delete_state_key,
                            None,
                        )
                        st.session_state.pop(
                            "nave_project_hub_focus_id",
                            None,
                        )
                        st.cache_data.clear()
                        st.success(
                            "Projeto excluído."
                        )
                        st.rerun()
                    except Exception as exc:
                        report_service_error(
                            "exclusão do projeto",
                            user_message=(
                                "Não foi possível excluir "
                                "este projeto."
                            ),
                            exception=exc,
                        )

overview1, overview2, overview3, overview4 = (
    st.columns(4)
)
overview1.metric(
    "Versões de recomendação",
    int(
        selected_project.get(
            "recommendation_versions"
        )
        or 0
    ),
)
overview2.metric(
    "Apresentações finais",
    int(
        selected_project.get(
            "memory_documents_count"
        )
        or 0
    ),
)
overview3.metric(
    "Conteúdos da Memória",
    int(
        selected_project.get(
            "memory_items_count"
        )
        or 0
    ),
)
overview4.metric(
    "Última atualização",
    selected_project.get(
        "Última atualização"
    )
    or "Não informada",
)

st.markdown(
    "### Áreas do projeto"
)

action1, action2, action3 = st.columns(
    3
)

with action1:
    st.markdown(
        "#### Briefing & Recomendações"
    )
    st.write(
        "Consulte versões do briefing, diagnóstico, "
        "recomendações e feedbacks do recomendador."
    )

    if st.button(
        "Abrir briefing e recomendações",
        type="primary",
        width="stretch",
        key=(
            "open_recommendations_"
            + project_id
        ),
    ):
        st.switch_page(
            "pages/11_Briefing_e_Recomendacoes.py"
        )

with action2:
    st.markdown(
        "#### Memória do Projeto"
    )
    st.write(
        "Consulte estratégia, cenografia, ativações, "
        "brindes, custos, resultados e documentos."
    )

    if st.button(
        "Abrir Memória do Projeto",
        type="primary",
        width="stretch",
        key=(
            "open_memory_"
            + project_id
        ),
    ):
        st.session_state[
            "nave_project_hub_memory_mode"
        ] = "consult"
        st.switch_page(
            "pages/10_Memoria.py"
        )

with action3:
    st.markdown(
        "#### Apresentação final"
    )
    st.write(
        "Anexe uma nova apresentação ao projeto selecionado, "
        "sem criar outro projeto."
    )

    if st.button(
        "Adicionar apresentação final",
        type="primary",
        width="stretch",
        key=(
            "add_memory_document_"
            + project_id
        ),
    ):
        st.session_state[
            "nave_project_hub_memory_mode"
        ] = "upload"
        st.switch_page(
            "pages/10_Memoria.py"
        )
