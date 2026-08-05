from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from runtime_ui import (
    report_service_error,
    require_admin_access,
    require_app_access,
)
from supabase_db import (
    apply_taxonomy_normalization,
    fetch_custom_taxonomy_aliases,
    fetch_taxonomy_audit,
    get_supabase_client,
    set_custom_taxonomy_alias_active,
    upsert_custom_taxonomy_alias,
)
from taxonomy import (
    DOMAIN_LABELS,
    taxonomy_catalog_rows,
    taxonomy_options,
)


st.set_page_config(
    page_title="NAVE by VOE | Taxonomia NAVE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Taxonomia NAVE",
    "Organize abreviações, traduções, grafias alternativas "
    "e termos equivalentes em categorias canônicas.",
    eyebrow="Qualidade da base",
)

if not require_admin_access():
    st.stop()


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

try:
    client = get_supabase_client(
        url,
        key,
    )
    custom_aliases = (
        fetch_custom_taxonomy_aliases(
            client,
            include_inactive=True,
        )
    )
except Exception as exc:
    report_service_error(
        "consulta da taxonomia",
        user_message=(
            "Não foi possível carregar a taxonomia."
        ),
        exception=exc,
    )
    st.stop()

catalog = pd.DataFrame(
    taxonomy_catalog_rows(custom_aliases)
)

default_aliases = int(
    catalog["source"].eq("default").sum()
)
custom_active = int(
    sum(
        1
        for row in custom_aliases
        if row.get("is_active", True)
    )
)
canonical_count = int(
    catalog[
        [
            "entity_type",
            "canonical_term",
        ]
    ].drop_duplicates().shape[0]
)

metric1, metric2, metric3 = st.columns(3)
metric1.metric(
    "Categorias canônicas",
    canonical_count,
)
metric2.metric(
    "Variações padrão",
    default_aliases,
)
metric3.metric(
    "Variações personalizadas",
    custom_active,
)

catalog_tab, alias_tab, audit_tab = st.tabs(
    [
        "Dicionário",
        "Adicionar variação",
        "Padronizar base existente",
    ]
)

