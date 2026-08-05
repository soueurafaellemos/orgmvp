from __future__ import annotations

import os

import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from runtime_ui import (
    admin_logout_button,
    get_setting,
    report_service_error,
    require_admin_access,
    require_app_access,
)
from media_library import (
    MEDIA_BUCKET,
    ensure_media_bucket,
)
from supabase_db import (
    get_supabase_client,
    test_connection,
)


st.set_page_config(
    page_title="NAVE by VOE | Administração",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Administração",
    "Acesso interno às configurações e ao diagnóstico da NAVE.",
    eyebrow="Área restrita",
)

if not require_admin_access():
    st.stop()

admin_logout_button()

gemini_key = str(
    get_setting("GEMINI_API_KEY", "")
)
default_model = str(
    get_setting(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )
)
supabase_url = str(
    get_setting("SUPABASE_URL", "")
)
supabase_key = str(
    get_setting(
        "SUPABASE_SECRET_KEY",
        get_setting(
            "SUPABASE_SERVICE_ROLE_KEY",
            "",
        ),
    )
)

model_labels = {
    "Econômico — recomendado": "gemini-3.5-flash-lite",
    "Padrão": "gemini-3.5-flash",
    "Avançado": "gemini-3.6-flash",
}
reverse_models = {
    value: label
    for label, value in model_labels.items()
}

current_model = st.session_state.get(
    "nave_model",
    default_model,
)
current_label = reverse_models.get(
    current_model,
    "Econômico — recomendado",
)

st.subheader("Status dos serviços")

status1, status2, status3 = st.columns(3)
status1.metric(
    "Leitura inteligente",
    "Disponível" if gemini_key else "Indisponível",
)
status2.metric(
    "Base de conhecimento",
    (
        "Disponível"
        if supabase_url and supabase_key
        else "Indisponível"
    ),
)
status3.metric(
    "Identidade do produto",
    "NAVE by VOE",
)

st.divider()
st.subheader("Configuração de processamento")

selected_label = st.selectbox(
    "Perfil de processamento",
    options=list(model_labels.keys()),
    index=list(model_labels.keys()).index(
        current_label
    ),
    help=(
        "O perfil econômico é indicado para o uso cotidiano "
        "e reduz o consumo do serviço de leitura."
    ),
)
st.session_state["nave_model"] = model_labels[
    selected_label
]

st.divider()
st.subheader("Diagnóstico da base")

if supabase_url and supabase_key:
    try:
        client = get_supabase_client(
            supabase_url,
            supabase_key,
        )
        st.success("A base de conhecimento está disponível.")

        if st.button(
            "Verificar disponibilidade",
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "Verificando a base de conhecimento..."
                ):
                    result = test_connection(client)
                st.success(
                    "Verificação concluída. "
                    f"Fornecedores disponíveis: "
                    f"{result['supplier_count']}."
                )
            except Exception as exc:
                report_service_error(
                    "verificação administrativa da base",
                    user_message=(
                        "A base não respondeu à verificação."
                    ),
                    exception=exc,
                )
    except Exception as exc:
        report_service_error(
            "inicialização administrativa da base",
            user_message=(
                "A base de conhecimento não pôde ser preparada."
            ),
            exception=exc,
        )
else:
    st.warning(
        "A base de conhecimento ainda não foi configurada."
    )

st.divider()
st.subheader("Acervo visual e documental")

if supabase_url and supabase_key:
    if st.button(
        "Preparar armazenamento do acervo",
        use_container_width=True,
    ):
        try:
            ensure_media_bucket(client)
            st.success(
                "Armazenamento privado do acervo disponível."
            )
            st.caption(
                f"Identificação interna: {MEDIA_BUCKET}"
            )
        except Exception as exc:
            report_service_error(
                "preparação do armazenamento do acervo",
                user_message=(
                    "Não foi possível preparar o armazenamento "
                    "do acervo."
                ),
                exception=exc,
            )
else:
    st.info(
        "A base precisa estar disponível para preparar "
        "o acervo visual."
    )

st.divider()
st.subheader("Informações do produto")

st.markdown(
    """
    **Nome oficial:** NAVE by VOE

    **Significado:** Núcleo de Análise VOE para Experiências

    **Tagline:** Conectando briefing, repertório e decisão.

    **Descriptor:** Plataforma proprietária de inteligência de
    pré-produção que organiza conhecimento, qualifica briefings e
    recomenda soluções para projetos de live marketing.
    """
)

st.divider()

support_mode = st.checkbox(
    "Exibir detalhes para suporte",
    value=st.session_state.get(
        "nave_support_mode",
        False,
    ),
)
st.session_state["nave_support_mode"] = support_mode

if support_mode:
    with st.expander(
        "Detalhes técnicos",
        expanded=True,
    ):
        st.write(
            {
                "serviço_de_leitura": (
                    "configurado"
                    if gemini_key
                    else "não configurado"
                ),
                "perfil_interno": st.session_state[
                    "nave_model"
                ],
                "base_url": (
                    "configurada"
                    if supabase_url
                    else "não configurada"
                ),
                "base_key": (
                    "configurada"
                    if supabase_key
                    else "não configurada"
                ),
            }
        )
