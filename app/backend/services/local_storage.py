"""
Local disk storage backend — drop-in replacement for the platform OSS service.

Used when OSS_SERVICE_URL / OSS_API_KEY are not configured. Files are stored under
``app/backend/storage/<bucket>/<object_key>``. Upload/download "URLs" point to the
local blob endpoints (PUT/GET /api/v1/storage/blob/...), which the web-sdk calls
directly the same way it would call a presigned cloud URL.
"""

import hashlib
import hmac
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from schemas.storage import (
    BucketInfo,
    BucketListResponse,
    BucketRequest,
    BucketResponse,
    DeleteResponse,
    FileUpDownRequest,
    FileUpDownResponse,
    ObjectInfo,
    ObjectListResponse,
    ObjectRequest,
    OSSBaseModel,
    RenameRequest,
    RenameResponse,
)

logger = logging.getLogger(__name__)

# Overridable via env (STORAGE_ROOT) so les déploiements peuvent pointer vers un
# volume persistant. Par défaut : app/backend/storage (dev local).
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT") or (Path(__file__).resolve().parent.parent / "storage"))
BLOB_URL_PREFIX = "/api/v1/storage/blob"

# Durée de validité d'une URL de blob signée (1 h). Suffisant : le frontend demande une
# URL fraîche via /upload-url ou /download-url (endpoints authentifiés) juste avant usage.
BLOB_URL_TTL_SECONDS = 3600


def _signing_key() -> bytes:
    """Clé HMAC pour signer les URLs de blob. Réutilise le secret JWT (déjà requis en prod)."""
    key = os.environ.get("STORAGE_SIGNING_KEY") or os.environ.get("JWT_SECRET_KEY") or ""
    return key.encode()


def _sign_blob(method: str, bucket: str, key: str, exp: int) -> str:
    """Calcule la signature HMAC-SHA256 liant méthode + bucket + clé + expiration."""
    msg = f"{method.upper()}\n{bucket}\n{key}\n{exp}".encode()
    return hmac.new(_signing_key(), msg, hashlib.sha256).hexdigest()


def build_signed_blob_url(method: str, bucket: str, key: str, ttl: int = BLOB_URL_TTL_SECONDS) -> str:
    """Construit une URL de blob signée et à durée limitée (bucket/clé déjà assainis)."""
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=ttl)).timestamp())
    sig = _sign_blob(method, bucket, key, exp)
    return f"{BLOB_URL_PREFIX}/{bucket}/{key}?exp={exp}&sig={sig}"


def verify_blob_signature(method: str, bucket: str, key: str, exp: Optional[str], sig: Optional[str]) -> bool:
    """Vérifie la signature et l'expiration d'une URL de blob (assainit bucket/clé comme à la génération)."""
    if not exp or not sig or not _signing_key():
        return False
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_int < int(datetime.now(timezone.utc).timestamp()):
        return False
    expected = _sign_blob(method, sanitize_bucket(bucket), sanitize_key(key), exp_int)
    return hmac.compare_digest(expected, sig)


def sanitize_bucket(name: str) -> str:
    """Sanitize a bucket name to safe filesystem characters."""
    safe = re.sub(r"[^a-z0-9-]", "-", (name or "").lower()).strip("-")
    return safe or "default"


def sanitize_key(key: str) -> str:
    """Sanitize an object key to its safe base name (no path traversal)."""
    base = Path((key or "").strip()).name
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", base)
    return safe[:255] or "file"


def _far_future() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()


def resolve_blob_path(bucket: str, object_key: str) -> Path:
    """Resolve and validate the on-disk path for a blob (guards against traversal)."""
    bucket_dir = (STORAGE_ROOT / sanitize_bucket(bucket)).resolve()
    path = (bucket_dir / sanitize_key(object_key)).resolve()
    if not str(path).startswith(str(bucket_dir)):
        raise ValueError("Invalid object path")
    return path


class LocalStorageService:
    """File-system implementation of the storage API used by the frontend."""

    def __init__(self):
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    async def create_bucket(self, request: BucketRequest) -> BucketResponse:
        (STORAGE_ROOT / sanitize_bucket(request.bucket_name)).mkdir(parents=True, exist_ok=True)
        return BucketResponse(
            bucket_name=request.bucket_name,
            visibility=request.visibility,
            created_at=_far_future(),
        )

    async def list_buckets(self) -> BucketListResponse:
        resp = BucketListResponse()
        if STORAGE_ROOT.exists():
            for d in STORAGE_ROOT.iterdir():
                if d.is_dir():
                    resp.buckets.append(BucketInfo(bucket_name=d.name, visibility="private"))
        return resp

    async def list_objects(self, request: OSSBaseModel) -> ObjectListResponse:
        resp = ObjectListResponse()
        bucket_dir = STORAGE_ROOT / sanitize_bucket(request.bucket_name)
        if bucket_dir.exists():
            for f in bucket_dir.iterdir():
                if f.is_file():
                    stat = f.stat()
                    resp.objects.append(
                        ObjectInfo(
                            bucket_name=request.bucket_name,
                            object_key=f.name,
                            size=stat.st_size,
                            last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                            etag="",
                        )
                    )
        return resp

    async def get_object_info(self, request: ObjectRequest) -> ObjectInfo:
        path = resolve_blob_path(request.bucket_name, request.object_key)
        if not path.is_file():
            raise ValueError("Object not found")
        stat = path.stat()
        return ObjectInfo(
            bucket_name=request.bucket_name,
            object_key=path.name,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            etag="",
        )

    async def rename_object(self, request: RenameRequest) -> RenameResponse:
        src = resolve_blob_path(request.bucket_name, request.source_key)
        dst = resolve_blob_path(request.bucket_name, request.target_key)
        if not src.is_file():
            raise ValueError("Source object not found")
        if dst.exists() and not request.overwrite_key:
            raise ValueError("Target already exists")
        src.rename(dst)
        return RenameResponse(success=True)

    async def delete_object(self, request: ObjectRequest) -> DeleteResponse:
        path = resolve_blob_path(request.bucket_name, request.object_key)
        if path.is_file():
            path.unlink()
        return DeleteResponse(success=True)

    async def create_upload_url(self, request: FileUpDownRequest) -> FileUpDownResponse:
        bucket = sanitize_bucket(request.bucket_name)
        key = sanitize_key(request.object_key)
        (STORAGE_ROOT / bucket).mkdir(parents=True, exist_ok=True)
        upload_url = build_signed_blob_url("PUT", bucket, key)
        download_url = build_signed_blob_url("GET", bucket, key)
        return FileUpDownResponse(upload_url=upload_url, download_url=download_url, expires_at=_far_future())

    async def create_download_url(self, request: FileUpDownRequest) -> FileUpDownResponse:
        bucket = sanitize_bucket(request.bucket_name)
        key = sanitize_key(request.object_key)
        download_url = build_signed_blob_url("GET", bucket, key)
        return FileUpDownResponse(upload_url=download_url, download_url=download_url, expires_at=_far_future())


def save_blob(bucket: str, object_key: str, data: bytes) -> int:
    """Persist raw bytes for a blob and return the number of bytes written."""
    path = resolve_blob_path(bucket, object_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data)


def read_blob_path(bucket: str, object_key: str) -> Optional[Path]:
    """Return the on-disk path for a blob if it exists, else None."""
    path = resolve_blob_path(bucket, object_key)
    return path if path.is_file() else None
