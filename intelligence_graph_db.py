from __future__ import annotations

"""Persistência paralela do NAVE Intelligence Graph — File Analyst v1.

Este módulo NÃO substitui as tabelas legadas. Ele faz dual-write de forma idempotente
quando a Intelligence Foundation v1 está instalada. Se a fundação ainda não existir,
o pipeline legado continua funcionando normalmente.
"""

import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

from file_analyst import (
    FILE_ANALYST_PROMPT_VERSION,
    FILE_ANALYST_SCHEMA_VERSION,
    FILE_ANALYST_VERSION,
    ClaimCandidate,
    EntityCandidate,
    EvidenceUnit,
    FileAnalysisResult,
    RelationCandidate,
    analyze_file,
)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        return [dict(data)]
    return []


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        return _safe(value.model_dump())
    return str(value)


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _sha_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _first(client: Any, table: str, **filters: Any) -> dict[str, Any] | None:
    query = client.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    rows = _rows(query.limit(1).execute())
    return rows[0] if rows else None


def foundation_available(client: Any) -> bool:
    try:
        client.table("ontology_entity_types").select("code").limit(1).execute()
        client.table("source_assets").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def _project_row(client: Any, project_id: str) -> dict[str, Any]:
    try:
        rows = _rows(
            client.table("projects")
            .select("id,project_name,client_brand,event_name,status,event_date,location_city,location_state,raw_data,created_at,updated_at")
            .eq("id", project_id)
            .limit(1)
            .execute()
        )
        return rows[0] if rows else {"id": project_id, "project_name": f"Projeto {project_id[:8]}"}
    except Exception:
        return {"id": project_id, "project_name": f"Projeto {project_id[:8]}"}


def _ensure_project_entity(client: Any, project_id: str) -> dict[str, Any]:
    existing = _first(client, "knowledge_entities", domain_table="projects", domain_id=project_id)
    if existing:
        return existing
    project = _project_row(client, project_id)
    name = str(project.get("project_name") or project.get("event_name") or f"Projeto {project_id[:8]}").strip()
    payload = {
        "entity_type": "project",
        "canonical_name": name,
        "normalized_name": _normalize(name),
        "entity_kind": "canonical",
        "domain_table": "projects",
        "domain_id": project_id,
        "attributes": {
            "client_brand": project.get("client_brand"),
            "event_name": project.get("event_name"),
            "status_legacy": project.get("status"),
            "event_date_legacy": project.get("event_date"),
            "location_city": project.get("location_city"),
            "location_state": project.get("location_state"),
        },
        "status": "active",
        "confidence": 1.0,
    }
    try:
        rows = _rows(client.table("knowledge_entities").insert(_safe(payload)).execute())
        if rows:
            return rows[0]
    except Exception:
        # Pode ter havido corrida pela constraint única.
        existing = _first(client, "knowledge_entities", domain_table="projects", domain_id=project_id)
        if existing:
            return existing
        raise
    raise RuntimeError("Não foi possível criar a entidade do projeto no Intelligence Graph.")


def _ensure_brand_entity(client: Any, project_entity: Mapping[str, Any], project_id: str) -> dict[str, Any] | None:
    project = _project_row(client, project_id)
    name = str(project.get("client_brand") or "").strip()
    if not name:
        return None
    normalized = _normalize(name)
    try:
        rows = _rows(
            client.table("knowledge_entities")
            .select("*")
            .eq("entity_type", "brand")
            .eq("normalized_name", normalized)
            .eq("status", "active")
            .limit(2)
            .execute()
        )
    except Exception:
        rows = []
    if len(rows) == 1:
        return rows[0]
    payload = {
        "entity_type": "brand",
        "canonical_name": name,
        "normalized_name": normalized,
        "entity_kind": "canonical",
        "attributes": {"created_from_project_id": project_id},
        "status": "active" if len(rows) == 0 else "review_required",
        "confidence": 0.90 if len(rows) == 0 else 0.65,
    }
    inserted = _rows(client.table("knowledge_entities").insert(_safe(payload)).execute())
    return inserted[0] if inserted else None


