import logging

from core.config import settings
from dependencies.auth import get_admin_user, get_current_user
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from schemas.auth import UserResponse
from schemas.storage import (
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
from services import local_storage
from services.local_storage import LocalStorageService
from services.storage import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])

# Max blob upload size (10 MB) — enough for CV PDFs.
MAX_BLOB_BYTES = 10 * 1024 * 1024


def get_storage_service():
    """Return the platform OSS service if configured, else the local-disk backend."""
    if getattr(settings, "oss_service_url", "") and getattr(settings, "oss_api_key", ""):
        return StorageService()
    return LocalStorageService()


@router.post("/create-bucket", response_model=BucketResponse)
async def create_bucket(request: BucketRequest, _current_user: UserResponse = Depends(get_admin_user)):
    """
    Create a new bucket
    """
    try:
        service = get_storage_service()
        return await service.create_bucket(request)
    except ValueError as e:
        logger.error(f"Invalid create bucket request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create bucket: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.get("/list-buckets", response_model=BucketListResponse)
async def list_buckets(_current_user: UserResponse = Depends(get_current_user)):
    """
    List buckets of the user
    """
    try:
        service = get_storage_service()
        return await service.list_buckets()
    except ValueError as e:
        logger.error(f"Invalid list buckets request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list buckets: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.get("/list-objects", response_model=ObjectListResponse)
async def list_objects(request: OSSBaseModel = Depends(), _current_user: UserResponse = Depends(get_current_user)):
    """
    List objects under the bucket
    """
    try:
        service = get_storage_service()
        return await service.list_objects(request)
    except ValueError as e:
        logger.error(f"Invalid list objects request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list objects: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.get("/get-object-info", response_model=ObjectInfo)
async def get_object_info(request: ObjectRequest = Depends(), _current_user: UserResponse = Depends(get_current_user)):
    """
    Get object metadata from the bucket
    """
    try:
        service = get_storage_service()
        return await service.get_object_info(request)
    except ValueError as e:
        logger.error(f"Invalid get object metadata request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get object metadata: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.post("/rename-object", response_model=RenameResponse)
async def rename_object(request: RenameRequest, _current_user: UserResponse = Depends(get_current_user)):
    """
    Rename object inside the bucket
    """
    try:
        service = get_storage_service()
        return await service.rename_object(request)
    except ValueError as e:
        logger.error(f"Invalid rename object: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rename object: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.delete("/delete-object", response_model=DeleteResponse)
async def delete_object(request: ObjectRequest, _current_user: UserResponse = Depends(get_current_user)):
    """
    Delete object inside the bucket
    """
    try:
        service = get_storage_service()
        return await service.delete_object(request)
    except ValueError as e:
        logger.error(f"Invalid delete object: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete object: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.post("/upload-url", response_model=FileUpDownResponse)
async def upload_file(request: FileUpDownRequest, _current_user: UserResponse = Depends(get_current_user)):
    """
    Get a presigned URL for uploading a file to StorageService.

    Steps:
    1. Client calls this endpoint with file details
    2. Server validates and calls OSS service
    3. Returns presigned URL and access_url from OSS service
    4. Client uploads file directly to ObjectStorage using the presigned URL
    5. File is accessible at the returned access_url
    """
    try:
        service = get_storage_service()
        return await service.create_upload_url(request)
    except ValueError as e:
        logger.error(f"Invalid upload request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


@router.post("/download-url", response_model=FileUpDownResponse)
async def download_file(request: FileUpDownRequest, _current_user: UserResponse = Depends(get_current_user)):
    """
    Get a presigned URL for downloading a file to StorageService.
    """
    try:
        service = get_storage_service()
        return await service.create_download_url(request)
    except ValueError as e:
        logger.error(f"Invalid download request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


# --- Local blob endpoints (used only by the local-disk backend) ---
# These mimic cloud "presigned URLs": the web-sdk PUTs/GETs the file directly with no
# Authorization header. L'accès est autorisé par une SIGNATURE à durée limitée (HMAC)
# présente dans l'URL, émise uniquement par /upload-url et /download-url (authentifiés).
# La sécurité repose donc sur : signature valide + non expirée + assainissement du chemin.


@router.put("/blob/{bucket}/{object_key:path}")
async def put_blob(bucket: str, object_key: str, request: Request):
    """Receive a raw file body and store it on local disk (URL signée requise)."""
    if not local_storage.verify_blob_signature(
        "PUT", bucket, object_key, request.query_params.get("exp"), request.query_params.get("sig")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lien d'envoi invalide ou expiré")
    body = await request.body()
    if len(body) > MAX_BLOB_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux (10 Mo max).",
        )
    try:
        size = local_storage.save_blob(bucket, object_key, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True, "size": size}


@router.get("/blob/{bucket}/{object_key:path}")
async def get_blob(bucket: str, object_key: str, request: Request):
    """Serve a stored file from local disk (URL signée requise)."""
    if not local_storage.verify_blob_signature(
        "GET", bucket, object_key, request.query_params.get("exp"), request.query_params.get("sig")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lien de téléchargement invalide ou expiré")
    try:
        path = local_storage.read_blob_path(bucket, object_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier introuvable")
    return FileResponse(path, filename=path.name)
