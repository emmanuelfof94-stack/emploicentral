"""
Local disk storage backend — drop-in replacement for the platform OSS service.

Used when OSS_SERVICE_URL / OSS_API_KEY are not configured. Files are stored under
``app/backend/storage/<bucket>/<object_key>``. Upload/download "URLs" point to the
local blob endpoints (PUT/GET /api/v1/storage/blob/...), which the web-sdk calls
directly the same way it would call a presigned cloud URL.
"""

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
        url = f"{BLOB_URL_PREFIX}/{bucket}/{key}"
        return FileUpDownResponse(upload_url=url, download_url=url, expires_at=_far_future())

    async def create_download_url(self, request: FileUpDownRequest) -> FileUpDownResponse:
        bucket = sanitize_bucket(request.bucket_name)
        key = sanitize_key(request.object_key)
        url = f"{BLOB_URL_PREFIX}/{bucket}/{key}"
        return FileUpDownResponse(upload_url=url, download_url=url, expires_at=_far_future())


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
