import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.user_profiles import User_profilesService
from dependencies.auth import get_current_user, get_admin_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/user_profiles", tags=["user_profiles"])


# ---------- Pydantic Schemas ----------
class User_profilesData(BaseModel):
    """Entity data schema (for create/update)"""
    full_name: str = None
    email: str = None
    phone: str = None
    skills: str = None
    experience_years: int = None
    education: str = None
    sector: str = None
    job_title: str = None
    location: str = None
    cv_object_key: str = None
    cv_analyzed: bool = None
    profile_summary: str = None


class User_profilesUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[int] = None
    education: Optional[str] = None
    sector: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    cv_object_key: Optional[str] = None
    cv_analyzed: Optional[bool] = None
    profile_summary: Optional[str] = None


class User_profilesResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[int] = None
    education: Optional[str] = None
    sector: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    cv_object_key: Optional[str] = None
    cv_analyzed: Optional[bool] = None
    profile_summary: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class User_profilesListResponse(BaseModel):
    """List response schema"""
    items: List[User_profilesResponse]
    total: int
    skip: int
    limit: int


class User_profilesBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[User_profilesData]


class User_profilesBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: User_profilesUpdateData


class User_profilesBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[User_profilesBatchUpdateItem]


class User_profilesBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=User_profilesListResponse)
async def query_user_profiless(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query user_profiless with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying user_profiless: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = User_profilesService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")
        
        result = await service.get_list(
            skip=skip, 
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=str(current_user.id),
        )
        logger.debug(f"Found {result['total']} user_profiless")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying user_profiless: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=User_profilesListResponse)
async def query_user_profiless_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    # Query user_profiless with filtering, sorting, and pagination without user limitation
    # SECURITE: réservé aux administrateurs — expose les profils de TOUS les utilisateurs (données perso)
    logger.debug(f"Querying user_profiless: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = User_profilesService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")

        result = await service.get_list(
            skip=skip,
            limit=limit,
            query_dict=query_dict,
            sort=sort
        )
        logger.debug(f"Found {result['total']} user_profiless")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying user_profiless: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=User_profilesResponse)
async def get_user_profiles(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single user_profiles by ID (user can only see their own records)"""
    logger.debug(f"Fetching user_profiles with id: {id}, fields={fields}")
    
    service = User_profilesService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"User_profiles with id {id} not found")
            raise HTTPException(status_code=404, detail="User_profiles not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user_profiles {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=User_profilesResponse, status_code=201)
async def create_user_profiles(
    data: User_profilesData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user_profiles"""
    logger.debug(f"Creating new user_profiles with data: {data}")
    
    service = User_profilesService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create user_profiles")
        
        logger.info(f"User_profiles created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating user_profiles: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating user_profiles: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[User_profilesResponse], status_code=201)
async def create_user_profiless_batch(
    request: User_profilesBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple user_profiless in a single request"""
    logger.debug(f"Batch creating {len(request.items)} user_profiless")
    
    service = User_profilesService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} user_profiless successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[User_profilesResponse])
async def update_user_profiless_batch(
    request: User_profilesBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple user_profiless in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} user_profiless")
    
    service = User_profilesService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} user_profiless successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=User_profilesResponse)
async def update_user_profiles(
    id: int,
    data: User_profilesUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing user_profiles (requires ownership)"""
    logger.debug(f"Updating user_profiles {id} with data: {data}")

    service = User_profilesService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"User_profiles with id {id} not found for update")
            raise HTTPException(status_code=404, detail="User_profiles not found")
        
        logger.info(f"User_profiles {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating user_profiles {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user_profiles {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_user_profiless_batch(
    request: User_profilesBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple user_profiless by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} user_profiless")
    
    service = User_profilesService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} user_profiless successfully")
        return {"message": f"Successfully deleted {deleted_count} user_profiless", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_user_profiles(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single user_profiles by ID (requires ownership)"""
    logger.debug(f"Deleting user_profiles with id: {id}")
    
    service = User_profilesService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"User_profiles with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="User_profiles not found")
        
        logger.info(f"User_profiles {id} deleted successfully")
        return {"message": "User_profiles deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user_profiles {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")