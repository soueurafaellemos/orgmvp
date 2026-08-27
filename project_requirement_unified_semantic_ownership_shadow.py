from __future__ import annotations

"""NAVE V28.7.3B2.5 — Unified Semantic Ownership & Response Evidence Shadow.

READ ONLY / shadow only.

Contract order:
1) response-evidence role;
2) governed requirement identity;
3) exact evidence provenance across Current Domain;
4) semantic candidate = review only;
5) unresolved material response remains review_required.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re

from project_domain_reader import read_domain
from project_requirement_compatibility import compatibility_alias_maps, load_requirement_compatibility
from project_requirement_cross_domain_residual_audit import _object_id, _object_label, _object_text, _rank_score
from project_requirement_relational_shadow import build_domain_relational_shadow_snapshot
from project_requirement_unified_evidence_role_shadow import classify_response_evidence_role

SEMANTIC_OWNERSHIP_VERSION = "V28.7.3B2.5"
OWNERSHIP_DOMAIN_KEYS = ("context", "solutions", "strategy", "creative", "experience", "journey")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_EVIDENCE_KEYS = ("evidence_id", "evidence_unit_id", "source_evidence", "source_evidence_id", "evidence_ids", "evidence_unit_ids")
_REVIEW_MIN_RANK = 0.60
_REVIEW_MIN_TITLE = 0.40


@dataclass(frozen=True)
class SemanticOwnershipShadowResult:
    project_id: str
    status: str
    raw_legacy_match_count: int
    raw_domain_match_count: int
    excluded_non_response_legacy_count: int
    excluded_non_response_domain_count: int
    requirement_owned_response_count: int
    cross_domain_owned_same_evidence_count: int
    cross_domain_candidate_review_count: int
    material_response_component_unowned_count: int
    material_response_unowned_count: int
    mapped_response_asymmetry_count: int
    unresolved_ownership_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {"version": SEMANTIC_OWNERSHIP_VERSION, **self.__dict__, "detail_rows": list(self.detail_rows)}


def _text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _req_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for raw in rows:
        row = dict(raw)
        rid = _text(row, "id", "requirement_id", "resolved_domain_id")
        if rid:
            out[rid] = row
    return out


def _match_index(unified: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for raw in unified.get("briefing_matches") or []:
        if isinstance(raw, Mapping) and raw.get("requirement_id"):
            out[str(raw["requirement_id"])] = dict(raw)
    return out


def _uuid_values(value: Any) -> set[str]:
    found: set[str] = set()
    if value is None:
        return found
    if isinstance(value, str):
        text = value.strip()
        if _UUID_RE.match(text):
            found.add(text.lower())
        return found
    if isinstance(value, Mapping):
        for child in value.values():
            found.update(_uuid_values(child))
        return found
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            found.update(_uuid_values(child))
    return found


def evidence_ids_from_domain_row(row: Mapping[str, Any]) -> set[str]:
    """Only explicit evidence-shaped UUIDs; generic IDs never count as provenance."""
    found: set[str] = set()
    def visit(value: Any, key: str = "") -> None:
        key_cf = key.casefold()
        if isinstance(value, Mapping):
            for k, v in value.items():
                visit(v, str(k))
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if any(marker in key_cf for marker in _EVIDENCE_KEYS):
                found.update(_uuid_values(value))
            else:
                for child in value:
                    visit(child, key)
            return
        if any(marker in key_cf for marker in _EVIDENCE_KEYS):
            found.update(_uuid_values(value))
    visit(row)
    return found


def _provenance_index(domain_rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for domain_key in OWNERSHIP_DOMAIN_KEYS:
        for pos, raw in enumerate(domain_rows_by_key.get(domain_key) or []):
            row = dict(raw)
            for evidence_id in evidence_ids_from_domain_row(row):
                index.setdefault(evidence_id, []).append({
                    "domain_key": domain_key,
                    "object_id": _object_id(row, domain_key, pos),
                    "object_label": _object_label(row, domain_key),
                    "object_type": row.get("_domain_object_type") or domain_key,
                })
    return index


def _best_review_candidate(title: str, evidence_text: str, domain_rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any] | None:
    candidates = []
    for domain_key in OWNERSHIP_DOMAIN_KEYS:
        for pos, raw in enumerate(domain_rows_by_key.get(domain_key) or []):
            row = dict(raw)
            object_text = _object_text(row)
            if not object_text:
                continue
            rank, title_score, evidence_score, title_overlap, shared = _rank_score(title, evidence_text, object_text)
            if rank >= _REVIEW_MIN_RANK and title_score >= _REVIEW_MIN_TITLE:
                candidates.append({
                    "domain_key": domain_key,
                    "object_id": _object_id(row, domain_key, pos),
                    "object_label": _object_label(row, domain_key),
                    "rank": round(rank, 4),
                    "title_score": round(title_score, 4),
                    "evidence_score": round(evidence_score, 4),
                    "title_overlap": round(title_overlap, 4),
                    "shared": shared,
                })
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x["rank"], -x["title_score"], x["domain_key"], x["object_label"].casefold()))
    return candidates[0]


def _title_explicit_in_evidence(title: str, evidence_text: str) -> bool:
    from project_intelligence_unified import _norm
    t = _norm(title).strip(" ;:,. ")
    e = _norm(evidence_text)
    if not t or not e:
        return False
    if len(t.split()) <= 4 and len(t) >= 4:
        return bool(re.search(rf"\b{re.escape(t)}\b", e))
    return t in e


def build_semantic_ownership_shadow(*, project_id: str, legacy_requirement_rows: Sequence[Mapping[str, Any]], domain_requirement_rows: Sequence[Mapping[str, Any]], legacy_unified: Mapping[str, Any], domain_unified: Mapping[str, Any], compatibility: Any, domain_rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]]) -> SemanticOwnershipShadowResult:
    legacy_idx = _req_index(legacy_requirement_rows)
    domain_idx = _req_index(domain_requirement_rows)
    legacy_matches = _match_index(legacy_unified)
    domain_matches = _match_index(domain_unified)
    legacy_to_domain, _ = compatibility_alias_maps(compatibility)
    provenance = _provenance_index(domain_rows_by_key)

    detail = []
    excluded_legacy = excluded_domain = requirement_owned = cross_owned = candidate_review = component_unowned = material_unowned = asymmetry = 0

    domain_roles: dict[str, str] = {}
    for domain_id, match in domain_matches.items():
        req = domain_idx.get(domain_id, {})
        role, flags, reason = classify_response_evidence_role(req, match)
        domain_roles[domain_id] = role
        if role != "retain_response_candidate":
            excluded_domain += 1
        ev = match.get("evidence") if isinstance(match.get("evidence"), Mapping) else {}
        detail.append({
            "side": "domain", "legacy_requirement_id": None, "legacy_title": None,
            "domain_requirement_id": domain_id, "domain_title": req.get("title"), "match_score": match.get("score"),
            "evidence_id": ev.get("evidence_id"), "evidence_locator": ev.get("locator_text"), "evidence_text": ev.get("text"),
            "response_evidence_role": role, "response_evidence_flags": " | ".join(flags),
            "contract_disposition": "domain_requirement_response_candidate" if role == "retain_response_candidate" else "domain_non_response_excluded",
            "ownership_domain": "requirements", "ownership_object_ids": domain_id, "ownership_labels": req.get("title"),
            "ownership_basis": "current_domain_requirement", "review_candidate_domain": None, "review_candidate_label": None,
            "review_candidate_score": None, "review_required": False, "reason": reason,
        })

    for legacy_id, match in legacy_matches.items():
        req = legacy_idx.get(legacy_id, {})
        role, flags, reason = classify_response_evidence_role(req, match)
        ev = match.get("evidence") if isinstance(match.get("evidence"), Mapping) else {}
        evidence_id = str(ev.get("evidence_id") or "").lower()
        evidence_text = str(ev.get("text") or "")
        title = str(req.get("title") or "")
        mapped_domain_id = legacy_to_domain.get(legacy_id)
        base = {
            "side": "legacy", "legacy_requirement_id": legacy_id, "legacy_title": title,
            "domain_requirement_id": mapped_domain_id, "domain_title": domain_idx.get(mapped_domain_id or "", {}).get("title"),
            "match_score": match.get("score"), "evidence_id": ev.get("evidence_id"), "evidence_locator": ev.get("locator_text"),
            "evidence_text": evidence_text, "response_evidence_role": role, "response_evidence_flags": " | ".join(flags),
            "review_candidate_domain": None, "review_candidate_label": None, "review_candidate_score": None, "reason": reason,
        }
        if role != "retain_response_candidate":
            excluded_legacy += 1
            detail.append({**base, "contract_disposition": "legacy_non_response_excluded", "ownership_domain": None,
                           "ownership_object_ids": None, "ownership_labels": None, "ownership_basis": "evidence_role_gate", "review_required": False})
            continue
        if mapped_domain_id:
            requirement_owned += 1
            bad = domain_roles.get(mapped_domain_id) != "retain_response_candidate"
            if bad:
                asymmetry += 1
            detail.append({**base, "contract_disposition": "mapped_requirement_response_asymmetry" if bad else "requirement_owned_response",
                           "ownership_domain": "requirements", "ownership_object_ids": mapped_domain_id,
                           "ownership_labels": domain_idx.get(mapped_domain_id, {}).get("title"), "ownership_basis": "governed_requirement_alias",
                           "review_required": bad, "reason": "mapped Domain response is not retained" if bad else "governed requirement identity + material response evidence"})
            continue
        owners = provenance.get(evidence_id, []) if evidence_id else []
        if owners:
            cross_owned += 1
            detail.append({**base, "contract_disposition": "cross_domain_owned_same_evidence",
                           "ownership_domain": " | ".join(sorted({o["domain_key"] for o in owners})),
                           "ownership_object_ids": " | ".join(str(o["object_id"]) for o in owners),
                           "ownership_labels": " | ".join(str(o["object_label"]) for o in owners),
                           "ownership_basis": "exact_source_evidence_id", "review_required": False,
                           "reason": "material proposal evidence is already owned by Current Domain outside requirements"})
            continue
        candidate = _best_review_candidate(title, evidence_text, domain_rows_by_key)
        if candidate:
            candidate_review += 1
            detail.append({**base, "contract_disposition": "cross_domain_candidate_review", "ownership_domain": None,
                           "ownership_object_ids": None, "ownership_labels": None, "ownership_basis": "semantic_candidate_not_identity",
                           "review_candidate_domain": candidate["domain_key"], "review_candidate_label": candidate["object_label"],
                           "review_candidate_score": candidate["rank"], "review_required": True,
                           "reason": "strong semantic placement candidate exists without exact evidence lineage"})
            continue
        if _title_explicit_in_evidence(title, evidence_text):
            component_unowned += 1
            detail.append({**base, "contract_disposition": "material_response_component_unowned", "ownership_domain": None,
                           "ownership_object_ids": None, "ownership_labels": None, "ownership_basis": "explicit_component_in_material_evidence",
                           "review_required": True,
                           "reason": "material response explicitly contains this semantic atom but no Current Domain owner exposes the same evidence lineage"})
            continue
        material_unowned += 1
        detail.append({**base, "contract_disposition": "material_response_unowned", "ownership_domain": None,
                       "ownership_object_ids": None, "ownership_labels": None, "ownership_basis": "none", "review_required": True,
                       "reason": "material response has no governed requirement alias or exact-evidence Current Domain owner"})

    unresolved = candidate_review + component_unowned + material_unowned
    status = "BLOCKED_MAPPED_RESPONSE_ASYMMETRY" if asymmetry else ("PASS_WITH_OWNERSHIP_REVIEW" if unresolved else "PASS_PROJECTED_SEMANTIC_OWNERSHIP")
    detail.sort(key=lambda r: (str(r.get("side") or ""), str(r.get("contract_disposition") or ""), str(r.get("legacy_title") or r.get("domain_title") or "").casefold()))
    return SemanticOwnershipShadowResult(
        project_id=str(project_id), status=status, raw_legacy_match_count=len(legacy_matches), raw_domain_match_count=len(domain_matches),
        excluded_non_response_legacy_count=excluded_legacy, excluded_non_response_domain_count=excluded_domain,
        requirement_owned_response_count=requirement_owned, cross_domain_owned_same_evidence_count=cross_owned,
        cross_domain_candidate_review_count=candidate_review, material_response_component_unowned_count=component_unowned,
        material_response_unowned_count=material_unowned, mapped_response_asymmetry_count=asymmetry,
        unresolved_ownership_count=unresolved, detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (getattr(response, "data", None) or []) if isinstance(row, Mapping)]


def run_semantic_ownership_shadow(client: Any, *, project_id: str) -> SemanticOwnershipShadowResult:
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(client, project_id=project_id)
    if not compatibility.pass_data_bridge:
        raise RuntimeError("B2.5 BLOCKED: B2.1 compatibility is not PASS_DATA_BRIDGE.")

    source_snapshot = fetch_project_workspace_snapshot(client, project_id=project_id)
    domain_requirement_rows = _rows(client.table("project_requirement_truth_status").select("*").eq("project_id", project_id).execute())
    domain_shadow = build_domain_relational_shadow_snapshot(source_snapshot, domain_requirement_rows=domain_requirement_rows, compatibility=compatibility)

    legacy_snapshot = dict(source_snapshot); legacy_snapshot.pop("unified_intelligence", None)
    domain_shadow.pop("unified_intelligence", None)
    legacy_unified = build_unified_project_snapshot(legacy_snapshot)
    domain_unified = build_unified_project_snapshot(domain_shadow)

    domain_rows_by_key: dict[str, list[dict[str, Any]]] = {}
    for domain_key in OWNERSHIP_DOMAIN_KEYS:
        result = read_domain(client, project_id, domain_key, legacy_loader=lambda: [], audit=False)
        if result.read_mode != "shadow_compare":
            raise RuntimeError(f"B2.5 BLOCKED: {domain_key} is not shadow_compare.")
        domain_rows_by_key[domain_key] = [dict(row) for row in (result.domain_candidate or []) if isinstance(row, Mapping)]

    return build_semantic_ownership_shadow(
        project_id=project_id,
        legacy_requirement_rows=[dict(r) for r in (source_snapshot.get("briefing_requirements") or []) if isinstance(r, Mapping)],
        domain_requirement_rows=[dict(r) for r in (domain_shadow.get("briefing_requirements") or []) if isinstance(r, Mapping)],
        legacy_unified=legacy_unified, domain_unified=domain_unified, compatibility=compatibility,
        domain_rows_by_key=domain_rows_by_key,
    )
