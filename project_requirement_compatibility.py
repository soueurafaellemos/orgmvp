from __future__ import annotations

"""NAVE V28.7.3B2.1 — Requirement Identity Compatibility Layer (shadow only).

This module translates Legacy requirement identities used by historical/operational
links into Current Domain requirement identities using only governed structural
bridges already present in the database.

No lexical matching. No writes. No Truth/readiness/read_mode changes.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


COMPATIBILITY_VERSION = "V28.7.3B2.1"
CURRENT_TRUTH_STATES = {"verified", "human_confirmed"}
ACTIVE_LINK_STATUSES = {"suggested", "confirmed", "approved", "active"}


class RequirementCompatibilityBlocked(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class RequirementIdentity:
    domain_requirement_id: str
    domain_entity_id: str | None
    title: str
    requirement_type: str | None
    mandatory: bool | None
    priority: str | None
    truth_state: str
    legacy_aliases: tuple[str, ...]
    bridge_sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_requirement_id": self.domain_requirement_id,
            "domain_entity_id": self.domain_entity_id,
            "title": self.title,
            "requirement_type": self.requirement_type,
            "mandatory": self.mandatory,
            "priority": self.priority,
            "truth_state": self.truth_state,
            "legacy_aliases": list(self.legacy_aliases),
            "bridge_sources": list(self.bridge_sources),
        }


@dataclass(frozen=True)
class CompatibleRequirementLink:
    legacy_link_id: str
    legacy_requirement_id: str
    domain_requirement_id: str
    memory_item_id: str | None
    link_status: str
    adherence_status: str | None
    evidence: str | None
    notes: str | None
    bridge_sources: tuple[str, ...]
    mapping_status: str = "PASS_UNIQUE_CURRENT_DOMAIN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "legacy_link_id": self.legacy_link_id,
            "legacy_requirement_id": self.legacy_requirement_id,
            "domain_requirement_id": self.domain_requirement_id,
            "memory_item_id": self.memory_item_id,
            "link_status": self.link_status,
            "adherence_status": self.adherence_status,
            "evidence": self.evidence,
            "notes": self.notes,
            "bridge_sources": list(self.bridge_sources),
            "mapping_status": self.mapping_status,
        }


@dataclass(frozen=True)
class RequirementCompatibilityReport:
    project_id: str
    current_domain_count: int
    legacy_requirement_count: int
    active_link_count: int
    resolved_active_link_count: int
    active_links_unmapped: int
    active_links_ambiguous: int
    domain_without_legacy_alias_count: int
    identities: tuple[RequirementIdentity, ...]
    links: tuple[CompatibleRequirementLink, ...]
    legacy_unmapped_ids: tuple[str, ...]
    legacy_ambiguous_ids: tuple[str, ...]

    @property
    def pass_data_bridge(self) -> bool:
        return (
            self.active_link_count == self.resolved_active_link_count
            and self.active_links_unmapped == 0
            and self.active_links_ambiguous == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": COMPATIBILITY_VERSION,
            "project_id": self.project_id,
            "status": "PASS_DATA_BRIDGE" if self.pass_data_bridge else "BLOCKED",
            "current_domain_count": self.current_domain_count,
            "legacy_requirement_count": self.legacy_requirement_count,
            "active_link_count": self.active_link_count,
            "resolved_active_link_count": self.resolved_active_link_count,
            "active_links_unmapped": self.active_links_unmapped,
            "active_links_ambiguous": self.active_links_ambiguous,
            "domain_without_legacy_alias_count": self.domain_without_legacy_alias_count,
            "identities": [row.to_dict() for row in self.identities],
            "links": [row.to_dict() for row in self.links],
            "legacy_unmapped_ids": list(self.legacy_unmapped_ids),
            "legacy_ambiguous_ids": list(self.legacy_ambiguous_ids),
        }


def _text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip().casefold()
    if text in {"true", "t", "1", "yes", "sim"}:
        return True
    if text in {"false", "f", "0", "no", "nao", "não"}:
        return False
    return None


def _active_link(row: Mapping[str, Any]) -> bool:
    status = (_text(row, "link_status") or "suggested").casefold()
    return status != "rejected"


def build_requirement_compatibility_from_rows(
    *,
    project_id: str,
    current_domain_rows: Sequence[Mapping[str, Any]],
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    occurrence_rows: Sequence[Mapping[str, Any]],
    legacy_link_rows: Sequence[Mapping[str, Any]],
) -> RequirementCompatibilityReport:
    """Build the compatibility graph from already-fetched rows.

    Only two structural bridges are legal:
      1. Current Domain legacy_source_id
      2. active project_requirement_occurrences legacy_requirement_id -> requirement_id
    """
    current: dict[str, Mapping[str, Any]] = {}
    for row in current_domain_rows:
        truth = (_text(row, "truth_state", "verification_state") or "").casefold()
        domain_id = _text(row, "id", "requirement_id", "resolved_domain_id")
        if not domain_id or truth not in CURRENT_TRUTH_STATES:
            continue
        current[domain_id] = row

    legacy: dict[str, Mapping[str, Any]] = {
        legacy_id: row
        for row in legacy_requirement_rows
        if (legacy_id := _text(row, "id"))
    }

    candidates: dict[str, dict[str, set[str]]] = {}

    def add_edge(legacy_id: str | None, domain_id: str | None, source: str) -> None:
        if not legacy_id or not domain_id or domain_id not in current:
            return
        candidates.setdefault(legacy_id, {}).setdefault(domain_id, set()).add(source)

    for domain_id, row in current.items():
        add_edge(_text(row, "legacy_source_id"), domain_id, "legacy_source_id")

    for row in occurrence_rows:
        lifecycle = (_text(row, "lifecycle_status") or "active").casefold()
        if lifecycle != "active":
            continue
        add_edge(
            _text(row, "legacy_requirement_id"),
            _text(row, "requirement_id"),
            "requirement_occurrence",
        )

    identities: list[RequirementIdentity] = []
    for domain_id, row in current.items():
        aliases: list[str] = []
        sources: set[str] = set()
        for legacy_id, domain_map in candidates.items():
            if domain_id in domain_map:
                aliases.append(legacy_id)
                sources.update(domain_map[domain_id])
        identities.append(
            RequirementIdentity(
                domain_requirement_id=domain_id,
                domain_entity_id=_text(row, "entity_id"),
                title=_text(
                    row,
                    "title",
                    "requirement_name",
                    "canonical_name",
                    "description",
                ) or "Demanda",
                requirement_type=_text(row, "requirement_type", "semantic_role"),
                mandatory=_bool_or_none(row.get("mandatory", row.get("is_mandatory"))),
                priority=_text(row, "priority"),
                truth_state=(_text(row, "truth_state", "verification_state") or "").casefold(),
                legacy_aliases=tuple(sorted(set(aliases))),
                bridge_sources=tuple(sorted(sources)),
            )
        )

    compatible_links: list[CompatibleRequirementLink] = []
    active_links_unmapped = 0
    active_links_ambiguous = 0

    for row in legacy_link_rows:
        if not _active_link(row):
            continue

        legacy_id = _text(row, "requirement_id")
        link_id = _text(row, "id")
        if not legacy_id or not link_id:
            active_links_unmapped += 1
            continue

        domain_map = candidates.get(legacy_id, {})
        domain_ids = sorted(domain_map)
        if len(domain_ids) == 0:
            active_links_unmapped += 1
            continue
        if len(domain_ids) > 1:
            active_links_ambiguous += 1
            continue

        domain_id = domain_ids[0]
        if domain_id not in current:
            active_links_unmapped += 1
            continue

        compatible_links.append(
            CompatibleRequirementLink(
                legacy_link_id=link_id,
                legacy_requirement_id=legacy_id,
                domain_requirement_id=domain_id,
                memory_item_id=_text(row, "memory_item_id"),
                link_status=_text(row, "link_status") or "suggested",
                adherence_status=_text(row, "adherence_status"),
                evidence=_text(row, "evidence", "adherence_evidence"),
                notes=_text(row, "notes", "adherence_notes"),
                bridge_sources=tuple(sorted(domain_map[domain_id])),
            )
        )

    legacy_unmapped = sorted(
        legacy_id for legacy_id in legacy
        if len(candidates.get(legacy_id, {})) == 0
    )
    legacy_ambiguous = sorted(
        legacy_id for legacy_id in legacy
        if len(candidates.get(legacy_id, {})) > 1
    )
    domain_without_alias = sum(
        1 for identity in identities if not identity.legacy_aliases
    )
    active_link_count = sum(1 for row in legacy_link_rows if _active_link(row))

    return RequirementCompatibilityReport(
        project_id=str(project_id),
        current_domain_count=len(current),
        legacy_requirement_count=len(legacy),
        active_link_count=active_link_count,
        resolved_active_link_count=len(compatible_links),
        active_links_unmapped=active_links_unmapped,
        active_links_ambiguous=active_links_ambiguous,
        domain_without_legacy_alias_count=domain_without_alias,
        identities=tuple(sorted(identities, key=lambda row: (row.title.casefold(), row.domain_requirement_id))),
        links=tuple(sorted(compatible_links, key=lambda row: row.legacy_link_id)),
        legacy_unmapped_ids=tuple(legacy_unmapped),
        legacy_ambiguous_ids=tuple(legacy_ambiguous),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (getattr(response, "data", None) or []) if isinstance(row, Mapping)]


def load_requirement_compatibility(client: Any, *, project_id: str) -> RequirementCompatibilityReport:
    """Read real tables and build the shadow compatibility report."""
    current = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    legacy_requirements = _rows(
        client.table("memory_briefing_requirements")
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
    links = _rows(
        client.table("memory_briefing_links")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    return build_requirement_compatibility_from_rows(
        project_id=project_id,
        current_domain_rows=current,
        legacy_requirement_rows=legacy_requirements,
        occurrence_rows=occurrences,
        legacy_link_rows=links,
    )


def compatibility_alias_maps(
    report: RequirementCompatibilityReport,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Return deterministic alias maps for future consumers.

    legacy_to_domain is emitted only for 1:1 resolvable Legacy requirements.
    domain_to_legacy preserves zero/one/many historical aliases.
    """
    legacy_to_domain: dict[str, str] = {}
    domain_to_legacy: dict[str, tuple[str, ...]] = {}

    for identity in report.identities:
        domain_to_legacy[identity.domain_requirement_id] = identity.legacy_aliases
        for legacy_id in identity.legacy_aliases:
            previous = legacy_to_domain.get(legacy_id)
            if previous and previous != identity.domain_requirement_id:
                raise RequirementCompatibilityBlocked(
                    "AMBIGUOUS_LEGACY_REQUIREMENT_ALIAS",
                    f"{legacy_id}: {previous} vs {identity.domain_requirement_id}",
                )
            legacy_to_domain[legacy_id] = identity.domain_requirement_id

    return legacy_to_domain, domain_to_legacy


def shadow_compatible_snapshot(
    snapshot: Mapping[str, Any],
    report: RequirementCompatibilityReport,
) -> dict[str, Any]:
    """Decorate a copied snapshot without replacing any production Legacy field."""
    legacy_to_domain, domain_to_legacy = compatibility_alias_maps(report)
    result = dict(snapshot)
    result["requirement_compatibility"] = {
        "version": COMPATIBILITY_VERSION,
        "status": "PASS_DATA_BRIDGE" if report.pass_data_bridge else "BLOCKED",
        "legacy_to_domain": dict(legacy_to_domain),
        "domain_to_legacy": {
            key: list(value) for key, value in domain_to_legacy.items()
        },
        "active_links": [link.to_dict() for link in report.links],
        "metrics": {
            "current_domain_count": report.current_domain_count,
            "legacy_requirement_count": report.legacy_requirement_count,
            "active_link_count": report.active_link_count,
            "resolved_active_link_count": report.resolved_active_link_count,
            "active_links_unmapped": report.active_links_unmapped,
            "active_links_ambiguous": report.active_links_ambiguous,
            "domain_without_legacy_alias_count": report.domain_without_legacy_alias_count,
        },
    }
    return result
