from __future__ import annotations

"""NAVE V28.7.3B2.12.4 — Requirement Identity Supersession · DRY RUN.

READ ONLY. Simulates the exact effects required by a future governed supersession.
No UPDATE/INSERT/DELETE, no Human Review, no Truth effect, no cutover.
"""

from dataclasses import dataclass
from typing import Any, Mapping
import hashlib
import json

from project_requirement_identity_collision_shadow import run_identity_collision_shadow
from project_requirement_compatibility import build_requirement_compatibility_from_rows

VERSION = "V28.7.3B2.12.4"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(x) for x in (data or []) if isinstance(x, Mapping)]


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def occurrence_hash(project_id: str, requirement_id: str, evidence_unit_id: str, role: str) -> str:
    return _sha({
        "project": project_id,
        "requirement": requirement_id,
        "evidence": evidence_unit_id,
        "role": role,
    })


def _truth(row: Mapping[str, Any]) -> str:
    return str(row.get("truth_state") or row.get("verification_state") or "").casefold()


@dataclass(frozen=True)
class DryPlan:
    canonical_obligation_text: str
    survivor_requirement_id: str
    survivor_entity_id: str
    superseded_requirement_ids: tuple[str, ...]
    superseded_entity_ids: tuple[str, ...]
    metadata_conflicts: tuple[str, ...]
    occurrence_actions: tuple[dict[str, Any], ...]
    alias_actions: tuple[dict[str, Any], ...]
    evidence_actions: tuple[dict[str, Any], ...]
    semantic_observation_actions: tuple[dict[str, Any], ...]
    compatibility_status_after: str
    compatibility_active_links_after: int
    compatibility_resolved_links_after: int
    compatibility_unmapped_after: int
    compatibility_ambiguous_after: int
    current_before: int
    projected_current_after: int
    projected_collisions_after: int
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers and self.compatibility_status_after == "PASS_DATA_BRIDGE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_obligation_text": self.canonical_obligation_text,
            "survivor_requirement_id": self.survivor_requirement_id,
            "survivor_entity_id": self.survivor_entity_id,
            "superseded_requirement_ids": list(self.superseded_requirement_ids),
            "superseded_entity_ids": list(self.superseded_entity_ids),
            "metadata_conflicts": list(self.metadata_conflicts),
            "metadata_resolution_policy": "preserve_survivor_values_no_silent_merge",
            "projected_requirement_update": {
                "superseded_status": "superseded",
                "survivor_business_metadata_changed": False,
            },
            "projected_governance_update": {
                "superseded_lifecycle_status": "superseded",
                "superseded_by_entity_id": self.survivor_entity_id,
                "review_status_changed": False,
            },
            "projected_knowledge_entity_update": {
                "superseded_status": "merged",
                "canonical_entity_id": self.survivor_entity_id,
            },
            "occurrence_actions": list(self.occurrence_actions),
            "alias_actions": list(self.alias_actions),
            "evidence_actions": list(self.evidence_actions),
            "semantic_observation_actions": list(self.semantic_observation_actions),
            "compatibility_status_after": self.compatibility_status_after,
            "compatibility_active_links_after": self.compatibility_active_links_after,
            "compatibility_resolved_links_after": self.compatibility_resolved_links_after,
            "compatibility_unmapped_after": self.compatibility_unmapped_after,
            "compatibility_ambiguous_after": self.compatibility_ambiguous_after,
            "current_before": self.current_before,
            "projected_current_after": self.projected_current_after,
            "projected_collisions_after": self.projected_collisions_after,
            "blockers": list(self.blockers),
            "write_performed": False,
            "truth_changed": False,
        }


@dataclass(frozen=True)
class DryReport:
    project_id: str
    current_before: int
    collisions_before: int
    plans: tuple[DryPlan, ...]

    @property
    def ready_count(self) -> int:
        return sum(1 for x in self.plans if x.ready)

    @property
    def blocked_count(self) -> int:
        return sum(1 for x in self.plans if not x.ready)

    @property
    def projected_current_after(self) -> int:
        if self.blocked_count:
            return self.current_before
        return self.current_before - sum(len(x.superseded_requirement_ids) for x in self.plans)

    @property
    def projected_collisions_after(self) -> int:
        if self.blocked_count:
            return self.collisions_before
        return 0

    @property
    def status(self) -> str:
        if self.blocked_count:
            return "BLOCKED_TRANSACTIONAL_SUPERSESSION_DESIGN"
        if self.plans:
            return "PASS_DRY_RUN_READY_FOR_GOVERNED_WRITE_DESIGN"
        return "PASS_NO_TRANSACTION_REQUIRED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "current_requirement_count_before": self.current_before,
            "collision_count_before": self.collisions_before,
            "transaction_plan_count": len(self.plans),
            "ready_transaction_plan_count": self.ready_count,
            "blocked_transaction_plan_count": self.blocked_count,
            "projected_current_requirement_count_after": self.projected_current_after,
            "projected_collision_count_after": self.projected_collisions_after,
            "write_performed": False,
            "persistence_performed": False,
            "truth_changed": False,
            "human_review_created": False,
            "cutover_approved": False,
            "plans": [x.to_dict() for x in self.plans],
        }


