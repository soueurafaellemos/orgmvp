from __future__ import annotations

"""Unified private storage layer for NAVE.

New objects are written to Cloudflare R2. Existing Supabase Storage rows remain
readable/deletable during the migration window. Callers should never access R2
credentials or boto3 directly; they work only with the functions in this module.

The existing database columns ``storage_bucket`` / ``storage_path`` are kept for
backward compatibility. R2 locations are represented by a provider-qualified
bucket marker such as ``r2:nave-project-files``. Legacy Supabase rows keep their
original bucket name (for example ``nave-memory``).
"""

import hashlib
import io
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable


R2_PROVIDER = "r2"
R2_BUCKET_PREFIX = "r2:"
DEFAULT_R2_BUCKET = "nave-project-files"
DEFAULT_MULTIPART_THRESHOLD_MB = 100
DEFAULT_MULTIPART_CHUNK_MB = 16
MAX_OBJECT_BYTES = 5 * 1024**4  # R2 multipart object limit: 5 TiB.


class NaveStorageError(RuntimeError):
    """Safe storage-layer error intended to be surfaced by application code."""


@dataclass(frozen=True)
class R2Settings:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint: str
    multipart_threshold_bytes: int
    multipart_chunk_bytes: int

    @property
    def bucket_marker(self) -> str:
        return f"{R2_BUCKET_PREFIX}{self.bucket}"


def _streamlit_secret(name: str) -> str:
    try:
        import streamlit as st  # imported lazily so tests/CLI do not require it

        value = st.secrets.get(name)
        return str(value or "").strip()
    except Exception:
        return ""


def _setting(name: str, default: str = "") -> str:
    value = str(os.getenv(name) or "").strip()
    if value:
        return value
    value = _streamlit_secret(name)
    return value or default


def _positive_int_setting(name: str, default: int) -> int:
    raw = _setting(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


@lru_cache(maxsize=1)
def get_r2_settings() -> R2Settings:
    account_id = _setting("R2_ACCOUNT_ID")
    access_key_id = _setting("R2_ACCESS_KEY_ID")
    secret_access_key = _setting("R2_SECRET_ACCESS_KEY")
    bucket = _setting("R2_BUCKET", DEFAULT_R2_BUCKET)
    endpoint = _setting("R2_ENDPOINT")

    missing = [
        name
        for name, value in (
            ("R2_ACCOUNT_ID", account_id),
            ("R2_ACCESS_KEY_ID", access_key_id),
            ("R2_SECRET_ACCESS_KEY", secret_access_key),
            ("R2_BUCKET", bucket),
        )
        if not value
    ]
    if missing:
        raise NaveStorageError(
            "O armazenamento R2 da NAVE ainda não está configurado. "
            "Confira os Secrets do Streamlit: " + ", ".join(missing) + "."
        )

    if not endpoint:
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"

    threshold_mb = _positive_int_setting(
        "R2_MULTIPART_THRESHOLD_MB", DEFAULT_MULTIPART_THRESHOLD_MB
    )
    chunk_mb = _positive_int_setting("R2_MULTIPART_CHUNK_MB", DEFAULT_MULTIPART_CHUNK_MB)
    # S3 multipart requires parts >= 5 MiB (except final part). Keep a safe floor.
    chunk_mb = max(5, chunk_mb)

    return R2Settings(
        account_id=account_id,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        bucket=bucket,
        endpoint=endpoint,
        multipart_threshold_bytes=threshold_mb * 1024 * 1024,
        multipart_chunk_bytes=chunk_mb * 1024 * 1024,
    )


def reset_storage_caches() -> None:
    """Useful for tests and after local environment changes."""

    get_r2_settings.cache_clear()
    _r2_client.cache_clear()


@lru_cache(maxsize=1)
def _r2_client():
    settings = get_r2_settings()
    try:
        import boto3
        from botocore.config import Config
    except Exception as exc:  # pragma: no cover - covered by deployment smoke test
        raise NaveStorageError(
            "A dependência boto3 não está instalada. Atualize requirements.txt e reinicie a NAVE."
        ) from exc

    return boto3.client(
        service_name="s3",
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            connect_timeout=20,
            read_timeout=180,
            retries={"max_attempts": 5, "mode": "adaptive"},
        ),
    )


def r2_bucket_marker() -> str:
    return get_r2_settings().bucket_marker


