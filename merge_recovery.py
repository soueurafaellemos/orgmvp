from __future__ import annotations

import json
from typing import Any

import pandas as pd
from supabase import Client

from entity_matching import (
    MATCH_CONFIG,
    analyze_candidate_pair,
    normalize_match_name,
)
from supabase_db import (
    DUPLICATE_ENTITY_COLUMNS,
    DUPLICATE_ENTITY_TABLES,
    _entity_record,
    _json_safe,
    _prepare_record,
)


PAYLOAD_KEYS = {
    "product": "products",
    "activation": "solutions",
    "venue": "venues",
}

IDENTITY_ID_FIELDS = {
    "product": "supplier_id",
    "activation": "supplier_id",
    "venue": "operator_id",
}

PROVENANCE_FIELDS = {
    "id", "created_at", "updated_at", "normalized_name",
    "import_id", "source_file_id", "raw_data",
}


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _same_value(first: Any, second: Any) -> bool:
    return _json_safe(first) == _json_safe(second)


def _source_file_record(client: Client, source_file_id: str | None) -> dict:
    if not source_file_id:
        return {}
    response = (
        client.table("source_files")
        .select("*")
        .eq("id", source_file_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}


def _import_record(client: Client, import_id: str | None) -> dict:
    if not import_id:
        return {}
    response = (
        client.table("imports")
        .select("*")
        .eq("id", import_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}


def _payload_candidates(import_record: dict, entity_type: str) -> list[dict]:
    payload = _as_dict(import_record.get("original_payload"))
    return [
        dict(item)
        for item in _as_list(payload.get(PAYLOAD_KEYS[entity_type]))
        if isinstance(item, dict)
    ]


def reconstruct_merged_source(
    client: Client,
    review: dict,
) -> tuple[dict, str]:
    resolution_data = _as_dict(review.get("resolution_data"))
    snapshot = _as_dict(resolution_data.get("source_snapshot"))
    if snapshot:
        return snapshot, "merge_snapshot"

    entity_type = str(review.get("entity_type") or "")
    import_record = _import_record(client, str(review.get("import_id") or ""))
    candidates = _payload_candidates(import_record, entity_type)
    if not candidates:
        return {}, "import_payload_unavailable"

    source_name = normalize_match_name(review.get("source_name"))
    source_file = _source_file_record(
        client,
        str(review.get("source_file_id") or "") or None,
    )
    file_name = str(source_file.get("file_name") or "").strip()
    context = _as_dict(review.get("match_context"))
    context_page = context.get("source_page")

    exact_name = [
        item for item in candidates
        if normalize_match_name(item.get("name")) == source_name
    ]
    pool = exact_name or candidates

    if file_name:
        by_file = [
            item for item in pool
            if str(item.get("source_file") or "").strip() == file_name
        ]
        if by_file:
            pool = by_file

    if context_page not in (None, ""):
        by_page = [
            item for item in pool
            if str(item.get("source_page") or "") == str(context_page)
        ]
        if by_page:
            pool = by_page

    if len(pool) == 1:
        return dict(pool[0]), "import_original_payload"

    # A unique exact name is still safe even when the source file metadata was
    # not retained in older candidate rows.
    if len(exact_name) == 1:
        return dict(exact_name[0]), "import_original_payload_name"

    return {}, "ambiguous_import_payload"


def classify_merged_review(client: Client, review: dict) -> dict:
    entity_type = str(review.get("entity_type") or "")
    source, source_method = reconstruct_merged_source(client, review)
    target = _entity_record(
        client,
        entity_type=entity_type,
        entity_id=str(review.get("candidate_entity_id") or ""),
    )

    if not source:
        return {
            "classification": "unrecoverable",
            "reason": source_method,
            "source_record": {},
            "target_record": target,
            "analysis": {},
        }
    if not target:
        return {
            "classification": "unrecoverable",
            "reason": "target_record_unavailable",
            "source_record": source,
            "target_record": {},
            "analysis": {},
        }

    analysis = analyze_candidate_pair(entity_type, source, target)
    relation = analysis.get("relation") or {}
    exact_name = (
        normalize_match_name(source.get("name"))
        == normalize_match_name(target.get("name"))
        and bool(normalize_match_name(source.get("name")))
    )
    evidence = set(analysis.get("evidence") or [])
    strong_name_identity = bool(
        exact_name
        or evidence
        & {"name_exact", "name_token_set_same", "name_semantic_alias"}
    )
    threshold = float(MATCH_CONFIG[entity_type]["review_threshold"])

    review_conflicts = evidence & {
        "operator_conflict_review",
        "official_domains_conflict_review",
    }

    if relation.get("type") == "parent_subspace":
        classification = "hierarchy"
        reason = "parent_subspace_relation"
    elif analysis.get("blocked"):
        classification = "incompatible"
        reason = ", ".join(analysis.get("blockers") or [])
    elif strong_name_identity and review_conflicts:
        classification = "ambiguous"
        reason = "semantic_identity_with_real_conflict"
    elif strong_name_identity:
        # Uma união antiga entre nomes semanticamente equivalentes não deve ser
        # oferecida como recuperação automática só porque faltavam endereço,
        # domínio ou taxonomia consistente no arquivo original.
        classification = "likely_correct"
        reason = "semantic_identity_confirmed"
    elif float(analysis.get("score") or 0) < threshold:
        classification = "incompatible"
        reason = "insufficient_identity_evidence"
    else:
        classification = "ambiguous"
        reason = "human_review_required"

    return {
        "classification": classification,
        "reason": reason,
        "source_record": source,
        "target_record": target,
        "analysis": analysis,
        "source_method": source_method,
    }


def fetch_merge_recovery_candidates(
    client: Client,
    *,
    limit: int = 1000,
) -> pd.DataFrame:
    response = (
        client.table("knowledge_duplicate_candidates")
        .select("*")
        .eq("status", "merged")
        .order("resolved_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows: list[dict] = []
    for review in response.data or []:
        classified = classify_merged_review(client, review)
        source = classified.get("source_record") or {}
        target = classified.get("target_record") or {}
        analysis = classified.get("analysis") or {}
        rows.append(
            {
                **review,
                "source_name": source.get("name") or review.get("source_name"),
                "candidate_name": target.get("name") or review.get("candidate_name"),
                "recovery_classification": classified["classification"],
                "recovery_reason": classified["reason"],
                "source_reconstruction": classified.get("source_method"),
                "corrected_score": float(analysis.get("score") or 0),
                "source_record": source,
                "candidate_record": target,
                "match_analysis": analysis,
            }
        )
    return pd.DataFrame(rows)


def _recover_media(
    client: Client,
    *,
    review: dict,
    source_record: dict,
    new_entity_id: str,
    target_entity_id: str,
) -> dict:
    resolution_data = _as_dict(review.get("resolution_data"))
    moved_ids = [
        str(item) for item in _as_list(resolution_data.get("moved_media_ids"))
        if str(item).strip()
    ]
    original_states = {
        str(item.get("id")): item
        for item in _as_list(resolution_data.get("moved_media_original_states"))
        if isinstance(item, dict) and item.get("id")
    }

    target_response = (
        client.table("media_assets")
        .select("*")
        .eq("entity_type", str(review.get("entity_type")))
        .eq("entity_id", target_entity_id)
        .execute()
    )
    target_assets = [dict(item) for item in (target_response.data or [])]

    selected: list[dict] = []
    if moved_ids:
        selected = [item for item in target_assets if str(item.get("id")) in moved_ids]
    else:
        source_file_id = str(review.get("source_file_id") or "").strip()
        source_file = str(source_record.get("source_file") or "").strip()
        source_page = source_record.get("source_page")
        for item in target_assets:
            same_file_id = bool(
                source_file_id
                and str(item.get("source_file_id") or "") == source_file_id
            )
            same_file_name = bool(
                source_file
                and str(item.get("source_file") or "").strip() == source_file
            )
            same_page = (
                source_page not in (None, "")
                and str(item.get("source_page") or "") == str(source_page)
            )
            if same_page and (same_file_id or same_file_name):
                selected.append(item)

        # Older rows may omit page metadata. Only move by file when there is a
        # single attributable asset; moving a whole multi-item PDF would be unsafe.
        if not selected and source_file_id:
            by_file = [
                item for item in target_assets
                if str(item.get("source_file_id") or "") == source_file_id
            ]
            if len(by_file) == 1:
                selected = by_file

    moved = 0
    for item in selected:
        changes = {"entity_id": new_entity_id}
        state = original_states.get(str(item.get("id"))) or {}
        if "is_primary" in state:
            changes["is_primary"] = bool(state.get("is_primary"))
        if state.get("asset_type"):
            changes["asset_type"] = state.get("asset_type")
        (
            client.table("media_assets")
            .update(changes)
            .eq("id", item["id"])
            .execute()
        )
        moved += 1

    # Guarantee a useful cover for the recovered record and leave the target
    # with a primary image when it still owns image assets.
    if selected and not any(bool(item.get("is_primary")) for item in selected):
        first = selected[0]
        changes = {"is_primary": True}
        if first.get("asset_type") == "gallery_image":
            changes["asset_type"] = "main_image"
        (
            client.table("media_assets")
            .update(changes)
            .eq("id", first["id"])
            .execute()
        )

    remaining = [item for item in target_assets if item not in selected]
    if remaining and not any(bool(item.get("is_primary")) for item in remaining):
        first_remaining = remaining[0]
        changes = {"is_primary": True}
        if first_remaining.get("asset_type") == "gallery_image":
            changes["asset_type"] = "main_image"
        (
            client.table("media_assets")
            .update(changes)
            .eq("id", first_remaining["id"])
            .execute()
        )

    return {"media_restored": moved, "media_ids": [item.get("id") for item in selected]}


def _recover_activation_costs(
    client: Client,
    *,
    review: dict,
    source_record: dict,
    new_entity_id: str,
    target_entity_id: str,
) -> dict:
    if str(review.get("entity_type") or "") != "activation":
        return {"costs_restored": 0, "cost_ids": []}

    resolution_data = _as_dict(review.get("resolution_data"))
    moved_ids = {
        str(item)
        for item in _as_list(resolution_data.get("moved_cost_ids"))
        if str(item).strip()
    }
    response = (
        client.table("activation_costs")
        .select("*")
        .eq("solution_id", target_entity_id)
        .execute()
    )
    target_costs = [dict(item) for item in (response.data or [])]

    selected: list[dict] = []
    if moved_ids:
        selected = [
            item for item in target_costs
            if str(item.get("id") or "") in moved_ids
        ]
    else:
        source_page = source_record.get("source_page")
        source_file = str(source_record.get("source_file") or "").strip()
        page_matches: list[dict] = []
        for item in target_costs:
            raw_data = _as_dict(item.get("raw_data"))
            same_page = bool(
                source_page not in (None, "")
                and str(item.get("source_page") or raw_data.get("source_page") or "")
                == str(source_page)
            )
            same_file = bool(
                source_file
                and str(raw_data.get("source_file") or "").strip() == source_file
            )
            if same_page and same_file:
                selected.append(item)
            elif same_page:
                page_matches.append(item)

        # Old cost rows may not retain the source filename. A unique page match
        # is safe; several costs on the same page are intentionally left in the
        # preserved target rather than guessed.
        if not selected and len(page_matches) == 1:
            selected = page_matches

    restored_ids: list[str] = []
    for item in selected:
        (
            client.table("activation_costs")
            .update({"solution_id": new_entity_id})
            .eq("id", item["id"])
            .execute()
        )
        restored_ids.append(str(item.get("id") or ""))

    # Future merges snapshot costs deleted only because an equivalent row
    # already existed in the target. Recreate that source-side history when a
    # recovery is requested; omit system-generated identifiers/timestamps.
    for snapshot in _as_list(resolution_data.get("duplicate_cost_snapshots")):
        if not isinstance(snapshot, dict):
            continue
        payload = {
            key: _json_safe(value)
            for key, value in snapshot.items()
            if key not in {"id", "created_at", "updated_at", "solution_id"}
        }
        payload["solution_id"] = new_entity_id
        try:
            inserted = client.table("activation_costs").insert(payload).execute()
            if inserted.data:
                restored_ids.append(str(inserted.data[0].get("id") or ""))
        except Exception:
            # The underlying schema may enforce uniqueness. In that case the
            # non-destructive result is to retain the target copy and report no
            # extra restored cost rather than fail the entity recovery.
            continue

    return {
        "costs_restored": len(restored_ids),
        "cost_ids": restored_ids,
    }


def _revert_target_fields(
    client: Client,
    *,
    review: dict,
    source_record: dict,
    target_record: dict,
) -> dict:
    resolution_data = _as_dict(review.get("resolution_data"))
    target_snapshot = _as_dict(resolution_data.get("target_snapshot"))
    target_post = _as_dict(resolution_data.get("target_post_merge_snapshot"))
    fields = list(
        dict.fromkeys(
            [
                *_as_list(resolution_data.get("fields_filled")),
                *_as_list(resolution_data.get("fields_updated")),
                *_as_list(resolution_data.get("fields_merged")),
            ]
        )
    )
    changes: dict[str, Any] = {}
    unresolved: list[str] = []

    if target_snapshot:
        for field in fields:
            if field in PROVENANCE_FIELDS or field == "name":
                continue
            # Three-way safety: do not overwrite an edit made after the merge.
            if target_post and not _same_value(
                target_record.get(field), target_post.get(field)
            ):
                unresolved.append(field)
                continue
            changes[field] = _json_safe(target_snapshot.get(field))
    else:
        # Older merges did not store the pre-merge snapshot. We can safely undo
        # only fields explicitly reported as filled into an empty target and
        # only while the current value is still exactly the source value.
        for field in _as_list(resolution_data.get("fields_filled")):
            if field in PROVENANCE_FIELDS or field in {"name", "tags"}:
                continue
            if _same_value(target_record.get(field), source_record.get(field)):
                changes[field] = None
        unresolved.extend(
            str(field)
            for field in [
                *_as_list(resolution_data.get("fields_updated")),
                *_as_list(resolution_data.get("fields_merged")),
            ]
            if str(field) not in PROVENANCE_FIELDS
        )

    if changes:
        table = DUPLICATE_ENTITY_TABLES[str(review.get("entity_type"))]
        (
            client.table(table)
            .update(changes)
            .eq("id", str(review.get("candidate_entity_id")))
            .execute()
        )

    return {
        "target_fields_reverted": sorted(changes),
        "target_fields_preserved_for_review": sorted(set(unresolved)),
    }


def _record_recovery_event(client: Client, payload: dict) -> None:
    try:
        client.table("knowledge_merge_recovery_events").insert(payload).execute()
    except Exception:
        # The recovery itself remains functional even before the optional audit
        # table migration is applied; hierarchy columns are validated by insert.
        pass


def recover_merged_review(
    client: Client,
    *,
    review_id: str,
    force: bool = False,
) -> dict:
    response = (
        client.table("knowledge_duplicate_candidates")
        .select("*")
        .eq("id", review_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise ValueError("A união não foi encontrada.")

    review = dict(response.data[0])
    if str(review.get("status") or "") != "merged":
        raise ValueError("Esta união já foi recuperada ou não está ativa.")

    classified = classify_merged_review(client, review)
    classification = classified["classification"]
    if not force and classification not in {"incompatible", "hierarchy"}:
        raise ValueError(
            "A correspondência exige revisão individual antes da recuperação."
        )

    entity_type = str(review.get("entity_type"))
    source_record = dict(classified.get("source_record") or {})
    target_record = dict(classified.get("target_record") or {})
    if not source_record or not target_record:
        raise ValueError("Não há dados suficientes para reconstruir a união.")

    table = DUPLICATE_ENTITY_TABLES[entity_type]
    old_source_id = str(review.get("source_entity_id") or "")
    existing_source = _entity_record(
        client,
        entity_type=entity_type,
        entity_id=old_source_id,
    )
    if existing_source:
        new_entity_id = old_source_id
        inserted = False
    else:
        payload = _prepare_record(
            source_record,
            DUPLICATE_ENTITY_COLUMNS[entity_type],
        )
        payload.pop("id", None)
        payload["import_id"] = review.get("import_id")
        payload["source_file_id"] = review.get("source_file_id")

        identity_field = IDENTITY_ID_FIELDS[entity_type]
        resolution_data = _as_dict(review.get("resolution_data"))
        source_snapshot = _as_dict(resolution_data.get("source_snapshot"))
        context = _as_dict(review.get("match_context"))
        identity_value = source_snapshot.get(identity_field) or context.get(identity_field)
        if identity_value:
            payload[identity_field] = identity_value

        analysis = classified.get("analysis") or {}
        relation = analysis.get("relation") or {}
        if entity_type == "venue":
            if relation.get("type") == "parent_subspace":
                payload["parent_venue_id"] = str(review.get("candidate_entity_id"))
                payload["venue_scope"] = "subspace"
                payload["subspace_name"] = source_record.get("name")
            else:
                payload.setdefault("venue_scope", "venue")

        raw_data = _as_dict(payload.get("raw_data"))
        raw_data["_nave_merge_recovery"] = {
            "review_id": review_id,
            "old_source_entity_id": old_source_id,
            "target_entity_id": review.get("candidate_entity_id"),
            "recovered_at": pd.Timestamp.utcnow().isoformat(),
            "classification": classification,
        }
        payload["raw_data"] = _json_safe(raw_data)

        insert_response = client.table(table).insert(payload).execute()
        if not insert_response.data:
            raise RuntimeError("A base não devolveu o cadastro reconstruído.")
        new_entity_id = str(insert_response.data[0]["id"])
        inserted = True

    media_result = _recover_media(
        client,
        review=review,
        source_record=source_record,
        new_entity_id=new_entity_id,
        target_entity_id=str(review.get("candidate_entity_id")),
    )
    cost_result = _recover_activation_costs(
        client,
        review=review,
        source_record=source_record,
        new_entity_id=new_entity_id,
        target_entity_id=str(review.get("candidate_entity_id")),
    )
    target_result = _revert_target_fields(
        client,
        review=review,
        source_record=source_record,
        target_record=target_record,
    )

    old_resolution = _as_dict(review.get("resolution_data"))
    recovery_data = {
        "recovered": True,
        "recovered_at": pd.Timestamp.utcnow().isoformat(),
        "new_entity_id": new_entity_id,
        "old_source_entity_id": old_source_id,
        "classification": classification,
        "reason": classified.get("reason"),
        "source_reconstruction": classified.get("source_method"),
        "inserted": inserted,
        **media_result,
        **cost_result,
        **target_result,
    }
    old_resolution["recovery"] = recovery_data

    strategy = (
        "merge_reverted_as_hierarchy"
        if classification == "hierarchy"
        else "merge_reverted_as_distinct"
    )
    (
        client.table("knowledge_duplicate_candidates")
        .update(
            {
                "status": "different",
                "resolution_strategy": strategy,
                "resolved_at": pd.Timestamp.utcnow().isoformat(),
                "resolution_data": _json_safe(old_resolution),
            }
        )
        .eq("id", review_id)
        .execute()
    )

    _record_recovery_event(
        client,
        {
            "duplicate_candidate_id": review_id,
            "entity_type": entity_type,
            "old_source_entity_id": old_source_id or None,
            "recovered_entity_id": new_entity_id,
            "target_entity_id": review.get("candidate_entity_id"),
            "recovery_type": strategy,
            "details": _json_safe(recovery_data),
        },
    )
    return recovery_data


def recover_incompatible_merges(client: Client, *, limit: int = 1000) -> dict:
    candidates = fetch_merge_recovery_candidates(client, limit=limit)
    if candidates.empty:
        return {"recovered": 0, "failed": 0, "errors": []}

    safe = candidates[
        candidates["recovery_classification"].isin(["incompatible", "hierarchy"])
    ]
    recovered = 0
    failed = 0
    errors: list[dict] = []
    media_restored = 0
    costs_restored = 0

    for _, row in safe.iterrows():
        try:
            result = recover_merged_review(
                client,
                review_id=str(row["id"]),
                force=False,
            )
            recovered += 1
            media_restored += int(result.get("media_restored", 0) or 0)
            costs_restored += int(result.get("costs_restored", 0) or 0)
        except Exception as exc:
            failed += 1
            errors.append({
                "review_id": str(row.get("id") or ""),
                "source_name": row.get("source_name"),
                "candidate_name": row.get("candidate_name"),
                "error": str(exc),
            })

    return {
        "recovered": recovered,
        "failed": failed,
        "media_restored": media_restored,
        "costs_restored": costs_restored,
        "errors": errors,
    }
