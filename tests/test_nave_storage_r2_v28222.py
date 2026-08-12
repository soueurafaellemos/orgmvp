from __future__ import annotations

import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import nave_storage as ns


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeR2:
    def __init__(self):
        self.objects: dict[tuple[str, str], dict] = {}
        self.put_calls = 0
        self.multipart_calls = 0
        self.delete_calls = 0

    def list_objects_v2(self, *, Bucket, MaxKeys=1):
        keys = [key for (bucket, key) in self.objects if bucket == Bucket][:MaxKeys]
        return {"Contents": [{"Key": key} for key in keys]}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata, **kwargs):
        self.put_calls += 1
        data = bytes(Body)
        self.objects[(Bucket, Key)] = {
            "data": data,
            "ContentType": ContentType,
            "Metadata": dict(Metadata),
        }
        return {"ETag": "fake"}

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None, Config=None):
        self.multipart_calls += 1
        data = fileobj.read()
        self.objects[(bucket, key)] = {
            "data": data,
            "ContentType": (ExtraArgs or {}).get("ContentType"),
            "Metadata": dict((ExtraArgs or {}).get("Metadata") or {}),
        }

    def head_object(self, *, Bucket, Key):
        obj = self.objects[(Bucket, Key)]
        return {
            "ContentLength": len(obj["data"]),
            "Metadata": obj["Metadata"],
        }

    def get_object(self, *, Bucket, Key):
        return {"Body": _Body(self.objects[(Bucket, Key)]["data"])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def delete_objects(self, *, Bucket, Delete):
        self.delete_calls += 1
        for item in Delete.get("Objects") or []:
            self.objects.pop((Bucket, item["Key"]), None)
        return {"Deleted": Delete.get("Objects") or []}

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://signed.invalid/{Params['Bucket']}/{Params['Key']}?op={operation}&exp={ExpiresIn}"


def _settings(*, threshold: int = 100) -> ns.R2Settings:
    return ns.R2Settings(
        account_id="acct",
        access_key_id="key",
        secret_access_key="secret",
        bucket="nave-project-files",
        endpoint="https://acct.r2.cloudflarestorage.com",
        multipart_threshold_bytes=threshold,
        multipart_chunk_bytes=5 * 1024 * 1024,
    )


def _install_fake(monkeypatch, fake: FakeR2, *, threshold: int = 100):
    monkeypatch.setattr(ns, "get_r2_settings", lambda: _settings(threshold=threshold))
    monkeypatch.setattr(ns, "_r2_client", lambda: fake)


def test_r2_small_upload_integrity_and_download(monkeypatch):
    fake = FakeR2()
    _install_fake(monkeypatch, fake, threshold=10_000)
    payload = b"NAVE-storage-test"
    digest = hashlib.sha256(payload).hexdigest()

    result = ns.put_bytes(
        path="projects/p1/source.pdf",
        data=payload,
        content_type="application/pdf",
        sha256=digest,
        logical_kind="project-source",
    )

    assert result["storage_bucket"] == "r2:nave-project-files"
    assert result["multipart"] is False
    assert fake.put_calls == 1
    assert fake.multipart_calls == 0
    assert ns.get_bytes(
        None,
        bucket_name=result["storage_bucket"],
        path=result["storage_path"],
    ) == payload


def test_r2_large_upload_uses_multipart(monkeypatch):
    fake = FakeR2()
    _install_fake(monkeypatch, fake, threshold=8)
    payload = b"0123456789abcdef"

    result = ns.put_bytes(
        path="projects/p1/large.pptx",
        data=payload,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

    assert result["multipart"] is True
    assert fake.multipart_calls == 1
    assert fake.put_calls == 0


def test_r2_signed_url_and_delete(monkeypatch):
    fake = FakeR2()
    _install_fake(monkeypatch, fake, threshold=1000)
    result = ns.put_bytes(path="media/a.jpg", data=b"abc", content_type="image/jpeg")

    url = ns.create_signed_url(
        None,
        bucket_name=result["storage_bucket"],
        path=result["storage_path"],
        expires_in=90,
    )
    assert url and "signed.invalid" in url

    ns.delete_objects(
        None,
        bucket_name=result["storage_bucket"],
        paths=[result["storage_path"]],
    )
    assert fake.delete_calls == 1
    assert not fake.objects


def test_r2_healthcheck_uses_object_level_list_permission(monkeypatch):
    fake = FakeR2()
    _install_fake(monkeypatch, fake)
    result = ns.verify_r2_access()
    assert result["provider"] == "r2"
    assert result["reachable"] is True


class FakeLegacyBucket:
    def __init__(self):
        self.removed = []

    def download(self, path):
        return b"legacy:" + path.encode()

    def create_signed_url(self, path, expires, *args):
        return {"signedURL": f"https://legacy.invalid/{path}"}

    def remove(self, paths):
        self.removed.extend(paths)


class FakeLegacyStorage:
    def __init__(self):
        self.bucket = FakeLegacyBucket()

    def from_(self, name):
        return self.bucket


def test_legacy_supabase_rows_remain_readable_and_deletable():
    client = SimpleNamespace(storage=FakeLegacyStorage())
    assert ns.get_bytes(client, bucket_name="nave-memory", path="old.pdf") == b"legacy:old.pdf"
    assert ns.create_signed_url(client, bucket_name="nave-memory", path="old.pdf") == "https://legacy.invalid/old.pdf"
    ns.delete_objects(client, bucket_name="nave-memory", paths=["old.pdf"])
    assert client.storage.bucket.removed == ["old.pdf"]


def test_project_ingestion_no_longer_requires_supabase_storage_client():
    from project_batch_ingestion import _assert_project_db_client

    client = SimpleNamespace(table=lambda *args, **kwargs: None)
    _assert_project_db_client(client)


def test_new_file_writes_are_centralized_in_nave_storage():
    root = Path(__file__).resolve().parents[1]
    production_files = [
        root / "project_batch_ingestion.py",
        root / "project_workspace_db.py",
        root / "memory_db.py",
        root / "memory_learning_db.py",
        root / "media_library.py",
        root / "project_workspace_visuals.py",
    ]
    for path in production_files:
        text = path.read_text(encoding="utf-8")
        assert ".upload(" not in text, f"direct storage upload remains in {path.name}"
