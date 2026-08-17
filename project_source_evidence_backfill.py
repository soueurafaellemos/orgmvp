from __future__ import annotations

"""NAVE V28.7.2A2 — historical Source Asset / Evidence recovery.

Old project bundles can contain a perfectly valid ``project_files`` master while the
Intelligence Foundation has no matching ``source_assets`` row because the project was
imported before File Analyst dual-write was available (or because that optional write
failed at the time).

This module repairs that *missing intelligence substrate* from the canonical master
already stored by NAVE. It never fabricates Evidence from legacy JSON and never changes
project-file hashes. The same File Analyst persistence service used by new imports is
reused, so Source Asset, Evidence Units, mentions, claims and contexts follow the same
contracts as a fresh import.
"""

from dataclasses import dataclass, asdict
import hashlib
from typing import Any, Mapping, Sequence

from nave_storage import get_bytes as storage_get_bytes

BACKFILL_VERSION = "V28.7.2A2"

PRIMARY_SOURCE_ROLES = {
    "briefing_original",
    "proposal_presentation",
    "final_presentation",
    "detailed_costs",
    "preliminary_budget",
    "feedback_approval",
    "post_event_report",
    "post_execution_report",
    "closure_report",
}

SEMANTIC_ROLES = {
    "briefing_original",
    "proposal_presentation",
    "final_presentation",
    "feedback_approval",
    "post_event_report",
    "post_execution_report",
    "closure_report",
}


@dataclass(frozen=True)
class BackfillItem:
    project_file_id: str
    file_name: str
    role: str
    content_sha256: str
    status: str
    source_asset_id: str | None = None
    evidence_units: int = 0
    entities: int = 0
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _norm_role(value: Any) -> str:
    return str(value or "").strip().casefold().replace(" ", "_")


