from __future__ import annotations

import base64
import hmac
import logging
import os
from pathlib import Path
from typing import Any

import streamlit as st


LOGGER = logging.getLogger("nave")


ROOT_DIR = Path(__file__).resolve().parent
LOGIN_LOGO_PATH = ROOT_DIR / "assets" / "nave_login_lockup.svg"


def _login_logo_data_uri() -> str:
    svg_bytes = LOGIN_LOGO_PATH.read_bytes()
    encoded = base64.b64encode(svg_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


LOGIN_CSS = """
<style>
:root {
    --nave-navy: #121B42;
    --nave-cyan: #18CDEA;
    --nave-surface: #F4F6F9;
    --nave-border: #DCE2ED;
    --nave-muted: #687188;
}

[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(
            circle at 50% -10%,
            rgba(24, 205, 234, 0.08),
            transparent 31rem
        ),
        #FFFFFF !important;
}

[data-testid="stMain"] {
    min-height: 100vh !important;
}

[data-testid="stMainBlockContainer"],
.block-container {
    box-sizing: border-box !important;
    margin: 0 auto !important;
    max-width: 1180px !important;
    padding:
        clamp(2rem, 6vh, 4rem)
        1.25rem
        2.5rem !important;
    width: 100% !important;
}

[data-testid="stHorizontalBlock"] {
    align-items: flex-start !important;
}

.nave-login-logo {
    display: flex !important;
    justify-content: center !important;
    margin: 0 auto 0.8rem !important;
    max-width: 390px !important;
    text-align: center;
    width: min(100%, 390px) !important;
}

.nave-login-logo img {
    display: block;
    height: auto !important;
    margin: 0 auto;
    max-width: 100% !important;
    width: 100% !important;
}

.nave-login-mark {
    color: var(--nave-cyan);
    font-size: clamp(0.66rem, 1.8vw, 0.76rem);
    font-weight: 800;
    letter-spacing: 0.15em;
    line-height: 1.4;
    margin: 0.15rem auto 0.35rem;
    max-width: 430px;
    text-align: center;
    text-transform: uppercase;
}

.nave-login-copy {
    color: var(--nave-muted);
    font-size: clamp(0.95rem, 2.4vw, 1.08rem);
    line-height: 1.5;
    margin: 0 auto 1.6rem;
    max-width: 430px;
    text-align: center;
}

[data-testid="stForm"] {
    background: #FFFFFF !important;
    border: 1px solid var(--nave-border) !important;
    border-radius: 18px !important;
    box-shadow:
        0 18px 42px rgba(18, 27, 66, 0.08) !important;
    box-sizing: border-box !important;
    margin: 0 auto !important;
    padding: 1.35rem 1.45rem 1.45rem !important;
    width: 100% !important;
}

[data-testid="stForm"] > div {
    gap: 0.8rem !important;
}

[data-testid="stForm"] label,
[data-testid="stForm"] [data-testid="stWidgetLabel"] {
    color: var(--nave-navy) !important;
    font-size: 0.93rem !important;
    font-weight: 650 !important;
}

[data-testid="stTextInput"] input {
    background: var(--nave-surface) !important;
    border: 1px solid var(--nave-border) !important;
    border-radius: 12px !important;
    color: var(--nave-navy) !important;
    min-height: 3rem !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: var(--nave-cyan) !important;
    box-shadow:
        0 0 0 1px var(--nave-cyan) !important;
}

[data-testid="stFormSubmitButton"] button {
    background: var(--nave-navy) !important;
    border: 1px solid var(--nave-navy) !important;
    border-radius: 12px !important;
    box-shadow: none !important;
    color: #FFFFFF !important;
    font-size: 0.98rem !important;
    font-weight: 700 !important;
    min-height: 3rem !important;
    transition: all 0.18s ease-in-out !important;
}

[data-testid="stFormSubmitButton"] button p,
[data-testid="stFormSubmitButton"] button span {
    color: #FFFFFF !important;
}

[data-testid="stFormSubmitButton"] button:hover {
    background: var(--nave-cyan) !important;
    border-color: var(--nave-cyan) !important;
    color: #0C122F !important;
}

[data-testid="stFormSubmitButton"] button:hover p,
[data-testid="stFormSubmitButton"] button:hover span {
    color: #0C122F !important;
}

[data-testid="stDecoration"],
[data-testid="manage-app-button"],
.stDeployButton,
#MainMenu,
footer {
    display: none !important;
    visibility: hidden !important;
}

[data-testid="stToolbar"],
[data-testid="stStatusWidget"] {
    display: flex !important;
    visibility: visible !important;
}

@media (max-width: 600px) {
    [data-testid="stMainBlockContainer"],
    .block-container {
        max-width: 100% !important;
        padding:
            1.8rem
            1rem
            2rem !important;
    }

    .nave-login-logo {
        max-width: 310px !important;
        width: min(100%, 310px) !important;
    }

    [data-testid="stForm"] {
        border-radius: 15px !important;
        padding: 1.1rem 1rem 1.2rem !important;
    }
}
</style>
"""


def get_setting(
    name: str,
    default: Any = "",
) -> Any:
    try:
        return st.secrets.get(
            name,
            os.getenv(name, default),
        )
    except Exception:
        return os.getenv(name, default)


def report_service_error(
    context: str,
    *,
    user_message: str,
    exception: Exception | None = None,
) -> None:
    if exception is not None:
        LOGGER.exception(
            "NAVE service error: %s",
            context,
            exc_info=exception,
        )
    else:
        LOGGER.error("NAVE service error: %s", context)

    st.error(user_message)
    st.caption(
        "A ocorrência foi registrada para diagnóstico. "
        "Tente novamente em alguns instantes ou consulte a Administração."
    )


def _password_matches(
    supplied: str,
    expected: str,
) -> bool:
    return hmac.compare_digest(
        supplied.encode("utf-8"),
        expected.encode("utf-8"),
    )


def require_app_access() -> bool:
    expected_password = str(
        get_setting("NAVE_APP_PASSWORD", "")
    ).strip()

    if st.session_state.get(
        "nave_app_authenticated",
        False,
    ):
        return True

    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    login_logo = _login_logo_data_uri()

    _, login_column, _ = st.columns(
        [1, 1.55, 1],
        gap="large",
    )

    with login_column:
        st.markdown(
            f"""
            <div class="nave-login-logo">
                <img
                    src="{login_logo}"
                    alt="NAVE by VOE"
                >
            </div>
            <div class="nave-login-mark">
                Núcleo de Análise VOE para Experiências
            </div>
            <div class="nave-login-copy">
                Conectando briefing, repertório e decisão.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not expected_password:
            st.error(
                "O acesso à NAVE ainda não foi configurado."
            )
            st.info(
                "Adicione NAVE_APP_PASSWORD aos Secrets do aplicativo "
                "e reinicie a NAVE."
            )
            return False

        with st.form("nave_app_login"):
            password = st.text_input(
                "Senha de acesso",
                type="password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Entrar na NAVE",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if _password_matches(
                password,
                expected_password,
            ):
                st.session_state[
                    "nave_app_authenticated"
                ] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")

    return False


def require_admin_access() -> bool:
    expected_password = str(
        get_setting("NAVE_ADMIN_PASSWORD", "")
    ).strip()

    if st.session_state.get(
        "nave_admin_authenticated",
        False,
    ):
        return True

    if not expected_password:
        st.error(
            "A senha administrativa ainda não foi configurada."
        )
        st.info(
            "Adicione NAVE_ADMIN_PASSWORD aos Secrets do aplicativo "
            "e reinicie a NAVE."
        )
        return False

    st.subheader("Acesso administrativo")
    st.caption(
        "Digite a senha específica da Administração."
    )

    with st.form("nave_admin_login"):
        password = st.text_input(
            "Senha de administração",
            type="password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button(
            "Abrir Administração",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if _password_matches(
            password,
            expected_password,
        ):
            st.session_state[
                "nave_admin_authenticated"
            ] = True
            st.rerun()
        else:
            st.error("Senha administrativa incorreta.")

    return False


def logout_all() -> None:
    st.session_state.pop(
        "nave_app_authenticated",
        None,
    )
    st.session_state.pop(
        "nave_admin_authenticated",
        None,
    )
    st.session_state.pop(
        "nave_support_mode",
        None,
    )


def app_logout_button() -> None:
    if st.button(
        "Sair da NAVE",
        use_container_width=True,
        key="nave_app_logout",
    ):
        logout_all()
        st.rerun()


def admin_logout_button() -> None:
    if st.button(
        "Bloquear Administração",
        use_container_width=True,
        key="nave_admin_logout",
    ):
        st.session_state.pop(
            "nave_admin_authenticated",
            None,
        )
        st.session_state.pop(
            "nave_support_mode",
            None,
        )
        st.rerun()
