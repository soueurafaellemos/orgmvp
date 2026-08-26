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
    page_title="NAVE by VOE | Home",
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

first_row = st.columns(3)

with first_row[0]:
    st.page_link(
        "pages/1_Organizar_Conhecimento.py",
        label="Upload de Conhecimento",
        icon="📥",
        width="stretch",
    )

with first_row[1]:
    st.page_link(
        "pages/2_Consultar_Base.py",
        label="Base de Conhecimento",
        icon="🗂️",
        width="stretch",
    )

with first_row[2]:
    st.page_link(
        "pages/3_Nova_Recomendacao.py",
        label="Analisar e Recomendar",
        icon="🧭",
        width="stretch",
    )

second_row = st.columns(2)

with second_row[0]:
    st.page_link(
        "pages/5_Cobertura_de_Fornecedores.py",
        label="Fornecedores",
        icon="🤝",
        width="stretch",
    )

with second_row[1]:
    st.page_link(
        "pages/4_Historico_de_Projetos.py",
        label="Projetos",
        icon="📚",
        width="stretch",
    )

st.divider()
st.caption("Diagnósticos temporários · V28.7.3")

diagnostic_row = st.columns(5)

with diagnostic_row[0]:
    st.page_link(
        "pages/15_Domain_Read_Canary.py",
        label="Domain Read Canary",
        icon="🧪",
        width="stretch",
    )

with diagnostic_row[1]:
    st.page_link(
        "pages/16_Requirement_Identity_Compatibility.py",
        label="Requirement Identity Compatibility",
        icon="🔗",
        width="stretch",
    )

with diagnostic_row[2]:
    st.page_link(
        "pages/17_Requirements_Relational_Consumer_Shadow.py",
        label="Requirements Relational Shadow",
        icon="🧬",
        width="stretch",
    )

with diagnostic_row[3]:
    st.page_link(
        "pages/18_Unified_Requirements_Reconciliation.py",
        label="Unified Requirements Reconciliation",
        icon="🔬",
        width="stretch",
    )


# B2.4.1 diagnostic link
st.page_link(
    "pages/19_Unified_Matcher_Input_Audit.py",
    label="Unified Matcher Input Audit",
    icon="🧫",
    width="stretch",
)
