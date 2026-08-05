from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from runtime_ui import app_logout_button
from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent
ASSET_DIR = ROOT_DIR / "assets"

NAVE_LOCKUP_PATH = ASSET_DIR / "nave_lockup.svg"
NAVE_LOCKUP_WHITE_PATH = ASSET_DIR / "nave_lockup_white.svg"
NAVE_SYMBOL_PATH = ASSET_DIR / "nave_symbol.svg"
NAVE_APP_ICON_PATH = ASSET_DIR / "nave_app_icon.png"
NAVE_APP_ICON = Image.open(NAVE_APP_ICON_PATH)


BRAND_CSS = """
<style>
:root {
    --nave-navy: #121B42;
    --nave-cyan: #18CDEA;
    --nave-white: #FFFFFF;
    --nave-surface: #F4F6F9;
    --nave-border: #E1E6EF;
    --nave-text: #121B42;
    --nave-muted: #687188;
    --nave-magenta: #E91E63;
    --nave-yellow: #FFD400;
}

html, body, [class*="css"] {
    font-family:
        "Avenir Next",
        "Avenir",
        "Inter",
        "Segoe UI",
        Arial,
        sans-serif;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(
            circle at 100% 0%,
            rgba(24, 205, 234, 0.06),
            transparent 28rem
        ),
        #FFFFFF;
}

[data-testid="stHeader"] {
    background: rgba(255, 255, 255, 0);
}

[data-testid="stDecoration"],
[data-testid="manage-app-button"],
.stDeployButton,
#MainMenu,
footer {
    display: none !important;
    visibility: hidden !important;
}

/*
Mantém os controles essenciais do Streamlit visíveis:
- toolbar minimal no topo;
- indicador de execução e botão Stop.
*/
[data-testid="stToolbar"],
[data-testid="stStatusWidget"] {
    display: flex !important;
    visibility: visible !important;
}

[data-testid="stSidebarNav"] {
    display: none !important;
}

[data-testid="stSidebar"] {
    background: var(--nave-navy);
    border-right: 0;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.1rem;
}

[data-testid="stSidebar"] * {
    color: rgba(255, 255, 255, 0.92);
}

[data-testid="stSidebar"] [data-testid="stImage"] {
    margin-bottom: 0.25rem;
}

[data-testid="stSidebar"] a {
    border-radius: 10px;
    margin: 0.12rem 0;
    padding: 0.15rem 0.35rem;
    text-decoration: none;
}

[data-testid="stSidebar"] a:hover {
    background: rgba(24, 205, 234, 0.12);
}

[data-testid="stSidebar"] button {
    color: var(--nave-navy);
}

.block-container {
    max-width: 1440px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

h1, h2, h3, h4 {
    color: var(--nave-navy);
    letter-spacing: -0.025em;
}

p, label {
    color: var(--nave-text);
}

[data-testid="stCaptionContainer"] {
    color: var(--nave-muted);
}

[data-testid="stMetric"] {
    background: rgba(244, 246, 249, 0.92);
    border: 1px solid var(--nave-border);
    border-radius: 15px;
    min-height: 112px;
    padding: 0.95rem 1.05rem;
}

[data-testid="stMetricLabel"] {
    color: var(--nave-muted);
}

[data-testid="stMetricValue"] {
    color: var(--nave-navy);
    font-weight: 700;
}

div[data-testid="stExpander"] {
    border: 1px solid var(--nave-border);
    border-radius: 14px;
    overflow: hidden;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
textarea,
[data-testid="stFileUploaderDropzone"] {
    border-radius: 12px !important;
}

/* =========================
   BOTÕES PADRONIZADOS NAVE
   Padrão: azul escuro + texto branco
   Hover: azul claro + texto escuro
   ========================= */

.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button,
.stLinkButton > a,
[data-testid="stLinkButton"] > a {
    background: var(--nave-navy) !important;
    border: 1px solid var(--nave-navy) !important;
    color: #FFFFFF !important;
    border-radius: 11px !important;
    font-weight: 650 !important;
    min-height: 2.7rem !important;
    text-decoration: none !important;
    box-shadow: none !important;
    transition: all 0.18s ease-in-out !important;
}

.stButton > button p,
.stDownloadButton > button p,
[data-testid="stFormSubmitButton"] > button p,
.stLinkButton > a p,
[data-testid="stLinkButton"] > a p,
.stLinkButton > a span,
[data-testid="stLinkButton"] > a span {
    color: #FFFFFF !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover,
.stLinkButton > a:hover,
[data-testid="stLinkButton"] > a:hover {
    background: var(--nave-cyan) !important;
    border-color: var(--nave-cyan) !important;
    color: #0C122F !important;
}

.stButton > button:hover p,
.stDownloadButton > button:hover p,
[data-testid="stFormSubmitButton"] > button:hover p,
.stLinkButton > a:hover p,
[data-testid="stLinkButton"] > a:hover p,
.stLinkButton > a:hover span,
[data-testid="stLinkButton"] > a:hover span {
    color: #0C122F !important;
}

.stButton > button:disabled,
.stDownloadButton > button:disabled,
[data-testid="stFormSubmitButton"] > button:disabled,
.stLinkButton > a[aria-disabled="true"],
[data-testid="stLinkButton"] > a[aria-disabled="true"] {
    background: #E8ECF6 !important;
    border-color: #D3DAEC !important;
    color: #7C88A8 !important;
    opacity: 1 !important;
    cursor: not-allowed !important;
}

.stButton > button:disabled p,
.stDownloadButton > button:disabled p,
[data-testid="stFormSubmitButton"] > button:disabled p {
    color: #7C88A8 !important;
}

[data-testid="stAlert"] {
    border-radius: 13px;
}

.nave-sidebar-symbol {
    margin: 0 auto 0.55rem;
    max-width: 76px;
}

.nave-sidebar-brand {
    color: #FFFFFF;
    font-size: 1.08rem;
    font-weight: 760;
    letter-spacing: -0.02em;
    margin: 0;
    text-align: center;
}

.nave-sidebar-expansion {
    color: rgba(255, 255, 255, 0.64);
    font-size: 0.68rem;
    line-height: 1.4;
    margin: 0.25rem auto 1rem;
    max-width: 205px;
    text-align: center;
}

.nave-sidebar-section {
    color: var(--nave-cyan) !important;
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.13em;
    margin: 1.2rem 0 0.4rem;
    text-transform: uppercase;
}

.nave-sidebar-footer {
    border-top: 1px solid rgba(255,255,255,0.14);
    color: rgba(255, 255, 255, 0.55) !important;
    font-size: 0.68rem;
    line-height: 1.5;
    margin-top: 1.45rem;
    padding-top: 0.9rem;
}

.nave-page-header {
    border-bottom: 1px solid var(--nave-border);
    margin-bottom: 1.45rem;
    padding: 0 0 1.05rem;
}

.nave-eyebrow {
    color: var(--nave-cyan);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.13em;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
}

.nave-page-title {
    color: var(--nave-navy);
    font-size: clamp(2rem, 4vw, 3.25rem);
    font-weight: 760;
    letter-spacing: -0.045em;
    line-height: 1.03;
    margin: 0;
}

.nave-page-subtitle {
    color: var(--nave-muted);
    font-size: 0.98rem;
    line-height: 1.55;
    margin: 0.62rem 0 0;
    max-width: 880px;
}

.nave-home {
    border-bottom: 1px solid var(--nave-border);
    margin-bottom: 1.45rem;
    padding-bottom: 1.45rem;
}

.nave-home-brand {
    margin-bottom: 0.75rem;
    max-width: 600px;
}

.nave-home-expansion {
    color: var(--nave-navy);
    font-size: 1rem;
    font-weight: 520;
    margin-bottom: 0.35rem;
}

.nave-home-tagline {
    color: var(--nave-navy);
    font-size: clamp(1.7rem, 3.2vw, 2.7rem);
    font-weight: 740;
    letter-spacing: -0.04em;
    line-height: 1.08;
    margin: 0;
    max-width: 900px;
}

.nave-home-description {
    color: var(--nave-muted);
    font-size: 0.98rem;
    line-height: 1.58;
    margin: 0.8rem 0 0;
    max-width: 930px;
}

.nave-card {
    background: #FFFFFF;
    border: 1px solid var(--nave-border);
    border-radius: 15px;
    min-height: 137px;
    padding: 1.1rem;
}

.nave-card-number {
    color: var(--nave-cyan);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.12em;
}

.nave-card-title {
    color: var(--nave-navy);
    font-size: 1rem;
    font-weight: 720;
    margin-top: 0.5rem;
}

.nave-card-copy {
    color: var(--nave-muted);
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.35rem;
}

.nave-admin-box {
    background: var(--nave-surface);
    border: 1px solid var(--nave-border);
    border-radius: 15px;
    padding: 1rem 1.1rem;
}

.nave-detail-section-title {
    border-bottom: 1px solid var(--nave-border);
    color: var(--nave-navy);
    font-size: 1rem;
    font-weight: 760;
    margin: 1.6rem 0 0.8rem;
    padding-bottom: 0.45rem;
}

.nave-field-card {
    background: #FFFFFF;
    border: 1px solid var(--nave-border);
    border-radius: 12px;
    height: calc(100% - 0.5rem);
    margin-bottom: 0.75rem;
    min-height: 92px;
    padding: 0.85rem 0.95rem;
}

.nave-field-label {
    color: var(--nave-cyan);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    margin-bottom: 0.42rem;
    text-transform: uppercase;
}

.nave-field-value {
    color: var(--nave-navy);
    font-size: 0.88rem;
    line-height: 1.46;
    overflow-wrap: anywhere;
}

.nave-field-value a {
    color: var(--nave-navy);
    font-weight: 700;
}

.nave-field-empty {
    color: #929AAF;
    font-style: italic;
}
</style>
"""


