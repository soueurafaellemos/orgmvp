from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

import streamlit as st
from supabase import Client, create_client


_LOGIN_FUNCTIONS = (
    "require_app_access",
    "require_app_login",
    "require_login",
    "ensure_authenticated",
    "app_login_gate",
)

_CLIENT_FUNCTIONS = (
    "get_supabase_client",
    "get_client",
    "create_supabase_client",
    "supabase_client",
)

_SESSION_CLIENT_KEYS = (
    "supabase_client",
    "nave_supabase_client",
    "db_client",
    "client",
)


def _call_zero_arg(function: Callable[..., Any]) -> Any:
    try:
        return function()
    except TypeError:
        return None


def apply_existing_login_gate() -> None:
    """Reaproveita a proteção já instalada na NAVE, sem duplicar login."""
    try:
        module = import_module("runtime_ui")
    except Exception:
        return

    for name in _LOGIN_FUNCTIONS:
        function = getattr(module, name, None)
        if not callable(function):
            continue

        result = _call_zero_arg(function)
        if result is False:
            st.stop()
        return


def _client_from_session() -> Client | None:
    for key in _SESSION_CLIENT_KEYS:
        value = st.session_state.get(key)
        if value is not None and hasattr(value, "table"):
            return value
    return None


def _client_from_modules() -> Client | None:
    for module_name in ("supabase_db", "runtime_ui"):
        try:
            module = import_module(module_name)
        except Exception:
            continue

        for function_name in _CLIENT_FUNCTIONS:
            candidate = getattr(module, function_name, None)

            if candidate is not None and hasattr(candidate, "table"):
                return candidate

            if callable(candidate):
                result = _call_zero_arg(candidate)
                if result is not None and hasattr(result, "table"):
                    return result

    return None


def _secret_value(*names: str) -> str | None:
    for name in names:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
        if value:
            return str(value)
    return None


@st.cache_resource(show_spinner=False)
def _client_from_secrets() -> Client:
    url = _secret_value("SUPABASE_URL", "supabase_url")
    key = _secret_value(
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
        "supabase_service_role_key",
        "supabase_key",
    )

    if not url or not key:
        raise RuntimeError(
            "A conexão com a base da NAVE não foi encontrada nos Secrets."
        )

    return create_client(url, key)


def get_workspace_client() -> Client:
    client = _client_from_session()
    if client is not None:
        return client

    client = _client_from_modules()
    if client is not None:
        return client

    return _client_from_secrets()