def is_r2_bucket(bucket_name: str | None) -> bool:
    return str(bucket_name or "").strip().casefold().startswith(R2_BUCKET_PREFIX)


def _physical_r2_bucket(bucket_name: str | None = None) -> str:
    marker = str(bucket_name or "").strip()
    if marker.casefold().startswith(R2_BUCKET_PREFIX):
        explicit = marker[len(R2_BUCKET_PREFIX) :].strip()
        if explicit:
            return explicit
    return get_r2_settings().bucket


def _normalise_key(value: str) -> str:
    key = str(value or "").replace("\\", "/").strip().lstrip("/")
    key = re.sub(r"/{2,}", "/", key)
    if not key or key in {".", ".."}:
        raise NaveStorageError("O caminho do arquivo no Storage está vazio ou inválido.")
    if any(part == ".." for part in key.split("/")):
        raise NaveStorageError("O caminho do arquivo no Storage contém navegação inválida.")
    return key


def verify_r2_access() -> dict[str, Any]:
    """Validate credentials/bucket without writing an object."""

    settings = get_r2_settings()
    try:
        response = _r2_client().list_objects_v2(Bucket=settings.bucket, MaxKeys=1)
    except Exception as exc:
        raise NaveStorageError(
            "A NAVE não conseguiu acessar o bucket privado do Cloudflare R2. "
            "Confira R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY e R2_BUCKET."
        ) from exc
    return {
        "provider": R2_PROVIDER,
        "bucket": settings.bucket,
        "bucket_marker": settings.bucket_marker,
        "reachable": True,
        "objects_sampled": len(response.get("Contents") or []),
    }


def put_bytes(
    *,
    path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    cache_control: str | None = None,
    sha256: str | None = None,
    logical_kind: str | None = None,
) -> dict[str, Any]:
    """Write a new object to R2 and verify its SHA-256 metadata.

    ``put_object`` is used for smaller objects. Files at/above the configured
    threshold use boto3's multipart transfer manager, which resumes/retries parts
    independently inside the request lifecycle.
    """

    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data precisa ser bytes.")
    payload = bytes(data)
    if not payload:
        raise NaveStorageError("O arquivo está vazio.")
    if len(payload) > MAX_OBJECT_BYTES:
        raise NaveStorageError("O arquivo ultrapassa o limite máximo suportado pelo R2.")

    settings = get_r2_settings()
    key = _normalise_key(path)
    digest = str(sha256 or "").strip().lower() or hashlib.sha256(payload).hexdigest()
    metadata = {"sha256": digest, "nave-provider": R2_PROVIDER}
    if logical_kind:
        # R2/S3 user metadata values must be ASCII-friendly. Keep only a safe subset.
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(logical_kind)).strip("-")[:80]
        if cleaned:
            metadata["nave-kind"] = cleaned

    extra_args: dict[str, Any] = {
        "ContentType": str(content_type or "application/octet-stream"),
        "Metadata": metadata,
    }
    if cache_control:
        extra_args["CacheControl"] = str(cache_control)

    s3 = _r2_client()
    multipart = len(payload) >= settings.multipart_threshold_bytes
    try:
        if multipart:
            from boto3.s3.transfer import TransferConfig

            config = TransferConfig(
                multipart_threshold=settings.multipart_threshold_bytes,
                multipart_chunksize=settings.multipart_chunk_bytes,
                max_concurrency=4,
                use_threads=True,
            )
            s3.upload_fileobj(
                io.BytesIO(payload),
                settings.bucket,
                key,
                ExtraArgs=extra_args,
                Config=config,
            )
        else:
            s3.put_object(Bucket=settings.bucket, Key=key, Body=payload, **extra_args)

        head = s3.head_object(Bucket=settings.bucket, Key=key)
        stored_digest = str((head.get("Metadata") or {}).get("sha256") or "").strip().lower()
        stored_size = int(head.get("ContentLength") or 0)
        if stored_digest != digest or stored_size != len(payload):
            try:
                s3.delete_object(Bucket=settings.bucket, Key=key)
            finally:
                raise NaveStorageError(
                    "O R2 recebeu o arquivo, mas a verificação de integridade não conferiu. "
                    "O objeto inconsistente foi removido."
                )
    except NaveStorageError:
        raise
    except Exception as exc:
        raise NaveStorageError(
            "A NAVE não conseguiu gravar o arquivo no Cloudflare R2. "
            "Confira as credenciais, permissões do token e o bucket configurado."
        ) from exc

    return {
        "provider": R2_PROVIDER,
        "storage_bucket": settings.bucket_marker,
        "storage_path": key,
        "sha256": digest,
        "size_bytes": len(payload),
        "multipart": multipart,
    }


