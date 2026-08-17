from project_source_evidence_backfill import _as_source_file, _project_file_role, _sha256


def test_project_file_metadata_role_is_authoritative_for_historical_project_document():
    row = {
        "file_role": "project_document",
        "metadata": {"document_role": "proposal_presentation"},
    }
    assert _project_file_role(row) == "proposal_presentation"


def test_source_file_adapter_uses_canonical_project_file_master_and_lineage():
    project_file = {
        "id": "pf-1",
        "project_id": "project-1",
        "file_name": "proposal.pdf",
        "mime_type": "application/pdf",
        "storage_bucket": "r2:nave-project-files",
        "storage_path": "projects/project-1/proposal.pdf",
        "content_sha256": "abc123",
        "file_size_bytes": 123,
        "file_role": "project_document",
        "metadata": {"source_file_id": "sf-1", "document_role": "proposal_presentation"},
    }
    source = _as_source_file(project_file, {"id": "sf-1", "import_id": "imp-1", "text_excerpt": "legacy"})
    assert source["id"] == "sf-1"
    assert source["project_id"] == "project-1"
    assert source["sha256"] == "abc123"
    assert source["document_role"] == "proposal_presentation"
    assert source["storage_path"] == "projects/project-1/proposal.pdf"
    assert source["metadata"]["project_file_id"] == "pf-1"
    assert source["metadata"]["evidence_backfill_version"] == "V28.7.2A2"


def test_backfill_sha_uses_original_bytes():
    assert _sha256(b"NAVE") == "1030fde0942e9ed7e3d2d1a851b79a38a0973b8ff50f4618b1eac56ab4144ed1"
