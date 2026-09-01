from __future__ import annotations

import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, home_header, journey_cards
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
    st.page_link("pages/1_Organizar_Conhecimento.py", label="Upload de Conhecimento", icon="📥", width="stretch")
with first_row[1]:
    st.page_link("pages/2_Consultar_Base.py", label="Base de Conhecimento", icon="🗂️", width="stretch")
with first_row[2]:
    st.page_link("pages/3_Nova_Recomendacao.py", label="Analisar e Recomendar", icon="🧭", width="stretch")
second_row = st.columns(2)
with second_row[0]:
    st.page_link("pages/5_Cobertura_de_Fornecedores.py", label="Fornecedores", icon="🤝", width="stretch")
with second_row[1]:
    st.page_link("pages/4_Historico_de_Projetos.py", label="Projetos", icon="📚", width="stretch")

st.divider()
st.caption("Diagnósticos temporários · V28.7.3")
d1 = st.columns(3)
with d1[0]:
    st.page_link("pages/15_Domain_Read_Canary.py", label="Domain Read Canary", icon="🧪", width="stretch")
with d1[1]:
    st.page_link("pages/16_Requirement_Identity_Compatibility.py", label="Requirement Identity Compatibility", icon="🔗", width="stretch")
with d1[2]:
    st.page_link("pages/17_Requirements_Relational_Consumer_Shadow.py", label="Requirements Relational Shadow", icon="🧬", width="stretch")
d2 = st.columns(3)
with d2[0]:
    st.page_link("pages/18_Unified_Requirements_Reconciliation.py", label="Unified Requirements Reconciliation", icon="🔬", width="stretch")
with d2[1]:
    st.page_link("pages/19_Unified_Matcher_Input_Audit.py", label="Unified Matcher Input Audit", icon="🧫", width="stretch")
with d2[2]:
    st.page_link("pages/20_Unified_Semantic_Counterpart_Audit.py", label="Unified Semantic Counterpart Audit", icon="🧭", width="stretch")
d3 = st.columns(3)
with d3[0]:
    st.page_link("pages/21_Unified_Evidence_Role_Shadow.py", label="Unified Evidence Role Shadow", icon="🧪", width="stretch")
with d3[1]:
    st.page_link("pages/22_Unified_Residual_Evidence_Coverage.py", label="Unified Residual Evidence Coverage", icon="🔎", width="stretch")
with d3[2]:
    st.page_link("pages/23_Cross_Domain_Residual_Placement.py", label="Cross-Domain Residual Placement", icon="🧭", width="stretch")

st.page_link(
    "pages/24_Semantic_Ownership_Response_Evidence.py",
    label="Semantic Ownership & Response Evidence",
    icon="🧠",
    width="stretch",
)

st.page_link(
    "pages/25_Response_Entailment_Shadow.py",
    label="Response Entailment Shadow",
    icon="🧪",
    width="stretch",
)

st.page_link(
    "pages/26_Requirement_Response_Contract.py",
    label="Requirement Response Contract",
    icon="✅",
    width="stretch",
)

st.page_link(
    "pages/27_Response_Evidence_Recall.py",
    label="Response Evidence Recall",
    icon="🔎",
    width="stretch",
)

st.page_link(
    "pages/28_Semantic_Recall_Bridge.py",
    label="Semantic Recall Bridge",
    icon="🌐",
    width="stretch",
)

st.page_link(
    "pages/29_Requirement_Obligation_Atom_Gate.py",
    label="Requirement Obligation Atom Gate",
    icon="🧩",
    width="stretch",
)

st.page_link(
    "pages/30_Governed_Response_Recall_Review_Projection.py",
    label="Governed Response Recall Review Projection",
    icon="🛡️",
    width="stretch",
)

st.page_link(
    "pages/31_Human_Response_Adjudication_Contract.py",
    label="Human Response Adjudication Contract",
    icon="👤",
    width="stretch",
)

st.page_link(
    "pages/32_Automated_Adjudication_Recommendations.py",
    label="Automated Adjudication Recommendations",
    icon="🤖",
    width="stretch",
)

st.page_link(
    "pages/33_Requirement_Semantic_Truth_Repair.py",
    label="Requirement Semantic Truth Repair",
    icon="🧬",
    width="stretch",
)

st.page_link(
    "pages/34_Requirement_Identity_Collision_Shadow.py",
    label="Requirement Identity Collision Shadow",
    icon="🧬",
    width="stretch",
)
