from __future__ import annotations

"""NAVE V28.7.2C0.2.4H3.1 — Cross-unit structural context repair.

READ/CLASSIFY helper used by Requirement Reconciliation before persistence.

H3.1 does not invent a new Requirement taxonomy. It reuses the H3 classifier and
only repairs a structural blind spot in the legacy-recall route: when a legacy bullet
occupies its own Evidence Unit, H3 could find the bullet in the current unit and stop
before considering the immediately preceding Evidence Units that contained its parent
section (e.g. Público-Alvo, Adequação à Plataforma, or an illustrative "como:").

The Evidence-first route already carries previous_text and is intentionally left intact.
Human-confirmed Requirement Truth is never demoted by this machine structural repair.
"""

from copy import deepcopy
from typing import Any, Mapping
import re

import project_requirement_semantic_extractor as h3

H31_VERSION = "V28.7.2C0.2.4H3.1"

_NO_DOMAIN_SECTION_MAP: dict[str, tuple[str, str]] = {
    "audience_context": ("audience_context", "context"),
    "product_attribute": ("product_attribute", "attribute"),
    "platform_scope": ("platform_scope", "scope"),
    "strategy_context": ("strategy_context", "context"),
    "example_signal": ("example_signal", "reference"),
}


def _find_title_index(lines: list[str], title: str) -> int | None:
    tnorm = h3._norm(title)
    if not tnorm:
        return None
    for idx, line in enumerate(lines):
        lnorm = h3._norm(line)
        if tnorm == lnorm or (len(tnorm) >= 4 and tnorm in lnorm):
            return idx
    return None


def _is_example_container(raw: str) -> bool:
    norm = h3._norm(raw)
    # Check punctuation on RAW text because _norm deliberately removes punctuation.
    if re.search(r"\b(?:como|por exemplo|exemplo|example)\s*:\s*$", str(raw), re.I):
        return True
    return (
        norm.endswith("ambiente dinamico como")
        or norm.endswith("dynamic environment such as")
        or norm.endswith("such as")
    )


def cross_unit_section_role(
    title: str,
    evidence_text: str,
    surrounding_text: str = "",
) -> str | None:
    """Resolve the nearest structural parent across Evidence Unit boundaries.

    Current-unit evidence always has positional priority. Previous Evidence Units are
    prepended only as backward context. This avoids H3's bug where a hit at index 0 in
    the current unit prevented any previous-unit parent from being visible.
    """

    current_lines = h3._lines(evidence_text)
    previous_lines = h3._lines(surrounding_text)
    hit_current = _find_title_index(current_lines, title)

    lines = previous_lines + current_lines
    if hit_current is not None:
        hit = len(previous_lines) + hit_current
    else:
        hit = _find_title_index(lines, title)

    if hit is None:
        return None

    # If the current line itself embeds the structural parent plus the nominal child,
    # honor that same-line structure before walking backward.
    hit_raw = lines[hit].strip() if 0 <= hit < len(lines) else ""
    hit_norm = h3._norm(hit_raw)
    if "publico alvo" in hit_norm or "target audience" in hit_norm:
        return "audience_context"
    if h3.PRODUCT_TARGET_PARENT_RE.search(hit_raw) or any(
        marker in hit_norm
        for marker in (
            "foco do produto", "product focus", "destaques",
            "evidenciando", "product highlights",
        )
    ):
        return "product_attribute"
    if (
        "adequacao a plataforma" in hit_norm
        or "platform fit" in hit_norm
        or "platform adequacy" in hit_norm
    ):
        return "platform_scope"
    if _is_example_container(hit_raw):
        return "example_signal"

    # Same H3 structural vocabulary, but now with true cross-unit backward context.
    # The lookback is deliberately wider than H3's old 24-line search because a parent
    # may precede a list with many sibling Evidence Units. A nearer compact heading
    # still stops inheritance, so widening recall does not remove the structural brake.
    for j in range(hit - 1, max(-1, hit - 64), -1):
        raw = lines[j].strip()
        norm = h3._norm(raw)
        if not norm:
            continue

        if "publico alvo" in norm or "target audience" in norm:
            return "audience_context"

        if h3.PRODUCT_TARGET_PARENT_RE.search(raw) or any(
            marker in norm
            for marker in (
                "foco do produto",
                "product focus",
                "destaques",
                "evidenciando",
                "product highlights",
            )
        ):
            return "product_attribute"

        if (
            "adequacao a plataforma" in norm
            or "platform fit" in norm
            or "platform adequacy" in norm
        ):
            return "platform_scope"

        if _is_example_container(raw):
            return "example_signal"

        # A mandatory parent can require alignment TO an audience while its nominal
        # children remain audience descriptors.
        if raw.endswith(":") and h3._direct_obligation(raw) and (
            "publico alvo" in norm or "target audience" in norm
        ):
            return "audience_context"

        if any(
            marker in norm
            for marker in (
                "alinhamento estrategico",
                "objetivos estrategicos",
                "strategic objectives",
                "strategic alignment",
            )
        ):
            recent = " ".join(h3._norm(x) for x in lines[max(0, j):hit])
            if "publico alvo" in recent or "target audience" in recent:
                return "audience_context"
            return "strategy_context"

        if raw.endswith(":") and h3._direct_obligation(raw):
            if _is_example_container(raw):
                return "example_signal"
            return "requirement_parent"

        # Stop inheritance when a newer compact section heading sits between the old
        # structural parent and the current bullet.
        if raw.endswith(":") and len(norm.split()) <= 9 and j < hit - 1:
            break

    return None



