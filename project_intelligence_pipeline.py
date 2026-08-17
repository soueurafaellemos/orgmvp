from __future__ import annotations

"""NAVE V28.7.2C0 — evidence-led Requirement reconciliation finalization.

The action preserves V28.7.1D Truth Gate, runs the approved V28.7.2A Solution
reconciliation and audits, reconciles Requirement identity/occurrence semantics in C0,
then materializes the approved V28.7.2B Strategy / Creative / Experience domains.
Everything remains in legacy_shadow; Graph V28.6 and the old Project Analyst synthesis
remain frozen.
"""

import os
from typing import Any, Mapping

from nave_storage import get_bytes as storage_get_bytes


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _ai_settings() -> tuple[str | None, str]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash"
    try:
        import streamlit as st
        api_key = str(st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY") or api_key or "").strip() or None
        model = str(st.secrets.get("GEMINI_MODEL") or model).strip() or model
    except Exception:
        pass
    return api_key, model


def _pending_report_files(client: Any, project_id: str) -> list[dict[str, Any]]:
    try:
        files = _rows(
            client.table("project_files").select("*")
            .eq("project_id", project_id).eq("is_archived", False).execute()
        )
    except Exception:
        files = []
    try:
        analysed = _rows(
            client.table("project_report_analyses").select("report_file_id")
            .eq("project_id", project_id).execute()
        )
    except Exception:
        analysed = []
    analysed_ids = {str(row.get("report_file_id")) for row in analysed if row.get("report_file_id")}
    return [
        row for row in files
        if str(row.get("file_role") or "") in {"post_execution_report", "closure_report"}
        and str(row.get("id") or "") not in analysed_ids
    ]


def auto_analyze_pending_reports(client: Any, project_id: str) -> dict[str, Any]:
    """Structure reports already attached. This precedes the deterministic Truth Gate."""
    pending = _pending_report_files(client, project_id)
    if not pending:
        return {"processed": 0, "errors": [], "skipped": 0}
    api_key, model = _ai_settings()
    if not api_key:
        return {"processed": 0, "errors": [], "skipped": len(pending), "warning": "GEMINI_API_KEY ausente"}

    from project_report_extractor import analyze_project_report
    from project_workspace_db import save_project_report_analysis

    processed = 0
    errors: list[str] = []
    for row in pending:
        path = str(row.get("storage_path") or "")
        bucket = str(row.get("storage_bucket") or "nave-project-files")
        file_name = str(row.get("file_name") or row.get("title") or "Relatório")
        if not path:
            errors.append(f"{file_name}: caminho de storage ausente")
            continue
        try:
            file_bytes = storage_get_bytes(client, bucket_name=bucket, path=path)
            if not file_bytes:
                raise RuntimeError("arquivo não pôde ser recuperado")
            report_type = "closure" if str(row.get("file_role")) == "closure_report" else "post_execution"
            analysis = analyze_project_report(
                file_name=file_name,
                mime_type=row.get("mime_type"),
                file_bytes=file_bytes,
                report_type=report_type,
                api_key=api_key,
                model=model,
            )
            save_project_report_analysis(
                client,
                project_id=project_id,
                report_file_id=str(row.get("id")),
                report_type=report_type,
                analysis=analysis,
            )
            processed += 1
        except Exception as exc:
            errors.append(f"{file_name}: {exc}")
    return {"processed": processed, "errors": errors, "skipped": max(0, len(pending) - processed - len(errors))}


def _refresh_domain_result(client: Any, project_id: str, domain_normalization: dict[str, Any]) -> dict[str, Any]:
    """Refresh Truth/Audit counters after analysts publish their findings."""
    try:
        from project_domain_normalization import fetch_project_domain_status

        latest = fetch_project_domain_status(client, project_id)
        if latest.get("status") != "ready":
            return domain_normalization
        parity = domain_normalization.setdefault("parity", {})
        parity["normalized"] = latest.get("normalized") or parity.get("normalized") or {}
        parity["legacy"] = latest.get("legacy") or parity.get("legacy") or {}
        parity["integrity"] = latest.get("integrity") or parity.get("integrity") or {}
        return domain_normalization
    except Exception:
        return domain_normalization


def finalize_project_intelligence(client: Any, project_id: str, *, analyze_pending_reports: bool = True) -> dict[str, Any]:
    warnings: list[str] = []
    frozen_graph = {
        "status": "frozen_v28_6",
        "version": "V28.6",
        "reason": "V28.7.1D congela o Graph legado; Domain Refresh não o reconstrói nem usa seus contadores como truth gate.",
    }
    frozen_prelinks = {"cost": 0, "briefing": 0, "status": "frozen_v28_6"}

    # Fail closed before report/domain mutations if the V28.7.1D Truth Gate is
    # unavailable. A stale V28.7.1B schema cannot be presented as the new gate.
    try:
        from project_domain_normalization import probe_domain_schema
        schema_probe = probe_domain_schema(client)
    except Exception as exc:
        schema_probe = {"available": False, "status": "schema_check_error", "error": str(exc)}

    if not schema_probe.get("available"):
        failure_status = str(schema_probe.get("status") or "schema_check_error")
        error = str(schema_probe.get("error") or "schema de domínio indisponível")
        domain_normalization = {
            "project_id": project_id,
            "status": failure_status,
            "warnings": [error],
        }
        warnings.append(f"Domain Truth Gate preflight: {error}")
        return {
            "status": "domain_blocked",
            "project_id": project_id,
            "report_analysis": {"status": "skipped_domain_blocked", "processed": 0, "errors": []},
            "domain_normalization": domain_normalization,
            "domain_audits": {"status": "skipped_domain_blocked"},
            "canonical_entity_graph": None,
            "cross_source": frozen_graph,
            "semantic_project_analysis": None,
            "structured_prelinks": frozen_prelinks,
            "warnings": warnings[:40],
        }

    if analyze_pending_reports:
        report_result = auto_analyze_pending_reports(client, project_id)
        warnings.extend(report_result.get("errors") or [])
        if report_result.get("warning"):
            warnings.append(str(report_result["warning"]))
    else:
        report_result = {"status": "skipped_explicit_domain_refresh", "processed": 0, "errors": [], "skipped": 0}

    domain_normalization: dict[str, Any]
    try:
        from project_domain_normalization import sync_project_domain_normalization
        domain_normalization = sync_project_domain_normalization(client, project_id)
    except Exception as exc:
        domain_normalization = {
            "project_id": project_id,
            "status": "orchestration_error",
            "warnings": [str(exc)],
        }

    domain_status = str((domain_normalization or {}).get("status") or "")
    if domain_status != "completed":
        for value in (domain_normalization or {}).get("warnings") or []:
            if str(value).strip():
                warnings.append(f"Domain Normalization: {str(value)[:700]}")
        return {
            "status": "domain_blocked",
            "project_id": project_id,
            "report_analysis": report_result,
            "domain_normalization": domain_normalization,
            "domain_audits": {"status": "skipped_domain_blocked"},
            "canonical_entity_graph": None,
            "cross_source": frozen_graph,
            "semantic_project_analysis": None,
            "structured_prelinks": frozen_prelinks,
            "warnings": warnings[:40],
        }

    # V28.7.2A: reconcile evidence-led semantic observations after the approved
    # Truth Gate baseline exists. This stays legacy_shadow and never rebuilds V28.6.
    try:
        from project_domain_reconciliation import reconcile_project_domain

        domain_reconciliation = reconcile_project_domain(client, project_id)
    except Exception as exc:
        domain_reconciliation = {"status": "orchestration_error", "warnings": [str(exc)]}

    reconciliation_status = str(domain_reconciliation.get("status") or "")
    if reconciliation_status != "completed":
        for value in domain_reconciliation.get("warnings") or []:
            if str(value).strip():
                warnings.append(f"Domain Reconciliation: {str(value)[:700]}")
        return {
            "status": "domain_reconciliation_blocked",
            "project_id": project_id,
            "report_analysis": report_result,
            "domain_normalization": domain_normalization,
            "domain_reconciliation": domain_reconciliation,
            "domain_audits": {"status": "skipped_reconciliation_blocked"},
            "canonical_entity_graph": None,
            "cross_source": frozen_graph,
            "semantic_project_analysis": None,
            "structured_prelinks": frozen_prelinks,
            "warnings": warnings[:40],
        }

    try:
        from project_domain_truth_audit import run_project_domain_truth_audits

        audits = run_project_domain_truth_audits(
            client,
            project_id,
            parent_run_id=str(domain_reconciliation.get("run_id") or domain_normalization.get("run_id") or "") or None,
        )
    except Exception as exc:
        audits = {"status": "error", "error": str(exc)}

    domain_normalization = _refresh_domain_result(client, project_id, domain_normalization)

    if str(audits.get("status") or "") != "completed":
        warnings.append("Domain Truth Audits: " + str(audits.get("error") or "coverage/identity audit incompleto"))
        for key in ("coverage", "identity"):
            part = audits.get(key) if isinstance(audits.get(key), Mapping) else {}
            if part and part.get("error"):
                warnings.append(f"{key}: {str(part.get('error'))[:700]}")
        return {
            "status": "domain_audit_blocked",
            "project_id": project_id,
            "report_analysis": report_result,
            "domain_normalization": domain_normalization,
            "domain_reconciliation": domain_reconciliation,
            "domain_audits": audits,
            "canonical_entity_graph": None,
            "cross_source": frozen_graph,
            "semantic_project_analysis": None,
            "structured_prelinks": frozen_prelinks,
            "warnings": warnings[:40],
        }

    # V28.7.2C0: Requirement Semantic Reconciliation runs after A + audits and
    # before B. It may verify, classify or leave legacy requirements unresolved, but
    # never auto-merges two existing Requirement identities.
    try:
        from project_requirement_reconciliation import reconcile_project_requirements

        requirement_reconciliation = reconcile_project_requirements(client, project_id)
    except Exception as exc:
        requirement_reconciliation = {"status": "orchestration_error", "warnings": [str(exc)]}

    requirement_status = str(requirement_reconciliation.get("status") or "")
    if requirement_status != "completed":
        for value in requirement_reconciliation.get("warnings") or []:
            if str(value).strip():
                warnings.append(f"Requirement Reconciliation: {str(value)[:700]}")
        return {
            "status": "requirement_reconciliation_blocked",
            "project_id": project_id,
            "report_analysis": report_result,
            "domain_normalization": domain_normalization,
            "domain_reconciliation": domain_reconciliation,
            "domain_audits": audits,
            "requirement_reconciliation": requirement_reconciliation,
            "core_semantics": {"status": "skipped_requirement_reconciliation_blocked"},
            "canonical_entity_graph": None,
            "cross_source": frozen_graph,
            "semantic_project_analysis": None,
            "structured_prelinks": frozen_prelinks,
            "warnings": warnings[:40],
        }

    # V28.7.2B: Core Semantic Domains runs after the approved A kernel + audits + C0.
    # A/C0 generations remain valid if B is unavailable or fails.
    try:
        from project_core_semantic_domains import materialize_project_core_semantics
        core_semantics = materialize_project_core_semantics(client, project_id)
    except Exception as exc:
        core_semantics = {"status": "orchestration_error", "warnings": [str(exc)]}

    core_status = str(core_semantics.get("status") or "")
    if core_status != "completed":
        for value in core_semantics.get("warnings") or []:
            if str(value).strip():
                warnings.append(f"Core Semantic Domains: {str(value)[:700]}")
        return {
            "status": "core_semantics_blocked",
            "project_id": project_id,
            "report_analysis": report_result,
            "domain_normalization": domain_normalization,
            "domain_reconciliation": domain_reconciliation,
            "domain_audits": audits,
            "requirement_reconciliation": requirement_reconciliation,
            "core_semantics": core_semantics,
            "canonical_entity_graph": None,
            "cross_source": frozen_graph,
            "semantic_project_analysis": None,
            "structured_prelinks": frozen_prelinks,
            "warnings": warnings[:40],
        }

    # No V28.6 graph rebuild, no old cross-source linker, no Project Analyst synthesis.
    return {
        "status": "completed",
        "project_id": project_id,
        "report_analysis": report_result,
        "domain_normalization": domain_normalization,
        "domain_reconciliation": domain_reconciliation,
        "domain_audits": audits,
        "requirement_reconciliation": requirement_reconciliation,
        "core_semantics": core_semantics,
        "canonical_entity_graph": None,
        "cross_source": frozen_graph,
        "semantic_project_analysis": None,
        "structured_prelinks": frozen_prelinks,
        "warnings": warnings[:40],
    }
