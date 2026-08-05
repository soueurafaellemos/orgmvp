from __future__ import annotations

import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    home_header,
    journey_cards,
)
from runtime_ui import require_app_access


st.set_page_config(
    page_title="NAVE by VOE | Início",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
home_header()
journey_cards()

st.divider()
st.subheader("Acesse a NAVE")

column1, column2, column3, column4 = st.columns(4)

with column1:
    st.page_link(
        "pages/1_Organizar_Conhecimento.py",
        label="Upload de Conhecimento",
        icon="📥",
        use_container_width=True,
    )

with column2:
    st.page_link(
        "pages/2_Consultar_Base.py",
        label="Base de conhecimento",
        icon="🗂️",
        use_container_width=True,
    )

with column3:
    st.page_link(
        "pages/3_Nova_Recomendacao.py",
        label="Analisar e recomendar",
        icon="🧭",
        use_container_width=True,
    )

with column4:
    st.page_link(
        "pages/4_Historico_de_Projetos.py",
        label="Projetos",
        icon="📚",
        use_container_width=True,
    )
