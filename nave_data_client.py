from __future__ import annotations

import os
from typing import Any


def get_nave_client() -> Any:
    """Resolve o cliente Supabase sem acoplar a V28.0.3 a uma fábrica específica."""
    try:
        import supabase_db  # type: ignore

        for name in (
            "get_supabase_client",
            "get_database_client",
            "get_client",
            "create_database_client",
        ):
            factory = getattr(supabase_db, name, None)
            if callable(factory):
                client = factory()
                if client is not None:
                    return client
    except Exception:
        pass

    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        secrets = {}

    def _value(*names: str) -> str:
        for name in names:
            try:
                value = secrets.get(name, "")
            except Exception:
                value = ""
            value = value or os.getenv(name, "")
            if value:
                return str(value)
        return ""

    url = _value("SUPABASE_URL", "SUPABASE_PROJECT_URL")
    key = _value(
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
    )

    if not url or not key:
        raise RuntimeError(
            "A NAVE não encontrou a configuração do Supabase. "
            "Mantenha os mesmos Secrets já usados pela aplicação."
        )

    from supabase import create_client

    return create_client(url, key)


def enforce_existing_app_access() -> None:
    """Reaproveita o guard de acesso instalado, sem redefinir autenticação."""
    try:
        import runtime_ui  # type: ignore
    except Exception:
        return

    for name in (
        "require_app_access",
        "require_access",
        "ensure_app_access",
        "app_access_gate",
        "require_login",
        "require_app_login",
        "ensure_authenticated",
        "require_authenticated_session",
    ):
        fn = getattr(runtime_ui, name, None)
        if callable(fn):
            fn()
            return