def get_bytes(
    client: Any,
    *,
    bucket_name: str | None,
    path: str | None,
) -> bytes | None:
    """Read R2 objects and transparently fall back to legacy Supabase Storage."""

    key = str(path or "").strip()
    bucket = str(bucket_name or "").strip()
    if not key:
        return None

    if is_r2_bucket(bucket):
        try:
            response = _r2_client().get_object(
                Bucket=_physical_r2_bucket(bucket), Key=_normalise_key(key)
            )
            body = response.get("Body")
            return body.read() if body is not None else None
        except Exception as exc:
            raise NaveStorageError("A NAVE não conseguiu baixar o arquivo do R2.") from exc

    if not bucket or client is None or not hasattr(client, "storage"):
        return None
    try:
        data = client.storage.from_(bucket).download(key)
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        if hasattr(data, "read"):
            return data.read()
    except Exception:
        return None
    return None


def create_signed_url(
    client: Any,
    *,
    bucket_name: str | None,
    path: str | None,
    expires_in: int = 3600,
    download: bool = False,
) -> str | None:
    key = str(path or "").strip()
    bucket = str(bucket_name or "").strip()
    if not key:
        return None

    if is_r2_bucket(bucket):
        params: dict[str, Any] = {
            "Bucket": _physical_r2_bucket(bucket),
            "Key": _normalise_key(key),
        }
        # We deliberately do not force Content-Disposition here because many callers
        # use the same URL for inline preview. The UI can still download the response.
        try:
            return _r2_client().generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=max(1, min(int(expires_in), 604800)),
            )
        except Exception:
            return None

    if not bucket or client is None or not hasattr(client, "storage"):
        return None
    try:
        storage = client.storage.from_(bucket)
        if download:
            response = storage.create_signed_url(key, expires_in, {"download": True})
        else:
            response = storage.create_signed_url(key, expires_in)
    except Exception:
        return None

    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
    return (
        getattr(response, "signedURL", None)
        or getattr(response, "signedUrl", None)
        or getattr(response, "signed_url", None)
    )


def delete_objects(
    client: Any,
    *,
    bucket_name: str | None,
    paths: Iterable[str],
) -> None:
    unique = list(
        dict.fromkeys(_normalise_key(path) for path in paths if str(path or "").strip())
    )
    if not unique:
        return

    bucket = str(bucket_name or "").strip()
    if is_r2_bucket(bucket):
        s3 = _r2_client()
        physical = _physical_r2_bucket(bucket)
        for start in range(0, len(unique), 1000):
            chunk = unique[start : start + 1000]
            try:
                response = s3.delete_objects(
                    Bucket=physical,
                    Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
                )
                errors = response.get("Errors") or []
                if errors:
                    raise NaveStorageError(
                        f"O R2 recusou a exclusão de {len(errors)} objeto(s)."
                    )
            except NaveStorageError:
                raise
            except Exception as exc:
                raise NaveStorageError("A NAVE não conseguiu excluir arquivo(s) do R2.") from exc
        return

    if not bucket or client is None or not hasattr(client, "storage"):
        return
    client.storage.from_(bucket).remove(unique)


def object_exists(
    client: Any,
    *,
    bucket_name: str | None,
    path: str | None,
) -> bool:
    key = str(path or "").strip()
    bucket = str(bucket_name or "").strip()
    if not key:
        return False
    if is_r2_bucket(bucket):
        try:
            _r2_client().head_object(
                Bucket=_physical_r2_bucket(bucket), Key=_normalise_key(key)
            )
            return True
        except Exception:
            return False
    if not bucket or client is None or not hasattr(client, "storage"):
        return False
    try:
        # Supabase has no consistent HEAD wrapper across storage3 versions; a signed
        # URL is sufficient as a lightweight compatibility check.
        return bool(create_signed_url(client, bucket_name=bucket, path=key, expires_in=30))
    except Exception:
        return False
