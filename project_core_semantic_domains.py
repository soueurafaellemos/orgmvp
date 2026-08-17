from __future__ import annotations

"""NAVE V28.7.2B — Strategy, Creative Platform & Experience Architecture shadow domain."""

from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from project_core_semantic_extractor import collect_project_core_semantic_observations
from project_semantic_relations import plan_core_semantic_relations

CORE_VERSION = "V28.7.2B"
CORE_SCHEMA_VERSION = "28.7.2b"
CORE_RPC = "apply_project_core_semantics_v2872b"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_rows(client: Any, table: str, *, equals: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    query = client.table(table).select("*")
    for key, value in (equals or {}).items():
        query = query.eq(key, value)
    return _rows(query.execute())


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _best_observation(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return dict(max(
        rows,
        key=lambda row: (
            float(row.get("source_authority_score") or 0.0),
            float(row.get("model_confidence") or 0.0),
            -len(str((row.get("attributes") or {}).get("statement") or row.get("observed_name") or "")),
        ),
    ))


def _ids(rows: Sequence[Mapping[str, Any]], field: str) -> list[str]:
    return list(dict.fromkeys(str(row.get(field)) for row in rows if row.get(field)))


def probe_core_semantic_schema(client: Any) -> dict[str, Any]:
    try:
        for table in (
            "project_strategy_elements", "project_creative_platforms", "project_creative_elements",
            "project_experience_architectures", "project_journey_moments",
        ):
            client.table(table).select("id").limit(1).execute()
        client.table("project_core_semantic_status").select("project_id").limit(1).execute()
        return {"available": True, "status": "ready"}
    except Exception as exc:
        text = str(exc)
        missing = "PGRST205" in text or "does not exist" in text.lower() or "schema cache" in text.lower()
        return {"available": False, "status": "schema_missing" if missing else "schema_check_error", "error": text}


def _project_entity(client: Any, project_id: str) -> dict[str, Any] | None:
    rows = _rows(
        client.table("knowledge_entities").select("*")
        .eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute()
    )
    return rows[0] if rows else None


def build_core_semantic_plan(project_id: str, observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pure plan: only eligible evidence-backed observations may create Domain Truth.

    Identity keys deliberately exclude Evidence IDs so repeated source occurrences attach to
    one project-domain identity instead of recreating the old identity=occurrence mistake.
    """
    eligible = [
        dict(row) for row in observations
        if str(row.get("assertion_mode") or "") in {"source_explicit", "evidence_synthesis", "human_confirmed"}
        and float(row.get("model_confidence") or 0.0) >= 0.84
        and row.get("evidence_unit_id")
    ]
    strategy_elements: list[dict[str, Any]] = []
    creative_platforms: list[dict[str, Any]] = []
    creative_elements: list[dict[str, Any]] = []
    experience_architectures: list[dict[str, Any]] = []
    journey_moments: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []

    # Strategy identity: project + semantic type + normalized title.
    strategy_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for obs in eligible:
        if str(obs.get("domain_hint") or "") != "strategy":
            continue
        role = str(obs.get("semantic_role") or "strategic_direction")
        name = str(obs.get("observed_name") or role).strip()
        if not _norm(name):
            continue
        strategy_groups.setdefault((role, _norm(name)), []).append(obs)
    for (role, norm_name), group in strategy_groups.items():
        primary = _best_observation(group)
        key = _sha({"project": project_id, "type": role, "name": norm_name})
        domain_id = _stable_uuid("nave:v2872b:strategy:" + key)
        entity_id = _stable_uuid("nave:v2872b:strategy-entity:" + key)
        statement = str((primary.get("attributes") or {}).get("statement") or primary.get("observed_name") or "").strip()
        observation_ids = _ids(group, "id")
        evidence_ids = _ids(group, "evidence_unit_id")
        strategy_elements.append({
            "id": domain_id,
            "entity_id": entity_id,
            "strategy_key": key,
            "strategy_type": role,
            "title": str(primary.get("observed_name") or role).strip(),
            "statement": statement,
            "assertion_mode": primary.get("assertion_mode"),
            "scope": {},
            "attributes": {
                "semantic_observation_ids": observation_ids,
                "evidence_ids": evidence_ids,
                "source_asset_ids": _ids(group, "source_asset_id"),
                "normalized_by": CORE_VERSION,
            },
            "source_observation_id": primary.get("id"),
            "source_evidence_id": primary.get("evidence_unit_id"),
            "evidence_ids": evidence_ids,
            "confidence": max(float(row.get("model_confidence") or 0.0) for row in group),
            "authority_score": max(float(row.get("source_authority_score") or 0.0) for row in group),
        })
        for obs in group:
            resolutions.append({
                "id": obs.get("id"), "status": "reconciled", "resolution_action": "reconcile_domain_object",
                "resolved_entity_id": entity_id, "resolved_domain_table": "project_strategy_elements", "resolved_domain_id": domain_id,
                "resolution_detail": {"domain": "strategy", "strategy_type": role},
            })

    # Creative Platform identity is created only by a platform-capable source signal
    # (big idea / POV / naming). Other creative signals remain elements and require a
    # deterministic platform association; they never become parallel platforms by accident.
    creative_observations = [
        obs for obs in eligible if str(obs.get("domain_hint") or "") == "creative"
    ]
    platform_roles = {"big_idea", "pov", "naming"}
    platform_groups: dict[str, list[dict[str, Any]]] = {}
    for obs in creative_observations:
        role = str(obs.get("semantic_role") or "")
        name = str(obs.get("observed_name") or "").strip()
        if role in platform_roles and _norm(name):
            platform_groups.setdefault(_norm(name), []).append(obs)

    for norm_name, group in platform_groups.items():
        primary = _best_observation(group)
        platform_key = _sha({"project": project_id, "name": norm_name})
        platform_id = _stable_uuid("nave:v2872b:creative-platform:" + platform_key)
        platform_entity_id = _stable_uuid("nave:v2872b:creative-platform-entity:" + platform_key)
        observation_ids = _ids(group, "id")
        evidence_ids = _ids(group, "evidence_unit_id")
        creative_platforms.append({
            "id": platform_id,
            "entity_id": platform_entity_id,
            "platform_key": platform_key,
            "name": str(primary.get("observed_name") or "Creative Platform").strip(),
            "description": str((primary.get("attributes") or {}).get("statement") or primary.get("observed_name") or "").strip(),
            "assertion_mode": primary.get("assertion_mode"),
            "attributes": {
                "semantic_observation_ids": observation_ids,
                "evidence_ids": evidence_ids,
                "source_asset_ids": _ids(group, "source_asset_id"),
                "platform_source_roles": sorted(set(str(obs.get("semantic_role") or "") for obs in group)),
                "normalized_by": CORE_VERSION,
            },
            "source_observation_id": primary.get("id"),
            "source_evidence_id": primary.get("evidence_unit_id"),
            "evidence_ids": evidence_ids,
            "confidence": max(float(row.get("model_confidence") or 0.0) for row in group),
            "authority_score": max(float(row.get("source_authority_score") or 0.0) for row in group),
        })

    platform_by_evidence: dict[str, list[dict[str, Any]]] = {}
    platform_by_asset: dict[str, list[dict[str, Any]]] = {}
    for platform in creative_platforms:
        for evidence_id in platform.get("evidence_ids") or []:
            platform_by_evidence.setdefault(str(evidence_id), []).append(platform)
        for asset_id in (platform.get("attributes") or {}).get("source_asset_ids") or []:
            platform_by_asset.setdefault(str(asset_id), []).append(platform)

    creative_element_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    element_association_mode: dict[tuple[str, str, str], str] = {}
    unresolved_creative: list[dict[str, Any]] = []
    for obs in creative_observations:
        role = str(obs.get("semantic_role") or "big_idea")
        title = str(obs.get("observed_name") or "").strip()
        if not _norm(title):
            continue
        evidence_id = str(obs.get("evidence_unit_id") or "")
        asset_id = str(obs.get("source_asset_id") or "")
        candidates = platform_by_evidence.get(evidence_id) or []
        association_mode = "source_explicit"
        platform: dict[str, Any] | None = None
        # A platform-generating observation deterministically belongs to its own platform.
        own_platform = next(
            (row for row in creative_platforms if _norm(row.get("name")) == _norm(title)),
            None,
        ) if role in platform_roles else None
        if own_platform is not None:
            platform = own_platform
        elif len(candidates) == 1:
            platform = candidates[0]
        elif not candidates:
            same_asset = platform_by_asset.get(asset_id) or []
            if len(same_asset) == 1:
                platform = same_asset[0]
                association_mode = "evidence_synthesis"
        if platform is None:
            unresolved_creative.append(obs)
            continue
        key = (str(platform["id"]), role, _norm(title))
        creative_element_groups.setdefault(key, []).append(obs)
        # Prefer explicit association if any observation in the group has it.
        prior = element_association_mode.get(key)
        if prior != "source_explicit":
            element_association_mode[key] = association_mode

    for (platform_id, role, element_name), element_group in creative_element_groups.items():
        platform = next(row for row in creative_platforms if str(row["id"]) == platform_id)
        element_primary = _best_observation(element_group)
        element_key = _sha({"project": project_id, "platform": platform_id, "role": role, "name": element_name})
        element_id = _stable_uuid("nave:v2872b:creative-element:" + element_key)
        element_entity_id = _stable_uuid("nave:v2872b:creative-element-entity:" + element_key)
        association_mode = element_association_mode[(platform_id, role, element_name)]
        creative_elements.append({
            "id": element_id,
            "entity_id": element_entity_id,
            "platform_id": platform_id,
            "platform_entity_id": platform["entity_id"],
            "element_key": element_key,
            "creative_type": role,
            "title": str(element_primary.get("observed_name") or role).strip(),
            "statement": str((element_primary.get("attributes") or {}).get("statement") or element_primary.get("observed_name") or "").strip(),
            "assertion_mode": element_primary.get("assertion_mode"),
            "attributes": {
                "semantic_observation_ids": _ids(element_group, "id"),
                "evidence_ids": _ids(element_group, "evidence_unit_id"),
                "source_asset_ids": _ids(element_group, "source_asset_id"),
                "platform_association_mode": association_mode,
                "normalized_by": CORE_VERSION,
            },
            "platform_association_mode": association_mode,
            "source_observation_id": element_primary.get("id"),
            "source_evidence_id": element_primary.get("evidence_unit_id"),
            "evidence_ids": _ids(element_group, "evidence_unit_id"),
            "confidence": max(float(row.get("model_confidence") or 0.0) for row in element_group),
            "authority_score": max(float(row.get("source_authority_score") or 0.0) for row in element_group),
        })
        for obs in element_group:
            resolutions.append({
                "id": obs.get("id"), "status": "reconciled", "resolution_action": "reconcile_domain_object",
                "resolved_entity_id": platform["entity_id"], "resolved_domain_table": "project_creative_platforms", "resolved_domain_id": platform_id,
                "resolution_detail": {
                    "domain": "creative", "creative_type": role, "creative_element_id": element_id,
                    "platform_association_mode": association_mode,
                },
            })

    for obs in unresolved_creative:
        resolutions.append({
            "id": obs.get("id"), "status": "open", "resolution_action": "insufficient_evidence",
            "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
            "resolution_detail": {"reason": "creative_element_requires_unambiguous_creative_platform"},
        })

    # Experience Architecture identity: project + explicit architecture name.
    experience_groups: dict[str, list[dict[str, Any]]] = {}
    for obs in eligible:
        if str(obs.get("domain_hint") or "") != "experience":
            continue
        name = str(obs.get("observed_name") or "Experience Architecture").strip()
        if _norm(name):
            experience_groups.setdefault(_norm(name), []).append(obs)
    for norm_name, group in experience_groups.items():
        primary = _best_observation(group)
        key = _sha({"project": project_id, "name": norm_name})
        domain_id = _stable_uuid("nave:v2872b:experience:" + key)
        entity_id = _stable_uuid("nave:v2872b:experience-entity:" + key)
        evidence_ids = _ids(group, "evidence_unit_id")
        experience_architectures.append({
            "id": domain_id,
            "entity_id": entity_id,
            "architecture_key": key,
            "name": str(primary.get("observed_name") or "Experience Architecture").strip(),
            "experience_principle": None,
            "participation_logic": None,
            "flow_summary": str((primary.get("attributes") or {}).get("statement") or primary.get("observed_name") or "").strip(),
            "assertion_mode": primary.get("assertion_mode"),
            "attributes": {
                "semantic_observation_ids": _ids(group, "id"),
                "evidence_ids": evidence_ids,
                "source_asset_ids": _ids(group, "source_asset_id"),
                "normalized_by": CORE_VERSION,
            },
            "source_observation_id": primary.get("id"),
            "source_evidence_id": primary.get("evidence_unit_id"),
            "evidence_ids": evidence_ids,
            "confidence": max(float(row.get("model_confidence") or 0.0) for row in group),
            "authority_score": max(float(row.get("source_authority_score") or 0.0) for row in group),
        })
        for obs in group:
            resolutions.append({
                "id": obs.get("id"), "status": "reconciled", "resolution_action": "reconcile_domain_object",
                "resolved_entity_id": entity_id, "resolved_domain_table": "project_experience_architectures", "resolved_domain_id": domain_id,
                "resolution_detail": {"domain": "experience", "experience_type": obs.get("semantic_role")},
            })

    # Journey moments: direct same-evidence architecture is strongest. A unique explicit
    # architecture may organize an explicit moment elsewhere in the same project, but the
    # association is marked as evidence_synthesis rather than mislabelled source-explicit.
    architecture_by_evidence: dict[str, dict[str, Any]] = {}
    for row in experience_architectures:
        for evidence_id in row.get("evidence_ids") or []:
            architecture_by_evidence[str(evidence_id)] = row
    sole_architecture = experience_architectures[0] if len(experience_architectures) == 1 else None
    journey_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    unresolved_journey: list[dict[str, Any]] = []
    association_by_observation: dict[str, tuple[dict[str, Any], str]] = {}
    for obs in eligible:
        if str(obs.get("domain_hint") or "") != "journey":
            continue
        evidence_id = str(obs.get("evidence_unit_id") or "")
        architecture = architecture_by_evidence.get(evidence_id)
        association_mode = "source_explicit"
        if architecture is None and sole_architecture is not None:
            architecture = sole_architecture
            association_mode = "evidence_synthesis"
        if architecture is None:
            unresolved_journey.append(obs)
            continue
        attrs = dict(obs.get("attributes") or {})
        moment_type = str(attrs.get("moment_type") or obs.get("semantic_role") or "other")
        name = str(obs.get("observed_name") or moment_type).strip()
        journey_groups.setdefault((architecture["id"], moment_type, _norm(name)), []).append(obs)
        association_by_observation[str(obs.get("id"))] = (architecture, association_mode)

    for (architecture_id, moment_type, norm_name), group in journey_groups.items():
        primary = _best_observation(group)
        architecture, association_mode = association_by_observation[str(primary.get("id"))]
        key = _sha({"project": project_id, "architecture": architecture_id, "type": moment_type, "name": norm_name})
        domain_id = _stable_uuid("nave:v2872b:journey:" + key)
        entity_id = _stable_uuid("nave:v2872b:journey-entity:" + key)
        sequences = [
            int((row.get("attributes") or {}).get("sequence_index"))
            for row in group
            if isinstance((row.get("attributes") or {}).get("sequence_index"), (int, float))
        ]
        evidence_ids = _ids(group, "evidence_unit_id")
        journey_moments.append({
            "id": domain_id,
            "entity_id": entity_id,
            "architecture_id": architecture_id,
            "moment_key": key,
            "sequence_index": min(sequences) if sequences else None,
            "moment_type": moment_type,
            "title": str(primary.get("observed_name") or moment_type).strip(),
            "purpose": str((primary.get("attributes") or {}).get("statement") or primary.get("observed_name") or "").strip(),
            "participant_action": None,
            "experience_role": None,
            "attributes": {
                "semantic_observation_ids": _ids(group, "id"),
                "evidence_ids": evidence_ids,
                "source_asset_ids": _ids(group, "source_asset_id"),
                "architecture_association_mode": association_mode,
                "parent_stage_hint": (primary.get("attributes") or {}).get("parent_stage_hint"),
                "normalized_by": CORE_VERSION,
            },
            "assertion_mode": primary.get("assertion_mode"),
            "architecture_association_mode": association_mode,
            "source_observation_id": primary.get("id"),
            "source_evidence_id": primary.get("evidence_unit_id"),
            "evidence_ids": evidence_ids,
            "confidence": max(float(row.get("model_confidence") or 0.0) for row in group),
            "authority_score": max(float(row.get("source_authority_score") or 0.0) for row in group),
        })
        for obs in group:
            resolutions.append({
                "id": obs.get("id"), "status": "reconciled", "resolution_action": "reconcile_domain_object",
                "resolved_entity_id": entity_id, "resolved_domain_table": "project_journey_moments", "resolved_domain_id": domain_id,
                "resolution_detail": {
                    "domain": "journey", "architecture_id": architecture_id,
                    "moment_type": moment_type, "architecture_association_mode": association_mode,
                },
            })
    for obs in unresolved_journey:
        resolutions.append({
            "id": obs.get("id"), "status": "open", "resolution_action": "insufficient_evidence",
            "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
            "resolution_detail": {"reason": "journey_moment_requires_explicit_experience_architecture"},
        })

    return {
        "strategy_elements": strategy_elements,
        "creative_platforms": creative_platforms,
        "creative_elements": creative_elements,
        "experience_architectures": experience_architectures,
        "journey_moments": journey_moments,
        "observation_resolutions": resolutions,
    }


def _start_run(client: Any, project_id: str, project_entity_id: str, signature: Any) -> str:
    run_id = str(uuid4())
    payload = {
        "id": run_id,
        "analyzer_type": "project_core_semantic_domains",
        "scope_kind": "project",
        "scope_entity_id": project_entity_id,
        "pipeline_version": CORE_VERSION,
        "code_version": CORE_VERSION,
        "schema_version": CORE_SCHEMA_VERSION,
        "input_signature": _sha(signature),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"project_id": project_id, "legacy_shadow": True, "analyst_inference_as_truth": False},
    }
    rows = _rows(client.table("intelligence_runs").insert(payload).execute())
    if not rows:
        raise RuntimeError("Supabase não confirmou intelligence_run de Core Semantic Domains")
    return str(rows[0].get("id") or run_id)


def _mark_run_error(client: Any, run_id: str, exc: Exception) -> None:
    try:
        client.table("intelligence_runs").update({
            "status": "error",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "core_semantic_domains_error",
            "error_detail": str(exc)[:4000],
        }).eq("id", run_id).execute()
    except Exception:
        pass


def fetch_project_core_semantic_status(client: Any, project_id: str) -> dict[str, Any]:
    rows = _rows(client.table("project_core_semantic_status").select("*").eq("project_id", project_id).limit(1).execute())
    return rows[0] if rows else {"project_id": project_id}


def materialize_project_core_semantics(client: Any, project_id: str) -> dict[str, Any]:
    probe = probe_core_semantic_schema(client)
    if not probe.get("available"):
        return {"project_id": project_id, "status": probe.get("status"), "warnings": [probe.get("error")]}
    project_entity = _project_entity(client, project_id)
    if not project_entity:
        return {"project_id": project_id, "status": "blocked", "warnings": ["Project knowledge_entity mirror ausente."]}

    extraction = collect_project_core_semantic_observations(client, project_id)
    observations = extraction.get("observations") or []
    plan = build_core_semantic_plan(project_id, observations)

    solution_instances = _read_rows(client, "project_solution_instances", equals={"project_id": project_id})
    solution_occurrences = _read_rows(client, "project_solution_occurrences", equals={"project_id": project_id})
    context_elements = _read_rows(client, "project_context_elements", equals={"project_id": project_id})
    requirements = _read_rows(client, "project_requirements", equals={"project_id": project_id})

    req_entities = [str(row.get("entity_id")) for row in requirements if row.get("entity_id")]
    req_evidence_links: list[dict[str, Any]] = []
    if req_entities:
        for start in range(0, len(req_entities), 80):
            req_evidence_links.extend(_rows(
                client.table("domain_object_evidence").select("*")
                .in_("object_entity_id", req_entities[start:start + 80]).execute()
            ))
    evidence_by_req_entity: dict[str, list[str]] = {}
    for link in req_evidence_links:
        if link.get("object_entity_id") and link.get("evidence_unit_id"):
            evidence_by_req_entity.setdefault(str(link["object_entity_id"]), []).append(str(link["evidence_unit_id"]))
    requirements_for_relations = [
        {**row, "evidence_ids": evidence_by_req_entity.get(str(row.get("entity_id") or ""), [])}
        for row in requirements
    ]

    relations = plan_core_semantic_relations(
        project_id,
        strategy_elements=plan["strategy_elements"],
        creative_platforms=plan["creative_platforms"],
        creative_elements=plan["creative_elements"],
        experience_architectures=plan["experience_architectures"],
        journey_moments=plan["journey_moments"],
        solution_occurrences=solution_occurrences,
        solution_instances=solution_instances,
        context_elements=context_elements,
        requirements=requirements_for_relations,
    )

    bundle = {
        "version": CORE_VERSION,
        "project_entity_id": str(project_entity.get("id")),
        "observations": observations,
        **plan,
        "relations": relations,
    }
    run_id = _start_run(client, project_id, str(project_entity.get("id")), {
        "observations": [(row.get("observation_hash"), row.get("domain_hint"), row.get("semantic_role")) for row in observations],
        "plan": {key: len(value) for key, value in plan.items() if isinstance(value, list)},
        "relations": [row.get("relation_hash") for row in relations],
    })
    try:
        response = client.rpc(CORE_RPC, {"p_project_id": project_id, "p_run_id": run_id, "p_bundle": bundle}).execute()
        rpc_rows = _rows(response)
        status = fetch_project_core_semantic_status(client, project_id)
        return {
            "project_id": project_id,
            "status": "completed",
            "run_id": run_id,
            "rpc": rpc_rows[0] if rpc_rows else {},
            "core_semantics": status,
            "actions": {
                "observations": len(observations),
                "strategy_elements": len(plan["strategy_elements"]),
                "creative_platforms": len(plan["creative_platforms"]),
                "creative_elements": len(plan["creative_elements"]),
                "experience_architectures": len(plan["experience_architectures"]),
                "journey_moments": len(plan["journey_moments"]),
                "relations": len(relations),
                "strategy_titles": [row["title"] for row in plan["strategy_elements"]],
                "creative_names": [row["name"] for row in plan["creative_platforms"]],
                "journey_titles": [row["title"] for row in plan["journey_moments"]],
            },
            "warnings": [],
        }
    except Exception as exc:
        _mark_run_error(client, run_id, exc)
        return {"project_id": project_id, "status": "transaction_error", "run_id": run_id, "warnings": [str(exc)]}