def build_dry_run(
    *,
    project_id: str,
    shadow: Mapping[str, Any],
    truth_rows: list[dict[str, Any]],
    requirement_rows: list[dict[str, Any]],
    occurrence_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    legacy_requirement_rows: list[dict[str, Any]],
    legacy_link_rows: list[dict[str, Any]],
) -> DryReport:
    current = [x for x in truth_rows if _truth(x) in {"verified", "human_confirmed"}]
    current_count = len(current)
    raw_by_id = {str(x.get("id")): x for x in requirement_rows if x.get("id")}
    truth_by_id = {str(x.get("id")): x for x in truth_rows if x.get("id")}
    active_hashes = {
        str(x.get("occurrence_hash")): x
        for x in occurrence_rows
        if x.get("occurrence_hash") and str(x.get("lifecycle_status") or "active") == "active"
    }

    plans: list[DryPlan] = []
    for source in shadow.get("plans") or []:
        if source.get("resolution_status") != "ready_for_transactional_resolution":
            continue

        survivor_id = str(source.get("proposed_survivor_id") or "")
        old_ids = tuple(str(x) for x in source.get("proposed_superseded_ids") or [])
        survivor = {**raw_by_id.get(survivor_id, {}), **truth_by_id.get(survivor_id, {})}
        survivor_entity = str(survivor.get("entity_id") or "")
        old_entities = tuple(
            str(({**raw_by_id.get(rid, {}), **truth_by_id.get(rid, {})}).get("entity_id") or "")
            for rid in old_ids
        )
        blockers: list[str] = []
        if not survivor_id or not survivor_entity:
            blockers.append("survivor_identity_or_entity_missing")
        if any(not x for x in old_entities):
            blockers.append("superseded_entity_missing")

        # Occurrence rebind must recompute occurrence_hash because requirement_id is part of it.
        occ_actions: list[dict[str, Any]] = []
        alias_carried: set[str] = set()
        aliases: set[str] = set()

        for rid in old_ids:
            raw = raw_by_id.get(rid, {})
            if raw.get("legacy_source_id"):
                aliases.add(str(raw["legacy_source_id"]))

        for occ in occurrence_rows:
            rid = str(occ.get("requirement_id") or "")
            if rid not in old_ids or str(occ.get("lifecycle_status") or "active") != "active":
                continue
            alias = str(occ.get("legacy_requirement_id") or "")
            if alias:
                aliases.add(alias)
            new_hash = occurrence_hash(
                project_id,
                survivor_id,
                str(occ.get("evidence_unit_id") or ""),
                str(occ.get("occurrence_role") or "requirement"),
            )
            existing = active_hashes.get(new_hash)
            if existing and str(existing.get("id")) != str(occ.get("id")):
                occ_actions.append({
                    "occurrence_id": occ.get("id"),
                    "action": "supersede_duplicate_occurrence",
                    "existing_survivor_occurrence_id": existing.get("id"),
                    "from_requirement_id": rid,
                    "to_requirement_id": survivor_id,
                    "target_occurrence_hash": new_hash,
                    "legacy_requirement_id": alias or None,
                })
            else:
                occ_actions.append({
                    "occurrence_id": occ.get("id"),
                    "action": "rebind_occurrence",
                    "from_requirement_id": rid,
                    "to_requirement_id": survivor_id,
                    "from_occurrence_hash": occ.get("occurrence_hash"),
                    "target_occurrence_hash": new_hash,
                    "legacy_requirement_id": alias or None,
                })
                if alias:
                    alias_carried.add(alias)

        # Alias can remain via active rebound occurrence. If one alias is left and survivor
        # has no legacy_source_id, the future transaction may place it there.
        alias_actions: list[dict[str, Any]] = []
        remaining = sorted(aliases - alias_carried)
        survivor_legacy = str(survivor.get("legacy_source_id") or "")
        if survivor_legacy and survivor_legacy in remaining:
            alias_actions.append({"alias": survivor_legacy, "action": "already_on_survivor"})
            remaining.remove(survivor_legacy)
        elif not survivor_legacy and len(remaining) == 1:
            survivor_legacy = remaining.pop()
            alias_actions.append({
                "alias": survivor_legacy,
                "action": "set_survivor_legacy_source_id",
                "survivor_requirement_id": survivor_id,
            })
        if remaining:
            blockers.append("legacy_alias_not_representable_without_new_bridge:" + ",".join(remaining))

        # Simulate B2.1 compatibility after the projected state.
        current_after: list[dict[str, Any]] = []
        for row in current:
            rid = str(row.get("id") or "")
            if rid in old_ids:
                continue
            copy = dict(row)
            if rid == survivor_id and survivor_legacy:
                copy["legacy_source_id"] = survivor_legacy
            current_after.append(copy)

        action_by_id = {str(x["occurrence_id"]): x for x in occ_actions}
        occ_after: list[dict[str, Any]] = []
        for row in occurrence_rows:
            copy = dict(row)
            action = action_by_id.get(str(copy.get("id") or ""))
            if action:
                if action["action"] == "rebind_occurrence":
                    copy["requirement_id"] = survivor_id
                    copy["occurrence_hash"] = action["target_occurrence_hash"]
                    copy["lifecycle_status"] = "active"
                else:
                    copy["lifecycle_status"] = "superseded"
            occ_after.append(copy)

        compat = build_requirement_compatibility_from_rows(
            project_id=project_id,
            current_domain_rows=current_after,
            legacy_requirement_rows=legacy_requirement_rows,
            occurrence_rows=occ_after,
            legacy_link_rows=legacy_link_rows,
        )
        compat_status = "PASS_DATA_BRIDGE" if compat.pass_data_bridge else "BLOCKED"
        if not compat.pass_data_bridge:
            blockers.append("projected_b2_1_compatibility_not_pass")

        # Preserve old evidence links. Project a survivor copy only.
        old_entity_set = set(old_entities)
        evidence_actions = tuple({
            "action": "project_survivor_evidence_link_preserve_old",
            "source_evidence_link_id": row.get("id"),
            "from_object_entity_id": row.get("object_entity_id"),
            "to_object_entity_id": survivor_entity,
            "from_domain_id": row.get("domain_id"),
            "to_domain_id": survivor_id,
            "evidence_unit_id": row.get("evidence_unit_id"),
            "link_role": row.get("link_role"),
        } for row in evidence_rows
        if str(row.get("object_entity_id") or "") in old_entity_set
        and str(row.get("domain_table") or "") == "project_requirements")

        semantic_actions = tuple({
            "semantic_observation_id": row.get("id"),
            "resolved_domain_id": row.get("resolved_domain_id"),
            "action": "preserve_immutable_historical_resolution",
        } for row in semantic_rows
        if str(row.get("resolved_domain_id") or "") in old_ids)

        plans.append(DryPlan(
            canonical_obligation_text=str(source.get("canonical_obligation_text") or ""),
            survivor_requirement_id=survivor_id,
            survivor_entity_id=survivor_entity,
            superseded_requirement_ids=old_ids,
            superseded_entity_ids=old_entities,
            metadata_conflicts=tuple(source.get("metadata_conflicts") or []),
            occurrence_actions=tuple(occ_actions),
            alias_actions=tuple(alias_actions),
            evidence_actions=evidence_actions,
            semantic_observation_actions=semantic_actions,
            compatibility_status_after=compat_status,
            compatibility_active_links_after=compat.active_link_count,
            compatibility_resolved_links_after=compat.resolved_active_link_count,
            compatibility_unmapped_after=compat.active_links_unmapped,
            compatibility_ambiguous_after=compat.active_links_ambiguous,
            current_before=current_count,
            projected_current_after=current_count - len(old_ids),
            projected_collisions_after=0 if not blockers else int(shadow.get("collision_count") or 0),
            blockers=tuple(blockers),
        ))

    return DryReport(
        project_id=project_id,
        current_before=current_count,
        collisions_before=int(shadow.get("collision_count") or 0),
        plans=tuple(plans),
    )


