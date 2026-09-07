from __future__ import annotations
import streamlit as st
from branding import NAVE_APP_ICON, apply_nave_branding, home_header, journey_cards
from runtime_ui import require_app_access

st.set_page_config(page_title="NAVE by VOE | Home", page_icon=NAVE_APP_ICON, layout="wide", initial_sidebar_state="expanded")
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
links = [
("pages/15_Domain_Read_Canary.py","Domain Read Canary","🧪"),
("pages/16_Requirement_Identity_Compatibility.py","Requirement Identity Compatibility","🔗"),
("pages/17_Requirements_Relational_Consumer_Shadow.py","Requirements Relational Shadow","🧬"),
("pages/18_Unified_Requirements_Reconciliation.py","Unified Requirements Reconciliation","🔬"),
("pages/19_Unified_Matcher_Input_Audit.py","Unified Matcher Input Audit","🧫"),
("pages/20_Unified_Semantic_Counterpart_Audit.py","Unified Semantic Counterpart Audit","🧭"),
("pages/21_Unified_Evidence_Role_Shadow.py","Unified Evidence Role Shadow","🧪"),
("pages/22_Unified_Residual_Evidence_Coverage.py","Unified Residual Evidence Coverage","🔎"),
("pages/23_Cross_Domain_Residual_Placement.py","Cross-Domain Residual Placement","🧭"),
("pages/24_Semantic_Ownership_Response_Evidence.py","Semantic Ownership & Response Evidence","🧠"),
("pages/25_Response_Entailment_Shadow.py","Response Entailment Shadow","🧪"),
("pages/26_Requirement_Response_Contract.py","Requirement Response Contract","✅"),
("pages/27_Response_Evidence_Recall.py","Response Evidence Recall","🔎"),
("pages/28_Semantic_Recall_Bridge.py","Semantic Recall Bridge","🌐"),
("pages/29_Requirement_Obligation_Atom_Gate.py","Requirement Obligation Atom Gate","🧩"),
("pages/30_Governed_Response_Recall_Review_Projection.py","Governed Response Recall Review Projection","🛡️"),
("pages/31_Human_Response_Adjudication_Contract.py","Human Response Adjudication Contract","👤"),
("pages/32_Automated_Adjudication_Recommendations.py","Automated Adjudication Recommendations","🤖"),
("pages/33_Requirement_Semantic_Truth_Repair.py","Requirement Semantic Truth Repair","🧬"),
("pages/34_Requirement_Identity_Collision_Shadow.py","Requirement Identity Collision Shadow","🧬"),
("pages/35_Requirement_Identity_Supersession_Dry_Run.py","Requirement Identity Supersession Dry Run","🧪"),
]
for path, label, icon in links:
    st.page_link(path, label=label, icon=icon, width="stretch")