def _ensure_source_asset(client: Any, source_file: Mapping[str, Any], analysis: FileAnalysisResult) -> dict[str, Any]:
    sha = str(source_file.get("sha256") or analysis.sha256).strip()
    existing = _first(client, "source_assets", content_sha256=sha)
    metadata = {
        "legacy_source_file_id": source_file.get("id"),
        "legacy_import_id": source_file.get("import_id"),
        "legacy_document_role": source_file.get("document_role"),
        "file_analyst_version": FILE_ANALYST_VERSION,
        "file_analyst_role_reasons": analysis.source_role_reasons,
        "file_analyst_summary": analysis.summary,
        "file_analyst_unknowns": analysis.unknowns,
        "file_analyst_contradictions": analysis.contradictions,
        "file_analyst_metadata": analysis.metadata,
    }
    storage_bucket = source_file.get("storage_bucket")
    storage_path = source_file.get("storage_path")
    if not (storage_bucket and storage_path):
        storage_bucket = None
        storage_path = None
    payload = {
        "content_sha256": sha,
        "canonical_file_name": str(source_file.get("file_name") or analysis.file_name),
        "mime_type": str(source_file.get("mime_type") or analysis.mime_type),
        "file_size_bytes": int(source_file.get("file_size_bytes") or 0),
        "storage_bucket": storage_bucket,
        "storage_path": storage_path,
        "origin_type": "upload",
        "source_role": analysis.source_role,
        "source_role_confidence": analysis.source_role_confidence,
        "language": analysis.language,
        "confidentiality": "client_confidential",
        "metadata": metadata,
    }
    if existing:
        current_meta = existing.get("metadata") if isinstance(existing.get("metadata"), Mapping) else {}
        merged_meta = {**dict(current_meta), **metadata}
        update = {
            "canonical_file_name": payload["canonical_file_name"],
            "mime_type": payload["mime_type"],
            "file_size_bytes": max(int(existing.get("file_size_bytes") or 0), int(payload["file_size_bytes"] or 0)),
            "source_role": payload["source_role"],
            "source_role_confidence": payload["source_role_confidence"],
            "language": payload["language"] or existing.get("language"),
            "metadata": merged_meta,
        }
        if payload["storage_bucket"] and payload["storage_path"]:
            update["storage_bucket"] = payload["storage_bucket"]
            update["storage_path"] = payload["storage_path"]
        client.table("source_assets").update(_safe(update)).eq("id", existing["id"]).execute()
        existing.update(update)
        return existing
    rows = _rows(client.table("source_assets").insert(_safe(payload)).execute())
    if not rows:
        raise RuntimeError("source_asset não foi criado")
    return rows[0]


def _ensure_context(client: Any, source_asset: Mapping[str, Any], project_entity: Mapping[str, Any], source_file: Mapping[str, Any], analysis: FileAnalysisResult) -> None:
    payload = {
        "source_asset_id": source_asset["id"],
        "context_entity_id": project_entity["id"],
        "context_role": analysis.source_role,
        "original_file_name": source_file.get("file_name") or analysis.file_name,
        "import_id": source_file.get("import_id"),
        "is_primary_source": analysis.source_role in {
            "briefing_original", "proposal_presentation", "final_presentation",
            "detailed_costs", "preliminary_budget", "feedback_approval", "post_event_report",
        },
        "notes": f"Dual-write {FILE_ANALYST_VERSION}",
    }
    try:
        client.table("source_asset_contexts").insert(_safe(payload)).execute()
    except Exception:
        # Unique composto: contexto já existe. Atualiza papel se necessário.
        try:
            client.table("source_asset_contexts").update({
                "context_role": analysis.source_role,
                "is_primary_source": payload["is_primary_source"],
                "notes": payload["notes"],
            }).eq("source_asset_id", source_asset["id"]).eq("context_entity_id", project_entity["id"]).execute()
        except Exception:
            pass