def run_dry_run(client: Any, *, project_id: str) -> DryReport:
    shadow = run_identity_collision_shadow(client, project_id=project_id).to_dict()

    truth = _rows(client.table("project_requirement_truth_status").select("*").eq("project_id", project_id).execute())
    requirements = _rows(client.table("project_requirements").select("*").eq("project_id", project_id).execute())
    occurrences = _rows(client.table("project_requirement_occurrences").select("*").eq("project_id", project_id).execute())
    evidence = _rows(client.table("domain_object_evidence").select("*").eq("project_id", project_id).eq("domain_table", "project_requirements").execute())
    semantics = _rows(client.table("semantic_observations").select("*").eq("project_id", project_id).eq("domain_hint", "requirement").execute())
    legacy_requirements = _rows(client.table("memory_briefing_requirements").select("*").eq("project_id", project_id).execute())
    legacy_links = _rows(client.table("memory_briefing_links").select("*").eq("project_id", project_id).execute())

    return build_dry_run(
        project_id=project_id,
        shadow=shadow,
        truth_rows=truth,
        requirement_rows=requirements,
        occurrence_rows=occurrences,
        evidence_rows=evidence,
        semantic_rows=semantics,
        legacy_requirement_rows=legacy_requirements,
        legacy_link_rows=legacy_links,
    )
