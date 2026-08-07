from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


ENTITY_TABLES = {
    "product": "products",
    "activation": "activation_solutions",
    "supplier": "suppliers",
    "project": "projects",
}
ENTITY_LABEL_FIELDS = {
    "product": ("name", "sku", "category"),
    "activation": ("name", "proposal_name", "category"),
    "supplier": ("name", "trade_name", "legal_name"),
    "project": ("project_name", "client_brand", "event_name"),
}


@dataclass
class DeleteResult:
    entity_type: str
    entity_id: str
    status: str
    label: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status,
            "label": self.label,
            "message": self.message,
        }


def _rows(response: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (getattr(response, "data", None) or []) if isinstance(row, Mapping)]


def _label(entity_type: str, row: Mapping[str, Any]) -> str:
    for field in ENTITY_LABEL_FIELDS.get(entity_type, ()):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return str(row.get("id") or "Registro")


def _snapshot(client: Any, entity_type: str, entity_id: str) -> dict[str, Any] | None:
    table = ENTITY_TABLES[entity_type]
    try:
        response = client.table(table).select("*").eq("id", entity_id).limit(1).execute()
        rows = _rows(response)
        return rows[0] if rows else None
    except Exception:
        return None


def _log_deletion(client: Any, entity_type: str, entity_id: str, row: Mapping[str, Any]) -> None:
    try:
        client.table("nave_deletion_events").insert({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_label": _label(entity_type, row),
            "snapshot": dict(row),
            "deletion_source": "selection_list_v28_1_1",
        }).execute()
    except Exception:
        # O log nunca deve impedir a correção de um cadastro que o usuário
        # explicitamente confirmou que deseja excluir.
        pass


def _storage_refs_for_project(client: Any, project_id: str) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    queries = [
        ("source_files", "storage_bucket,storage_path"),
        ("project_files", "storage_bucket,storage_path"),
        ("memory_documents", "storage_bucket,storage_path"),
        ("memory_briefing_documents", "storage_bucket,storage_path"),
        ("memory_cost_documents", "storage_bucket,storage_path"),
    ]
    for table, fields in queries:
        try:
            response = client.table(table).select(fields).eq("project_id", project_id).execute()
            for row in _rows(response):
                bucket = str(row.get("storage_bucket") or "").strip()
                path = str(row.get("storage_path") or "").strip()
                if bucket and path:
                    refs.append((bucket, path))
        except Exception:
            continue
    try:
        response = client.table("memory_pages").select("storage_bucket,storage_path").eq("project_id", project_id).execute()
        for row in _rows(response):
            bucket = str(row.get("storage_bucket") or "").strip()
            path = str(row.get("storage_path") or "").strip()
            if bucket and path:
                refs.append((bucket, path))
    except Exception:
        pass
    try:
        response = client.table("memory_items").select("visual_storage_bucket,visual_storage_path").eq("project_id", project_id).execute()
        for row in _rows(response):
            bucket = str(row.get("visual_storage_bucket") or "").strip()
            path = str(row.get("visual_storage_path") or "").strip()
            if bucket and path:
                refs.append((bucket, path))
    except Exception:
        pass
    return list(dict.fromkeys(refs))


def _storage_refs_for_entity(client: Any, entity_type: str, entity_id: str) -> list[tuple[str, str]]:
    try:
        response = (
            client.table("media_assets")
            .select("storage_bucket,storage_path")
            .eq("entity_type", entity_type)
            .eq("entity_id", entity_id)
            .execute()
        )
        refs = []
        for row in _rows(response):
            bucket = str(row.get("storage_bucket") or "").strip()
            path = str(row.get("storage_path") or "").strip()
            if bucket and path:
                refs.append((bucket, path))
        return list(dict.fromkeys(refs))
    except Exception:
        return []


def _remove_storage(client: Any, refs: Sequence[tuple[str, str]]) -> None:
    by_bucket: dict[str, list[str]] = {}
    for bucket, path in refs:
        by_bucket.setdefault(bucket, []).append(path)
    for bucket, paths in by_bucket.items():
        try:
            client.storage.from_(bucket).remove(list(dict.fromkeys(paths)))
        except Exception:
            continue


