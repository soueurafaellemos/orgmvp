from __future__ import annotations

import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from project_workspace_runtime import (
    apply_existing_login_gate,
    get_workspace_client,
)
from project_workspace_ui_b1 import render_projects_page


st.set_page_config(
    page_title="Projetos | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)

apply_existing_login_gate()
apply_nave_branding()

page_header(
    "Projetos",
    (
        "Um ambiente único para briefing, recomendações, estratégia, "
        "cenografia, brindes, orçamento, apresentações, feedbacks e resultados."
    ),
)

try:
    client = get_workspace_client()
except Exception as exc:
    st.error(str(exc))
    st.stop()

render_projects_page(client)
