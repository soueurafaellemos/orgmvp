from __future__ import annotations

"""NAVE V28.7.1D — deterministic Domain Coverage & Identity audits.

The audits are deliberately non-destructive. They never create/merge/split a
Project Solution Instance. They publish evidence-backed findings that become
inputs for V28.7.2 Semantic Domain Reconciliation.
"""

from datetime import datetime, timezone
import difflib
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

AUDIT_VERSION = "V28.7.1D"
AUDIT_SCHEMA_VERSION = "28.7.1d"


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


def _read_in(client: Any, table: str, field: str, values: Sequence[Any]) -> list[dict[str, Any]]:
    clean = list(dict.fromkeys(value for value in values if value not in (None, "")))
    if not clean:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(clean), 80):
        out.extend(_rows(client.table(table).select("*").in_(field, clean[start:start + 80]).execute()))
    return out


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in _norm(value).split() if len(token) >= 3 or token.isdigit()}


def _sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _similarity(left: Any, right: Any) -> float:
    a = _norm(left)
    b = _norm(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    contains = 0.92 if a in b or b in a else 0.0
    sequence = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = _tokens(a), _tokens(b)
    overlap = len(ta & tb) / max(len(ta | tb), 1)
    return max(contains, sequence, overlap)


def _best_solution_match(name: str, solutions: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, float, float]:
    scored = sorted(
        ((_similarity(name, row.get("name")), dict(row)) for row in solutions),
        key=lambda item: item[0],
        reverse=True,
    )
    if not scored:
        return None, 0.0, 0.0
    best_score, best = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    return best, best_score, second_score


def _solution_is_resolved(name: str, solutions: Sequence[Mapping[str, Any]]) -> bool:
    _best, best_score, second_score = _best_solution_match(name, solutions)
    if best_score >= 0.92:
        return True
    # Conservative alias tolerance: a lower fuzzy match must also be unique.
    return best_score >= 0.82 and (best_score - second_score) >= 0.10


def _report_result_candidates(report_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse report activation/item results to one candidate per normalized name."""
    by_name: dict[str, dict[str, Any]] = {}
    for report in report_rows:
        report_file_id = str(report.get("report_file_id") or "")
        for raw in report.get("activation_results") or []:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            key = _norm(name)
            by_name.setdefault(key, {
                "name": name,
                "report_file_id": report_file_id,
                "evidence_texts": [],
                "result_kinds": set(),
            })
            if raw.get("evidence"):
                by_name[key]["evidence_texts"].append(str(raw.get("evidence")))
            by_name[key]["result_kinds"].add("activation_result")
        for raw in report.get("item_results") or []:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("item_name") or raw.get("name") or "").strip()
            if not name:
                continue
            key = _norm(name)
            by_name.setdefault(key, {
                "name": name,
                "report_file_id": report_file_id,
                "evidence_texts": [],
                "result_kinds": set(),
            })
            if raw.get("evidence"):
                by_name[key]["evidence_texts"].append(str(raw.get("evidence")))
            by_name[key]["result_kinds"].add("item_result")
    out = []
    for value in by_name.values():
        value["evidence_texts"] = list(dict.fromkeys(v for v in value["evidence_texts"] if v.strip()))
        value["result_kinds"] = sorted(value["result_kinds"])
        out.append(value)
    return sorted(out, key=lambda item: _norm(item["name"]))


def _evidence_matches_text(evidence_rows: Sequence[Mapping[str, Any]], hints: Iterable[Any]) -> list[dict[str, Any]]:
    normalized_hints = [_norm(value) for value in hints if _norm(value) and len(_norm(value)) >= 4]
    if not normalized_hints:
        return []
    exact: dict[str, dict[str, Any]] = {}
    for raw in evidence_rows:
        content = _norm(raw.get("content_text"))
        if any(hint in content for hint in normalized_hints):
            row = dict(raw)
            exact[str(row.get("id"))] = row
    return list(exact.values())


def _start_run(client: Any, *, analyzer_type: str, project_entity_id: str, project_id: str, parent_run_id: str | None, signature_payload: Any) -> str:
    run_id = str(uuid4())
    payload = {
        "id": run_id,
        "parent_run_id": parent_run_id,
        "analyzer_type": analyzer_type,
        "scope_kind": "project",
        "scope_entity_id": project_entity_id,
        "pipeline_version": AUDIT_VERSION,
        "code_version": AUDIT_VERSION,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "input_signature": _sha(signature_payload),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"project_id": project_id, "destructive": False, "auto_mutates_domain": False},
    }
    rows = _rows(client.table("intelligence_runs").insert(payload).execute())
    if not rows:
        raise RuntimeError(f"Supabase não confirmou intelligence_run {analyzer_type}")
    return str(rows[0].get("id") or run_id)


def _complete_run(client: Any, run_id: str, *, findings: int, metadata: Mapping[str, Any] | None = None) -> None:
    client.table("intelligence_runs").update({
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "output_signature": _sha({"findings": findings, **dict(metadata or {})}),
        "metadata": {"findings": findings, **dict(metadata or {})},
    }).eq("id", run_id).execute()


def _fail_run(client: Any, run_id: str | None, exc: Exception) -> None:
    if not run_id:
        return
    try:
        client.table("intelligence_runs").update({
            "status": "error",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "domain_truth_audit_error",
            "error_detail": str(exc)[:4000],
        }).eq("id", run_id).execute()
    except Exception:
        pass


def _supersede_prior_findings(client: Any, *, project_entity_id: str, analyzer_type: str) -> None:
    client.table("intelligence_findings").update({"status": "superseded"}) \
        .eq("scope_entity_id", project_entity_id) \
        .eq("analyzer_type", analyzer_type) \
        .eq("status", "active").execute()


def _insert_finding(
    client: Any,
    *,
    run_id: str,
    analyzer_type: str,
    project_entity_id: str,
    finding_type: str,
    title: str,
    statement: str,
    finding_kind: str,
    importance: str,
    confidence: float,
    recommended_action: str,
    evidence_ids: Sequence[str] = (),
    entity_roles: Sequence[tuple[str, str]] = (),
    impact_domains: Sequence[str] = ("domain",),
) -> str:
    finding_id = str(uuid4())
    client.table("intelligence_findings").insert({
        "id": finding_id,
        "intelligence_run_id": run_id,
        "analyzer_type": analyzer_type,
        "scope_entity_id": project_entity_id,
        "finding_type": finding_type,
        "title": title,
        "statement": statement,
        "finding_kind": finding_kind,
        "importance": importance,
        "confidence": max(0.0, min(1.0, confidence)),
        "impact_domains": list(impact_domains),
        "recommended_action": recommended_action,
        "status": "active",
    }).execute()
    for evidence_id in list(dict.fromkeys(str(v) for v in evidence_ids if v)):
        client.table("finding_evidence").insert({
            "finding_id": finding_id,
            "evidence_unit_id": evidence_id,
            "evidence_role": "support" if finding_kind != "contradiction" else "comparison",
        }).execute()
    for entity_id, role in entity_roles:
        client.table("finding_entities").insert({
            "finding_id": finding_id,
            "entity_id": entity_id,
            "role": role,
        }).execute()
    return finding_id


def _project_source_evidence(client: Any, project_id: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Return current evidence for project source hashes without inventing project ownership."""
    memory_docs = _read_rows(client, "memory_documents", equals={"project_id": project_id})
    project_files = _read_rows(client, "project_files", equals={"project_id": project_id})
    sha_by_project_file_id = {
        str(row.get("id")): str(row.get("content_sha256") or "")
        for row in project_files if row.get("id") and row.get("content_sha256")
    }
    hashes = [str(row.get("content_sha256") or "") for row in memory_docs if row.get("content_sha256")]
    hashes.extend(sha_by_project_file_id.values())
    assets = _read_in(client, "source_assets", "content_sha256", hashes)
    asset_by_sha = {str(row.get("content_sha256") or ""): dict(row) for row in assets if row.get("content_sha256")}
    evidence = _read_in(client, "evidence_units", "source_asset_id", [row.get("id") for row in assets])
    current = [row for row in evidence if row.get("is_current") is True]
    by_asset: dict[str, list[dict[str, Any]]] = {}
    for row in current:
        by_asset.setdefault(str(row.get("source_asset_id") or ""), []).append(row)
    asset_id_by_project_file_id = {
        pfid: str((asset_by_sha.get(sha) or {}).get("id") or "")
        for pfid, sha in sha_by_project_file_id.items()
    }
    return current, by_asset, asset_id_by_project_file_id


def _coverage_audit(client: Any, project_id: str, project_entity_id: str, parent_run_id: str | None) -> dict[str, Any]:
    analyzer = "domain_coverage_audit"
    run_id: str | None = None
    try:
        solutions = _read_rows(client, "project_solution_instances", equals={"project_id": project_id})
        reports = _read_rows(client, "project_report_analyses", equals={"project_id": project_id})
        financial_lines = _read_rows(client, "financial_line_items", equals={"project_id": project_id})
        current_evidence, evidence_by_asset, report_asset_ids = _project_source_evidence(client, project_id)
        candidates = _report_result_candidates(reports)
        run_id = _start_run(
            client,
            analyzer_type=analyzer,
            project_entity_id=project_entity_id,
            project_id=project_id,
            parent_run_id=parent_run_id,
            signature_payload={"candidates": candidates, "solutions": [(r.get("id"), r.get("name")) for r in solutions]},
        )
        _supersede_prior_findings(client, project_entity_id=project_entity_id, analyzer_type=analyzer)

        findings = 0
        missing_names: list[str] = []
        for candidate in candidates:
            name = str(candidate.get("name") or "").strip()
            if not name or _solution_is_resolved(name, solutions):
                continue

            evidence_ids: list[str] = []
            report_asset_id = report_asset_ids.get(str(candidate.get("report_file_id") or ""), "")
            report_evidence = evidence_by_asset.get(report_asset_id) or []
            matched_report_evidence = _evidence_matches_text(
                report_evidence,
                [*(candidate.get("evidence_texts") or []), name],
            )
            evidence_ids.extend(str(row.get("id")) for row in matched_report_evidence if row.get("id"))

            # Cross-source corroboration: exact name mentions in the other project
            # source Evidence Units, plus financial lines that already have direct evidence.
            name_norm = _norm(name)
            for row in current_evidence:
                if name_norm and name_norm in _norm(row.get("content_text")):
                    evidence_ids.append(str(row.get("id")))
            for line in financial_lines:
                if _similarity(name, line.get("item_name")) >= 0.84 and line.get("source_evidence_id"):
                    evidence_ids.append(str(line.get("source_evidence_id")))

            evidence_ids = list(dict.fromkeys(v for v in evidence_ids if v))[:12]
            grounded = bool(evidence_ids)
            statement = (
                f"'{name}' aparece em resultado estruturado de relatório pós-evento, mas não possui "
                "Project Solution Instance reconciliada no domínio atual."
            )
            if len(evidence_ids) >= 2:
                statement += f" Há {len(evidence_ids)} Evidence Units de suporte/corroboração disponíveis para revisão."
            elif not grounded:
                statement += " A ocorrência estruturada existe, mas o vínculo à Evidence Unit ainda precisa de revisão."

            _insert_finding(
                client,
                run_id=run_id,
                analyzer_type=analyzer,
                project_entity_id=project_entity_id,
                finding_type="missing_solution_instance",
                title=f"Possível solução ausente: {name}",
                statement=statement,
                finding_kind="risk" if grounded else "unknown",
                importance="high" if grounded else "medium",
                confidence=0.96 if grounded else 0.65,
                recommended_action="Revisar na Semantic Domain Reconciliation; não criar entidade automaticamente na V28.7.1D.",
                evidence_ids=evidence_ids,
                impact_domains=("domain", "coverage", "execution"),
            )
            findings += 1
            missing_names.append(name)

        _complete_run(client, run_id, findings=findings, metadata={"missing_names": missing_names})
        return {"status": "completed", "run_id": run_id, "findings": findings, "missing_names": missing_names}
    except Exception as exc:
        _fail_run(client, run_id, exc)
        return {"status": "error", "run_id": run_id, "findings": 0, "error": str(exc)}


def _identity_audit(client: Any, project_id: str, project_entity_id: str, parent_run_id: str | None) -> dict[str, Any]:
    analyzer = "domain_identity_audit"
    run_id: str | None = None
    try:
        solutions = _read_rows(client, "project_solution_instances", equals={"project_id": project_id})
        evidence_links = _read_rows(client, "domain_object_evidence", equals={"project_id": project_id, "domain_table": "project_solution_instances"})
        current_evidence = _read_in(client, "evidence_units", "id", [row.get("evidence_unit_id") for row in evidence_links])
        current_ids = {str(row.get("id")) for row in current_evidence if row.get("is_current") is True}
        evidence_by_id = {str(row.get("id")): dict(row) for row in current_evidence if row.get("id")}
        solution_by_id = {str(row.get("id")): dict(row) for row in solutions if row.get("id")}

        run_id = _start_run(
            client,
            analyzer_type=analyzer,
            project_entity_id=project_entity_id,
            project_id=project_id,
            parent_run_id=parent_run_id,
            signature_payload={"solutions": [(r.get("id"), r.get("name")) for r in solutions], "links": evidence_links},
        )
        _supersede_prior_findings(client, project_entity_id=project_entity_id, analyzer_type=analyzer)

        domains_by_evidence: dict[str, set[str]] = {}
        for link in evidence_links:
            evidence_id = str(link.get("evidence_unit_id") or "")
            domain_id = str(link.get("domain_id") or "")
            if evidence_id in current_ids and domain_id in solution_by_id:
                domains_by_evidence.setdefault(evidence_id, set()).add(domain_id)

        findings = 0
        conflict_pairs: list[list[str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for evidence_id, domain_ids in domains_by_evidence.items():
            ids = sorted(domain_ids)
            if len(ids) < 2:
                continue
            for index, left_id in enumerate(ids):
                for right_id in ids[index + 1:]:
                    pair = (left_id, right_id)
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    left = solution_by_id[left_id]
                    right = solution_by_id[right_id]
                    left_name = str(left.get("name") or "Solução A")
                    right_name = str(right.get("name") or "Solução B")
                    if _norm(left_name) == _norm(right_name):
                        # Exact aliases are already expected to consolidate by identity_key;
                        # this audit focuses on two distinct identities sharing evidence.
                        continue
                    shared_evidence = evidence_by_id.get(evidence_id) or {}
                    evidence_text = _norm(shared_evidence.get("content_text"))
                    left_supported = _norm(left_name) in evidence_text or _similarity(left_name, evidence_text) >= 0.68
                    right_supported = _norm(right_name) in evidence_text or _similarity(right_name, evidence_text) >= 0.68
                    # A page/slide container can legitimately contain unrelated solutions.
                    # Duplicate-identity review is reserved for a compact shared fragment
                    # that materially supports both observed names.
                    if not (left_supported and right_supported):
                        continue
                    if len(evidence_text) > 260 and _similarity(left_name, right_name) < 0.55:
                        continue
                    _insert_finding(
                        client,
                        run_id=run_id,
                        analyzer_type=analyzer,
                        project_entity_id=project_entity_id,
                        finding_type="possible_duplicate_identity",
                        title=f"Conflito de identidade: {left_name} ↔ {right_name}",
                        statement=(
                            f"As Project Solution Instances '{left_name}' e '{right_name}' compartilham a mesma Evidence Unit. "
                            "A V28.7.1D bloqueia consolidação automática: revisar se são aliases, componentes da mesma solução ou identidades realmente distintas."
                        ),
                        finding_kind="contradiction",
                        importance="high",
                        confidence=0.98,
                        recommended_action="Revisar merge/split na V28.7.2; nenhuma alteração automática de identidade nesta versão.",
                        evidence_ids=(evidence_id,),
                        entity_roles=((str(left.get("entity_id")), "subject"), (str(right.get("entity_id")), "comparison")),
                        impact_domains=("domain", "identity"),
                    )
                    findings += 1
                    conflict_pairs.append([left_name, right_name])

        _complete_run(client, run_id, findings=findings, metadata={"conflict_pairs": conflict_pairs})
        return {"status": "completed", "run_id": run_id, "findings": findings, "conflict_pairs": conflict_pairs}
    except Exception as exc:
        _fail_run(client, run_id, exc)
        return {"status": "error", "run_id": run_id, "findings": 0, "error": str(exc)}


def run_project_domain_truth_audits(client: Any, project_id: str, *, parent_run_id: str | None = None) -> dict[str, Any]:
    """Run non-mutating truth/coverage diagnostics after a successful normalization."""
    try:
        project_entities = _rows(
            client.table("knowledge_entities").select("*")
            .eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute()
        )
        if not project_entities:
            raise RuntimeError("Project knowledge_entity não encontrada após Domain Normalization")
        project_entity_id = str(project_entities[0].get("id") or "")
        if not project_entity_id:
            raise RuntimeError("Project knowledge_entity sem id")
    except Exception as exc:
        return {
            "status": "error",
            "coverage": {"status": "error", "error": str(exc), "findings": 0},
            "identity": {"status": "error", "error": str(exc), "findings": 0},
        }

    coverage = _coverage_audit(client, project_id, project_entity_id, parent_run_id)
    identity = _identity_audit(client, project_id, project_entity_id, parent_run_id)
    status = "completed" if coverage.get("status") == "completed" and identity.get("status") == "completed" else "error"
    return {
        "status": status,
        "project_id": project_id,
        "project_entity_id": project_entity_id,
        "coverage": coverage,
        "identity": identity,
        "findings_total": int(coverage.get("findings") or 0) + int(identity.get("findings") or 0),
        "auto_mutates_domain": False,
    }
