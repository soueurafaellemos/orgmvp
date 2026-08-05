from __future__ import annotations

import hmac
import logging
import os
from typing import Any

import streamlit as st


LOGGER = logging.getLogger("nave")


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


def require_admin_access() -> bool:
    expected_password = str(
        get_setting("NAVE_ADMIN_PASSWORD", "")
    ).strip()

    if not expected_password:
        st.warning(
            "A área administrativa ainda não foi habilitada."
        )
        st.info(
            "Adicione uma senha administrativa nas configurações "
            "do aplicativo para liberar este acesso."
        )
        return False

    if st.session_state.get(
        "nave_admin_authenticated",
        False,
    ):
        return True

    st.subheader("Acesso restrito")
    st.caption(
        "Esta área reúne configurações e diagnósticos internos."
    )

    with st.form("nave_admin_login"):
        password = st.text_input(
            "Senha de administração",
            type="password",
        )
        submitted = st.form_submit_button(
            "Entrar",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if hmac.compare_digest(
            password,
            expected_password,
        ):
            st.session_state[
                "nave_admin_authenticated"
            ] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    return False


def admin_logout_button() -> None:
    if st.button(
        "Sair da Administração",
        use_container_width=True,
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
