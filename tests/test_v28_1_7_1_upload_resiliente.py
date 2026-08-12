from __future__ import annotations

import sys
import types

import pytest

# Mantém o teste executável no container enxuto usado para validar patches.
if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")
    supabase_stub.Client = object
    sys.modules["supabase"] = supabase_stub

if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = {}
    sys.modules["streamlit"] = streamlit_stub

try:
    import google
except ImportError:
    google = types.ModuleType("google")
    sys.modules["google"] = google

if not hasattr(google, "genai"):
    google.genai = types.SimpleNamespace(Client=object)

from project_batch_ingestion import (
    MAX_FILE_BYTES,
    MAX_FILE_MB,
    ProjectBatchError,
    _upload_bytes,
    prepare_document,
)


class _ReportedSizeBytes(bytes):
    """Bytes pequenos que reportam um tamanho lógico grande para testar limites sem gastar RAM."""

    reported_size = 0

    def __len__(self):
        return self.reported_size or super().__len__()


def _sized_bytes(payload: bytes, size_mb: int) -> bytes:
    cls = type(f"Reported{size_mb}MB", (_ReportedSizeBytes,), {"reported_size": size_mb * 1024 * 1024})
    return cls(payload)


def test_feedback_jpeg_between_200_and_300_mb_is_accepted_and_classified():
    data = _sized_bytes(b"\xff\xd8\xff\xe0JPEG", 250)
    doc = prepare_document("feedback.jpeg", data, "application/octet-stream")
    assert doc.mime_type == "image/jpeg"
    assert doc.role == "feedback_approval"
    assert doc.file_size_bytes == 250 * 1024 * 1024
    assert MAX_FILE_MB == 300
    assert MAX_FILE_BYTES == 300 * 1024 * 1024


def test_png_and_webp_are_recognized_by_binary_signature():
    png = prepare_document("print.png", b"\x89PNG\r\n\x1a\nPNGDATA", "application/octet-stream")
    webp = prepare_document("print.webp", b"RIFF\x04\x00\x00\x00WEBPdata", "application/octet-stream")
    assert png.mime_type == "image/png"
    assert webp.mime_type == "image/webp"


def test_image_mime_does_not_trust_wrong_browser_mime():
    doc = prepare_document("feedback.jpg", b"\x89PNG\r\n\x1a\nPNGDATA", "image/jpeg")
    assert doc.mime_type == "image/png"


def test_invalid_image_payload_is_rejected_cleanly():
    with pytest.raises(ProjectBatchError, match="não parece ser um JPG, PNG ou WEBP válido"):
        prepare_document("feedback.jpeg", b"isto nao e uma imagem", "image/jpeg")


def test_file_above_300_mb_is_rejected_before_processing():
    data = _sized_bytes(b"\xff\xd8\xff\xe0JPEG", 301)
    with pytest.raises(ProjectBatchError, match="limite de 300 MB"):
        prepare_document("feedback.jpeg", data, "image/jpeg")


def test_storage_failure_becomes_actionable_message(monkeypatch):
    import project_batch_ingestion as ingestion
    from nave_storage import NaveStorageError

    def _fail(**_kwargs):
        raise NaveStorageError("R2 indisponível para teste")

    monkeypatch.setattr(ingestion, "put_bytes", _fail)
    data = b"\xff\xd8\xff\xe0JPEG"
    with pytest.raises(ProjectBatchError, match="Cloudflare R2"):
        _upload_bytes(
            path="projects/test/feedback.jpeg",
            data=data,
            mime_type="image/jpeg",
            sha256=__import__("hashlib").sha256(data).hexdigest(),
        )


def test_visual_feedback_is_preserved_without_fabricating_text():
    from project_bundle_materializer import _materialize_feedback

    inserted_payloads = []

    class _Response:
        def __init__(self, data=None):
            self.data = data or []

    class _Query:
        def __init__(self, mode="select"):
            self.mode = mode

        def select(self, *_args, **_kwargs):
            self.mode = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def insert(self, payload):
            inserted_payloads.append(payload)
            self.mode = "insert"
            return self

        def execute(self):
            if self.mode == "insert":
                return _Response([{"id": "feedback-1"}])
            return _Response([])

    class _Client:
        def table(self, _name):
            return _Query()

    result = _materialize_feedback(
        _Client(),
        {
            "project_id": "project-1",
            "id": "source-1",
            "sha256": "abc123",
            "file_name": "feedback.jpeg",
            "mime_type": "image/jpeg",
        },
        "",
    )
    assert result == {"feedback_entries": 1}
    payload = inserted_payloads[0]
    assert "Conteúdo textual não extraído automaticamente" in payload["original_feedback"]
    assert "sem inferir texto, autor ou decisão" in payload["internal_interpretation"]
    assert payload["sentiment"] == "neutral"
    assert payload["confidence_level"] == "incomplete"
