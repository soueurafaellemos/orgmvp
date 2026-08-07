from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from nave_data_client import get_nave_client


RELATIONSHIP_LABELS = {
    "origin_project": "Projeto de origem",
    "proposed_in_project": "Proposto no projeto",
    "executed_in_project": "Executado no projeto",
    "used_in_project": "Utilizado no projeto",
    "supplier_in_project": "Fornecedor no projeto",
    "venue_for_project": "Local do projeto",
    "reference_in_project": "Referência no projeto",
    "other": "Outro vínculo",
}

ALLOWED_ENTITY_TYPES = {"product", "activation", "venue", "supplier"}


@dataclass(frozen=True)
class ProjectLink:
    id: str
    project_id: str
    project_name: str
    client_brand: str | None = None
    event_name: str | None = None
    status: str | None = None
    relationship_type: str = "used_in_project"
    relationship_label: str | None = None
    context: str | None = None
    source: str | None = None

    @property
    def relation_display(self) -> str:
        return (
            (self.relationship_label or "").strip()
            or RELATIONSHIP_LABELS.get(self.relationship_type, "Vínculo com projeto")
        )


def relationship_display(value: str | None, custom: str | None = None) -> str:
    return (custom or "").strip() or RELATIONSHIP_LABELS.get(
        str(value or "used_in_project"), "Vínculo com projeto"
    )


def _rows(response: Any) -> list[dict]:
    data = getattr(response, "data", None)
    return list(data or [])


def fetch_related_projects(
    client: Any,
    *,
    entity_type: str,
    entity_id: str,
) -> list[ProjectLink]:
    if entity_type not in ALLOWED_ENTITY_TYPES or not entity_id:
        return []

    response = (
        client.table("knowledge_project_links")
        .select("*")
        .eq("entity_type", entity_type)
        .eq("entity_id", entity_id)
        .order("created_at", desc=True)
        .execute()
    )
    links = _rows(response)
    if not links:
        return []

    project_ids = sorted({str(row.get("project_id")) for row in links if row.get("project_id")})
    projects: dict[str, dict] = {}
    if project_ids:
        project_response = (
            client.table("projects")
            .select("id,project_name,client_brand,event_name,status")
            .in_("id", project_ids)
            .execute()
        )
        projects = {
            str(row.get("id")): row
            for row in _rows(project_response)
            if row.get("id")
        }

    result: list[ProjectLink] = []
    for row in links:
        project_id = str(row.get("project_id") or "")
        project = projects.get(project_id, {})
        result.append(
            ProjectLink(
                id=str(row.get("id") or ""),
                project_id=project_id,
                project_name=str(project.get("project_name") or "Projeto"),
                client_brand=(str(project.get("client_brand")) if project.get("client_brand") else None),
                event_name=(str(project.get("event_name")) if project.get("event_name") else None),
                status=(str(project.get("status")) if project.get("status") else None),
                relationship_type=str(row.get("relationship_type") or "used_in_project"),
                relationship_label=(str(row.get("relationship_label")) if row.get("relationship_label") else None),
                context=(str(row.get("context")) if row.get("context") else None),
                source=(str(row.get("source")) if row.get("source") else None),
            )
        )
    return result


def fetch_project_options(client: Any) -> list[dict]:
    response = (
        client.table("projects")
        .select("id,project_name,client_brand,event_name,status")
        .order("project_name")
        .limit(2000)
        .execute()
    )
    return _rows(response)


def add_project_link(
    client: Any,
    *,
    entity_type: str,
    entity_id: str,
    project_id: str,
    relationship_type: str,
    context: str | None = None,
) -> None:
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError("Tipo de entidade inválido para relacionamento com projetos.")
    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "project_id": project_id,
        "relationship_type": relationship_type,
        "relationship_label": RELATIONSHIP_LABELS.get(relationship_type),
        "context": (context or "").strip() or None,
        "source": "manual_nave",
        "is_confirmed": True,
    }
    client.table("knowledge_project_links").upsert(
        payload,
        on_conflict="entity_type,entity_id,project_id,relationship_type",
    ).execute()


def delete_project_link(client: Any, *, link_id: str) -> None:
    client.table("knowledge_project_links").delete().eq("id", link_id).execute()


def _project_label(project: dict) -> str:
    name = str(project.get("project_name") or "Projeto sem nome")
    brand = str(project.get("client_brand") or "").strip()
    event = str(project.get("event_name") or "").strip()
    suffix = " · ".join(item for item in (brand, event) if item)
    return f"{name} — {suffix}" if suffix else name


def render_related_projects_panel(
    entity_type: str,
    entity_id: str,
    *,
    client: Any | None = None,
    allow_edit: bool = False,
    heading: str = "Projetos relacionados",
) -> None:
    if entity_type not in ALLOWED_ENTITY_TYPES or not entity_id:
        return

    try:
        client = client or get_nave_client()
        links = fetch_related_projects(
            client,
            entity_type=entity_type,
            entity_id=str(entity_id),
        )
    except Exception as exc:
        st.info(
            "Projetos relacionados ficarão disponíveis após a instalação "
            "do SQL da V28.0.3."
        )
        if st.session_state.get("nave_debug"):
            st.caption(str(exc))
        return

    st.markdown(f"### {heading}")
    if not links:
        st.caption("Nenhum projeto relacionado foi registrado ainda.")
    else:
        for link in links:
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"**{link.project_name}**")
                    meta = " · ".join(
                        item
                        for item in (link.client_brand, link.event_name, link.status)
                        if item
                    )
                    if meta:
                        st.caption(meta)
                    st.write(link.relation_display)
                    if link.context:
                        st.write(link.context)
                with right:
                    if allow_edit and link.source == "manual_nave":
                        if st.button(
                            "Remover vínculo",
                            key=f"unlink_{link.id}",
                            width="stretch",
                        ):
                            delete_project_link(client, link_id=link.id)
                            st.rerun()

        st.page_link(
            "pages/4_Historico_de_Projetos.py",
            label="Abrir Projetos",
        )

    if not allow_edit:
        return

    with st.expander("Relacionar a outro projeto", expanded=False):
        projects = fetch_project_options(client)
        if not projects:
            st.info("Ainda não há projetos cadastrados para relacionar.")
            return

        project_by_label = {_project_label(project): project for project in projects}
        project_label = st.selectbox(
            "Projeto",
            options=list(project_by_label.keys()),
            key=f"project_link_project_{entity_type}_{entity_id}",
        )
        relationship_type = st.selectbox(
            "Tipo de relação",
            options=list(RELATIONSHIP_LABELS.keys()),
            format_func=lambda value: RELATIONSHIP_LABELS[value],
            key=f"project_link_type_{entity_type}_{entity_id}",
        )
        context = st.text_area(
            "Contexto do vínculo",
            placeholder="Ex.: utilizado no press kit; local do evento; ativação executada...",
            key=f"project_link_context_{entity_type}_{entity_id}",
        )
        if st.button(
            "Relacionar projeto",
            type="primary",
            key=f"project_link_save_{entity_type}_{entity_id}",
            width="stretch",
        ):
            selected_project = project_by_label[project_label]
            add_project_link(
                client,
                entity_type=entity_type,
                entity_id=str(entity_id),
                project_id=str(selected_project["id"]),
                relationship_type=relationship_type,
                context=context,
            )
            st.success("Projeto relacionado.")
            st.rerun()