def _start_run(client: Any, source_asset: Mapping[str, Any], project_entity: Mapping[str, Any], analysis: FileAnalysisResult) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    input_signature = _sha_text(f"{analysis.sha256}|{analysis.source_role}|{FILE_ANALYST_VERSION}|{FILE_ANALYST_SCHEMA_VERSION}")
    payload = {
        "analyzer_type": "file_analyst",
        "scope_kind": "source_asset",
        "scope_entity_id": project_entity.get("id"),
        "scope_source_asset_id": source_asset["id"],
        "pipeline_version": FILE_ANALYST_VERSION,
        "code_version": FILE_ANALYST_VERSION,
        "prompt_version": FILE_ANALYST_PROMPT_VERSION,
        "schema_version": FILE_ANALYST_SCHEMA_VERSION,
        "model_provider": "google" if analysis.semantic_analysis_ran else None,
        "model_name": None,
        "input_signature": input_signature,
        "status": "running",
        "started_at": now,
        "metadata": {
            "semantic_analysis_ran": analysis.semantic_analysis_ran,
            "warnings": analysis.warnings,
            "source_role": analysis.source_role,
        },
    }
    rows = _rows(client.table("intelligence_runs").insert(_safe(payload)).execute())
    if not rows:
        raise RuntimeError("intelligence_run não foi criado")
    return rows[0]


def _finish_run(client: Any, run: Mapping[str, Any], *, started_monotonic: float, status: str, analysis: FileAnalysisResult, counts: Mapping[str, int], error: str | None = None) -> None:
    latency_ms = max(0, int((time.monotonic() - started_monotonic) * 1000))
    output_signature = _sha_text(json.dumps({
        "role": analysis.source_role,
        "evidence": counts.get("evidence", 0),
        "entities": counts.get("entities", 0),
        "claims": counts.get("claims", 0),
        "relations": counts.get("relations", 0),
    }, sort_keys=True))
    payload = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "latency_ms": latency_ms,
        "output_signature": output_signature,
        "error_detail": error,
        "metadata": {
            "semantic_analysis_ran": analysis.semantic_analysis_ran,
            "warnings": analysis.warnings,
            "unknowns": analysis.unknowns,
            "contradictions": analysis.contradictions,
            "counts": dict(counts),
        },
    }
    try:
        client.table("intelligence_runs").update(_safe(payload)).eq("id", run["id"]).execute()
    except Exception:
        pass


