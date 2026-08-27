from __future__ import annotations

"""NAVE V28.7.3B2.4.6 — Cross-Domain Residual Placement Audit.

READ ONLY / diagnostic only.

B2.4.5 proved that the retained JOVI Legacy response candidates are not covered
by Current Domain *requirements*. Before inventing new requirements or repairing
lineage, this audit asks whether those residual semantics already live in another
Current Domain object: context, solution, strategy, creative, experience or journey.

No candidate becomes Truth. No object is moved. No alias is created.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_domain_reader import read_domain
from project_requirement_compatibility import (
    compatibility_alias_maps,
    load_requirement_compatibility,
)
from project_requirement_relational_shadow import (
    build_domain_relational_shadow_snapshot,
)
from project_requirement_unified_evidence_role_shadow import (
    classify_response_evidence_role,
)

CROSS_DOMAIN_AUDIT_VERSION = "V28.7.3B2.4.6"

AUDITED_DOMAIN_KEYS = (
    "context",
    "solutions",
    "strategy",
    "creative",
    "experience",
    "journey",
)

_LABEL_KEYS = (
    "title",
    "name",
    "canonical_name",
    "label",
    "statement",
    "concept_name",
    "concept",
    "solution_name",
    "strategy_name",
    "platform_name",
    "element_name",
    "experience_name",
    "journey_name",
    "moment_name",
    "description",
    "summary",
)

_SKIP_KEY_PARTS = (
    "id",
    "created",
    "updated",
    "timestamp",
    "source_asset",
    "source_evidence",
    "evidence_unit",
    "legacy_source",
    "embedding",
    "vector",
)


@dataclass(frozen=True)
class CrossDomainResidualAudit:
    project_id: str
    status: str
    retained_residual_count: int
    domain_keys_scanned: tuple[str, ...]
    candidate_row_count: int
    strong_cross_domain_candidate_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CROSS_DOMAIN_AUDIT_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "retained_residual_count": self.retained_residual_count,
            "domain_keys_scanned": list(self.domain_keys_scanned),
            "candidate_row_count": self.candidate_row_count,
            "strong_cross_domain_candidate_count":
                self.strong_cross_domain_candidate_count,
            "detail_rows": list(self.detail_rows),
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


def _req_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        req_id = _text(row, "id", "requirement_id", "resolved_domain_id")
        if req_id:
            result[req_id] = row
    return result


def _match_index(unified: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in unified.get("briefing_matches") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        req_id = _text(row, "requirement_id")
        if req_id:
            result[req_id] = row
    return result


def _collect_semantic_strings(value: Any, *, key: str = "") -> list[str]:
    key_cf = str(key or "").casefold()
    if any(part in key_cf for part in _SKIP_KEY_PARTS):
        return []

    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (bool, int, float)):
        return []
    if isinstance(value, Mapping):
        parts: list[str] = []
        for child_key, child_value in value.items():
            parts.extend(
                _collect_semantic_strings(
                    child_value,
                    key=str(child_key),
                )
            )
        return parts
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        parts: list[str] = []
        for item in value:
            parts.extend(_collect_semantic_strings(item, key=key))
        return parts
    return []


def _object_text(row: Mapping[str, Any]) -> str:
    """Flatten semantic fields while excluding IDs/provenance plumbing."""
    preferred: list[str] = []
    used: set[str] = set()

    for key in _LABEL_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            preferred.append(value.strip())
            used.add(key)

    # Attributes frequently carry the canonical semantic detail.
    if isinstance(row.get("attributes"), Mapping):
        preferred.extend(
            _collect_semantic_strings(
                row.get("attributes"),
                key="attributes",
            )
        )
        used.add("attributes")

    for key, value in row.items():
        if key in used:
            continue
        key_cf = str(key).casefold()
        if any(part in key_cf for part in _SKIP_KEY_PARTS):
            continue
        preferred.extend(_collect_semantic_strings(value, key=str(key)))

    deduped: list[str] = []
    seen: set[str] = set()
    for part in preferred:
        normalized = " ".join(part.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return " | ".join(deduped)


def _object_label(row: Mapping[str, Any], domain_key: str) -> str:
    for key in _LABEL_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    object_type = _text(row, "_domain_object_type")
    return object_type or domain_key


def _object_id(row: Mapping[str, Any], domain_key: str, index: int) -> str:
    for key in ("id", "entity_id", "stable_key", "semantic_object_id"):
        value = row.get(key)
        if value:
            return str(value)
    return f"{domain_key}:row:{index}"


def _rank_score(
    residual_title: str,
    evidence_text: str,
    object_text: str,
) -> tuple[float, float, float, float, str]:
    from project_intelligence_unified import _match_score, _tokens

    title_score = _match_score(residual_title, object_text)
    evidence_score = _match_score(evidence_text, object_text)

    rt = _tokens(residual_title)
    ot = _tokens(object_text)
    title_overlap = (
        len(rt & ot) / max(1, min(len(rt), len(ot)))
        if rt and ot
        else 0.0
    )

    rank = max(
        title_score,
        evidence_score * 0.92,
        title_overlap * 0.94,
    )
    shared = " | ".join(sorted(rt & ot))
    return (
        rank,
        title_score,
        evidence_score,
        title_overlap,
        shared,
    )


def audit_cross_domain_residual_placement(
    *,
    project_id: str,
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_unified: Mapping[str, Any],
    compatibility: Any,
    domain_rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]],
    top_k_per_domain: int = 5,
) -> CrossDomainResidualAudit:
    legacy_idx = _req_index(legacy_requirement_rows)
    legacy_matches = _match_index(legacy_unified)
    legacy_to_domain, _ = compatibility_alias_maps(compatibility)

    residuals: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for legacy_id, match in legacy_matches.items():
        if legacy_id in legacy_to_domain:
            continue
        req = legacy_idx.get(legacy_id, {})
        role, _, _ = classify_response_evidence_role(req, match)
        if role == "retain_response_candidate":
            residuals.append((legacy_id, req, match))

    detail: list[dict[str, Any]] = []
    strong_pairs: set[tuple[str, str, str]] = set()

    for legacy_id, req, match in residuals:
        evidence = (
            match.get("evidence")
            if isinstance(match.get("evidence"), Mapping)
            else {}
        )
        evidence_text = str(evidence.get("text") or "")
        residual_title = str(req.get("title") or "")

        for domain_key in AUDITED_DOMAIN_KEYS:
            candidates: list[dict[str, Any]] = []
            for index, raw in enumerate(domain_rows_by_key.get(domain_key) or []):
                row = dict(raw)
                object_text = _object_text(row)
                if not object_text:
                    continue

                (
                    rank,
                    title_score,
                    evidence_score,
                    title_overlap,
                    shared_title_tokens,
                ) = _rank_score(
                    residual_title,
                    evidence_text,
                    object_text,
                )

                if rank <= 0:
                    continue

                candidate_id = _object_id(row, domain_key, index)
                candidate = {
                    "legacy_requirement_id": legacy_id,
                    "legacy_title": residual_title,
                    "legacy_type": req.get("requirement_type"),
                    "legacy_match_score": match.get("score"),
                    "legacy_evidence_id": evidence.get("evidence_id"),
                    "legacy_evidence_source": evidence.get("source_name"),
                    "legacy_evidence_locator": evidence.get("locator_text"),
                    "legacy_evidence_text": evidence_text,
                    "candidate_domain_key": domain_key,
                    "candidate_object_id": candidate_id,
                    "candidate_object_type":
                        row.get("_domain_object_type") or domain_key,
                    "candidate_label":
                        _object_label(row, domain_key),
                    "candidate_rank_score": round(rank, 4),
                    "candidate_title_score": round(title_score, 4),
                    "candidate_evidence_score": round(evidence_score, 4),
                    "candidate_title_overlap": round(title_overlap, 4),
                    "candidate_shared_title_tokens": shared_title_tokens,
                    "candidate_object_text": object_text[:1200],
                }
                candidates.append(candidate)

            candidates.sort(
                key=lambda row: (
                    -float(row["candidate_rank_score"]),
                    -float(row["candidate_title_score"]),
                    str(row["candidate_label"]).casefold(),
                    str(row["candidate_object_id"]),
                )
            )

            for rank_no, row in enumerate(
                candidates[: max(1, int(top_k_per_domain))],
                start=1,
            ):
                row["candidate_rank_within_domain"] = rank_no
                detail.append(row)
                if (
                    float(row["candidate_rank_score"]) >= 0.60
                    and float(row["candidate_title_score"]) >= 0.40
                ):
                    strong_pairs.add((
                        legacy_id,
                        domain_key,
                        str(row["candidate_object_id"]),
                    ))

    if not residuals:
        status = "PASS_NO_RETAINED_RESIDUALS"
    elif strong_pairs:
        status = "CROSS_DOMAIN_PLACEMENT_CANDIDATES_FOUND"
    else:
        status = "NO_STRONG_CROSS_DOMAIN_PLACEMENT"

    detail.sort(
        key=lambda row: (
            str(row.get("legacy_title") or "").casefold(),
            str(row.get("candidate_domain_key") or ""),
            int(row.get("candidate_rank_within_domain") or 999),
        )
    )

    return CrossDomainResidualAudit(
        project_id=str(project_id),
        status=status,
        retained_residual_count=len(residuals),
        domain_keys_scanned=AUDITED_DOMAIN_KEYS,
        candidate_row_count=len(detail),
        strong_cross_domain_candidate_count=len(strong_pairs),
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_cross_domain_residual_audit(
    client: Any,
    *,
    project_id: str,
) -> CrossDomainResidualAudit:
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    if not compatibility.pass_data_bridge:
        raise RuntimeError(
            "B2.4.6 BLOCKED: B2.1 compatibility is not PASS_DATA_BRIDGE."
        )

    source_snapshot = fetch_project_workspace_snapshot(
        client,
        project_id=project_id,
    )

    legacy_snapshot = dict(source_snapshot)
    legacy_snapshot.pop("unified_intelligence", None)
    legacy_unified = build_unified_project_snapshot(legacy_snapshot)

    domain_rows_by_key: dict[str, list[dict[str, Any]]] = {}
    for domain_key in AUDITED_DOMAIN_KEYS:
        result = read_domain(
            client,
            project_id,
            domain_key,
            legacy_loader=lambda: [],
            audit=False,
        )
        if result.read_mode != "shadow_compare":
            raise RuntimeError(
                f"B2.4.6 BLOCKED: {domain_key} is not shadow_compare."
            )
        domain_rows_by_key[domain_key] = [
            dict(row)
            for row in (result.domain_candidate or [])
            if isinstance(row, Mapping)
        ]

    return audit_cross_domain_residual_placement(
        project_id=project_id,
        legacy_requirement_rows=[
            dict(row)
            for row in (source_snapshot.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        legacy_unified=legacy_unified,
        compatibility=compatibility,
        domain_rows_by_key=domain_rows_by_key,
    )
