from __future__ import annotations

import os

import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
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

apply_nave_branding()
page_header(
    "Administração",
    "Configurações técnicas e diagnóstico dos serviços da NAVE.",
    eyebrow="Sistema",
)

try:
    gemini_key = st.secrets.get(
        "GEMINI_API_KEY",
        os.getenv("GEMINI_API_KEY", ""),
    )
    default_model = st.secrets.get(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )
    supabase_url = st.secrets.get(
        "SUPABASE_URL",
        os.getenv("SUPABASE_URL", ""),
    )
    supabase_key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get(
            "SUPABASE_SERVICE_ROLE_KEY",
            os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        ),
    )
except Exception:
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    default_model = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

st.subheader("Serviço de leitura")

model_options = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]
current_model = st.session_state.get(
    "nave_model",
    default_model,
)
if current_model not in model_options:
    current_model = model_options[0]

selected_model = st.selectbox(
    "Modelo ativo",
    model_options,
    index=model_options.index(current_model),
    help=(
        "O modelo econômico permanece recomendado para reduzir "
        "o consumo da quota."
    ),
)
st.session_state["nave_model"] = selected_model

g1, g2 = st.columns(2)
g1.metric(
    "Chave de leitura",
    "Configurada" if gemini_key else "Não configurada",
)
g2.metric(
    "Modelo desta sessão",
    selected_model,
)

st.divider()
st.subheader("Base de conhecimento")

s1, s2 = st.columns(2)
s1.metric(
    "URL do banco",
    "Configurada" if supabase_url else "Não configurada",
)
s2.metric(
    "Chave do banco",
    "Configurada" if supabase_key else "Não configurada",
)

if supabase_url and supabase_key:
    try:
        client = get_supabase_client(
            supabase_url,
            supabase_key,
        )
        st.success("Base de conhecimento disponível.")

        if st.button(
            "Testar conexão",
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "Verificando a base de conhecimento..."
                ):
                    result = test_connection(client)
                st.success(
                    "Conexão confirmada. "
                    f"Fornecedores cadastrados: "
                    f"{result['supplier_count']}."
                )
            except Exception:
                st.error(
                    "A conexão não pôde ser confirmada agora. "
                    "Revise os Secrets do aplicativo."
                )
    except Exception:
        st.error(
            "Não foi possível preparar a conexão com a base."
        )
else:
    st.warning(
        "Configure SUPABASE_URL e SUPABASE_SECRET_KEY "
        "nos Secrets do aplicativo."
    )

st.divider()
st.subheader("Identidade do produto")

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
