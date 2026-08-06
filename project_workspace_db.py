from __future__ import annotations

import hashlib
import mimetypes
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd
from supabase import Client


PROJECT_FILES_BUCKET = "nave-project-files"
PROJECT_FILE_MAX_BYTES = 100 * 1024 * 1024

SINGLETON_FILE_ROLES = {
    "briefing_original",
    "cost_sheet",
    "closure_report",
    "post_execution_report",
}

STATUS_LABELS = {
    "rascunho": "Rascunho",
    "em_briefing": "Em briefing",
    "em_desenvolvimento": "Em desenvolvimento",
    "apresentado": "Apresentado",
    "em_revisao": "Em revisão",
    "em_negociacao": "Em negociação",
    "aprovado_ganho": "Aprovado / ganho",
    "perdido": "Perdido",
    "cancelado": "Cancelado",
    "em_producao": "Em produção",
    "executado": "Executado",
    "arquivado": "Arquivado",
}

FILE_ROLE_LABELS = {
    "briefing_original": "Briefing original",
    "cost_sheet": "Planilha de custos",
    "final_presentation": "Apresentação final",
    "feedback": "Feedback",
    "approval": "Aprovação",
    "closure_report": "Relatório de encerramento",
    "post_execution_report": "Relatório pós-execução",
    "production_file": "Arquivo de produção",
    "supplier_reference": "Fornecedor / referência",
    "gift_presskit_reference": "Brinde / press kit",
    "project_document": "Documento do projeto",
    "other": "Outro arquivo",
}


