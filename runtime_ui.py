from __future__ import annotations

import hmac
import logging
import os
from typing import Any

import streamlit as st


LOGGER = logging.getLogger("nave")


LOGIN_CSS = """
<style>
[data-testid="stSidebar"] {
    display: none !important;
}

[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

.block-container {
    max-width: 560px !important;
    padding-top: 7vh !important;
}

.nave-login-mark {
    color: #18CDEA;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    margin-bottom: 0.55rem;
    text-align: center;
    text-transform: uppercase;
}

.nave-login-title {
    color: #121B42;
    font-size: 2.35rem;
    font-weight: 760;
    letter-spacing: -0.045em;
    line-height: 1.05;
    margin: 0;
    text-align: center;
}

.nave-login-copy {
    color: #687188;
    font-size: 0.94rem;
    line-height: 1.55;
    margin: 0.75rem auto 1.4rem;
    max-width: 430px;
    text-align: center;
}

.nave-login-box {
    background: #F4F6F9;
    border: 1px solid #E1E6EF;
    border-radius: 16px;
    padding: 1.1rem 1.2rem 0.25rem;
}

[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="manage-app-button"],
.stDeployButton,
#MainMenu,
footer {
    display: none !important;
    visibility: hidden !important;
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
    st.markdown(
        """
        <div class="nave-login-mark">
            Núcleo de Análise VOE para Experiências
        </div>
        <h1 class="nave-login-title">
            NAVE by VOE
        </h1>
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
        st.markdown(
            '<div class="nave-login-box">',
            unsafe_allow_html=True,
        )
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
        st.markdown("</div>", unsafe_allow_html=True)

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
