from __future__ import annotations

import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding
from knowledge_specialized import render_specialized_page
from nave_data_client import enforce_existing_app_access

st.set_page_config(page_title="Ativações | NAVE by VOE", page_icon=NAVE_APP_ICON, layout="wide")
enforce_existing_app_access()
apply_nave_branding()
render_specialized_page("activation")