def _safe_rows(
    client: Client,
    table_name: str,
    *,
    columns: str = "*",
    equals: dict[str, Any] | None = None,
    order_by: str | None = None,
    descending: bool = False,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    try:
        query = client.table(table_name).select(columns)

        for field, value in (equals or {}).items():
            query = query.eq(field, value)

        if order_by:
            query = query.order(order_by, desc=descending)

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return list(response.data or [])
    except Exception:
        return []


def _safe_one(
    client: Client,
    table_name: str,
    *,
    equals: dict[str, Any],
    columns: str = "*",
) -> dict[str, Any] | None:
    rows = _safe_rows(
        client,
        table_name,
        columns=columns,
        equals=equals,
        limit=1,
    )
    return rows[0] if rows else None


def _normalise_file_name(value: str) -> str:
    name = PurePosixPath(str(value or "arquivo")).name
    name = unicodedata.normalize("NFKD", name)
    name = "".join(
        character
        for character in name
        if not unicodedata.combining(character)
    )
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return name or "arquivo"


def _bucket_identifier(bucket: Any) -> str:
    if isinstance(bucket, dict):
        return str(bucket.get("id") or bucket.get("name") or "")
    return str(
        getattr(bucket, "id", None)
        or getattr(bucket, "name", None)
        or ""
    )


def ensure_project_files_bucket(client: Client) -> None:
    buckets = client.storage.list_buckets() or []
    identifiers = {_bucket_identifier(bucket) for bucket in buckets}

    if PROJECT_FILES_BUCKET in identifiers:
        return

    try:
        client.storage.create_bucket(
            PROJECT_FILES_BUCKET,
            options={"public": False},
        )
    except Exception as exc:
        message = str(exc).casefold()
        if (
            "already exists" in message
            or "duplicate" in message
            or "409" in message
        ):
            return
        raise RuntimeError(
            "A NAVE não conseguiu preparar o armazenamento "
            "privado dos arquivos do projeto."
        ) from exc


def _upload_bytes(
    client: Client,
    *,
    storage_path: str,
    file_bytes: bytes,
    mime_type: str,
) -> None:
    bucket = client.storage.from_(PROJECT_FILES_BUCKET)
    options = {
        "content-type": mime_type or "application/octet-stream",
        "upsert": "false",
    }

    try:
        bucket.upload(storage_path, file_bytes, options)
    except TypeError:
        bucket.upload(
            storage_path,
            file_bytes,
            file_options=options,
        )


def create_project_file_signed_url(
    client: Client,
    storage_path: str | None,
    *,
    expires_in: int = 3600,
    download: bool = False,
) -> str | None:
    path = str(storage_path or "").strip()
    if not path:
        return None

    bucket = client.storage.from_(PROJECT_FILES_BUCKET)

    try:
        if download:
            response = bucket.create_signed_url(
                path,
                expires_in,
                {"download": True},
            )
        else:
            response = bucket.create_signed_url(path, expires_in)
    except Exception:
        return None

    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        return (
            response.get("signedURL")
            or response.get("signedUrl")
            or response.get("signed_url")
        )

    return (
        getattr(response, "signedURL", None)
        or getattr(response, "signedUrl", None)
        or getattr(response, "signed_url", None)
    )


def fetch_project_files(
    client: Client,
    *,
    project_id: str,
    roles: Iterable[str] | None = None,
    include_archived: bool = False,
) -> pd.DataFrame:
    rows = _safe_rows(
        client,
        "project_files",
        equals={"project_id": project_id},
        order_by="created_at",
        descending=True,
    )

    accepted_roles = set(roles or [])
    filtered = []

    for row in rows:
        if accepted_roles and row.get("file_role") not in accepted_roles:
            continue
        if not include_archived and bool(row.get("is_archived")):
            continue
        filtered.append(row)

    return pd.DataFrame(filtered)


def _next_version_number(
    client: Client,
    *,
    project_id: str,
    file_role: str,
) -> int:
    rows = _safe_rows(
        client,
        "project_files",
        columns="version_number",
        equals={
            "project_id": project_id,
            "file_role": file_role,
        },
    )
    versions = [
        int(row.get("version_number") or 0)
        for row in rows
    ]
    return max(versions, default=0) + 1


def save_project_file(
    client: Client,
    *,
    project_id: str,
    file_role: str,
    title: str,
    file_name: str,
    file_bytes: bytes,
    mime_type: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not file_bytes:
        raise ValueError("O arquivo está vazio.")

    if len(file_bytes) > PROJECT_FILE_MAX_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise ValueError(
            f"O arquivo tem {size_mb:.1f} MB. "
            "O limite desta área é 100 MB."
        )

    if file_role not in FILE_ROLE_LABELS:
        raise ValueError("Tipo de arquivo não reconhecido.")

    ensure_project_files_bucket(client)

    clean_file_name = _normalise_file_name(file_name)
    digest = hashlib.sha256(file_bytes).hexdigest()
    version_number = _next_version_number(
        client,
        project_id=project_id,
        file_role=file_role,
    )

    extension_mime, _ = mimetypes.guess_type(clean_file_name)
    resolved_mime = (
        str(mime_type or "").strip()
        or extension_mime
        or "application/octet-stream"
    )

    storage_path = (
        f"{project_id}/{file_role}/"
        f"v{version_number:03d}-{uuid4().hex[:10]}-{clean_file_name}"
    )

    if file_role in SINGLETON_FILE_ROLES:
        try:
            (
                client.table("project_files")
                .update({"is_current": False})
                .eq("project_id", project_id)
                .eq("file_role", file_role)
                .execute()
            )
        except Exception:
            pass

    _upload_bytes(
        client,
        storage_path=storage_path,
        file_bytes=file_bytes,
        mime_type=resolved_mime,
    )

    payload = {
        "project_id": project_id,
        "file_role": file_role,
        "title": str(title or "").strip()
        or FILE_ROLE_LABELS[file_role],
        "file_name": clean_file_name,
        "mime_type": resolved_mime,
        "file_size_bytes": len(file_bytes),
        "content_sha256": digest,
        "version_number": version_number,
        "storage_bucket": PROJECT_FILES_BUCKET,
        "storage_path": storage_path,
        "notes": str(notes or "").strip() or None,
        "metadata": metadata or {},
        "is_current": True,
        "is_archived": False,
    }

    try:
        inserted = client.table("project_files").insert(payload).execute()
    except Exception:
        try:
            client.storage.from_(PROJECT_FILES_BUCKET).remove([storage_path])
        except Exception:
            pass
        raise

    if not inserted.data:
        raise RuntimeError("O arquivo foi enviado, mas não pôde ser registrado.")

    return dict(inserted.data[0])


def archive_project_file(
    client: Client,
    *,
    file_id: str,
) -> None:
    (
        client.table("project_files")
        .update(
            {
                "is_archived": True,
                "is_current": False,
            }
        )
        .eq("id", file_id)
        .execute()
    )


def fetch_project(
    client: Client,
    *,
    project_id: str,
) -> dict[str, Any] | None:
    return _safe_one(
        client,
        "projects",
        equals={"id": project_id},
    )


def update_project_workspace_data(
    client: Client,
    *,
    project_id: str,
    status: str | None = None,
    next_action: str | None = None,
    workspace_notes: str | None = None,
) -> None:
    project = fetch_project(client, project_id=project_id) or {}
    raw_data = project.get("raw_data")
    if not isinstance(raw_data, dict):
        raw_data = {}

    workspace = raw_data.get("workspace")
    if not isinstance(workspace, dict):
        workspace = {}

    if next_action is not None:
        workspace["next_action"] = str(next_action).strip() or None

    if workspace_notes is not None:
        workspace["notes"] = str(workspace_notes).strip() or None

    workspace["updated_at"] = datetime.utcnow().isoformat() + "Z"
    raw_data["workspace"] = workspace

    payload: dict[str, Any] = {"raw_data": raw_data}
    if status:
        payload["status"] = status

    (
        client.table("projects")
        .update(payload)
        .eq("id", project_id)
        .execute()
    )


def _count_by_project(
    client: Client,
    table_name: str,
    *,
    project_field: str = "project_id",
) -> Counter:
    rows = _safe_rows(
        client,
        table_name,
        columns=project_field,
    )
    return Counter(
        str(row.get(project_field))
        for row in rows
        if row.get(project_field)
    )


def _latest_by_project(
    client: Client,
    table_name: str,
    *,
    project_field: str = "project_id",
    date_fields: tuple[str, ...] = ("updated_at", "created_at"),
) -> dict[str, str]:
    columns = ",".join((project_field, *date_fields))
    rows = _safe_rows(
        client,
        table_name,
        columns=columns,
    )

    result: dict[str, str] = {}
    for row in rows:
        project_id = row.get(project_field)
        if not project_id:
            continue

        candidate = None
        for field in date_fields:
            value = row.get(field)
            if value:
                candidate = str(value)
                break

        if not candidate:
            continue

        current = result.get(str(project_id))
        if current is None or candidate > current:
            result[str(project_id)] = candidate

    return result


def fetch_projects_workspace(client: Client) -> pd.DataFrame:
    projects = _safe_rows(
        client,
        "projects",
        order_by="updated_at",
        descending=True,
    )

    counters = {
        "briefings": _count_by_project(
            client,
            "memory_briefing_documents",
        ),
        "recommendations": _count_by_project(
            client,
            "recommendation_queries",
        ),
        "presentations": _count_by_project(
            client,
            "memory_documents",
        ),
        "contents": _count_by_project(
            client,
            "memory_items",
        ),
        "costs": _count_by_project(
            client,
            "memory_cost_documents",
        ),
        "feedbacks": _count_by_project(
            client,
            "memory_feedback_entries",
        ),
        "files": _count_by_project(
            client,
            "project_files",
        ),
    }

    latest_maps = [
        _latest_by_project(client, "memory_briefing_documents"),
        _latest_by_project(client, "memory_documents"),
        _latest_by_project(client, "memory_items"),
        _latest_by_project(client, "memory_cost_documents"),
        _latest_by_project(client, "memory_feedback_entries"),
        _latest_by_project(client, "project_files"),
    ]

    rows: list[dict[str, Any]] = []

    for project in projects:
        project_id = str(project.get("id") or "")
        if not project_id:
            continue

        dates = [
            str(project.get("updated_at") or ""),
            str(project.get("created_at") or ""),
        ]
        for latest_map in latest_maps:
            value = latest_map.get(project_id)
            if value:
                dates.append(value)

        raw_data = project.get("raw_data")
        workspace = (
            raw_data.get("workspace")
            if isinstance(raw_data, dict)
            else {}
        )
        if not isinstance(workspace, dict):
            workspace = {}

        rows.append(
            {
                "project_id": project_id,
                "Projeto": project.get("project_name") or "Sem nome",
                "Cliente": project.get("client_brand") or "Não informado",
                "Evento": project.get("event_name") or "Não informado",
                "Status": STATUS_LABELS.get(
                    str(project.get("status") or ""),
                    str(project.get("status") or "Não informado"),
                ),
                "Briefings": counters["briefings"][project_id],
                "Recomendações": counters["recommendations"][project_id],
                "Apresentações": counters["presentations"][project_id],
                "Conteúdos": counters["contents"][project_id],
                "Arquivos": counters["files"][project_id],
                "Próxima ação": workspace.get("next_action")
                or "Não informada",
                "Última atualização": max(
                    (value for value in dates if value),
                    default="",
                ),
            }
        )

    return pd.DataFrame(rows)


def fetch_project_workspace_snapshot(
    client: Client,
    *,
    project_id: str,
) -> dict[str, Any]:
    project = fetch_project(client, project_id=project_id) or {}

    tables = {
        "briefing_documents": "memory_briefing_documents",
        "briefing_requirements": "memory_briefing_requirements",
        "memory_documents": "memory_documents",
        "memory_items": "memory_items",
        "cost_documents": "memory_cost_documents",
        "cost_items": "memory_cost_items",
        "feedback_entries": "memory_feedback_entries",
        "project_files": "project_files",
        "recommendation_queries": "recommendation_queries",
    }

    snapshot: dict[str, Any] = {"project": project}

    for key, table_name in tables.items():
        snapshot[key] = _safe_rows(
            client,
            table_name,
            equals={"project_id": project_id},
            order_by="created_at",
            descending=True,
        )

    snapshot["outcome"] = _safe_one(
        client,
        "memory_project_outcomes",
        equals={"project_id": project_id},
    )

    return snapshot


def save_project_feedback(
    client: Client,
    *,
    project_id: str,
    feedback_date: date | None,
    source_type: str,
    process_stage: str,
    theme: str,
    sentiment: str,
    original_feedback: str,
    internal_interpretation: str | None = None,
    action_taken: str | None = None,
    confidence_level: str = "incomplete",
) -> None:
    text = str(original_feedback or "").strip()
    if not text:
        raise ValueError("Escreva o feedback recebido.")

    payload = {
        "project_id": project_id,
        "feedback_date": (
            feedback_date.isoformat()
            if feedback_date
            else None
        ),
        "source_type": source_type,
        "process_stage": process_stage,
        "theme": theme,
        "sentiment": sentiment,
        "original_feedback": text,
        "internal_interpretation": (
            str(internal_interpretation or "").strip() or None
        ),
        "action_taken": str(action_taken or "").strip() or None,
        "confidence_level": confidence_level,
    }

    client.table("memory_feedback_entries").insert(payload).execute()


def save_project_outcome(
    client: Client,
    *,
    project_id: str,
    process_type: str,
    commercial_result: str,
    proposal_result: str,
    execution_result: str,
    result_date: date | None,
    execution_date: date | None,
    contracting_client: str | None,
    partners_involved: str | None,
    result_reasons: list[str],
    result_context: str | None,
    execution_notes: str | None,
    budget_amount: float | None,
    confidence_level: str,
    information_source: str,
) -> None:
    payload = {
        "project_id": project_id,
        "process_type": process_type,
        "commercial_result": commercial_result,
        "proposal_result": proposal_result,
        "execution_result": execution_result,
        "result_date": result_date.isoformat() if result_date else None,
        "execution_date": (
            execution_date.isoformat()
            if execution_date
            else None
        ),
        "contracting_client": (
            str(contracting_client or "").strip() or None
        ),
        "partners_involved": (
            str(partners_involved or "").strip() or None
        ),
        "result_reasons": [
            item.strip()
            for item in result_reasons
            if item.strip()
        ],
        "result_context": str(result_context or "").strip() or None,
        "execution_notes": str(execution_notes or "").strip() or None,
        "budget_amount": budget_amount,
        "currency": "BRL",
        "confidence_level": confidence_level,
        "information_source": information_source,
    }

    client.table("memory_project_outcomes").upsert(
        payload,
        on_conflict="project_id",
    ).execute()


def fetch_memory_items_by_sections(
    client: Client,
    *,
    project_id: str,
    section_keys: Iterable[str],
) -> pd.DataFrame:
    accepted = set(section_keys)
    rows = _safe_rows(
        client,
        "memory_items",
        equals={"project_id": project_id},
        order_by="sort_order",
    )
    return pd.DataFrame(
        [
            row
            for row in rows
            if row.get("section_key") in accepted
        ]
    )


def fetch_project_linked_suppliers(
    client: Client,
    *,
    project_id: str,
) -> pd.DataFrame:
    supplier_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    for table_name in ("products", "activation_solutions", "venues"):
        linked = _safe_rows(
            client,
            table_name,
            equals={"project_id": project_id},
        )

        for item in linked:
            supplier_id = (
                item.get("supplier_id")
                or item.get("operator_id")
            )
            if supplier_id:
                supplier_ids.add(str(supplier_id))

            rows.append(
                {
                    "Origem": table_name,
                    "Solução / item": (
                        item.get("name")
                        or item.get("proposal_name")
                        or "Sem nome"
                    ),
                    "Categoria": (
                        item.get("category")
                        or item.get("record_type")
                        or item.get("venue_type")
                        or "Não informada"
                    ),
                    "supplier_id": (
                        str(supplier_id)
                        if supplier_id
                        else None
                    ),
                }
            )

    supplier_map = {
        str(row.get("id")): row
        for row in _safe_rows(client, "suppliers")
        if row.get("id")
    }

    for row in rows:
        supplier = supplier_map.get(str(row.get("supplier_id")))
        row["Fornecedor"] = (
            supplier.get("name")
            if supplier
            else "Não vinculado"
        )
        row.pop("supplier_id", None)

    return pd.DataFrame(rows)