def _content_hash(unit: EvidenceUnit) -> str:
    # content_sha256 fingerprints the evidence CONTENT only. Identity is formed
    # separately by source_asset + unit_type + locator_sha256 + this hash. Ordinal
    # is deliberately excluded because parser ordering may change without the
    # underlying evidence changing.
    payload = {
        "text": unit.content_text,
        "json": unit.content_json,
    }
    return _sha_text(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _locator_hash(locator: Mapping[str, Any] | None) -> str:
    payload = json.dumps(_safe(dict(locator or {})), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha_text(payload)


def _persist_evidence(client: Any, source_asset_id: str, run_id: str, units: list[EvidenceUnit]) -> dict[str, str]:
    """Persist evidence by source + type + locator + content.

    V28.7.1 fixes a subtle identity bug: two fragments on the same page/slide may
    share an ordinal but have different locators. We supersede only evidence at the
    SAME canonical locator. Database/read errors are no longer converted into an
    empty set, because that could silently invalidate prior evidence.
    """
    refs: dict[str, str] = {}
    for unit in units:
        content_hash = _content_hash(unit)
        locator_hash = _locator_hash(unit.locator)
        target_locator = _safe(dict(unit.locator or {}))

        # Fast path for evidence written by V28.7.1+. We still compare the
        # locator object itself before trusting the hash: the hash is an index,
        # not business truth.
        fast_query = (
            client.table("evidence_units")
            .select("*")
            .eq("source_asset_id", source_asset_id)
            .eq("unit_type", unit.unit_type)
            .eq("locator_sha256", locator_hash)
            .eq("is_current", True)
        )
        candidates = _rows(fast_query.limit(24).execute())
        existing_rows = [
            row for row in candidates
            if _safe(dict(row.get("locator") or {})) == target_locator
        ]

        # Compatibility path for evidence created before locator_sha256 used the
        # Python canonical hash. SQL backfill fingerprints may differ in textual
        # JSON formatting, so a hash-only lookup would orphan prior evidence.
        # Ordinal narrows the legacy search without a global arbitrary row cap;
        # exact locator equality remains the final identity check.
        if not existing_rows:
            legacy_query = (
                client.table("evidence_units")
                .select("*")
                .eq("source_asset_id", source_asset_id)
                .eq("unit_type", unit.unit_type)
                .eq("is_current", True)
            )
            if unit.ordinal is not None:
                legacy_query = legacy_query.eq("ordinal", unit.ordinal).limit(48)
            legacy_candidates = _rows(legacy_query.execute())
            existing_rows = [
                row for row in legacy_candidates
                if _safe(dict(row.get("locator") or {})) == target_locator
            ]
        same_rows = [row for row in existing_rows if str(row.get("content_sha256")) == content_hash]
        if same_rows:
            # Collapse accidental duplicate-current rows at the same exact locator.
            same = max(same_rows, key=lambda row: str(row.get("created_at") or ""))
            for duplicate in existing_rows:
                if str(duplicate.get("id")) != str(same.get("id")):
                    client.table("evidence_units").update({"is_current": False}).eq("id", duplicate["id"]).execute()
            refs[unit.ref] = str(same["id"])
            continue

        supersedes_id = None
        if existing_rows:
            current = max(existing_rows, key=lambda row: str(row.get("created_at") or ""))
            supersedes_id = str(current.get("id") or "") or None
            for old in existing_rows:
                client.table("evidence_units").update({"is_current": False}).eq("id", old["id"]).execute()

        payload = {
            "source_asset_id": source_asset_id,
            "unit_type": unit.unit_type,
            "ordinal": unit.ordinal,
            "locator": unit.locator,
            "locator_sha256": locator_hash,
            "content_text": unit.content_text,
            "content_json": unit.content_json,
            "content_sha256": content_hash,
            "extraction_method": unit.extraction_method,
            "extraction_confidence": unit.extraction_confidence,
            "language": unit.language,
            "intelligence_run_id": run_id,
            "supersedes_evidence_id": supersedes_id,
            "is_current": True,
        }
        rows = _rows(client.table("evidence_units").insert(_safe(payload)).execute())
        if not rows:
            raise RuntimeError(f"Supabase não confirmou evidence_unit {unit.ref}")
        refs[unit.ref] = str(rows[0]["id"])
    return refs


def _find_entity(client: Any, candidate: EntityCandidate, project_entity: Mapping[str, Any]) -> dict[str, Any] | None:
    normalized = _normalize(candidate.canonical_name)
    query = (
        client.table("knowledge_entities")
        .select("*")
        .eq("entity_type", candidate.entity_type)
        .eq("normalized_name", normalized)
        .eq("status", "active")
    )
    scoped = candidate.entity_kind in {"project_instance", "scoped_profile", "ephemeral"}
    if scoped:
        query = query.eq("scope_entity_id", project_entity["id"])
    rows = _rows(query.limit(3).execute())
    if len(rows) == 1:
        return rows[0]

    # V28.2.2 — aliases resolvidos em rodadas anteriores passam a evitar novas
    # duplicatas. O alias precisa respeitar o mesmo escopo para instâncias de
    # projeto; entidades canônicas globais podem usar alias global.
    try:
        alias_query = (
            client.table("entity_aliases")
            .select("entity_id,scope_entity_id")
            .eq("normalized_alias", normalized)
            .eq("active", True)
        )
        if scoped:
            alias_query = alias_query.eq("scope_entity_id", project_entity["id"])
        aliases = _rows(alias_query.limit(4).execute())
        entity_ids = list(dict.fromkeys(str(row.get("entity_id") or "") for row in aliases if row.get("entity_id")))
        if len(entity_ids) == 1:
            alias_rows = _rows(
                client.table("knowledge_entities").select("*")
                .eq("id", entity_ids[0]).eq("entity_type", candidate.entity_type).eq("status", "active")
                .limit(1).execute()
            )
            if alias_rows:
                return alias_rows[0]
    except Exception:
        pass
    return None


def _ensure_entity(client: Any, candidate: EntityCandidate, project_entity: Mapping[str, Any]) -> dict[str, Any]:
    existing = _find_entity(client, candidate, project_entity)
    if existing:
        attrs = existing.get("attributes") if isinstance(existing.get("attributes"), Mapping) else {}
        merged_attrs = {**dict(attrs), **dict(candidate.attributes)}
        update = {
            "attributes": merged_attrs,
            "confidence": max(float(existing.get("confidence") or 0.0), float(candidate.confidence)),
        }
        try:
            client.table("knowledge_entities").update(_safe(update)).eq("id", existing["id"]).execute()
            existing.update(update)
        except Exception:
            pass
        # Não descarte aliases só porque a entidade já existia. Esses aliases são
        # justamente o que permite que o Entity Resolver aprenda variações entre
        # arquivos e evite criar uma nova entidade no próximo documento.
        for alias in candidate.aliases:
            normalized_alias = _normalize(alias)
            if not normalized_alias:
                continue
            try:
                found = _rows(
                    client.table("entity_aliases").select("id")
                    .eq("entity_id", existing["id"]).eq("normalized_alias", normalized_alias).eq("active", True)
                    .limit(1).execute()
                )
                if found:
                    continue
                client.table("entity_aliases").insert({
                    "entity_id": existing["id"],
                    "alias": alias,
                    "normalized_alias": normalized_alias,
                    "alias_type": "name",
                    "scope_entity_id": project_entity["id"] if candidate.entity_kind != "canonical" else None,
                    "confidence": candidate.confidence,
                    "active": True,
                }).execute()
            except Exception:
                pass
        return existing
    payload = {
        "entity_type": candidate.entity_type,
        "canonical_name": candidate.canonical_name,
        "normalized_name": _normalize(candidate.canonical_name),
        "entity_kind": candidate.entity_kind,
        "scope_entity_id": project_entity["id"] if candidate.entity_kind in {"project_instance", "scoped_profile", "ephemeral"} else None,
        "attributes": candidate.attributes,
        "status": "active",
        "confidence": candidate.confidence,
    }
    rows = _rows(client.table("knowledge_entities").insert(_safe(payload)).execute())
    if not rows:
        raise RuntimeError(f"Entidade não criada: {candidate.canonical_name}")
    entity = rows[0]
    for alias in candidate.aliases:
        try:
            client.table("entity_aliases").insert({
                "entity_id": entity["id"],
                "alias": alias,
                "normalized_alias": _normalize(alias),
                "alias_type": "name",
                "scope_entity_id": project_entity["id"] if candidate.entity_kind != "canonical" else None,
                "confidence": candidate.confidence,
                "active": True,
            }).execute()
        except Exception:
            pass
    return entity


def _persist_entities(client: Any, project_entity: Mapping[str, Any], analysis: FileAnalysisResult, evidence_refs: Mapping[str, str], run_id: str) -> dict[str, dict[str, Any]]:
    entity_map: dict[str, dict[str, Any]] = {"project": dict(project_entity)}
    for candidate in analysis.entities:
        try:
            entity = _ensure_entity(client, candidate, project_entity)
        except Exception:
            continue
        entity_map[candidate.key] = entity
        for ref in candidate.evidence_refs:
            evidence_id = evidence_refs.get(ref)
            if not evidence_id:
                continue
            try:
                existing = _rows(
                    client.table("entity_mentions")
                    .select("id")
                    .eq("evidence_unit_id", evidence_id)
                    .eq("entity_id", entity["id"])
                    .limit(1)
                    .execute()
                )
                if existing:
                    continue
                client.table("entity_mentions").insert({
                    "evidence_unit_id": evidence_id,
                    "entity_id": entity["id"],
                    "mention_text": candidate.canonical_name,
                    "mention_locator": {},
                    "mention_role": "file_analyst_entity",
                    "confidence": candidate.confidence,
                    "intelligence_run_id": run_id,
                }).execute()
            except Exception:
                pass
    return entity_map


def _claim_value_payload(claim: ClaimCandidate, entity_map: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    payload: dict[str, Any] = {
        "value_type": claim.value_type,
        "object_entity_id": None,
        "value_text": None,
        "value_numeric": None,
        "value_boolean": None,
        "value_date": None,
        "value_timestamp": None,
        "value_json": None,
    }
    if claim.value_type == "entity":
        obj = entity_map.get(str(claim.object_key or ""))
        if not obj:
            return None
        payload["object_entity_id"] = obj["id"]
    elif claim.value_type == "text":
        payload["value_text"] = claim.value_text
    elif claim.value_type == "numeric":
        payload["value_numeric"] = claim.value_numeric
    elif claim.value_type == "boolean":
        payload["value_boolean"] = claim.value_boolean
    elif claim.value_type == "date":
        payload["value_date"] = claim.value_date
    elif claim.value_type == "timestamp":
        payload["value_timestamp"] = claim.value_timestamp
    elif claim.value_type == "json":
        payload["value_json"] = _safe(claim.value_json)
    else:
        return None
    return payload


def _persist_claims(client: Any, project_entity: Mapping[str, Any], analysis: FileAnalysisResult, entity_map: Mapping[str, Mapping[str, Any]], evidence_refs: Mapping[str, str], run_id: str) -> list[str]:
    claim_ids: list[str] = []
    for claim in analysis.claims:
        subject = entity_map.get(claim.subject_key)
        if not subject:
            continue
        value_payload = _claim_value_payload(claim, entity_map)
        if value_payload is None:
            continue
        hash_payload = {
            "subject": subject["id"],
            "predicate": claim.predicate,
            "value": value_payload,
            "unit": claim.unit,
            "currency": claim.currency,
            "scope": project_entity["id"],
            "kind": claim.claim_kind,
        }
        claim_hash = _sha_text(json.dumps(_safe(hash_payload), ensure_ascii=False, sort_keys=True))
        payload = {
            "subject_entity_id": subject["id"],
            "predicate": claim.predicate,
            **value_payload,
            "unit": claim.unit,
            "currency": claim.currency,
            "claim_kind": claim.claim_kind,
            "scope_entity_id": project_entity["id"],
            "model_confidence": claim.confidence,
            "authority_score": claim.authority_score,
            "status": "active",
            "intelligence_run_id": run_id,
            "claim_hash": claim_hash,
        }
        existing = _first(client, "knowledge_claims", claim_hash=claim_hash)
        if existing:
            claim_id = str(existing["id"])
            try:
                client.table("knowledge_claims").update({
                    "model_confidence": max(float(existing.get("model_confidence") or 0.0), claim.confidence),
                    "authority_score": max(float(existing.get("authority_score") or 0.0), float(claim.authority_score or 0.0)) or None,
                    "intelligence_run_id": run_id,
                }).eq("id", claim_id).execute()
            except Exception:
                pass
        else:
            rows = _rows(client.table("knowledge_claims").insert(_safe(payload)).execute())
            if not rows:
                continue
            claim_id = str(rows[0]["id"])
        claim_ids.append(claim_id)
        for ref in claim.evidence_refs:
            evidence_id = evidence_refs.get(ref)
            if not evidence_id:
                continue
            try:
                client.table("claim_evidence").insert({
                    "claim_id": claim_id,
                    "evidence_unit_id": evidence_id,
                    "support_type": "supports",
                    "evidence_weight": 1.0,
                }).execute()
            except Exception:
                pass
    return claim_ids


def _persist_relation(client: Any, relation: RelationCandidate, project_entity: Mapping[str, Any], entity_map: Mapping[str, Mapping[str, Any]], evidence_refs: Mapping[str, str], run_id: str) -> str | None:
    source = entity_map.get(relation.source_key)
    target = entity_map.get(relation.target_key)
    if not source or not target or source["id"] == target["id"]:
        return None
    hash_payload = {
        "source": source["id"],
        "relation": relation.relation_type,
        "target": target["id"],
        "scope": project_entity["id"],
        "kind": relation.relation_kind,
    }
    relation_hash = _sha_text(json.dumps(hash_payload, sort_keys=True))
    payload = {
        "source_entity_id": source["id"],
        "relation_type": relation.relation_type,
        "target_entity_id": target["id"],
        "scope_entity_id": project_entity["id"],
        "relation_kind": relation.relation_kind,
        "strength": relation.confidence,
        "confidence": relation.confidence,
        "authority_score": relation.authority_score,
        "status": "active",
        "attributes": relation.attributes,
        "intelligence_run_id": run_id,
        "relation_hash": relation_hash,
    }
    existing = _first(client, "knowledge_relations", relation_hash=relation_hash)
    if existing:
        relation_id = str(existing["id"])
        try:
            client.table("knowledge_relations").update({
                "confidence": max(float(existing.get("confidence") or 0.0), relation.confidence),
                "strength": max(float(existing.get("strength") or 0.0), relation.confidence),
                "intelligence_run_id": run_id,
            }).eq("id", relation_id).execute()
        except Exception:
            pass
    else:
        rows = _rows(client.table("knowledge_relations").insert(_safe(payload)).execute())
        if not rows:
            return None
        relation_id = str(rows[0]["id"])
    for ref in relation.evidence_refs:
        evidence_id = evidence_refs.get(ref)
        if not evidence_id:
            continue
        try:
            client.table("relation_evidence").insert({
                "relation_id": relation_id,
                "evidence_unit_id": evidence_id,
                "support_type": "supports",
                "evidence_weight": 1.0,
            }).execute()
        except Exception:
            pass
    return relation_id


def _derive_feedback_actor_relations(client: Any, analysis: FileAnalysisResult, project_entity: Mapping[str, Any], entity_map: dict[str, dict[str, Any]], evidence_refs: Mapping[str, str], run_id: str, project_id: str) -> int:
    source_type = str(analysis.metadata.get("feedback_source_type") or "")
    if source_type not in {"client", "procurement", "marketing", "branding"}:
        return 0
    actor = _ensure_brand_entity(client, project_entity, project_id)
    if not actor:
        return 0
    entity_map.setdefault("feedback_actor", actor)
    count = 0
    sentiment_by_subject: dict[str, str] = {}
    approval_by_subject: dict[str, str] = {}
    refs_by_subject: dict[str, list[str]] = {}
    for claim in analysis.claims:
        if claim.subject_key == "project" and claim.predicate == "commercial_result":
            continue
        refs_by_subject.setdefault(claim.subject_key, []).extend(claim.evidence_refs)
        if claim.predicate == "sentiment" and claim.value_text:
            sentiment_by_subject[claim.subject_key] = claim.value_text
        if claim.predicate == "approval_status" and claim.value_text:
            approval_by_subject[claim.subject_key] = claim.value_text
    for subject_key, entity in list(entity_map.items()):
        if subject_key in {"project", "feedback_actor"}:
            continue
        sentiment = sentiment_by_subject.get(subject_key)
        approval = approval_by_subject.get(subject_key)
        relation_type = None
        if approval in {"approved", "approved_with_changes"} or sentiment == "positive":
            relation_type = "validated_by"
        elif approval in {"not_approved", "removed_budget", "removed_timeline"} or sentiment == "negative":
            relation_type = "challenged_by"
        if not relation_type:
            continue
        relation = RelationCandidate(
            source_key=subject_key,
            relation_type=relation_type,
            target_key="feedback_actor",
            relation_kind="decision",
            confidence=0.95,
            authority_score=1.0,
            evidence_refs=list(dict.fromkeys(refs_by_subject.get(subject_key, [])))[:8],
            attributes={"derived_from_feedback_source_type": source_type},
        )
        if _persist_relation(client, relation, project_entity, entity_map, evidence_refs, run_id):
            count += 1
    return count


def _persist_relations(client: Any, project_entity: Mapping[str, Any], analysis: FileAnalysisResult, entity_map: dict[str, dict[str, Any]], evidence_refs: Mapping[str, str], run_id: str, project_id: str) -> int:
    count = 0
    for relation in analysis.relations:
        if _persist_relation(client, relation, project_entity, entity_map, evidence_refs, run_id):
            count += 1
    count += _derive_feedback_actor_relations(client, analysis, project_entity, entity_map, evidence_refs, run_id, project_id)
    return count


def _persist_low_findings(client: Any, run_id: str, project_entity: Mapping[str, Any], analysis: FileAnalysisResult, evidence_refs: Mapping[str, str]) -> int:
    count = 0
    # Contradições/unknowns ainda não possuem refs granulares no schema v1;
    # ficam low/medium para não violar o gate de grounding high/critical.
    for kind, rows, importance, confidence in (
        ("unknown", analysis.unknowns, "low", 0.75),
        ("contradiction", analysis.contradictions, "medium", 0.72),
    ):
        for idx, statement in enumerate(rows[:24], start=1):
            payload = {
                "intelligence_run_id": run_id,
                "analyzer_type": "file_analyst",
                "scope_entity_id": project_entity["id"],
                "finding_type": f"file_{kind}",
                "title": "Lacuna na fonte" if kind == "unknown" else "Contradição interna da fonte",
                "statement": statement,
                "finding_kind": kind,
                "importance": importance,
                "confidence": confidence,
                "impact_domains": ["source_understanding"],
                "status": "active",
            }
            try:
                rows_inserted = _rows(client.table("intelligence_findings").insert(_safe(payload)).execute())
                if rows_inserted:
                    count += 1
            except Exception:
                pass
    return count


def persist_file_analysis(client: Any, source_file: Mapping[str, Any], analysis: FileAnalysisResult) -> dict[str, Any]:
    if not foundation_available(client):
        return {
            "status": "skipped_foundation_missing",
            "evidence": 0,
            "entities": 0,
            "claims": 0,
            "relations": 0,
            "findings": 0,
            "warning": "Intelligence Foundation v1 ainda não está disponível; dual-write ignorado sem afetar o workspace legado.",
        }
    project_id = str(source_file.get("project_id") or "").strip()
    if not project_id:
        return {"status": "skipped_no_project", "evidence": 0, "entities": 0, "claims": 0, "relations": 0, "findings": 0}

    started = time.monotonic()
    project_entity = _ensure_project_entity(client, project_id)
    source_asset = _ensure_source_asset(client, source_file, analysis)
    _ensure_context(client, source_asset, project_entity, source_file, analysis)
    run = _start_run(client, source_asset, project_entity, analysis)
    counts = {"evidence": 0, "entities": 0, "claims": 0, "relations": 0, "findings": 0}
    try:
        evidence_refs = _persist_evidence(client, str(source_asset["id"]), str(run["id"]), analysis.evidence_units)
        counts["evidence"] = len(evidence_refs)
        entity_map = _persist_entities(client, project_entity, analysis, evidence_refs, str(run["id"]))
        counts["entities"] = max(0, len(entity_map) - 1)
        claim_ids = _persist_claims(client, project_entity, analysis, entity_map, evidence_refs, str(run["id"]))
        counts["claims"] = len(claim_ids)
        counts["relations"] = _persist_relations(client, project_entity, analysis, entity_map, evidence_refs, str(run["id"]), project_id)
        counts["findings"] = _persist_low_findings(client, str(run["id"]), project_entity, analysis, evidence_refs)
        status = "completed" if not analysis.warnings else "partial"
        _finish_run(client, run, started_monotonic=started, status=status, analysis=analysis, counts=counts)
        return {
            "status": status,
            "source_asset_id": source_asset["id"],
            "run_id": run["id"],
            **counts,
            "semantic_analysis_ran": analysis.semantic_analysis_ran,
            "warnings": list(analysis.warnings),
        }
    except Exception as exc:
        _finish_run(client, run, started_monotonic=started, status="error", analysis=analysis, counts=counts, error=str(exc))
        raise


def dual_write_source_file(
    client: Any,
    source_file: Mapping[str, Any],
    *,
    source_bytes: bytes | None,
    enable_semantic: bool = True,
) -> dict[str, Any]:
    """Analisa + persiste um source_file sem interferir na materialização legada."""
    if not foundation_available(client):
        return {
            "status": "skipped_foundation_missing",
            "evidence": 0,
            "entities": 0,
            "claims": 0,
            "relations": 0,
            "findings": 0,
            "warning": "Intelligence Foundation v1 não encontrada.",
        }
    if source_bytes is None:
        return {
            "status": "skipped_no_bytes",
            "evidence": 0,
            "entities": 0,
            "claims": 0,
            "relations": 0,
            "findings": 0,
            "warning": "Arquivo original indisponível para o File Analyst; o workspace legado continua preservado.",
        }
    analysis = analyze_file(
        file_name=str(source_file.get("file_name") or "arquivo"),
        data=source_bytes,
        mime_type=str(source_file.get("mime_type") or "application/octet-stream"),
        declared_role=str(source_file.get("document_role") or "") or None,
        enable_semantic=enable_semantic,
    )
    return persist_file_analysis(client, source_file, analysis)
