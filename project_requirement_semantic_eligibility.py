from __future__ import annotations

"""NAVE V28.7.3B2.12.2.1 — Requirement semantic eligibility + precedence veto.

READ ONLY.

This module does not mutate Requirement Truth. It reuses semantic decisions already
persisted by Requirement Reconciliation (C0/H3) to prevent no-domain signals from
entering response adjudication merely because an older Requirement identity still has
Evidence/Occurrence provenance.

It also derives a source-bounded canonical obligation text. A display title may be
truncated; arbitrary description/source_excerpt text is never used as the canonical
obligation. Expansion is allowed only from the semantic observation's source atom or
from the exact current Evidence Unit that produced that observation.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re
import unicodedata

SEMANTIC_ELIGIBILITY_VERSION = "V28.7.3B2.12.2.1"

ELIGIBLE_SEMANTIC_ROLES = {
    "requirement_candidate",
    "constraint_candidate",
}

NO_DOMAIN_SEMANTIC_ROLES = {
    "channel_scope",
    "platform_scope",
    "deliverable_scope",
    "product_attribute",
    "experience_attribute",
    "audience_context",
    "strategy_context",
    "form_prompt",
    "reference_signal",
    "solution_reference",
    "suggestion_signal",
    "example_signal",
    "parameter_signal",
    "constraint_qualifier",
}

NO_DOMAIN_ACTIONS = {
    "attach_scope",
    "attach_attribute",
    "preserve_context",
    "preserve_reference",
    "preserve_suggestion",
    "preserve_example",
    "attach_parameter",
    "attach_constraint_qualifier",
    "no_domain_object",
}


@dataclass(frozen=True)
class RequirementSemanticEligibility:
    project_id: str
    input_count: int
    eligible_count: int
    excluded_no_domain_count: int
    unknown_count: int
    eligible_rows: tuple[dict[str, Any], ...]
    excluded_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SEMANTIC_ELIGIBILITY_VERSION,
            "project_id": self.project_id,
            "input_count": self.input_count,
            "eligible_count": self.eligible_count,
            "excluded_no_domain_count": self.excluded_no_domain_count,
            "unknown_count": self.unknown_count,
            "eligible_rows": list(self.eligible_rows),
            "excluded_rows": list(self.excluded_rows),
        }


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9$+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _attrs(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("attributes")
    return value if isinstance(value, Mapping) else {}


def _rid(row: Mapping[str, Any]) -> str:
    return str(
        row.get("id")
        or row.get("requirement_id")
        or row.get("resolved_domain_id")
        or row.get("stable_key")
        or ""
    )


def _title(row: Mapping[str, Any]) -> str:
    for key in (
        "requirement_name",
        "canonical_name",
        "name",
        "title",
        "observed_name",
        "requirement_text",
        "statement",
        "description",
        "observed_text",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def classify_requirement_semantic_eligibility(
    row: Mapping[str, Any],
    observation: Mapping[str, Any] | None = None,
) -> tuple[bool, str, str | None]:
    """Fail closed with semantic-precedence rules.

    B2.12.2 Golden JOVI exposed a precedence bug: an eligible-looking newer
    observation could mask the Requirement Truth row's persisted H3 legacy
    explanation (for example ``platform_scope`` or ``example_signal``).
    The H3 no-domain explanation is therefore a hard veto for machine-derived
    ``verified`` rows. Only an explicit ``human_confirmed`` Requirement Truth
    may override that machine semantic veto.
    """

    obs = dict(observation or {})

    truth_state = str(
        row.get("truth_state")
        or row.get("verification_state")
        or row.get("truth_status")
        or ""
    ).casefold()

    legacy_role = str(row.get("legacy_explanation_role") or "").strip()
    legacy_status = str(row.get("legacy_explanation_status") or "").strip()
    legacy_action = str(row.get("legacy_explanation_action") or "").strip()

    legacy_no_domain = (
        legacy_role in NO_DOMAIN_SEMANTIC_ROLES
        or legacy_status == "no_domain_object"
        or legacy_action in NO_DOMAIN_ACTIONS
    )

    # Human correction is the only allowed override of an H3 machine no-domain
    # explanation. This preserves the architecture invariant that human
    # corrections can become learning signals without letting a later machine
    # observation silently resurrect a pseudo-requirement.
    if truth_state == "human_confirmed":
        role = str(obs.get("semantic_role") or legacy_role or "").strip()
        return True, "eligible_human_confirmed_override", role or None

    if legacy_no_domain:
        return False, "excluded_legacy_no_domain_veto", legacy_role or None

    role = str(obs.get("semantic_role") or legacy_role or "").strip()
    status = str(obs.get("status") or legacy_status or "").strip()
    action = str(obs.get("resolution_action") or legacy_action or "").strip()

    if role in NO_DOMAIN_SEMANTIC_ROLES or status == "no_domain_object" or action in NO_DOMAIN_ACTIONS:
        return False, "excluded_no_domain_semantic_role", role or None

    if role in ELIGIBLE_SEMANTIC_ROLES:
        return True, "eligible_explicit_requirement_role", role

    return False, "semantic_eligibility_unknown", role or None


def _source_candidates(text: str) -> list[str]:
    """Produce bounded source clauses without inventing cross-paragraph context."""
    raw = str(text or "").strip()
    if not raw:
        return []

    candidates: list[str] = []
    for line in re.split(r"[\r\n]+", raw):
        line = re.sub(r"\s+", " ", line).strip(" \t•·")
        if not line:
            continue
        candidates.append(line)
        for part in re.split(r"(?<=[.!?;])\s+", line):
            part = re.sub(r"\s+", " ", part).strip(" \t•·-")
            if part and part != line:
                candidates.append(part)

    out: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = _norm(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _prefix_token_score(title: str, candidate: str) -> float:
    t = _norm(title).split()
    c = _norm(candidate).split()
    if not t or not c:
        return 0.0

    nt = _norm(title)
    nc = _norm(candidate)
    if nt == nc:
        return 1.0
    if len(nt) >= 18 and (nt in nc or nc.startswith(nt)):
        return 0.995

    matched = 0
    for i, token in enumerate(t):
        if i >= len(c):
            break
        if token == c[i]:
            matched += 1
            continue
        if i == len(t) - 1 and len(token) >= 2 and c[i].startswith(token):
            matched += 1
        break

    prefix_coverage = matched / max(1, len(t))
    token_set_coverage = len(set(t) & set(c)) / max(1, len(set(t)))
    if prefix_coverage >= 0.85:
        return 0.94 + min(0.05, 0.05 * prefix_coverage)
    if token_set_coverage >= 0.88 and len(t) >= 8:
        return 0.90 + min(0.04, 0.04 * token_set_coverage)
    return 0.0


def derive_canonical_obligation_text(
    row: Mapping[str, Any],
    observation: Mapping[str, Any] | None = None,
    evidence_text: str | None = None,
) -> tuple[str, str, float]:
    """Return source-bounded canonical obligation text."""

    display_title = _title(row)
    obs = dict(observation or {})
    obs_attrs = _attrs(obs)

    source_atom = str(obs_attrs.get("source_atom") or "").strip()
    if source_atom:
        score = _prefix_token_score(display_title, source_atom)
        if score >= 0.90 or str(obs_attrs.get("origin_route") or "") == "evidence_first":
            return source_atom, "semantic_observation.source_atom", max(score, 0.99)

    source_text = str(
        evidence_text
        or obs_attrs.get("evidence_text")
        or ""
    ).strip()
    if source_text and display_title:
        ranked: list[tuple[float, int, str]] = []
        for clause in _source_candidates(source_text):
            score = _prefix_token_score(display_title, clause)
            if score >= 0.90:
                ranked.append((score, -len(clause), clause))
        if ranked:
            ranked.sort(reverse=True)
            score, _neg_len, clause = ranked[0]
            if len(_norm(clause)) >= len(_norm(display_title)):
                return clause, "current_evidence.source_clause", score

    return display_title, "display_title", 1.0 if display_title else 0.0


def _latest_observation_map(
    observations: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_requirement: dict[str, dict[str, Any]] = {}

    active = [
        dict(row)
        for row in observations
        if str(row.get("status") or "") != "superseded"
    ]
    active.sort(
        key=lambda row: (
            str(row.get("updated_at") or row.get("created_at") or ""),
            str(row.get("id") or ""),
        )
    )

    for obs in active:
        oid = str(obs.get("id") or "")
        if oid:
            by_id[oid] = obs
        attrs = _attrs(obs)
        keys = {
            str(obs.get("resolved_domain_id") or ""),
            str(attrs.get("requirement_id") or ""),
            str(attrs.get("legacy_requirement_id") or ""),
        }
        for key in keys:
            if key:
                by_requirement[key] = obs
    return by_id, by_requirement


def _fetch_observations(client: Any, project_id: str) -> list[dict[str, Any]]:
    return _rows(
        client.table("semantic_observations")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_hint", "requirement")
        .execute()
    )


def _fetch_evidence_map(
    client: Any,
    evidence_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    ids = list(dict.fromkeys(str(x) for x in evidence_ids if x))
    output: dict[str, dict[str, Any]] = {}
    for start in range(0, len(ids), 80):
        chunk = ids[start:start + 80]
        if not chunk:
            continue
        rows = _rows(
            client.table("evidence_units")
            .select("*")
            .in_("id", chunk)
            .execute()
        )
        for row in rows:
            if row.get("id"):
                output[str(row["id"])] = row
    return output


def resolve_requirement_semantics(
    client: Any,
    *,
    project_id: str,
    current_requirement_rows: Sequence[Mapping[str, Any]],
) -> RequirementSemanticEligibility:
    """Resolve semantic eligibility and canonical text for Current Requirement rows."""

    input_rows = [dict(row) for row in current_requirement_rows if isinstance(row, Mapping)]
    observations = _fetch_observations(client, project_id)
    by_id, by_requirement = _latest_observation_map(observations)

    selected_obs: dict[str, dict[str, Any] | None] = {}
    evidence_ids: list[str] = []

    for row in input_rows:
        rid = _rid(row)
        attrs = _attrs(row)
        source_oid = str(attrs.get("source_observation_id") or "")
        obs = by_id.get(source_oid) if source_oid else None

        if obs is None:
            for key in (rid, str(row.get("legacy_source_id") or "")):
                if key and key in by_requirement:
                    obs = by_requirement[key]
                    break

        selected_obs[rid] = obs
        eid = str(
            (obs or {}).get("evidence_unit_id")
            or row.get("legacy_explanation_evidence_id")
            or ""
        )
        if eid:
            evidence_ids.append(eid)

    evidence = _fetch_evidence_map(client, evidence_ids)

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    no_domain = 0
    unknown = 0

    for row in input_rows:
        rid = _rid(row)
        obs = selected_obs.get(rid)
        ok, reason, role = classify_requirement_semantic_eligibility(row, obs)
        eid = str(
            (obs or {}).get("evidence_unit_id")
            or row.get("legacy_explanation_evidence_id")
            or ""
        )
        evidence_text = str((evidence.get(eid) or {}).get("content_text") or "")
        canonical, canonical_source, canonical_confidence = derive_canonical_obligation_text(
            row,
            obs,
            evidence_text,
        )

        enriched = {
            **row,
            "semantic_eligibility": "eligible" if ok else "excluded",
            "semantic_eligibility_reason": reason,
            "semantic_role_current": role,
            "semantic_observation_id": (obs or {}).get("id"),
            "selected_observation_semantic_role": (obs or {}).get("semantic_role"),
            "selected_observation_status": (obs or {}).get("status"),
            "selected_observation_resolution_action": (obs or {}).get("resolution_action"),
            "legacy_explanation_role_at_gate": row.get("legacy_explanation_role"),
            "legacy_explanation_status_at_gate": row.get("legacy_explanation_status"),
            "legacy_explanation_action_at_gate": row.get("legacy_explanation_action"),
            "canonical_obligation_text": canonical,
            "canonical_obligation_source": canonical_source,
            "canonical_obligation_confidence": round(float(canonical_confidence), 4),
        }

        if ok:
            eligible.append(enriched)
        else:
            if reason == "excluded_no_domain_semantic_role":
                no_domain += 1
            else:
                unknown += 1
            excluded.append({
                "requirement_id": rid,
                "requirement_title": _title(row),
                "truth_state": row.get("truth_state") or row.get("verification_state"),
                "semantic_role_current": role,
                "semantic_observation_id": (obs or {}).get("id"),
                "selected_observation_semantic_role": (obs or {}).get("semantic_role"),
                "selected_observation_status": (obs or {}).get("status"),
                "legacy_explanation_role_at_gate": row.get("legacy_explanation_role"),
                "legacy_explanation_status_at_gate": row.get("legacy_explanation_status"),
                "legacy_explanation_action_at_gate": row.get("legacy_explanation_action"),
                "semantic_eligibility_reason": reason,
                "canonical_obligation_text": canonical,
            })

    return RequirementSemanticEligibility(
        project_id=str(project_id),
        input_count=len(input_rows),
        eligible_count=len(eligible),
        excluded_no_domain_count=no_domain,
        unknown_count=unknown,
        eligible_rows=tuple(eligible),
        excluded_rows=tuple(excluded),
    )