def _surrounding_by_evidence_h31(
    source: Mapping[str, Any],
    asset_ids: set[str],
    *,
    max_previous_units: int = 32,
    max_chars: int = 20000,
) -> dict[str, str]:
    """Build a bounded cross-unit context window wider than H3's legacy 3 units.

    The H3 false-green surfaced precisely on fourth/fifth children of a structural
    container: a three-unit window could never see their parent. H3.1 stays within the
    same source asset, preserves ordinal order, and lets ``cross_unit_section_role``
    stop at nearer section headings.
    """
    out: dict[str, str] = {}
    for aid in asset_ids:
        rows = [
            dict(r)
            for r in (source.get("evidence_by_asset") or {}).get(aid, [])
            if r.get("id") and r.get("is_current") is True
        ]
        rows.sort(key=lambda r: (int(r.get("ordinal") or 0), str(r.get("id") or "")))
        for idx, row in enumerate(rows):
            start = max(0, idx - max_previous_units)
            parts = [str(rows[j].get("content_text") or "") for j in range(start, idx)]
            out[str(row["id"])] = "\n".join(parts)[-max_chars:]
    return out

def _human_confirmed_requirement_ids(client: Any, project_id: str) -> set[str]:
    # Fail closed: if H3.1 cannot inspect human corrections, it must not risk
    # demoting a human-confirmed Requirement with a machine structural rule.
    try:
        rows = h3._read_rows(
            client,
            "project_requirement_truth_status",
            equals={"project_id": project_id},
        )
    except Exception as exc:
        raise RuntimeError(
            "H3.1 BLOCKED: não foi possível verificar human_confirmed Requirement Truth."
        ) from exc
    out: set[str] = set()
    for row in rows:
        if str(row.get("truth_state") or "") != "human_confirmed":
            continue
        rid = str(row.get("id") or row.get("requirement_id") or "")
        if rid:
            out.add(rid)
    return out


def collect_project_requirement_observations_h31(
    client: Any,
    project_id: str,
) -> dict[str, Any]:
    """Run H3 collection, then repair only cross-unit legacy structural semantics.

    This is deliberately conservative:
    - Evidence-first observations are not reclassified;
    - explicit obligations are not demoted;
    - human-confirmed Requirement Truth is not demoted;
    - if cross-unit context does not yield a known semantic parent, H3 is preserved.
    """

    extraction = deepcopy(h3.collect_project_requirement_observations(client, project_id))
    observations = [dict(row) for row in (extraction.get("observations") or [])]
    diagnostics = [dict(row) for row in (extraction.get("diagnostics") or [])]

    source = h3._project_evidence(client, project_id)
    requirements = h3._read_rows(
        client,
        "project_requirements",
        equals={"project_id": project_id},
    )
    requirement_by_id = {
        str(row.get("id")): dict(row)
        for row in requirements
        if row.get("id")
    }
    human_confirmed = _human_confirmed_requirement_ids(client, project_id)
    briefing_assets = h3._briefing_asset_ids(client, project_id, source)
    surrounding = _surrounding_by_evidence_h31(source, briefing_assets)
    evidence_by_id = {
        str(row.get("id")): dict(row)
        for row in (source.get("evidence") or [])
        if row.get("id")
    }

    overrides = 0
    overridden_ids: set[str] = set()

    for obs in observations:
        attrs = dict(obs.get("attributes") or {})
        attrs["normalized_by"] = H31_VERSION
        obs["attributes"] = attrs

        if str(attrs.get("origin_route") or "") != "legacy_recall":
            continue

        rid = str(attrs.get("requirement_id") or "")
        if not rid or rid in human_confirmed:
            if rid in human_confirmed:
                attrs["h31_structural_context"] = "human_confirmed_override_preserved"
            continue

        req = requirement_by_id.get(rid) or {}
        title = str(req.get("title") or obs.get("observed_name") or "").strip()
        if not title or h3._direct_obligation(title):
            continue

        evidence_id = str(obs.get("evidence_unit_id") or "")
        evidence = evidence_by_id.get(evidence_id) or {}
        current_text = str(
            evidence.get("content_text")
            or attrs.get("evidence_text")
            or ""
        )
        role = cross_unit_section_role(
            title,
            current_text,
            surrounding.get(evidence_id, ""),
        )
        if role not in _NO_DOMAIN_SECTION_MAP:
            continue

        semantic_role, occurrence_role = _NO_DOMAIN_SECTION_MAP[role]
        previous_role = str(obs.get("semantic_role") or "")
        obs["semantic_role"] = semantic_role
        obs["occurrence_role"] = "reference"
        attrs["h31_structural_context"] = "cross_unit_parent"
        attrs["h31_structural_role"] = role
        attrs["h31_previous_semantic_role"] = previous_role or None
        attrs["h31_surrounding_context_used"] = True

        if previous_role != semantic_role:
            overrides += 1
            overridden_ids.add(rid)

    for row in diagnostics:
        rid = str(row.get("requirement_id") or "")
        if rid not in overridden_ids:
            continue
        obs = next(
            (
                item
                for item in observations
                if str((item.get("attributes") or {}).get("requirement_id") or "") == rid
                and str((item.get("attributes") or {}).get("origin_route") or "") == "legacy_recall"
            ),
            None,
        )
        if obs:
            row["classification"] = obs.get("semantic_role")
            row["h31_structural_context"] = "cross_unit_parent"

    summary = dict(extraction.get("summary") or {})
    summary.update({
        "semantic_extractor_version": H31_VERSION,
        "h31_cross_unit_structural_overrides": overrides,
        "h31_human_confirmed_preserved": len(human_confirmed),
    })

    extraction["observations"] = observations
    extraction["diagnostics"] = diagnostics
    extraction["summary"] = summary
    extraction["version"] = H31_VERSION
    return extraction
