from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from base_quality import (
    TYPE_LABELS,
    build_quality_records,
    missing_field_summary,
    overall_readiness,
    type_summary,
)
from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from runtime_ui import (
    report_service_error,
    require_app_access,
)
from supabase_db import (
    fetch_base_quality_snapshot,
    get_supabase_client,
)


st.set_page_config(
    page_title="NAVE by VOE | Prontidão da base",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Prontidão da base",
    "Acompanhe a qualidade dos cadastros e priorize os dados "
    "que mais aumentam a capacidade de recomendação da NAVE.",
    eyebrow="Qualidade da base",
)


def _setting(
    name: str,
    default: str = "",
) -> str:
    try:
        return str(
            st.secrets.get(
                name,
                os.getenv(name, default),
            )
        )
    except Exception:
        return str(os.getenv(name, default))


@st.cache_data(
    ttl=120,
    show_spinner=False,
)
def _cached_snapshot(
    service_url: str,
    _service_key: str,
) -> dict:
    cached_client = get_supabase_client(
        service_url,
        _service_key,
    )
    return fetch_base_quality_snapshot(
        cached_client
    )


url = _setting("SUPABASE_URL")
key = (
    _setting("SUPABASE_SECRET_KEY")
    or _setting("SUPABASE_SERVICE_ROLE_KEY")
)

if not url or not key:
    st.error(
        "A base de conhecimento não está disponível."
    )
    st.stop()

refresh_column, refresh_note = st.columns(
    [1, 5]
)

with refresh_column:
    refresh = st.button(
        "Atualizar diagnóstico",
        use_container_width=True,
    )

with refresh_note:
    st.caption(
        "O painel usa cache de dois minutos para manter "
        "o carregamento rápido."
    )

if refresh:
    _cached_snapshot.clear()
    st.rerun()

try:
    snapshot = _cached_snapshot(
        url,
        key,
    )
    quality = build_quality_records(
        snapshot
    )
except Exception as exc:
    report_service_error(
        "diagnóstico de qualidade da base",
        user_message=(
            "Não foi possível calcular a prontidão da base."
        ),
        exception=exc,
    )
    st.stop()

if quality.empty:
    st.info(
        "Ainda não existem cadastros suficientes para "
        "calcular a prontidão da base."
    )
    st.page_link(
        "pages/1_Organizar_Conhecimento.py",
        label="Fazer upload de conhecimento",
        use_container_width=True,
    )
    st.stop()

overall = overall_readiness(quality)
pending_duplicates = int(
    snapshot.get(
        "pending_duplicates",
        0,
    )
)

metric1, metric2, metric3, metric4, metric5 = st.columns(5)

metric1.metric(
    "Prontidão média",
    f"{overall['score']:.0f}/100",
)
metric2.metric(
    "Cadastros avaliados",
    overall["total"],
)
metric3.metric(
    "Prontos para recomendação",
    overall["ready"],
)
metric4.metric(
    "Prioritários",
    overall["priority"],
)
metric5.metric(
    "Duplicidades pendentes",
    pending_duplicates,
)

if overall["ready"] == 0:
    st.warning(
        "A base ainda não possui registros completos o bastante "
        "para testar recomendações com segurança. O painel abaixo "
        "mostra as prioridades de alimentação."
    )
elif overall["ready"] < 10:
    st.info(
        "Já existem alguns registros utilizáveis, mas a variedade "
        "ainda é pequena para validar rankings e comparações."
    )
else:
    st.success(
        "A base já possui um núcleo inicial de registros prontos "
        "para recomendações."
    )

overview_tab, priorities_tab, fields_tab = st.tabs(
    [
        "Visão geral",
        "Prioridades de alimentação",
        "Campos mais ausentes",
    ]
)

with overview_tab:
    summary = type_summary(quality)

    st.subheader("Prontidão por tipo")
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pontuação média": st.column_config.ProgressColumn(
                "Pontuação média",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "% prontos": st.column_config.ProgressColumn(
                "% prontos",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
            "% com mídia": st.column_config.ProgressColumn(
                "% com mídia",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
            "% com preço / logística": (
                st.column_config.ProgressColumn(
                    "% com preço / logística",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                )
            ),
        },
    )

    chart_data = summary.set_index(
        "Tipo"
    )[
        [
            "Pontuação média",
            "% prontos",
            "% com mídia",
        ]
    ]
    st.bar_chart(
        chart_data,
        use_container_width=True,
    )

    action1, action2 = st.columns(2)

    with action1:
        st.page_link(
            "pages/1_Organizar_Conhecimento.py",
            label="Fazer upload de conhecimento",
            use_container_width=True,
        )

    with action2:
        st.page_link(
            "pages/2_Consultar_Base.py",
            label="Abrir Base de conhecimento",
            use_container_width=True,
        )