with catalog_tab:
    filter1, filter2 = st.columns(
        [1.2, 2.8]
    )

    with filter1:
        selected_domain = st.selectbox(
            "Tipo",
            [
                "Todos",
                *DOMAIN_LABELS.keys(),
            ],
            format_func=lambda value: (
                value
                if value == "Todos"
                else DOMAIN_LABELS[value]
            ),
        )

    with filter2:
        search = st.text_input(
            "Buscar categoria ou variação",
            placeholder=(
                "Ex.: phopp, photo opportunity, "
                "instagramável, mochila..."
            ),
        )

    visible = catalog.copy()

    if selected_domain != "Todos":
        visible = visible[
            visible["entity_type"].eq(
                selected_domain
            )
        ]

    if search.strip():
        term = search.strip().casefold()
        searchable = (
            visible["canonical_term"]
            .fillna("")
            .astype(str)
            + " "
            + visible["alias"]
            .fillna("")
            .astype(str)
        ).str.casefold()

        visible = visible[
            searchable.str.contains(
                term,
                regex=False,
            )
        ]

    visible["Tipo"] = visible[
        "entity_type"
    ].map(DOMAIN_LABELS)
    visible["Categoria NAVE"] = visible[
        "canonical_term"
    ]
    visible["Variação reconhecida"] = visible[
        "alias"
    ]
    visible["Origem"] = visible[
        "source"
    ].map(
        {
            "default": "Padrão NAVE",
        }
    ).fillna("Personalizada")
    visible["Situação"] = visible[
        "is_active"
    ].apply(
        lambda value: (
            "Ativa"
            if bool(value)
            else "Inativa"
        )
    )

    st.dataframe(
        visible[
            [
                "Tipo",
                "Categoria NAVE",
                "Variação reconhecida",
                "Origem",
                "Situação",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        height=610,
    )

with alias_tab:
    st.subheader(
        "Adicionar uma nova forma de dizer a mesma coisa"
    )
    st.caption(
        "Exemplo: vincular “foto opportunity” ou uma abreviação "
        "recorrente à categoria Photo-op."
    )

    with st.form("new_taxonomy_alias"):
        alias_col1, alias_col2 = st.columns(2)

        with alias_col1:
            entity_type = st.selectbox(
                "Tipo",
                list(DOMAIN_LABELS.keys()),
                format_func=lambda value: (
                    DOMAIN_LABELS[value]
                ),
            )

        with alias_col2:
            canonical_term = st.selectbox(
                "Categoria NAVE",
                taxonomy_options(entity_type),
            )

        alias = st.text_input(
            "Nova variação, abreviação ou grafia",
            placeholder=(
                "Ex.: phopp, foto opportunity, "
                "selfie corner..."
            ),
        )

        notes = st.text_area(
            "Observação interna",
            placeholder=(
                "Onde essa expressão costuma aparecer?"
            ),
            height=80,
        )

        add_clicked = st.form_submit_button(
            "Adicionar à taxonomia",
            type="primary",
            use_container_width=True,
        )

    if add_clicked:
        try:
            upsert_custom_taxonomy_alias(
                client,
                entity_type=entity_type,
                canonical_term=canonical_term,
                alias=alias,
                notes=notes.strip() or None,
            )
            st.success(
                "Nova variação adicionada. Ela já será "
                "considerada nas próximas buscas, uploads "
                "e recomendações."
            )
            st.cache_data.clear()
            st.rerun()

        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            report_service_error(
                "adição de variação à taxonomia",
                user_message=(
                    "Não foi possível adicionar a variação."
                ),
                exception=exc,
            )

    custom_frame = pd.DataFrame(
        custom_aliases
    )

    if not custom_frame.empty:
        st.divider()
        st.subheader(
            "Variações personalizadas"
        )

        custom_frame["Tipo"] = custom_frame[
            "entity_type"
        ].map(DOMAIN_LABELS)
        custom_frame["Categoria NAVE"] = (
            custom_frame["canonical_term"]
        )
        custom_frame["Variação"] = custom_frame[
            "alias"
        ]
        custom_frame["Situação"] = custom_frame[
            "is_active"
        ].apply(
            lambda value: (
                "Ativa"
                if bool(value)
                else "Inativa"
            )
        )

        st.dataframe(
            custom_frame[
                [
                    "Tipo",
                    "Categoria NAVE",
                    "Variação",
                    "Situação",
                    "notes",
                ]
            ].rename(
                columns={
                    "notes": "Observação",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        alias_options = {
            (
                f"{row.get('alias')} → "
                f"{row.get('canonical_term')}"
            ): str(row.get("id"))
            for row in custom_aliases
        }

        selected_alias = st.selectbox(
            "Variação personalizada",
            list(alias_options.keys()),
        )

        active_choice = st.radio(
            "Alterar situação",
            ["Ativar", "Desativar"],
            horizontal=True,
        )

        if st.button(
            "Aplicar situação",
            use_container_width=True,
        ):
            try:
                set_custom_taxonomy_alias_active(
                    client,
                    alias_id=alias_options[
                        selected_alias
                    ],
                    is_active=(
                        active_choice == "Ativar"
                    ),
                )
                st.success(
                    "Situação da variação atualizada."
                )
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                report_service_error(
                    "alteração de variação da taxonomia",
                    user_message=(
                        "Não foi possível alterar "
                        "essa variação."
                    ),
                    exception=exc,
                )

with audit_tab:
    st.subheader(
        "Padronização da base existente"
    )
    st.caption(
        "A NAVE preserva nomes, descrições e documentos de origem. "
        "A atualização altera somente a categoria canônica e "
        "acrescenta tags semânticas."
    )

    try:
        with st.spinner(
            "Analisando categorias e variações existentes..."
        ):
            audit = fetch_taxonomy_audit(
                client
            )
    except Exception as exc:
        report_service_error(
            "auditoria da taxonomia",
            user_message=(
                "Não foi possível analisar a base."
            ),
            exception=exc,
        )
        audit = pd.DataFrame()

    if audit.empty:
        st.info(
            "Não existem registros para analisar."
        )
    else:
        changes = audit[
            audit[
                "Precisa atualizar"
            ].eq(True)
        ].copy()

        audit_metric1, audit_metric2 = (
            st.columns(2)
        )
        audit_metric1.metric(
            "Cadastros analisados",
            len(audit),
        )
        audit_metric2.metric(
            "Cadastros a reorganizar",
            len(changes),
        )

        if changes.empty:
            st.success(
                "A base existente já está alinhada "
                "à taxonomia atual."
            )
        else:
            st.dataframe(
                changes[
                    [
                        "Tipo",
                        "Item",
                        "Categoria atual",
                        "Categoria NAVE",
                        "Termos reconhecidos",
                        "Variações encontradas",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=470,
            )

            st.warning(
                "Revise a amostra antes de aplicar. "
                "As mudanças ficam registradas no histórico "
                "de curadoria."
            )

            confirmation = st.text_input(
                "Digite PADRONIZAR para confirmar",
            )

            apply_clicked = st.button(
                "Aplicar taxonomia à base existente",
                type="primary",
                disabled=(
                    confirmation.strip().upper()
                    != "PADRONIZAR"
                ),
                use_container_width=True,
            )

            if apply_clicked:
                try:
                    with st.spinner(
                        "Padronizando categorias e tags..."
                    ):
                        result = (
                            apply_taxonomy_normalization(
                                client
                            )
                        )

                    st.success(
                        f"{result['updated_records']} cadastro(s) "
                        "atualizado(s). "
                        f"{result['category_changes']} categoria(s) "
                        "padronizada(s) e "
                        f"{result['tag_changes']} conjunto(s) "
                        "de tags enriquecido(s)."
                    )
                    st.cache_data.clear()
                    st.rerun()

                except Exception as exc:
                    report_service_error(
                        "aplicação da taxonomia",
                        user_message=(
                            "Não foi possível aplicar "
                            "a padronização."
                        ),
                        exception=exc,
                    )
