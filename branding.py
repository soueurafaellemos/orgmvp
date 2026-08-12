from __future__ import annotations

from html import escape
from pathlib import Path
import hashlib

import streamlit as st
from nave_table_utils import COVER_COLUMN_NAMES, sanitize_cover_dataframe
from runtime_ui import app_logout_button

ROOT_DIR = Path(__file__).resolve().parent
ASSET_DIR = ROOT_DIR / "assets"
NAVE_LOCKUP_PATH = ASSET_DIR / "nave_lockup.svg"
NAVE_LOCKUP_WHITE_PATH = ASSET_DIR / "nave_lockup_white.svg"
NAVE_SYMBOL_PATH = ASSET_DIR / "nave_symbol.svg"
NAVE_APP_ICON_PATH = ASSET_DIR / "nave_app_icon.png"
NAVE_APP_ICON = str(NAVE_APP_ICON_PATH)

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
    font-family: "Avenir Next", "Avenir", "Inter", "Segoe UI", Arial, sans-serif;
}
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 100% 0%, rgba(24, 205, 234, 0.06), transparent 28rem), #FFFFFF;
}
[data-testid="stHeader"] { background: rgba(255,255,255,0); }
[data-testid="stDecoration"], [data-testid="manage-app-button"], .stDeployButton, #MainMenu, footer {
    display: none !important; visibility: hidden !important;
}
[data-testid="stToolbar"], [data-testid="stStatusWidget"] { display:flex !important; visibility:visible !important; }
[data-testid="stSidebarNav"] { display:none !important; }
[data-testid="stSidebar"] { background:var(--nave-navy); border-right:0; }
[data-testid="stSidebar"] > div:first-child { padding-top:1.1rem; }
[data-testid="stSidebar"] * { color:rgba(255,255,255,0.92); }
[data-testid="stSidebar"] [data-testid="stImage"] { margin-bottom:0.25rem; }
[data-testid="stSidebar"] a { border-radius:10px; margin:0.12rem 0; padding:0.15rem 0.35rem; text-decoration:none; }
[data-testid="stSidebar"] a:hover { background:rgba(24,205,234,0.12); }
[data-testid="stSidebar"] button { color:var(--nave-navy); }
.block-container { max-width:1440px; padding-top:2rem; padding-bottom:4rem; }
h1,h2,h3,h4 { color:var(--nave-navy); letter-spacing:-0.025em; }
p,label { color:var(--nave-text); }
[data-testid="stCaptionContainer"] { color:var(--nave-muted); }
[data-testid="stMetric"] { background:rgba(244,246,249,0.92); border:1px solid var(--nave-border); border-radius:15px; min-height:112px; padding:0.95rem 1.05rem; }
[data-testid="stMetricLabel"] { color:var(--nave-muted); }
[data-testid="stMetricValue"] { color:var(--nave-navy); font-weight:700; }
div[data-testid="stExpander"] { border:1px solid var(--nave-border); border-radius:14px; overflow:hidden; }
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, textarea, [data-testid="stFileUploaderDropzone"] { border-radius:12px !important; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, .stLinkButton > a, [data-testid="stLinkButton"] > a {
    background:var(--nave-navy) !important; border:1px solid var(--nave-navy) !important; color:#FFFFFF !important; border-radius:11px !important; font-weight:650 !important; min-height:2.7rem !important; text-decoration:none !important; box-shadow:none !important; transition:all 0.18s ease-in-out !important;
}
.stButton > button p, .stDownloadButton > button p, [data-testid="stFormSubmitButton"] > button p, .stLinkButton > a p, [data-testid="stLinkButton"] > a p, .stLinkButton > a span, [data-testid="stLinkButton"] > a span { color:#FFFFFF !important; }
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover, .stLinkButton > a:hover, [data-testid="stLinkButton"] > a:hover { background:var(--nave-cyan) !important; border-color:var(--nave-cyan) !important; color:#0C122F !important; }
.stButton > button:hover p, .stDownloadButton > button:hover p, [data-testid="stFormSubmitButton"] > button:hover p, .stLinkButton > a:hover p, [data-testid="stLinkButton"] > a:hover p, .stLinkButton > a:hover span, [data-testid="stLinkButton"] > a:hover span { color:#0C122F !important; }
.stButton > button:disabled, .stDownloadButton > button:disabled, [data-testid="stFormSubmitButton"] > button:disabled, .stLinkButton > a[aria-disabled="true"], [data-testid="stLinkButton"] > a[aria-disabled="true"] { background:#E8ECF6 !important; border-color:#D3DAEC !important; color:#7C88A8 !important; opacity:1 !important; cursor:not-allowed !important; }
.stButton > button:disabled p, .stDownloadButton > button:disabled p, [data-testid="stFormSubmitButton"] > button:disabled p { color:#7C88A8 !important; }
[data-testid="stAlert"] { border-radius:13px; }
.nave-sidebar-symbol { margin:0 auto 0.55rem; max-width:76px; }
.nave-sidebar-brand { color:#FFFFFF; font-size:1.08rem; font-weight:760; letter-spacing:-0.02em; margin:0; text-align:center; }
.nave-sidebar-expansion { color:rgba(255,255,255,0.64); font-size:0.68rem; line-height:1.4; margin:0.25rem auto 1rem; max-width:205px; text-align:center; }
.nave-sidebar-section { color:var(--nave-cyan) !important; font-size:0.65rem; font-weight:800; letter-spacing:0.13em; margin:1.2rem 0 0.4rem; text-transform:uppercase; }
.nave-sidebar-footer { border-top:1px solid rgba(255,255,255,0.14); color:rgba(255,255,255,0.55) !important; font-size:0.68rem; line-height:1.5; margin-top:1.45rem; padding-top:0.9rem; }
.nave-page-header { border-bottom:1px solid var(--nave-border); margin-bottom:1.45rem; padding:0 0 1.05rem; }
.nave-eyebrow { color:var(--nave-cyan); font-size:0.72rem; font-weight:800; letter-spacing:0.13em; margin-bottom:0.5rem; text-transform:uppercase; }
.nave-page-title { color:var(--nave-navy); font-size:clamp(2rem,4vw,3.25rem); font-weight:760; letter-spacing:-0.045em; line-height:1.03; margin:0; }
.nave-page-subtitle { color:var(--nave-muted); font-size:0.98rem; line-height:1.55; margin:0.62rem 0 0; max-width:880px; }
.nave-home { border-bottom:1px solid var(--nave-border); margin-bottom:1.45rem; padding-bottom:1.45rem; }
.nave-home-brand { margin-bottom:0.75rem; max-width:600px; }
.nave-home-expansion { color:var(--nave-navy); font-size:1rem; font-weight:520; margin-bottom:0.35rem; }
.nave-home-tagline { color:var(--nave-navy); font-size:clamp(1.7rem,3.2vw,2.7rem); font-weight:740; letter-spacing:-0.04em; line-height:1.08; margin:0; max-width:900px; }
.nave-home-description { color:var(--nave-muted); font-size:0.98rem; line-height:1.58; margin:0.8rem 0 0; max-width:930px; }
.nave-card { background:#FFFFFF; border:1px solid var(--nave-border); border-radius:15px; min-height:137px; padding:1.1rem; }
.nave-card-number { color:var(--nave-cyan); font-size:0.7rem; font-weight:800; letter-spacing:0.12em; }
.nave-card-title { color:var(--nave-navy); font-size:1rem; font-weight:720; margin-top:0.5rem; }
.nave-card-copy { color:var(--nave-muted); font-size:0.82rem; line-height:1.45; margin-top:0.35rem; }
.nave-admin-box { background:var(--nave-surface); border:1px solid var(--nave-border); border-radius:15px; padding:1rem 1.1rem; }
.nave-detail-section-title { border-bottom:1px solid var(--nave-border); color:var(--nave-navy); font-size:1rem; font-weight:760; margin:1.6rem 0 0.8rem; padding-bottom:0.45rem; }
.nave-field-card { background:#FFFFFF; border:1px solid var(--nave-border); border-radius:12px; height:calc(100% - 0.5rem); margin-bottom:0.75rem; min-height:92px; padding:0.85rem 0.95rem; }
.nave-field-label { color:var(--nave-cyan); font-size:0.68rem; font-weight:800; letter-spacing:0.06em; margin-bottom:0.42rem; text-transform:uppercase; }
.nave-field-value { color:var(--nave-navy); font-size:0.88rem; line-height:1.46; overflow-wrap:anywhere; }
.nave-field-value a { color:var(--nave-navy); font-weight:700; }
.nave-field-empty { color:#929AAF; font-style:italic; }
</style>
"""



def _entity_type_from_table_columns(columns: set[str]) -> str | None:
    if "Brinde" in columns:
        return "product"
    if "Ativação" in columns or "Ativacao" in columns:
        return "activation"
    if "Local" in columns:
        return "venue"
    if "Fornecedor" in columns and (
        "Cobertura" in columns or "Locais relacionados" in columns
    ):
        return "supplier"
    return None


def _hydrate_missing_covers(data):
    """Recupera capas validadas para tabelas especializadas sem alterar as páginas."""
    if not hasattr(data, "columns"):
        return data
    columns = set(str(column) for column in data.columns)
    cover_column = next((name for name in COVER_COLUMN_NAMES if name in data.columns), None)
    entity_type = _entity_type_from_table_columns(columns)
    id_column = "_id" if "_id" in data.columns else ("id" if "id" in data.columns else None)
    if not cover_column or not entity_type or not id_column:
        return data

    missing_positions = [
        position
        for position, value in enumerate(data[cover_column].tolist())
        if not str(value or "").strip() or str(value).strip().casefold() in {"none", "nan", "null", "<na>"}
    ]
    if not missing_positions:
        return data

    ids = [
        str(data.iloc[position].get(id_column) or "").strip()
        for position in missing_positions
    ]
    ids = [entity_id for entity_id in ids if entity_id]
    if not ids:
        return data

    try:
        from nave_data_client import get_nave_client
        from knowledge_specialized import fetch_media_assets_batch, primary_image_url

        client = get_nave_client()
        table = {
            "product": "products",
            "activation": "activation_solutions",
            "venue": "venues",
            "supplier": "suppliers",
        }[entity_type]
        response = client.table(table).select("*").in_("id", ids).execute()
        full_rows = {
            str(row.get("id") or ""): dict(row)
            for row in (getattr(response, "data", None) or [])
            if isinstance(row, dict) and row.get("id")
        }
        media = fetch_media_assets_batch(client, entity_type, ids)
        result = data.copy()
        for position in missing_positions:
            entity_id = str(result.iloc[position].get(id_column) or "").strip()
            if not entity_id:
                continue
            # A linha visível pode carregar pistas de mídia que não fazem parte
            # do SELECT enxuto da página. O registro completo continua tendo
            # prioridade, mas os dois contextos são combinados antes da busca.
            visible = {str(key): value for key, value in result.iloc[position].to_dict().items()}
            record = dict(visible)
            record.update(full_rows.get(entity_id) or {})
            record["id"] = entity_id
            cover = primary_image_url(
                client,
                entity_type,
                record,
                media.get(entity_id, []),
            )
            if cover:
                result.iat[position, result.columns.get_loc(cover_column)] = cover
        return result
    except Exception:
        return data

def _deletion_context(columns: set[str], data) -> tuple[str, str, str] | None:
    """Detecta somente listas canônicas em que exclusão explícita é segura.

    Locais ficam de fora deliberadamente. A exclusão é oferecida para Brindes,
    Ativações, Fornecedores e Projetos quando a tabela carrega um identificador
    real do registro — nunca por posição visual da linha.
    """
    id_candidates = ("_id", "id", "_project_id", "project_id")
    id_column = next((item for item in id_candidates if item in getattr(data, "columns", [])), None)
    if not id_column:
        return None
    if "Brinde" in columns:
        return "product", "brinde", id_column
    if "Ativação" in columns or "Ativacao" in columns:
        return "activation", "ativação", id_column
    if "Fornecedor" in columns:
        return "supplier", "fornecedor", id_column
    if "Projeto" in columns and ({"Cliente", "Evento", "Status"} & columns):
        return "project", "projeto", id_column
    return None


def _render_deletion_action(*, cleaned, valid_rows: list[int], context: tuple[str, str, str], table_key: str) -> None:
    entity_type, singular_label, id_column = context
    entity_ids = [
        str(cleaned.iloc[position].get(id_column) or "").strip()
        for position in valid_rows
    ]
    entity_ids = [item for item in dict.fromkeys(entity_ids) if item]
    if not entity_ids:
        return

    amount = len(entity_ids)
    plural = singular_label if amount == 1 else {
        "brinde": "brindes",
        "ativação": "ativações",
        "fornecedor": "fornecedores",
        "projeto": "projetos",
    }.get(singular_label, f"{singular_label}s")
    suffix = hashlib.sha1(
        f"{table_key}|{entity_type}|{'|'.join(entity_ids)}".encode("utf-8")
    ).hexdigest()[:12]

    selected_word = "selecionado" if amount == 1 else "selecionados"
    with st.expander(f"Excluir {amount} {plural} {selected_word}", expanded=False):
        if entity_type == "project":
            st.warning(
                "A exclusão remove o projeto e os dados que pertencem exclusivamente a ele. "
                "Cadastros transversais que apenas estavam relacionados ao projeto não são apagados."
            )
        else:
            st.warning(
                "Use esta ação somente quando o cadastro realmente entrou errado. "
                "A exclusão é permanente; vínculos técnicos que usam este registro são preservados ou desvinculados quando o banco permitir."
            )
        confirmed = st.checkbox(
            f"Confirmo a exclusão de {amount} {plural} {selected_word}.",
            key=f"nave_delete_confirm_{suffix}",
        )
        if st.button(
            f"Excluir {plural} {selected_word}",
            disabled=not confirmed,
            width="stretch",
            key=f"nave_delete_button_{suffix}",
        ):
            from nave_data_client import get_nave_client
            from nave_delete import delete_entities

            client = get_nave_client()
            with st.spinner("Excluindo os registros selecionados com segurança..."):
                results = delete_entities(
                    client,
                    entity_type=entity_type,
                    entity_ids=entity_ids,
                )
            deleted = [item for item in results if item.get("status") == "deleted"]
            protected = [item for item in results if item.get("status") == "protected"]
            errors = [
                item for item in results
                if item.get("status") not in {"deleted", "not_found"}
                and item not in protected
            ]
            if deleted:
                st.success(f"{len(deleted)} registro(s) excluído(s).")
            for item in protected + errors:
                st.warning(f"{item.get('label')}: {item.get('message')}")
            if deleted:
                st.rerun()


def _install_cover_table_guard() -> None:
    """Padroniza tabelas canônicas sem exigir alterações em todas as páginas.

    Preserva o tratamento de Capa, seleção múltipla/PDF e acrescenta exclusão
    explícita por seleção para Brindes, Ativações, Fornecedores e Projetos.
    """
    current = st.dataframe
    if getattr(current, "_nave_cover_guard", False):
        return

    original = current

    def guarded_dataframe(data=None, *args, **kwargs):
        cleaned = _hydrate_missing_covers(sanitize_cover_dataframe(data))
        cover_column = None
        promote_to_multi = False
        deletion_context = None
        table_columns: set[str] = set()
        if hasattr(cleaned, "columns"):
            table_columns = set(str(column) for column in cleaned.columns)
            cover_column = next(
                (name for name in COVER_COLUMN_NAMES if name in cleaned.columns),
                None,
            )
            deletion_context = _deletion_context(table_columns, cleaned)
            config = dict(kwargs.get("column_config") or {})

            if cover_column:
                # Força Capa como imagem mesmo quando uma página antiga a configurou como texto.
                config[cover_column] = st.column_config.ImageColumn(
                    cover_column,
                    width="small",
                    help="Imagem principal validada no acervo.",
                )
                kwargs.setdefault("row_height", 64)

            # IDs são necessários para ações seguras, mas nunca precisam aparecer.
            for hidden_id in ("_id", "id", "_project_id", "project_id"):
                if hidden_id in getattr(cleaned, "columns", []):
                    config[hidden_id] = None
            if config:
                kwargs["column_config"] = config

            # Padrão NAVE: listas especializadas + Projetos aceitam seleção
            # múltipla. A posição nunca é usada como identidade para exclusão.
            if (
                kwargs.get("selection_mode") == "single-row"
                and kwargs.get("on_select") == "rerun"
                and (cover_column or deletion_context)
            ):
                kwargs["selection_mode"] = "multi-row"
                promote_to_multi = True

        event = original(cleaned, *args, **kwargs)

        selected_rows = list(
            getattr(getattr(event, "selection", None), "rows", []) or []
        )
        valid_rows = [
            position for position in selected_rows
            if isinstance(position, int) and hasattr(cleaned, "iloc") and 0 <= position < len(cleaned)
        ]

        # Uma ou mais linhas das áreas visuais podem gerar o PDF de repertório.
        # A seleção múltipla continua disponível, mas um único item também deve
        # poder ser exportado sem obrigar o usuário a marcar um segundo registro.
        if promote_to_multi and cover_column and hasattr(cleaned, "iloc") and len(valid_rows) >= 1:
            from selection_pdf import build_selection_pdf

            selected_records = cleaned.iloc[valid_rows].to_dict(orient="records")
            if "Brinde" in table_columns:
                source_context, file_slug = "Brindes", "brindes"
            elif "Ativação" in table_columns or "Ativacao" in table_columns:
                source_context, file_slug = "Ativações", "ativacoes"
            elif "Local" in table_columns:
                source_context, file_slug = "Locais e espaços", "locais"
            elif "Fornecedor" in table_columns:
                source_context, file_slug = "Fornecedores", "fornecedores"
            else:
                source_context, file_slug = "Base de Conhecimento", "base_conhecimento"

            pdf_bytes = build_selection_pdf(
                selected_records,
                title=f"Seleção de {source_context} - NAVE by VOE",
                source_context=source_context,
            )
            action_col, info_col = st.columns([1.15, 3.85])
            with action_col:
                st.download_button(
                    "Exportar seleção em PDF",
                    data=pdf_bytes,
                    file_name=f"NAVE_selecao_{file_slug}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key=f"nave_selection_pdf_{kwargs.get('key', 'table')}",
                )
            with info_col:
                item_label = "item selecionado" if len(valid_rows) == 1 else "itens selecionados"
                st.caption(
                    f"{len(valid_rows)} {item_label}. "
                    "A ficha abaixo continua usando o primeiro item selecionado."
                )

        if deletion_context and valid_rows and hasattr(cleaned, "iloc"):
            _render_deletion_action(
                cleaned=cleaned,
                valid_rows=valid_rows,
                context=deletion_context,
                table_key=str(kwargs.get("key") or "table"),
            )
        return event

    guarded_dataframe._nave_cover_guard = True
    guarded_dataframe._nave_original = original
    st.dataframe = guarded_dataframe


def apply_nave_branding() -> None:
    _install_cover_table_guard()

    # Branding não executa migrações nem materialização de dados.
    # Correções de projetos legados são explícitas na página de importação.

    st.markdown(BRAND_CSS, unsafe_allow_html=True)
    render_sidebar()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="nave-sidebar-symbol">'
            f'<img src="data:image/svg+xml;utf8,{_svg_data(NAVE_LOCKUP_WHITE_PATH, symbol_only=True)}" style="width:100%;height:auto;">'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="nave-sidebar-brand">NAVE by VOE</div>', unsafe_allow_html=True)
        st.markdown('<div class="nave-sidebar-expansion">Núcleo de Análise VOE para Experiências</div>', unsafe_allow_html=True)
        st.markdown('<div class="nave-sidebar-section">Navegação</div>', unsafe_allow_html=True)

        st.page_link("streamlit_app.py", label="Home")
        st.page_link("pages/1_Organizar_Conhecimento.py", label="Upload de Conhecimento")
        st.page_link("pages/14_Importar_Projeto.py", label="Importar projeto completo")
        st.page_link("pages/2_Consultar_Base.py", label="Base de Conhecimento")
        st.page_link("pages/12_Ativacoes.py", label="Ativações")
        st.page_link("pages/13_Brindes.py", label="Brindes")
        st.page_link("pages/11_Locais_e_Espacos.py", label="Locais e espaços")
        st.page_link("pages/5_Cobertura_de_Fornecedores.py", label="Fornecedores")
        st.page_link("pages/3_Nova_Recomendacao.py", label="Analisar e recomendar")
        st.page_link("pages/4_Historico_de_Projetos.py", label="Projetos")

        st.markdown('<div class="nave-sidebar-section">Qualidade da base</div>', unsafe_allow_html=True)
        st.page_link("pages/8_Qualidade_da_Base.py", label="Prontidão da base")
        st.page_link("pages/7_Revisar_Duplicidades.py", label="Revisar duplicidades")
        st.page_link("pages/9_Taxonomia_NAVE.py", label="Taxonomia NAVE")

        st.markdown('<div class="nave-sidebar-section">Sistema</div>', unsafe_allow_html=True)
        st.page_link("pages/6_Administracao.py", label="Acesso administrativo")
        st.markdown('<div class="nave-sidebar-footer">Inteligência que impulsiona decisões e experiências.<br>Confidencial e de uso interno.</div>', unsafe_allow_html=True)
        app_logout_button()


def _svg_data(path: Path, *, symbol_only: bool = False) -> str:
    if symbol_only:
        path = ASSET_DIR / "nave_symbol_white.svg"
    svg = path.read_text(encoding="utf-8")
    return svg.replace("#", "%23").replace("\n", "").replace('"', "'")


def page_header(title: str, subtitle: str, *, eyebrow: str = "NAVE by VOE") -> None:
    st.markdown(
        f'''<section class="nave-page-header"><div class="nave-eyebrow">{escape(eyebrow)}</div><h1 class="nave-page-title">{escape(title)}</h1><p class="nave-page-subtitle">{escape(subtitle)}</p></section>''',
        unsafe_allow_html=True,
    )


def home_header() -> None:
    lockup = _svg_data(NAVE_LOCKUP_PATH)
    st.markdown(
        f'''<section class="nave-home"><div class="nave-home-brand"><img src="data:image/svg+xml;utf8,{lockup}" style="width:100%;height:auto;"></div><div class="nave-home-expansion">Núcleo de Análise VOE para Experiências</div><h1 class="nave-home-tagline">Conectando briefing, repertório e decisão.</h1><p class="nave-home-description">Plataforma proprietária de inteligência de pré-produção que organiza conhecimento, qualifica briefings e recomenda soluções para projetos de live marketing.</p></section>''',
        unsafe_allow_html=True,
    )


def journey_cards() -> None:
    columns = st.columns(4)
    cards = [
        ("01", "Organizar", "Estruture brindes, soluções, locais e projetos."),
        ("02", "Qualificar", "Identifique lacunas, contradições e pontos críticos."),
        ("03", "Conectar", "Relacione necessidades ao repertório da agência."),
        ("04", "Recomendar", "Encontre direções aderentes a cada projeto."),
    ]
    for column, (number, title, copy) in zip(columns, cards):
        with column:
            st.markdown(
                f'''<article class="nave-card"><div class="nave-card-number">{number}</div><div class="nave-card-title">{escape(title)}</div><div class="nave-card-copy">{escape(copy)}</div></article>''',
                unsafe_allow_html=True,
            )