def _project_import_ids(client: Any, project_id: str) -> list[str]:
    try:
        response = client.table("imports").select("id").eq("project_id", project_id).execute()
        return [str(row.get("id")) for row in _rows(response) if row.get("id")]
    except Exception:
        return []


def _cleanup_non_fk_rows(client: Any, entity_type: str, entity_id: str, *, project_import_ids: Sequence[str] = ()) -> None:
    # media_assets e knowledge_enrichment_events usam identidade genérica e
    # portanto não possuem FK direta para a entidade. Removemos somente as
    # linhas que pertencem ao registro explicitamente excluído.
    try:
        client.table("media_assets").delete().eq("entity_type", entity_type).eq("entity_id", entity_id).execute()
    except Exception:
        pass
    if entity_type in {"product", "activation", "supplier"}:
        try:
            client.table("knowledge_enrichment_events").delete().eq("entity_type", entity_type).eq("entity_id", entity_id).execute()
        except Exception:
            pass
    if entity_type == "project":
        # imports.project_id é SET NULL no schema-base. Como esses lotes são
        # exclusivos do projeto removido, apagamos pelos IDs capturados antes
        # do DELETE do projeto; source_files caem por cascade e os repertórios
        # transversais apenas perdem a referência técnica ao import.
        for import_id in project_import_ids:
            try:
                client.table("imports").delete().eq("id", import_id).execute()
            except Exception:
                pass


def delete_entity(client: Any, *, entity_type: str, entity_id: str) -> DeleteResult:
    entity_type = str(entity_type or "").strip()
    entity_id = str(entity_id or "").strip()
    if entity_type not in ENTITY_TABLES or not entity_id:
        return DeleteResult(entity_type, entity_id, "invalid", entity_id or "Registro", "Tipo ou ID inválido.")

    row = _snapshot(client, entity_type, entity_id)
    if not row:
        return DeleteResult(entity_type, entity_id, "not_found", entity_id, "O registro já não existe ou não pôde ser localizado.")
    label = _label(entity_type, row)
    project_import_ids = _project_import_ids(client, entity_id) if entity_type == "project" else []
    refs = _storage_refs_for_project(client, entity_id) if entity_type == "project" else _storage_refs_for_entity(client, entity_type, entity_id)
    # Inclui também mídias genéricas do próprio projeto na limpeza física.
    if entity_type == "project":
        refs = list(dict.fromkeys([*refs, *_storage_refs_for_entity(client, "project", entity_id)]))
    _log_deletion(client, entity_type, entity_id, row)

    table = ENTITY_TABLES[entity_type]
    try:
        client.table(table).delete().eq("id", entity_id).execute()
    except Exception as exc:
        message = str(exc)
        lower = message.casefold()
        if entity_type == "project" and ("foreign key" in lower or "violates" in lower or "constraint" in lower):
            return DeleteResult(
                entity_type,
                entity_id,
                "protected",
                label,
                "O projeto possui histórico protegido por outra estrutura da NAVE. Nada foi apagado. Remova ou reassocie esse vínculo antes de tentar novamente.",
            )
        return DeleteResult(entity_type, entity_id, "error", label, f"A exclusão não foi concluída: {message}")

    # Confirma a remoção antes de limpar arquivos físicos. Se um schema antigo
    # ignorar o delete, o Storage permanece preservado.
    if _snapshot(client, entity_type, entity_id):
        return DeleteResult(entity_type, entity_id, "error", label, "O banco não confirmou a exclusão; os arquivos foram preservados.")
    _cleanup_non_fk_rows(
        client,
        entity_type,
        entity_id,
        project_import_ids=project_import_ids,
    )
    _remove_storage(client, refs)
    return DeleteResult(entity_type, entity_id, "deleted", label, "Registro excluído.")


def delete_entities(client: Any, *, entity_type: str, entity_ids: Sequence[str]) -> list[dict[str, str]]:
    unique_ids = [item for item in dict.fromkeys(str(value).strip() for value in entity_ids) if item]
    return [delete_entity(client, entity_type=entity_type, entity_id=entity_id).as_dict() for entity_id in unique_ids]