with priorities_tab:
    filter1, filter2, filter3 = st.columns(
        [1.3, 1.3, 2]
    )

    type_options = [
        "Todos",
        *list(TYPE_LABELS.values()),
    ]
    status_options = [
        "Todos",
        "Prioritário",
        "Em evolução",
        "Pronto para recomendação",
    ]

    with filter1:
        selected_type = st.selectbox(
            "Tipo de cadastro",
            type_options,
        )

    with filter2:
        selected_status = st.selectbox(
            "Status",
            status_options,
        )

    with filter3:
        search = st.text_input(
            "Buscar item",
            placeholder=(
                "Ex.: teatro, mochila, realidade virtual..."
            ),
        )

    priorities = quality.copy()

    if selected_type != "Todos":
        priorities = priorities[
            priorities["Tipo"].eq(
                selected_type
            )
        ]

    if selected_status != "Todos":
        priorities = priorities[
            priorities["Status"].eq(
                selected_status
            )
        ]

    if search.strip():
        term = search.strip().casefold()
        searchable = (
            priorities["Item"]
            .fillna("")
            .astype(str)
            + " "
            + priorities["Fornecedor"]
            .fillna("")
            .astype(str)
            + " "
            + priorities["Cidade"]
            .fillna("")
            .astype(str)
        ).str.casefold()

        priorities = priorities[
            searchable.str.contains(
                term,
                regex=False,
            )
        ]

    visible_columns = [
        "Tipo",
        "Item",
        "Fornecedor",
        "Cidade",
        "Pontuação",
        "Status",
        "Arquivado",
        "Mídia",
        "Preço / logística",
        "Lacunas críticas",
        "Outras lacunas",
    ]

    st.caption(
        "Os itens de menor pontuação aparecem primeiro."
    )
    priority_event = st.dataframe(
        priorities[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=560,
        key="quality_priority_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Pontuação": st.column_config.ProgressColumn(
                "Pontuação",
                min_value=0,
                max_value=100,
                format="%d",
            ),
            "Lacunas críticas": (
                st.column_config.TextColumn(
                    "Lacunas críticas",
                    width="large",
                )
            ),
            "Outras lacunas": (
                st.column_config.TextColumn(
                    "Outras lacunas",
                    width="large",
                )
            ),
        },
    )

    try:
        selected_priority_rows = list(
            priority_event.selection.rows
        )
    except Exception:
        selected_priority_rows = []

    if selected_priority_rows:
        selected_priority = priorities.iloc[
            selected_priority_rows[0]
        ].to_dict()

        st.info(
            "Cadastro selecionado: "
            + str(selected_priority.get("Item"))
        )

        if st.button(
            "Abrir cadastro para completar",
            type="primary",
            use_container_width=True,
            key="open_priority_record",
        ):
            st.session_state[
                "nave_curation_focus"
            ] = {
                "entity_type": selected_priority[
                    "entity_type"
                ],
                "entity_id": selected_priority[
                    "entity_id"
                ],
            }

            if (
                selected_priority["entity_type"]
                == "supplier"
            ):
                st.switch_page(
                    "pages/5_Cobertura_de_Fornecedores.py"
                )
            else:
                st.switch_page(
                    "pages/2_Consultar_Base.py"
                )

    export_frame = priorities[
        visible_columns
    ].copy()

    st.download_button(
        "Baixar diagnóstico em CSV",
        data=export_frame.to_csv(
            index=False,
        ).encode("utf-8-sig"),
        file_name=(
            "nave_diagnostico_qualidade_base.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )

with fields_tab:
    missing = missing_field_summary(
        quality
    )

    type_filter = st.selectbox(
        "Analisar campos de",
        [
            "Todos",
            *list(TYPE_LABELS.values()),
        ],
        key="missing_type_filter",
    )

    if type_filter != "Todos":
        missing = missing[
            missing["Tipo"].eq(type_filter)
        ]

    st.caption(
        "Campos que, quando preenchidos, melhoram mais rapidamente "
        "a qualidade e a capacidade de recomendação da base."
    )

    st.dataframe(
        missing,
        use_container_width=True,
        hide_index=True,
        column_config={
            "% do tipo": st.column_config.ProgressColumn(
                "% do tipo",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            )
        },
    )

    if not missing.empty:
        chart = (
            missing.head(15)
            .set_index("Campo ausente")[
                "Cadastros afetados"
            ]
        )
        st.bar_chart(
            chart,
            use_container_width=True,
        )

st.divider()
st.caption(
    "A pontuação é um indicador operacional de completude. "
    "Ela não substitui a validação humana dos valores, prazos, "
    "capacidades e documentos."
)
