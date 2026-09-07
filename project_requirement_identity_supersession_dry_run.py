from __future__ import annotations

"""NAVE V28.7.3B2.12.4.1 — Transaction Integrity Hardening · DRY RUN.

READ ONLY. No UPDATE / INSERT / DELETE.

Hardens B2.12.4 before any real supersession write:
1. validates the actual Governance + Knowledge Entity rows that would be mutated;
2. coalesces historical Domain Evidence so a survivor does not receive duplicate links;
3. projects occurrence rebind/dedup with the recomputed occurrence hash;
4. re-runs B2.1 compatibility in memory on the projected state;
5. preserves survivor business metadata and historical semantic observations.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import hashlib
import json

from project_requirement_identity_collision_shadow import run_identity_collision_shadow
from project_requirement_compatibility import build_requirement_compatibility_from_rows

VERSION = "V28.7.3B2.12.4.1"
CURRENT_TRUTH = {"verified", "human_confirmed"}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def occurrence_hash(
    project_id: str,
    requirement_id: str,
    evidence_unit_id: str,
    occurrence_role: str,
) -> str:
    # Must stay identical to project_requirement_reconciliation.py.
    return _sha({
        "project": project_id,
        "requirement": requirement_id,
        "evidence": evidence_unit_id,
        "role": occurrence_role,
    })


def _truth(row: Mapping[str, Any]) -> str:
    return str(
        row.get("truth_state")
        or row.get("verification_state")
        or row.get("truth_status")
        or ""
    ).casefold()


def _active_occ(row: Mapping[str, Any]) -> bool:
    return str(row.get("lifecycle_status") or "active").casefold() == "active"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _entity_integrity_findings(
    *,
    survivor_requirement_id: str,
    survivor_entity_id: str,
    superseded_pairs: Sequence[tuple[str, str]],
    governance_rows: Sequence[Mapping[str, Any]],
    knowledge_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[str] = []
    gov_by_entity: dict[str, list[dict[str, Any]]] = {}
    ke_by_entity: dict[str, list[dict[str, Any]]] = {}

    for raw in governance_rows:
        row = dict(raw)
        eid = str(row.get("entity_id") or "")
        if eid:
            gov_by_entity.setdefault(eid, []).append(row)
    for raw in knowledge_rows:
        row = dict(raw)
        eid = str(row.get("id") or "")
        if eid:
            ke_by_entity.setdefault(eid, []).append(row)

    all_pairs = [(survivor_requirement_id, survivor_entity_id), *superseded_pairs]
    for rid, eid in all_pairs:
        gov = gov_by_entity.get(eid, [])
        ke = ke_by_entity.get(eid, [])
        if len(gov) != 1:
            findings.append(f"governance_row_count:{rid}:{len(gov)}")
        if len(ke) != 1:
            findings.append(f"knowledge_entity_row_count:{rid}:{len(ke)}")
            continue

        entity = ke[0]
        domain_table = str(entity.get("domain_table") or "")
        domain_id = str(entity.get("domain_id") or "")
        if domain_table and domain_table != "project_requirements":
            findings.append(f"knowledge_entity_wrong_domain_table:{rid}:{domain_table}")
        if domain_id and domain_id != rid:
            findings.append(f"knowledge_entity_wrong_domain_id:{rid}:{domain_id}")

    if len(gov_by_entity.get(survivor_entity_id, [])) == 1:
        survivor_gov = gov_by_entity[survivor_entity_id][0]
        lifecycle = str(survivor_gov.get("lifecycle_status") or "active").casefold()
        if lifecycle != "active":
            findings.append(f"survivor_governance_not_active:{lifecycle}")

    if len(ke_by_entity.get(survivor_entity_id, [])) == 1:
        survivor_ke = ke_by_entity[survivor_entity_id][0]
        canonical = str(survivor_ke.get("canonical_entity_id") or "")
        if canonical and canonical != survivor_entity_id:
            findings.append(f"survivor_already_canonicalized_elsewhere:{canonical}")

    gov_actions: list[dict[str, Any]] = []
    ke_actions: list[dict[str, Any]] = []
    for rid, eid in superseded_pairs:
        gov_rows = gov_by_entity.get(eid, [])
        ke_rows = ke_by_entity.get(eid, [])
        if len(gov_rows) == 1:
            gov = gov_rows[0]
            lifecycle = str(gov.get("lifecycle_status") or "active").casefold()
            existing_target = str(gov.get("superseded_by_entity_id") or "")
            if lifecycle == "superseded" and existing_target and existing_target != survivor_entity_id:
                findings.append(f"superseded_to_different_entity:{rid}:{existing_target}")
            elif lifecycle not in {"active", "superseded"}:
                findings.append(f"unexpected_superseded_governance_lifecycle:{rid}:{lifecycle}")
            gov_actions.append({
                "requirement_id": rid,
                "entity_id": eid,
                "action": "set_lifecycle_superseded",
                "from_lifecycle_status": lifecycle,
                "to_lifecycle_status": "superseded",
                "superseded_by_entity_id": survivor_entity_id,
                "review_status_preserved": gov.get("review_status"),
            })

        if len(ke_rows) == 1:
            ke = ke_rows[0]
            existing_canonical = str(ke.get("canonical_entity_id") or "")
            if existing_canonical and existing_canonical != survivor_entity_id:
                findings.append(f"knowledge_entity_canonical_conflict:{rid}:{existing_canonical}")
            ke_actions.append({
                "requirement_id": rid,
                "entity_id": eid,
                "action": "set_entity_merged",
                "from_status": ke.get("status"),
                "to_status": "merged",
                "canonical_entity_id": survivor_entity_id,
            })

    return findings, gov_actions, ke_actions


def _project_occurrences_and_aliases(
    *,
    project_id: str,
    survivor_id: str,
    superseded_ids: set[str],
    survivor_legacy_source_id: str | None,
    raw_requirement_rows: Sequence[Mapping[str, Any]],
    occurrence_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    str | None,
    list[str],
    dict[str, str],
]:
    findings: list[str] = []
    raw_by_id = {
        str(row.get("id") or ""): dict(row)
        for row in raw_requirement_rows
        if row.get("id")
    }

    aliases: set[str] = set()
    for rid in superseded_ids:
        alias = str(raw_by_id.get(rid, {}).get("legacy_source_id") or "")
        if alias:
            aliases.add(alias)

    active_by_hash = {
        str(row.get("occurrence_hash") or ""): dict(row)
        for row in occurrence_rows
        if row.get("occurrence_hash") and _active_occ(row)
    }

    actions: list[dict[str, Any]] = []
    alias_carried: set[str] = set()
    target_occurrence_by_source: dict[str, str] = {}

    for raw in occurrence_rows:
        row = dict(raw)
        rid = str(row.get("requirement_id") or "")
        if rid not in superseded_ids or not _active_occ(row):
            continue

        oid = str(row.get("id") or "")
        evidence_id = str(row.get("evidence_unit_id") or "")
        role = str(row.get("occurrence_role") or "requirement")
        alias = str(row.get("legacy_requirement_id") or "")
        if alias:
            aliases.add(alias)

        target_hash = occurrence_hash(
            project_id,
            survivor_id,
            evidence_id,
            role,
        )
        existing = active_by_hash.get(target_hash)

        if existing and str(existing.get("id") or "") != oid:
            target_oid = str(existing.get("id") or "")
            actions.append({
                "occurrence_id": oid,
                "action": "supersede_duplicate_occurrence",
                "from_requirement_id": rid,
                "to_requirement_id": survivor_id,
                "existing_survivor_occurrence_id": target_oid,
                "target_occurrence_hash": target_hash,
                "legacy_requirement_id": alias or None,
            })
        else:
            target_oid = oid
            actions.append({
                "occurrence_id": oid,
                "action": "rebind_occurrence",
                "from_requirement_id": rid,
                "to_requirement_id": survivor_id,
                "from_occurrence_hash": row.get("occurrence_hash"),
                "target_occurrence_hash": target_hash,
                "legacy_requirement_id": alias or None,
                "evidence_unit_id": evidence_id,
                "occurrence_role": role,
            })
            if alias:
                alias_carried.add(alias)

        if oid:
            target_occurrence_by_source[oid] = target_oid

    remaining = sorted(aliases - alias_carried)
    alias_actions: list[dict[str, Any]] = []
    survivor_legacy = str(survivor_legacy_source_id or "")

    if survivor_legacy and survivor_legacy in remaining:
        alias_actions.append({
            "alias": survivor_legacy,
            "action": "already_on_survivor_legacy_source_id",
        })
        remaining.remove(survivor_legacy)
    elif not survivor_legacy and len(remaining) == 1:
        survivor_legacy = remaining.pop()
        alias_actions.append({
            "alias": survivor_legacy,
            "action": "set_survivor_legacy_source_id",
            "survivor_requirement_id": survivor_id,
        })

    if remaining:
        findings.append(
            "legacy_aliases_not_representable_without_new_bridge:"
            + ",".join(remaining)
        )

    return actions, alias_actions, survivor_legacy or None, findings, target_occurrence_by_source


def _coalesce_evidence_actions(
    *,
    survivor_id: str,
    survivor_entity_id: str,
    superseded_ids: set[str],
    superseded_entity_ids: set[str],
    evidence_rows: Sequence[Mapping[str, Any]],
    target_occurrence_by_source: Mapping[str, str],
) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    """Coalesce historical evidence to one canonical survivor action per Evidence+role.

    Old links remain untouched. We never copy each historical/rerun link one-for-one.
    """
    findings: list[str] = []
    old_rows = [
        dict(row)
        for row in evidence_rows
        if str(row.get("object_entity_id") or "") in superseded_entity_ids
        and str(row.get("domain_table") or "") == "project_requirements"
    ]
    survivor_rows = [
        dict(row)
        for row in evidence_rows
        if str(row.get("object_entity_id") or "") == survivor_entity_id
        and str(row.get("domain_table") or "") == "project_requirements"
    ]

    survivor_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in survivor_rows:
        key = (
            str(row.get("evidence_unit_id") or ""),
            str(row.get("link_role") or ""),
        )
        survivor_by_key.setdefault(key, []).append(row)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in old_rows:
        key = (
            str(row.get("evidence_unit_id") or ""),
            str(row.get("link_role") or ""),
        )
        grouped.setdefault(key, []).append(row)

    actions: list[dict[str, Any]] = []
    for (evidence_id, link_role), group in sorted(grouped.items()):
        source_ids = sorted(
            str(row.get("id") or "")
            for row in group
            if row.get("id")
        )

        target_occurrence_ids: set[str] = set()
        if link_role == "occurrence":
            for row in group:
                context = _mapping(row.get("context"))
                old_occurrence_id = str(context.get("requirement_occurrence_id") or "")
                if old_occurrence_id:
                    target = str(target_occurrence_by_source.get(old_occurrence_id) or "")
                    if target:
                        target_occurrence_ids.add(target)

            if len(target_occurrence_ids) > 1:
                findings.append(
                    "multiple_target_occurrences_for_one_evidence_role:"
                    + evidence_id
                )

        existing = survivor_by_key.get((evidence_id, link_role), [])
        if existing:
            actions.append({
                "action": "reuse_existing_survivor_evidence_link",
                "survivor_requirement_id": survivor_id,
                "survivor_entity_id": survivor_entity_id,
                "evidence_unit_id": evidence_id,
                "link_role": link_role,
                "existing_survivor_evidence_link_ids": sorted(
                    str(row.get("id") or "")
                    for row in existing
                    if row.get("id")
                ),
                "coalesced_source_evidence_link_ids": source_ids,
                "historical_source_links_preserved": True,
                "target_requirement_occurrence_id": (
                    sorted(target_occurrence_ids)[0]
                    if len(target_occurrence_ids) == 1
                    else None
                ),
            })
            continue

        context: dict[str, Any] = {
            "identity_resolution": {
                "version": VERSION,
                "canonical_requirement_id": survivor_id,
                "superseded_requirement_ids": sorted(superseded_ids),
            }
        }
        if len(target_occurrence_ids) == 1:
            context["requirement_occurrence_id"] = sorted(target_occurrence_ids)[0]

        actions.append({
            "action": "insert_single_survivor_evidence_link",
            "survivor_requirement_id": survivor_id,
            "survivor_entity_id": survivor_entity_id,
            "evidence_unit_id": evidence_id,
            "link_role": link_role,
            "context": context,
            "context_sha256": _sha(context),
            "coalesced_source_evidence_link_ids": source_ids,
            "historical_source_links_preserved": True,
            "target_requirement_occurrence_id": (
                sorted(target_occurrence_ids)[0]
                if len(target_occurrence_ids) == 1
                else None
            ),
        })

    return actions, len(old_rows), len(actions), findings


@dataclass(frozen=True)
class HardenedPlan:
    canonical_obligation_text: str
    survivor_requirement_id: str
    survivor_entity_id: str
    superseded_requirement_ids: tuple[str, ...]
    superseded_entity_ids: tuple[str, ...]
    metadata_conflicts: tuple[str, ...]
    requirement_actions: tuple[dict[str, Any], ...]
    governance_actions: tuple[dict[str, Any], ...]
    knowledge_entity_actions: tuple[dict[str, Any], ...]
    occurrence_actions: tuple[dict[str, Any], ...]
    alias_actions: tuple[dict[str, Any], ...]
    evidence_actions: tuple[dict[str, Any], ...]
    raw_historical_evidence_link_count: int
    coalesced_evidence_action_count: int
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
            "requirement_actions": list(self.requirement_actions),
            "governance_actions": list(self.governance_actions),
            "knowledge_entity_actions": list(self.knowledge_entity_actions),
            "occurrence_actions": list(self.occurrence_actions),
            "alias_actions": list(self.alias_actions),
            "evidence_actions": list(self.evidence_actions),
            "raw_historical_evidence_link_count": self.raw_historical_evidence_link_count,
            "coalesced_evidence_action_count": self.coalesced_evidence_action_count,
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
class HardenedReport:
    project_id: str
    current_before: int
    collisions_before: int
    plans: tuple[HardenedPlan, ...]

    @property
    def ready_count(self) -> int:
        return sum(1 for plan in self.plans if plan.ready)

    @property
    def blocked_count(self) -> int:
        return sum(1 for plan in self.plans if not plan.ready)

    @property
    def projected_current_after(self) -> int:
        if self.blocked_count:
            return self.current_before
        return self.current_before - sum(
            len(plan.superseded_requirement_ids)
            for plan in self.plans
        )

    @property
    def projected_collisions_after(self) -> int:
        if self.blocked_count:
            return self.collisions_before
        return 0

    @property
    def status(self) -> str:
        if self.blocked_count:
            return "BLOCKED_TRANSACTION_INTEGRITY"
        if self.plans:
            return "PASS_HARDENED_DRY_RUN_READY_FOR_GOVERNED_WRITE_DESIGN"
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
            "plans": [plan.to_dict() for plan in self.plans],
        }


def build_hardened_dry_run(
    *,
    project_id: str,
    shadow: Mapping[str, Any],
    truth_rows: Sequence[Mapping[str, Any]],
    requirement_rows: Sequence[Mapping[str, Any]],
    governance_rows: Sequence[Mapping[str, Any]],
    knowledge_rows: Sequence[Mapping[str, Any]],
    occurrence_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    semantic_rows: Sequence[Mapping[str, Any]],
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_link_rows: Sequence[Mapping[str, Any]],
) -> HardenedReport:
    current = [
        dict(row)
        for row in truth_rows
        if _truth(row) in CURRENT_TRUTH
    ]
    current_count = len(current)
    truth_by_id = {
        str(row.get("id") or ""): dict(row)
        for row in truth_rows
        if row.get("id")
    }
    raw_by_id = {
        str(row.get("id") or ""): dict(row)
        for row in requirement_rows
        if row.get("id")
    }

    plans: list[HardenedPlan] = []
    for raw_plan in shadow.get("plans") or []:
        if str(raw_plan.get("resolution_status") or "") != "ready_for_transactional_resolution":
            continue

        survivor_id = str(raw_plan.get("proposed_survivor_id") or "")
        superseded_ids = tuple(
            str(value)
            for value in (raw_plan.get("proposed_superseded_ids") or [])
            if value
        )
        survivor = {
            **raw_by_id.get(survivor_id, {}),
            **truth_by_id.get(survivor_id, {}),
        }
        survivor_entity_id = str(survivor.get("entity_id") or "")

        superseded_pairs: list[tuple[str, str]] = []
        blockers: list[str] = []
        for rid in superseded_ids:
            row = {
                **raw_by_id.get(rid, {}),
                **truth_by_id.get(rid, {}),
            }
            entity_id = str(row.get("entity_id") or "")
            if not entity_id:
                blockers.append(f"superseded_entity_missing:{rid}")
            superseded_pairs.append((rid, entity_id))

        if not survivor_id or not survivor_entity_id:
            blockers.append("survivor_identity_or_entity_missing")

        entity_findings, governance_actions, knowledge_actions = _entity_integrity_findings(
            survivor_requirement_id=survivor_id,
            survivor_entity_id=survivor_entity_id,
            superseded_pairs=superseded_pairs,
            governance_rows=governance_rows,
            knowledge_rows=knowledge_rows,
        )
        blockers.extend(entity_findings)

        occurrence_actions, alias_actions, survivor_legacy, alias_findings, target_occurrence_map = (
            _project_occurrences_and_aliases(
                project_id=project_id,
                survivor_id=survivor_id,
                superseded_ids=set(superseded_ids),
                survivor_legacy_source_id=str(survivor.get("legacy_source_id") or "") or None,
                raw_requirement_rows=requirement_rows,
                occurrence_rows=occurrence_rows,
            )
        )
        blockers.extend(alias_findings)

        evidence_actions, raw_evidence_count, coalesced_count, evidence_findings = _coalesce_evidence_actions(
            survivor_id=survivor_id,
            survivor_entity_id=survivor_entity_id,
            superseded_ids=set(superseded_ids),
            superseded_entity_ids={eid for _rid, eid in superseded_pairs if eid},
            evidence_rows=evidence_rows,
            target_occurrence_by_source=target_occurrence_map,
        )
        blockers.extend(evidence_findings)

        # Simulate the projected B2.1-compatible current state.
        current_after: list[dict[str, Any]] = []
        for raw in current:
            row = dict(raw)
            rid = str(row.get("id") or "")
            if rid in superseded_ids:
                continue
            if rid == survivor_id and survivor_legacy:
                row["legacy_source_id"] = survivor_legacy
            current_after.append(row)

        occurrence_action_by_id = {
            str(row.get("occurrence_id") or ""): row
            for row in occurrence_actions
        }
        occurrence_after: list[dict[str, Any]] = []
        for raw in occurrence_rows:
            row = dict(raw)
            action = occurrence_action_by_id.get(str(row.get("id") or ""))
            if action:
                if action["action"] == "rebind_occurrence":
                    row["requirement_id"] = survivor_id
                    row["occurrence_hash"] = action["target_occurrence_hash"]
                    row["lifecycle_status"] = "active"
                elif action["action"] == "supersede_duplicate_occurrence":
                    row["lifecycle_status"] = "superseded"
            occurrence_after.append(row)

        compat = build_requirement_compatibility_from_rows(
            project_id=project_id,
            current_domain_rows=current_after,
            legacy_requirement_rows=legacy_requirement_rows,
            occurrence_rows=occurrence_after,
            legacy_link_rows=legacy_link_rows,
        )
        compat_status = "PASS_DATA_BRIDGE" if compat.pass_data_bridge else "BLOCKED"
        if not compat.pass_data_bridge:
            blockers.append("projected_b2_1_compatibility_not_pass")

        requirement_actions = tuple({
            "requirement_id": rid,
            "action": "set_status_superseded",
            "from_status": raw_by_id.get(rid, {}).get("status"),
            "to_status": "superseded",
            "survivor_requirement_id": survivor_id,
            "survivor_business_metadata_changed": False,
        } for rid in superseded_ids)

        semantic_actions = tuple({
            "semantic_observation_id": row.get("id"),
            "resolved_domain_id": row.get("resolved_domain_id"),
            "action": "preserve_immutable_historical_resolution",
        } for row in semantic_rows
        if str(row.get("resolved_domain_id") or "") in set(superseded_ids))

        plans.append(HardenedPlan(
            canonical_obligation_text=str(raw_plan.get("canonical_obligation_text") or ""),
            survivor_requirement_id=survivor_id,
            survivor_entity_id=survivor_entity_id,
            superseded_requirement_ids=superseded_ids,
            superseded_entity_ids=tuple(eid for _rid, eid in superseded_pairs),
            metadata_conflicts=tuple(raw_plan.get("metadata_conflicts") or []),
            requirement_actions=requirement_actions,
            governance_actions=tuple(governance_actions),
            knowledge_entity_actions=tuple(knowledge_actions),
            occurrence_actions=tuple(occurrence_actions),
            alias_actions=tuple(alias_actions),
            evidence_actions=tuple(evidence_actions),
            raw_historical_evidence_link_count=raw_evidence_count,
            coalesced_evidence_action_count=coalesced_count,
            semantic_observation_actions=semantic_actions,
            compatibility_status_after=compat_status,
            compatibility_active_links_after=compat.active_link_count,
            compatibility_resolved_links_after=compat.resolved_active_link_count,
            compatibility_unmapped_after=compat.active_links_unmapped,
            compatibility_ambiguous_after=compat.active_links_ambiguous,
            current_before=current_count,
            projected_current_after=current_count - len(superseded_ids),
            projected_collisions_after=0 if not blockers else int(shadow.get("collision_count") or 0),
            blockers=tuple(blockers),
        ))

    return HardenedReport(
        project_id=project_id,
        current_before=current_count,
        collisions_before=int(shadow.get("collision_count") or 0),
        plans=tuple(plans),
    )


def run_hardened_dry_run(client: Any, *, project_id: str) -> HardenedReport:
    shadow = run_identity_collision_shadow(client, project_id=project_id).to_dict()

    truth = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    requirements = _rows(
        client.table("project_requirements")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    occurrences = _rows(
        client.table("project_requirement_occurrences")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    evidence = _rows(
        client.table("domain_object_evidence")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_table", "project_requirements")
        .execute()
    )
    semantics = _rows(
        client.table("semantic_observations")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_hint", "requirement")
        .execute()
    )
    legacy_requirements = _rows(
        client.table("memory_briefing_requirements")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    legacy_links = _rows(
        client.table("memory_briefing_links")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )

    entity_ids = sorted({
        str(row.get("entity_id") or "")
        for row in requirements
        if row.get("entity_id")
    })
    governance: list[dict[str, Any]] = []
    knowledge: list[dict[str, Any]] = []
    for start in range(0, len(entity_ids), 80):
        chunk = entity_ids[start:start + 80]
        if not chunk:
            continue
        governance.extend(_rows(
            client.table("domain_object_governance")
            .select("*")
            .in_("entity_id", chunk)
            .execute()
        ))
        knowledge.extend(_rows(
            client.table("knowledge_entities")
            .select("*")
            .in_("id", chunk)
            .execute()
        ))

    return build_hardened_dry_run(
        project_id=project_id,
        shadow=shadow,
        truth_rows=truth,
        requirement_rows=requirements,
        governance_rows=governance,
        knowledge_rows=knowledge,
        occurrence_rows=occurrences,
        evidence_rows=evidence,
        semantic_rows=semantics,
        legacy_requirement_rows=legacy_requirements,
        legacy_link_rows=legacy_links,
    )
