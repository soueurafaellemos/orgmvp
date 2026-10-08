from __future__ import annotations

"""NAVE V28.7.3B2.15.2.1 — Contract-Verified Response Truth Projection Shadow.

READ ONLY / DRY RUN.

Projects the B2.14 `eligible_contract_verified` rows into deterministic, immutable
Response Truth event/evidence plans compatible with the B2.15.1 ledger schema.

Nothing is written.

Governance:
- only governed B2.7.1 `verified_response` rows may enter this projection;
- machine recommendations are never Truth;
- human-confirmation candidates are explicitly excluded;
- the ledger must still be empty at this checkpoint;
- Requirement identities must still be Current and map to the exact entity id;
- every projected evidence id must exist as an Evidence Unit.
"""

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from project_requirement_auto_adjudication_completeness import (
    run_semantic_hardened_adjudication as run_b21222,
)
from project_requirement_response_truth_eligibility_shadow import (
    ELIGIBLE_CONTRACT,
    ELIGIBLE_HUMAN,
    run_response_truth_eligibility_shadow,
)

VERSION = "V28.7.3B2.15.2.1"
ELIGIBILITY_VERSION = "V28.7.3B2.14"
SOURCE_PROJECTION_VERSION = "V28.7.3B2.12.2.2"
SOURCE_CONTRACT_VERSION = "V28.7.3B2.7.1"

CHAMBINHO = "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136"
JOVI = "01415104-72f2-4b8e-aeca-2dd24c231a7d"

PROJECTS = {
    CHAMBINHO: "Festivalzinho Chambinho",
    JOVI: "Lançamento Jovi X300",
}

GOLDEN_EXPECTATIONS = {
    CHAMBINHO: {
        "current_requirement_count": 13,
        "contract_requirement_ids": {
            "cf0516d7-4cf4-49c2-94dd-858dd3ab907c",
            "40433db9-3b46-4d68-9add-18eb5d479ef8",
            "be3b3716-95bc-4689-b646-95cfe872988c",
        },
        "human_candidate_ids": {
            "bdbee458-8ba1-45c7-b871-60a604a2971a",
        },
        "evidence_by_requirement": {
            "cf0516d7-4cf4-49c2-94dd-858dd3ab907c": {
                "884f4586-c46a-4624-9fa5-c89f63fc1f2e",
            },
            "40433db9-3b46-4d68-9add-18eb5d479ef8": {
                "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
            },
            "be3b3716-95bc-4689-b646-95cfe872988c": {
                "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
            },
        },
    },
    JOVI: {
        "current_requirement_count": 69,
        "contract_requirement_ids": set(),
        "human_candidate_ids": {
            "6edad615-e726-5cd4-8db1-0d7bbbbcf610",
        },
        "evidence_by_requirement": {},
    },
}


