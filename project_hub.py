from __future__ import annotations

from typing import Any

from supabase import Client

from project_workspace_db import (
    fetch_projects_workspace,
)
from project_workspace_ui import (
    render_project_workspace,
    render_projects_page,
)


# Compatibilidade com a V26.3 e com possíveis imports já existentes.
def fetch_unified_projects(client: Client):
    return fetch_projects_workspace(client)


def render_project_hub(
    client: Client,
    *,
    project_id: str | None = None,
    project: dict[str, Any] | None = None,
) -> None:
    resolved_id = project_id or (
        str(project.get("id"))
        if isinstance(project, dict) and project.get("id")
        else None
    )

    if resolved_id:
        render_project_workspace(
            client,
            project_id=resolved_id,
        )
    else:
        render_projects_page(client)


def render_projects_hub(client: Client) -> None:
    render_projects_page(client)


def render_selected_project(
    client: Client,
    project_id: str,
) -> None:
    render_project_workspace(
        client,
        project_id=project_id,
    )