def _project_file_role(row: Mapping[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    role = _norm_role(metadata.get("document_role"))
    if role:
        return role
    role = _norm_role(row.get("file_role"))
    aliases = {
        "project_document": "complementary_document",
        "post_execution_report": "post_event_report",
    }
    return aliases.get(role, role or "complementary_document")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _source_file_row(client: Any, project_file: Mapping[str, Any]) -> dict[str, Any] | None:
    metadata = project_file.get("metadata") if isinstance(project_file.get("metadata"), Mapping) else {}
    source_file_id = str(metadata.get("source_file_id") or "").strip()
    if source_file_id:
        try:
            rows = _rows(client.table("source_files").select("*").eq("id", source_file_id).limit(1).execute())
            if rows:
                return rows[0]
        except Exception:
            pass

    project_id = str(project_file.get("project_id") or "").strip()
    sha = str(project_file.get("content_sha256") or "").strip()
    if project_id and sha:
        try:
            rows = _rows(
                client.table("source_files").select("*")
                .eq("project_id", project_id).eq("sha256", sha).limit(1).execute()
            )
            if rows:
                return rows[0]
        except Exception:
            pass
    return None


def _as_source_file(project_file: Mapping[str, Any], legacy_source_file: Mapping[str, Any] | None) -> dict[str, Any]:
    legacy = dict(legacy_source_file or {})
    metadata = project_file.get("metadata") if isinstance(project_file.get("metadata"), Mapping) else {}
    role = _project_file_role(project_file)
    result = {
        **legacy,
        "id": legacy.get("id") or metadata.get("source_file_id") or project_file.get("id"),
        "import_id": legacy.get("import_id") or metadata.get("import_id"),
        "project_id": project_file.get("project_id") or legacy.get("project_id"),
        "file_name": project_file.get("file_name") or project_file.get("title") or legacy.get("file_name") or "arquivo",
        "mime_type": project_file.get("mime_type") or legacy.get("mime_type") or "application/octet-stream",
        "storage_bucket": project_file.get("storage_bucket") or legacy.get("storage_bucket"),
        "storage_path": project_file.get("storage_path") or legacy.get("storage_path"),
        "sha256": project_file.get("content_sha256") or legacy.get("sha256"),
        "document_role": role,
        "file_size_bytes": project_file.get("file_size_bytes") or legacy.get("file_size_bytes") or 0,
        "metadata": {
            **(legacy.get("metadata") if isinstance(legacy.get("metadata"), Mapping) else {}),
            "evidence_backfill_version": BACKFILL_VERSION,
            "project_file_id": project_file.get("id"),
        },
    }
    return result


def _existing_assets(client: Any, hashes: Sequence[str]) -> dict[str, dict[str, Any]]:
    clean = list(dict.fromkeys(str(v).strip() for v in hashes if str(v or "").strip()))
    if not clean:
        return {}
    rows: list[dict[str, Any]] = []
    for start in range(0, len(clean), 80):
        try:
            rows.extend(_rows(client.table("source_assets").select("*").in_("content_sha256", clean[start:start + 80]).execute()))
        except Exception:
            pass
    return {str(row.get("content_sha256") or ""): row for row in rows if row.get("content_sha256")}


def _current_evidence_counts(client: Any, asset_ids: Sequence[str]) -> dict[str, int]:
    clean = list(dict.fromkeys(str(v).strip() for v in asset_ids if str(v or "").strip()))
    counts = {asset_id: 0 for asset_id in clean}
    if not clean:
        return counts
    for start in range(0, len(clean), 80):
        try:
            rows = _rows(
                client.table("evidence_units").select("id,source_asset_id,is_current")
                .in_("source_asset_id", clean[start:start + 80]).eq("is_current", True).execute()
            )
        except Exception:
            rows = []
        for row in rows:
            aid = str(row.get("source_asset_id") or "")
            if aid:
                counts[aid] = counts.get(aid, 0) + 1
    return counts


def _ensure_project_context(client: Any, project_id: str, source_asset: Mapping[str, Any], project_file: Mapping[str, Any]) -> None:
    try:
        entities = _rows(
            client.table("knowledge_entities").select("id")
            .eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute()
        )
    except Exception:
        entities = []
    if not entities:
        return
    entity_id = str(entities[0].get("id") or "")
    asset_id = str(source_asset.get("id") or "")
    if not entity_id or not asset_id:
        return
    role = _project_file_role(project_file)
    payload = {
        "source_asset_id": asset_id,
        "context_entity_id": entity_id,
        "context_role": role,
        "original_file_name": project_file.get("file_name") or project_file.get("title"),
        "is_primary_source": role in PRIMARY_SOURCE_ROLES,
        "notes": f"Historical Source Evidence Recovery {BACKFILL_VERSION}",
    }
    try:
        rows = _rows(
            client.table("source_asset_contexts").select("source_asset_id,context_entity_id")
            .eq("source_asset_id", asset_id).eq("context_entity_id", entity_id).limit(1).execute()
        )
        if rows:
            client.table("source_asset_contexts").update({
                "context_role": role,
                "is_primary_source": role in PRIMARY_SOURCE_ROLES,
                "notes": payload["notes"],
            }).eq("source_asset_id", asset_id).eq("context_entity_id", entity_id).execute()
        else:
            client.table("source_asset_contexts").insert(payload).execute()
    except Exception:
        # Context recovery must never destroy an otherwise valid Source Asset.
        pass


def ensure_project_source_evidence(client: Any, project_id: str) -> dict[str, Any]:
    """Backfill primary project files that have no Source Asset yet.

    Safe properties:
    - existing assets are skipped;
    - original bytes are read from NAVE storage, never reconstructed from legacy text;
    - SHA-256 is revalidated before File Analyst persistence;
    - File Analyst dual-write is idempotent by content hash;
    - errors are reported but do not invalidate previously valid domain knowledge.
    """
    try:
        files = _rows(
            client.table("project_files").select("*")
            .eq("project_id", project_id).eq("is_archived", False).execute()
        )
    except Exception as exc:
        return {
            "status": "error",
            "project_id": project_id,
            "candidates": 0,
            "backfilled": 0,
            "skipped_existing": 0,
            "failed": 0,
            "missing_after": 0,
            "results": [],
            "warnings": [f"project_files indisponível: {exc}"],
        }

    primary = [
        row for row in files
        if bool(row.get("is_current", True))
        and _project_file_role(row) in PRIMARY_SOURCE_ROLES
        and str(row.get("content_sha256") or "").strip()
    ]
    hashes = [str(row.get("content_sha256")) for row in primary]
    existing = _existing_assets(client, hashes)
    existing_evidence = _current_evidence_counts(
        client, [str(row.get("id") or "") for row in existing.values()]
    )

    results: list[BackfillItem] = []
    warnings: list[str] = []
    candidates = 0
    backfilled = 0
    skipped = 0
    failed = 0

    for project_file in primary:
        sha = str(project_file.get("content_sha256") or "").strip()
        role = _project_file_role(project_file)
        file_name = str(project_file.get("file_name") or project_file.get("title") or "arquivo")
        project_file_id = str(project_file.get("id") or "")

        existing_asset = existing.get(sha)
        if existing_asset:
            _ensure_project_context(client, project_id, existing_asset, project_file)
            asset_id = str(existing_asset.get("id") or "")
            if existing_evidence.get(asset_id, 0) > 0:
                skipped += 1
                results.append(BackfillItem(
                    project_file_id=project_file_id,
                    file_name=file_name,
                    role=role,
                    content_sha256=sha,
                    status="existing",
                    source_asset_id=asset_id or None,
                    evidence_units=int(existing_evidence.get(asset_id, 0)),
                ))
                continue

        candidates += 1
        legacy = _source_file_row(client, project_file)
        source_file = _as_source_file(project_file, legacy)
        bucket = str(source_file.get("storage_bucket") or "").strip()
        path = str(source_file.get("storage_path") or "").strip()
        if not bucket or not path:
            failed += 1
            warning = "master sem storage_bucket/storage_path"
            warnings.append(f"{file_name}: {warning}")
            results.append(BackfillItem(project_file_id, file_name, role, sha, "failed", warning=warning))
            continue

        try:
            payload = storage_get_bytes(client, bucket_name=bucket, path=path)
            if not payload:
                raise RuntimeError("master retornou vazio")
            actual_sha = _sha256(payload)
            if actual_sha != sha:
                raise RuntimeError(f"SHA-256 do master diverge do project_files ({actual_sha[:12]} != {sha[:12]})")

            from intelligence_graph_db import dual_write_source_file

            intelligence = dual_write_source_file(
                client,
                source_file,
                source_bytes=payload,
                enable_semantic=role in SEMANTIC_ROLES,
            )
            status = str(intelligence.get("status") or "")
            asset_id = str(intelligence.get("source_asset_id") or "") or None
            if status not in {"completed", "partial"} or not asset_id:
                raise RuntimeError(str(intelligence.get("warning") or intelligence.get("error") or f"File Analyst status={status or 'unknown'}"))
            backfilled += 1
            results.append(BackfillItem(
                project_file_id=project_file_id,
                file_name=file_name,
                role=role,
                content_sha256=sha,
                status="backfilled",
                source_asset_id=asset_id,
                evidence_units=int(intelligence.get("evidence") or 0),
                entities=int(intelligence.get("entities") or 0),
                warning=" | ".join(str(v) for v in (intelligence.get("warnings") or []) if str(v).strip()) or None,
            ))
        except Exception as exc:
            failed += 1
            warning = str(exc)[:1200]
            warnings.append(f"{file_name}: {warning}")
            results.append(BackfillItem(project_file_id, file_name, role, sha, "failed", warning=warning))

    after = _existing_assets(client, hashes)
    after_evidence = _current_evidence_counts(
        client, [str(row.get("id") or "") for row in after.values()]
    )
    missing_after = sum(
        1 for sha in hashes
        if sha not in after or after_evidence.get(str((after.get(sha) or {}).get("id") or ""), 0) <= 0
    )
    status = "completed" if failed == 0 else "partial"
    if candidates and backfilled == 0 and failed:
        status = "partial"

    return {
        "status": status,
        "project_id": project_id,
        "version": BACKFILL_VERSION,
        "primary_files": len(primary),
        "candidates": candidates,
        "backfilled": backfilled,
        "skipped_existing": skipped,
        "failed": failed,
        "missing_after": missing_after,
        "results": [row.to_dict() for row in results],
        "warnings": warnings[:30],
    }
