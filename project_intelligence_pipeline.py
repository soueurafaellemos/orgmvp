from __future__ import annotations

"""Finalização única de inteligência após uma importação/reprocessamento.

A regra arquitetural é simples: novos arquivos não podem alimentar só o workspace ou
só o Intelligence Graph. Ao terminar um lote, a NAVE fecha relatório pós-evento,
cross-source linking, snapshot unificado e Project Analyst no mesmo pipeline.
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
    """Estrutura relatórios já anexados automaticamente, sem depender de um clique manual."""
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


def finalize_project_intelligence(client: Any, project_id: str) -> dict[str, Any]:
    warnings: list[str] = []
    report_result = auto_analyze_pending_reports(client, project_id)
    warnings.extend(report_result.get("errors") or [])
    if report_result.get("warning"):
        warnings.append(str(report_result["warning"]))

    canonical_graph = None
    try:
        from project_entity_graph import materialize_project_canonical_entities
        canonical_graph = materialize_project_canonical_entities(client, project_id)
    except Exception as exc:
        warnings.append(f"Canonical Entity Graph: {exc}")

    cross_source = None
    try:
        from cross_source_linker import run_project_cross_source_intelligence
        cross_source = run_project_cross_source_intelligence(client, project_id)
        if str((cross_source or {}).get("status") or "") == "error":
            warnings.append(f"Cross-Source Linker: {(cross_source or {}).get('error') or 'erro não detalhado'}")
    except Exception as exc:
        warnings.append(f"Cross-Source Linker: {exc}")

    semantic: dict[str, Any] | None = None
    try:
        from project_workspace_db import fetch_project_workspace_snapshot
        from project_workspace_intelligence import (
            build_project_intelligence,
            ensure_automatic_briefing_links,
            ensure_automatic_cost_links,
            persist_project_intelligence,
        )
        from project_intelligence_unified import build_unified_project_snapshot
        from project_analyst import analyze_project_snapshot, semantic_synthesis_findings

        snapshot = fetch_project_workspace_snapshot(client, project_id=project_id)
        snapshot["unified_intelligence"] = build_unified_project_snapshot(snapshot)
        ensure_automatic_cost_links(client, project_id=project_id, snapshot=snapshot)
        ensure_automatic_briefing_links(client, project_id=project_id, snapshot=snapshot)
        # Recarrega após os links automáticos para que o snapshot final seja coerente.
        snapshot = fetch_project_workspace_snapshot(client, project_id=project_id)
        snapshot["unified_intelligence"] = build_unified_project_snapshot(snapshot)
        deterministic = build_project_intelligence(snapshot)

        api_key, model = _ai_settings()
        if api_key and snapshot.get("briefing_documents") and snapshot.get("memory_documents"):
            synthesis = analyze_project_snapshot(snapshot=snapshot, api_key=api_key, model=model)
            semantic = synthesis.model_dump()
            deterministic["semantic_synthesis"] = semantic
            deterministic.setdefault("metrics", {})["semantic_synthesis"] = semantic
            deterministic.setdefault("findings", []).extend(semantic_synthesis_findings(synthesis))
            deterministic.setdefault("recommendations", []).extend(synthesis.decision_recommendations)
            deterministic["recommendations"] = list(dict.fromkeys(
                str(value).strip() for value in deterministic.get("recommendations") or [] if str(value).strip()
            ))
        persist_project_intelligence(client, project_id=project_id, intelligence=deterministic)
    except Exception as exc:
        warnings.append(f"Project Intelligence finalization: {exc}")

    return {
        "project_id": project_id,
        "report_analysis": report_result,
        "canonical_entity_graph": canonical_graph,
        "cross_source": cross_source,
        "semantic_project_analysis": semantic,
        "warnings": warnings[:40],
    }