def apply_nave_branding() -> None:
    st.markdown(BRAND_CSS, unsafe_allow_html=True)
    render_sidebar()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            (
                '<div class="nave-sidebar-symbol">'
                f'<img src="data:image/svg+xml;utf8,'
                f'{_svg_data(NAVE_LOCKUP_WHITE_PATH, symbol_only=True)}" '
                'style="width:100%;height:auto;">'
                '</div>'
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="nave-sidebar-brand">NAVE by VOE</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="nave-sidebar-expansion">
                Núcleo de Análise VOE para Experiências
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="nave-sidebar-section">Navegação</div>',
            unsafe_allow_html=True,
        )
        st.page_link(
            "streamlit_app.py",
            label="Início",
        )
        st.page_link(
            "pages/1_Organizar_Conhecimento.py",
            label="Organizar conhecimento",
        )
        st.page_link(
            "pages/2_Consultar_Base.py",
            label="Base de conhecimento",
        )
        st.page_link(
            "pages/3_Nova_Recomendacao.py",
            label="Analisar e recomendar",
        )
        st.page_link(
            "pages/4_Historico_de_Projetos.py",
            label="Projetos",
        )
        st.page_link(
            "pages/5_Cobertura_de_Fornecedores.py",
            label="Fornecedores",
        )

        st.markdown(
            '<div class="nave-sidebar-section">Sistema</div>',
            unsafe_allow_html=True,
        )
        st.page_link(
            "pages/6_Administracao.py",
            label="Acesso administrativo",
        )

        st.markdown(
            """
            <div class="nave-sidebar-footer">
                Inteligência que impulsiona decisões e experiências.<br>
                Confidencial e de uso interno.
            </div>
            """,
            unsafe_allow_html=True,
        )
        app_logout_button()


