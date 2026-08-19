from __future__ import annotations

"""NAVE V28.7.3A — helpers for per-project / per-domain cutover readiness.

This module never promotes a read path. It only reads or refreshes readiness.
Promotion belongs to the controlled Canary phase (V28.7.3B).
"""

from typing import Any, Mapping

from project_domain_reader import SUPPORTED_DOMAIN_KEYS, READ_SCHEMA_VERSION


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def get_project_readiness(client: Any, project_id: str) -> list[dict[str, Any]]:
    rows = _rows(
        client.table("project_domain_cutover_readiness")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    order = {key: index for index, key in enumerate(SUPPORTED_DOMAIN_KEYS)}
    return sorted(rows, key=lambda row: order.get(str(row.get("domain_key")), 999))


def refresh_project_readiness(client: Any, project_id: str) -> dict[str, Any]:
    """Refresh readiness only; read_mode remains unchanged by SQL contract."""
    response = client.rpc(
        "refresh_project_domain_readiness_v2873a",
        {"p_project_id": project_id},
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return dict(data)
    return {
        "status": "completed",
        "project_id": project_id,
        "schema_version": READ_SCHEMA_VERSION,
        "rows": data or [],
    }