def project_options() -> list[dict[str, str]]:
    return [
        {"project_id": project_id, "label": label}
        for project_id, label in PROJECTS.items()
    ]


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _current_requirement_truth_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return only governed Current Requirement Truth rows.

    `project_requirement_truth_status` intentionally exposes historical/non-Current
    Requirement identities as well. B2.15.2 must compare against the Current
    denominator, not the raw view cardinality.
    """
    return [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("lifecycle_status") or "") == "active"
        and str(row.get("truth_state") or "") in {"verified", "human_confirmed"}
    ]


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): _canonical(v)
            for k, v in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, set):
        return sorted(_canonical(v) for v in value)
    return value


def _sha256_json(value: Any) -> str:
    raw = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def _evidence_text_hash(evidence: Mapping[str, Any]) -> str:
    return sha256(
        str(evidence.get("evidence_text") or "").encode("utf-8")
    ).hexdigest()


def _build_event_plan(
    *,
    project_id: str,
    projection_row: Mapping[str, Any],
    truth_row: Mapping[str, Any],
) -> dict[str, Any]:
    requirement_id = str(projection_row.get("requirement_id") or "")
    entity_id = str(truth_row.get("entity_id") or "")

    raw_evidence = [
        dict(item)
        for item in (projection_row.get("current_response_evidence") or [])
        if isinstance(item, Mapping)
    ]

    evidence_links = []
    for item in sorted(
        raw_evidence,
        key=lambda row: (
            str(row.get("evidence_id") or ""),
            str(row.get("entailment_status") or ""),
        ),
    ):
        evidence_unit_id = str(item.get("evidence_id") or "")
        evidence_snapshot = {
            "source_contract_version": SOURCE_CONTRACT_VERSION,
            "evidence_locator": item.get("evidence_locator"),
            "evidence_text": item.get("evidence_text"),
            "evidence_text_sha256": _evidence_text_hash(item),
        }
        evidence_links.append({
            "evidence_unit_id": evidence_unit_id,
            "evidence_role": "supports",
            "entailment_status": item.get("entailment_status"),
            "verdict": item.get("verdict"),
            "evidence_snapshot": evidence_snapshot,
        })

    signature_payload = {
        "signature_schema": "nave_response_truth_event_v1",
        "project_id": project_id,
        "requirement_id": requirement_id,
        "requirement_entity_id": entity_id,
        "event_action": "assertion",
        "truth_state": "verified_response",
        "provenance_type": "governed_response_contract",
        "actor_type": "system_contract",
        "source_contract_version": SOURCE_CONTRACT_VERSION,
        "evidence": [
            {
                "evidence_unit_id": row["evidence_unit_id"],
                "evidence_role": row["evidence_role"],
                "entailment_status": row["entailment_status"],
                "verdict": row["verdict"],
                "evidence_locator": row["evidence_snapshot"]["evidence_locator"],
                "evidence_text_sha256": row["evidence_snapshot"]["evidence_text_sha256"],
            }
            for row in evidence_links
        ],
    }
    event_signature = _sha256_json(signature_payload)
    projected_event_id = str(
        uuid5(NAMESPACE_URL, f"nave:response-truth:{event_signature}")
    )

    return {
        "projected_event_id": projected_event_id,
        "event_signature": event_signature,
        "event_action": "assertion",
        "project_id": project_id,
        "requirement_id": requirement_id,
        "requirement_entity_id": entity_id,
        "truth_state": "verified_response",
        "provenance_type": "governed_response_contract",
        "actor_type": "system_contract",
        "actor_id": None,
        "human_review_id": None,
        "source_run_id_policy": "writer_transaction_run_id",
        "source_contract_version": SOURCE_CONTRACT_VERSION,
        "source_projection_version": VERSION,
        "source_adjudication_version": None,
        "source_candidate_id": None,
        "supersedes_event_id": None,
        "reason": (
            "Governed B2.7.1 response contract is already verified with explicit "
            "supported Evidence; B2.15.2 projects the immutable ledger event only."
        ),
        "provenance_snapshot": {
            "version": VERSION,
            "eligibility_version": ELIGIBILITY_VERSION,
            "source_projection_version": SOURCE_PROJECTION_VERSION,
            "source_contract_version": SOURCE_CONTRACT_VERSION,
            "requirement_title": projection_row.get("title"),
            "canonical_obligation_text": projection_row.get(
                "canonical_obligation_text"
            ),
            "canonical_obligation_source": projection_row.get(
                "canonical_obligation_source"
            ),
            "canonical_obligation_confidence": projection_row.get(
                "canonical_obligation_confidence"
            ),
            "requirement_truth_state": truth_row.get("truth_state"),
            "requirement_lifecycle_status": truth_row.get("lifecycle_status"),
            "current_response_contract_status": projection_row.get(
                "current_response_contract_status"
            ),
            "projected_response_status": projection_row.get(
                "projected_response_status"
            ),
            "review_origin": projection_row.get("review_origin"),
            "evidence_count": len(evidence_links),
        },
        "evidence_links": evidence_links,
    }


def build_response_truth_ledger_projection_shadow(
    *,
    project_id: str,
    eligibility: Mapping[str, Any],
    source_projection: Mapping[str, Any],
    requirement_truth_rows: Sequence[Mapping[str, Any]],
    evidence_unit_rows: Sequence[Mapping[str, Any]],
    ledger_state: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(project_id or "")
    expected = GOLDEN_EXPECTATIONS.get(project_id)
    if expected is None:
        raise ValueError(f"B2.15.2 unsupported Golden project: {project_id}")

    projection_rows = [
        dict(row)
        for row in (source_projection.get("projection_rows") or [])
        if isinstance(row, Mapping)
    ]
    projection_by_id = {
        str(row.get("requirement_id") or ""): row
        for row in projection_rows
        if row.get("requirement_id")
    }

    eligibility_rows = [
        dict(row)
        for row in (eligibility.get("eligibility_rows") or [])
        if isinstance(row, Mapping)
    ]
    contract_rows = [
        row
        for row in eligibility_rows
        if row.get("eligibility_class") == ELIGIBLE_CONTRACT
    ]
    human_rows = [
        row
        for row in eligibility_rows
        if row.get("eligibility_class") == ELIGIBLE_HUMAN
    ]

    contract_ids = {
        str(row.get("requirement_id") or "")
        for row in contract_rows
        if row.get("requirement_id")
    }
    human_ids = {
        str(row.get("requirement_id") or "")
        for row in human_rows
        if row.get("requirement_id")
    }

    truth_rows = [
        dict(row)
        for row in requirement_truth_rows
        if isinstance(row, Mapping)
    ]
    truth_by_id = {
        str(row.get("id") or ""): row
        for row in truth_rows
        if row.get("id")
    }

    evidence_units = [
        dict(row)
        for row in evidence_unit_rows
        if isinstance(row, Mapping)
    ]
    evidence_unit_ids = {
        str(row.get("id") or "")
        for row in evidence_units
        if row.get("id")
    }

    event_plans: list[dict[str, Any]] = []
    missing_truth_rows: list[str] = []
    invalid_contract_rows: list[str] = []
    missing_evidence_units: set[str] = set()
    evidence_mismatches: list[dict[str, Any]] = []

    for rid in sorted(contract_ids):
        projection_row = projection_by_id.get(rid)
        truth_row = truth_by_id.get(rid)

        if projection_row is None or truth_row is None:
            if truth_row is None:
                missing_truth_rows.append(rid)
            invalid_contract_rows.append(rid)
            continue

        evidence = [
            dict(item)
            for item in (projection_row.get("current_response_evidence") or [])
            if isinstance(item, Mapping)
        ]
        actual_evidence_ids = {
            str(item.get("evidence_id") or "")
            for item in evidence
            if item.get("evidence_id")
        }
        expected_evidence_ids = set(
            expected["evidence_by_requirement"].get(rid, set())
        )

        if actual_evidence_ids != expected_evidence_ids:
            evidence_mismatches.append({
                "requirement_id": rid,
                "expected_evidence_ids": sorted(expected_evidence_ids),
                "actual_evidence_ids": sorted(actual_evidence_ids),
            })

        missing_evidence_units.update(actual_evidence_ids - evidence_unit_ids)

        row_ok = all([
            str(projection_row.get("current_response_contract_status") or "")
                == "verified_response",
            str(projection_row.get("projected_response_status") or "")
                == "verified_response",
            str(projection_row.get("review_origin") or "") == "current_contract",
            str(truth_row.get("truth_state") or "")
                in {"verified", "human_confirmed"},
            str(truth_row.get("lifecycle_status") or "") == "active",
            str(truth_row.get("entity_id") or "") != "",
            bool(evidence),
            all(
                str(item.get("verdict") or "") == "verified_response"
                and str(item.get("entailment_status") or "").startswith("SUPPORTED_")
                and bool(item.get("evidence_id"))
                for item in evidence
            ),
        ])
        if not row_ok:
            invalid_contract_rows.append(rid)
            continue

        event_plans.append(
            _build_event_plan(
                project_id=project_id,
                projection_row=projection_row,
                truth_row=truth_row,
            )
        )

    truth_status_rows = [
        dict(row)
        for row in (ledger_state.get("truth_status_rows") or [])
        if isinstance(row, Mapping)
    ]

    expected_contract_ids = set(expected["contract_requirement_ids"])
    expected_human_ids = set(expected["human_candidate_ids"])
    expected_current_count = int(expected["current_requirement_count"])

    event_signatures = [row["event_signature"] for row in event_plans]
    projected_event_ids = [row["projected_event_id"] for row in event_plans]
    projected_evidence_links = sum(
        len(row.get("evidence_links") or [])
        for row in event_plans
    )

    checks = {
        "eligibility_version_is_b214": (
            str(eligibility.get("version") or "") == ELIGIBILITY_VERSION
        ),
        "eligibility_passed": (
            eligibility.get("status") == "PASS_RESPONSE_TRUTH_ELIGIBILITY_SHADOW"
            and eligibility.get("all_checks_pass") is True
        ),
        "source_projection_version_is_b21222": (
            str(source_projection.get("version") or "")
            == SOURCE_PROJECTION_VERSION
        ),
        "project_matches_everywhere": all([
            str(eligibility.get("project_id") or "") == project_id,
            str(source_projection.get("project_id") or "") == project_id,
        ]),
        "requirement_truth_rows_are_current_only": all(
            str(row.get("lifecycle_status") or "") == "active"
            and str(row.get("truth_state") or "") in {"verified", "human_confirmed"}
            for row in truth_rows
        ),
        "current_requirement_count_matches_golden": (
            int(eligibility.get("current_requirement_count") or 0)
            == expected_current_count
            == len(truth_rows)
            == len(truth_status_rows)
        ),
        "contract_eligible_identity_set_matches_golden": (
            contract_ids == expected_contract_ids
        ),
        "human_candidate_identity_set_matches_golden": (
            human_ids == expected_human_ids
        ),
        "no_human_candidate_projected_to_truth": not bool(
            {row["requirement_id"] for row in event_plans} & human_ids
        ),
        "machine_recommendation_still_not_truth": (
            eligibility.get("machine_recommendation_is_truth") is False
        ),
        "eligibility_blocked_count_zero": int(
            eligibility.get("blocked_count") or 0
        ) == 0,
        "ledger_events_empty_before_projection": int(
            ledger_state.get("events_count") or 0
        ) == 0,
        "ledger_evidence_empty_before_projection": int(
            ledger_state.get("evidence_count") or 0
        ) == 0,
        "current_truth_empty_before_projection": int(
            ledger_state.get("current_truth_count") or 0
        ) == 0,
        "all_current_status_rows_have_no_persisted_truth": (
            len(truth_status_rows) == expected_current_count
            and all(
                str(row.get("response_truth_status") or "")
                == "no_persisted_response_truth"
                for row in truth_status_rows
            )
        ),
        "all_contract_requirements_have_current_truth_identity": not missing_truth_rows,
        "all_contract_rows_meet_governed_contract": not invalid_contract_rows,
        "golden_evidence_identity_sets_unchanged": not evidence_mismatches,
        "all_projected_evidence_units_exist": not missing_evidence_units,
        "event_plan_count_matches_contract_eligible_count": (
            len(event_plans) == len(expected_contract_ids)
        ),
        "event_signatures_unique": (
            len(event_signatures) == len(set(event_signatures))
        ),
        "projected_event_ids_unique": (
            len(projected_event_ids) == len(set(projected_event_ids))
        ),
        "all_events_are_contract_verified_assertions": all(
            row.get("event_action") == "assertion"
            and row.get("truth_state") == "verified_response"
            and row.get("provenance_type") == "governed_response_contract"
            and row.get("actor_type") == "system_contract"
            and row.get("human_review_id") is None
            and row.get("source_contract_version") == SOURCE_CONTRACT_VERSION
            for row in event_plans
        ),
        "all_event_signatures_are_sha256": all(
            len(str(row.get("event_signature") or "")) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(row.get("event_signature") or "")
            )
            for row in event_plans
        ),
    }

    failed = [key for key, value in checks.items() if not value]

    return {
        "version": VERSION,
        "project_id": project_id,
        "project_label": PROJECTS.get(project_id),
        "status": (
            "PASS_CONTRACT_VERIFIED_RESPONSE_TRUTH_PROJECTION"
            if not failed
            else "BLOCKED_CONTRACT_VERIFIED_RESPONSE_TRUTH_PROJECTION"
        ),
        "all_checks_pass": not failed,
        "failed_checks": failed,
        "checks": checks,
        "source_contract_version": SOURCE_CONTRACT_VERSION,
        "source_projection_version": SOURCE_PROJECTION_VERSION,
        "eligibility_version": ELIGIBILITY_VERSION,
        "current_requirement_count": len(truth_rows),
        "contract_eligible_count": len(contract_rows),
        "human_confirmation_candidate_count": len(human_rows),
        "projected_event_count": len(event_plans),
        "projected_evidence_link_count": projected_evidence_links,
        "ledger_state": {
            "events_count": int(ledger_state.get("events_count") or 0),
            "evidence_count": int(ledger_state.get("evidence_count") or 0),
            "current_truth_count": int(
                ledger_state.get("current_truth_count") or 0
            ),
            "truth_status_row_count": len(truth_status_rows),
            "requirement_truth_row_count_raw": int(
                ledger_state.get("requirement_truth_row_count_raw") or len(truth_rows)
            ),
            "requirement_truth_row_count_current": len(truth_rows),
            "requirement_truth_row_count_noncurrent": int(
                ledger_state.get("requirement_truth_row_count_noncurrent") or 0
            ),
        },
        "event_plans": event_plans,
        "excluded_human_confirmation_candidates": human_rows,
        "diagnostics": {
            "missing_truth_rows": sorted(set(missing_truth_rows)),
            "invalid_contract_rows": sorted(set(invalid_contract_rows)),
            "missing_evidence_units": sorted(missing_evidence_units),
            "evidence_mismatches": evidence_mismatches,
        },
        "response_truth_changed": False,
        "human_review_created": False,
        "persistence_performed": False,
        "writes_performed": False,
        "cutover_approved": False,
        "safe_to_write_response_truth": False,
    }


def _count_rows(client: Any, table_name: str) -> int:
    rows = _rows(
        client.table(table_name)
        .select("*")
        .limit(10000)
        .execute()
    )
    return len(rows)


def run_contract_verified_response_truth_projection_shadow(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    project_id = str(project_id or "")
    if project_id not in PROJECTS:
        raise ValueError(f"B2.15.2 unsupported Golden project: {project_id}")

    eligibility = run_response_truth_eligibility_shadow(
        client,
        project_id=project_id,
    )
    source_projection = run_b21222(
        client,
        project_id=project_id,
    ).to_dict()

    raw_requirement_truth_rows = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    requirement_truth_rows = _current_requirement_truth_rows(
        raw_requirement_truth_rows
    )

    source_by_id = {
        str(row.get("requirement_id") or ""): row
        for row in (source_projection.get("projection_rows") or [])
        if isinstance(row, Mapping) and row.get("requirement_id")
    }
    contract_ids = {
        str(row.get("requirement_id") or "")
        for row in (eligibility.get("eligibility_rows") or [])
        if isinstance(row, Mapping)
        and row.get("eligibility_class") == ELIGIBLE_CONTRACT
        and row.get("requirement_id")
    }
    evidence_ids: set[str] = set()
    for rid in contract_ids:
        row = source_by_id.get(rid) or {}
        for item in row.get("current_response_evidence") or []:
            if isinstance(item, Mapping) and item.get("evidence_id"):
                evidence_ids.add(str(item["evidence_id"]))

    evidence_unit_rows: list[dict[str, Any]] = []
    for evidence_id in sorted(evidence_ids):
        evidence_unit_rows.extend(
            _rows(
                client.table("evidence_units")
                .select("*")
                .eq("id", evidence_id)
                .limit(2)
                .execute()
            )
        )

    truth_status_rows = _rows(
        client.table("project_requirement_response_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    current_truth_rows = _rows(
        client.table("project_requirement_response_current_truth")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )

    ledger_state = {
        "events_count": _count_rows(
            client,
            "project_requirement_response_truth_events",
        ),
        "evidence_count": _count_rows(
            client,
            "project_requirement_response_truth_evidence",
        ),
        "current_truth_count": len(current_truth_rows),
        "truth_status_rows": truth_status_rows,
        "requirement_truth_row_count_raw": len(raw_requirement_truth_rows),
        "requirement_truth_row_count_noncurrent": (
            len(raw_requirement_truth_rows) - len(requirement_truth_rows)
        ),
    }

    return build_response_truth_ledger_projection_shadow(
        project_id=project_id,
        eligibility=eligibility,
        source_projection=source_projection,
        requirement_truth_rows=requirement_truth_rows,
        evidence_unit_rows=evidence_unit_rows,
        ledger_state=ledger_state,
    )