def _svg_data(path: Path, *, symbol_only: bool = False) -> str:
    if symbol_only:
        symbol_path = ASSET_DIR / "nave_symbol_white.svg"
        svg = symbol_path.read_text(encoding="utf-8")
    else:
        svg = path.read_text(encoding="utf-8")
    return (
        svg.replace("#", "%23")
        .replace("\n", "")
        .replace('"', "'")
    )


def page_header(
    title: str,
    subtitle: str,
    *,
    eyebrow: str = "NAVE by VOE",
) -> None:
    st.markdown(
        f"""
        <section class="nave-page-header">
            <div class="nave-eyebrow">{escape(eyebrow)}</div>
            <h1 class="nave-page-title">{escape(title)}</h1>
            <p class="nave-page-subtitle">{escape(subtitle)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def home_header() -> None:
    lockup = _svg_data(NAVE_LOCKUP_PATH)
    st.markdown(
        f"""
        <section class="nave-home">
            <div class="nave-home-brand">
                <img src="data:image/svg+xml;utf8,{lockup}"
                     style="width:100%;height:auto;">
            </div>
            <div class="nave-home-expansion">
                Núcleo de Análise VOE para Experiências
            </div>
            <h1 class="nave-home-tagline">
                Conectando briefing, repertório e decisão.
            </h1>
            <p class="nave-home-description">
                Plataforma proprietária de inteligência de pré-produção
                que organiza conhecimento, qualifica briefings e recomenda
                soluções para projetos de live marketing.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def journey_cards() -> None:
    columns = st.columns(4)
    cards = [
        (
            "01",
            "Organizar",
            "Estruture brindes, soluções, locais e projetos.",
        ),
        (
            "02",
            "Qualificar",
            "Identifique lacunas, contradições e pontos críticos.",
        ),
        (
            "03",
            "Conectar",
            "Relacione necessidades ao repertório da agência.",
        ),
        (
            "04",
            "Recomendar",
            "Encontre direções aderentes a cada projeto.",
        ),
    ]

    for column, (number, title, copy) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <article class="nave-card">
                    <div class="nave-card-number">{number}</div>
                    <div class="nave-card-title">{escape(title)}</div>
                    <div class="nave-card-copy">{escape(copy)}</div>
                </article>
                """,
                unsafe_allow_html=True,
            )
