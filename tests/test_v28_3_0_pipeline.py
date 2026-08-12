from __future__ import annotations

import sys
import types

import project_intelligence_pipeline as pipeline


class Response:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, table, store):
        self.table_name = table
        self.store = store
        self.filters = []
    def select(self, *args, **kwargs): return self
    def eq(self, key, value):
        self.filters.append((key, value)); return self
    def execute(self):
        rows = list(self.store.get(self.table_name, []))
        for key, value in self.filters:
            rows = [r for r in rows if r.get(key) == value]
        return Response(rows)


class Client:
    def __init__(self, store): self.store = store
    def table(self, name): return Query(name, self.store)


def test_pending_post_event_report_is_auto_analyzed(monkeypatch):
    client = Client({
        "project_files": [{
            "id": "pf1", "project_id": "p1", "is_archived": False,
            "file_role": "post_execution_report", "storage_path": "p1/report.pptx",
            "storage_bucket": "r2:nave-project-files", "file_name": "report.pptx",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }],
        "project_report_analyses": [],
    })
    monkeypatch.setattr(pipeline, "_ai_settings", lambda: ("test-key", "test-model"))
    monkeypatch.setattr(pipeline, "storage_get_bytes", lambda *a, **k: b"pptx-bytes")

    calls = {}
    extractor = types.ModuleType("project_report_extractor")
    extractor.analyze_project_report = lambda **kwargs: calls.setdefault("analysis", kwargs) or {"ok": True}
    db = types.ModuleType("project_workspace_db")
    def save(*args, **kwargs): calls["save"] = kwargs
    db.save_project_report_analysis = save
    monkeypatch.setitem(sys.modules, "project_report_extractor", extractor)
    monkeypatch.setitem(sys.modules, "project_workspace_db", db)

    result = pipeline.auto_analyze_pending_reports(client, "p1")
    assert result["processed"] == 1
    assert result["errors"] == []
    assert calls["analysis"]["file_name"] == "report.pptx"
    assert calls["analysis"]["report_type"] == "post_execution"
    assert calls["save"]["report_file_id"] == "pf1"


def test_already_analyzed_report_is_not_analyzed_twice(monkeypatch):
    client = Client({
        "project_files": [{"id": "pf1", "project_id": "p1", "is_archived": False, "file_role": "post_execution_report"}],
        "project_report_analyses": [{"project_id": "p1", "report_file_id": "pf1"}],
    })
    result = pipeline.auto_analyze_pending_reports(client, "p1")
    assert result == {"processed": 0, "errors": [], "skipped": 0}


def test_fresh_and_reprocess_flows_share_one_intelligence_finalizer():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fresh = (root / "project_batch_ingestion.py").read_text(encoding="utf-8")
    reprocess = (root / "project_bundle_materializer.py").read_text(encoding="utf-8")
    assert "finalize_project_intelligence" in fresh
    assert "finalize_project_intelligence" in reprocess
    # Evita retornar ao bug de sincronizar project_files antes de resolver file_role.
    ensure_pos = reprocess.find("_ensure_project_file_role")
    sync_pos = reprocess.find("_sync_project_file", ensure_pos)
    assert ensure_pos >= 0 and sync_pos > ensure_pos
