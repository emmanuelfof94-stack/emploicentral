import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.alert_preferences import Alert_preferencesService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/alert_preferences", tags=["alert_preferences"])


# ---------- Pydantic Schemas ----------
class Alert_preferencesData(BaseModel):
    """Entity data schema (for create/update)"""
    notify_email: bool = None
    notify_whatsapp: bool = None
    notify_push: bool = None
    min_score: int = None
    sectors: str = None
    locations: str = None
    contract_types: str = None
    min_salary: int = None
    keywords: str = None
    is_active: bool = None


class Alert_preferencesUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    notify_email: Optional[bool] = None
    notify_whatsapp: Optional[bool] = None
    notify_push: Optional[bool] = None
    min_score: Optional[int] = None
    sectors: Optional[str] = None
    locations: Optional[str] = None
    contract_types: Optional[str] = None
    min_salary: Optional[int] = None
    keywords: Optional[str] = None
    is_active: Optional[bool] = None


class Alert_preferencesResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    notify_email: Optional[bool] = None
    notify_whatsapp: Optional[bool] = None
    notify_push: Optional[bool] = None
    min_score: Optional[int] = None
    sectors: Optional[str] = None
    locations: Optional[str] = None
    contract_types: Optional[str] = None
    min_salary: Optional[int] = None
    keywords: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Alert_preferencesListResponse(BaseModel):
    """List response schema"""
    items: List[Alert_preferencesResponse]
    total: int
    skip: int
    limit: int


class Alert_preferencesBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Alert_preferencesData]


class Alert_preferencesBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Alert_preferencesUpdateData


class Alert_preferencesBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Alert_preferencesBatchUpdateItem]


class Alert_preferencesBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Alert_preferencesListResponse)
async def query_alert_preferencess(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query alert_preferencess with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying alert_preferencess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Alert_preferencesService(db)
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
        logger.debug(f"Found {result['total']} alert_preferencess")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying alert_preferencess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Alert_preferencesListResponse)
async def query_alert_preferencess_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query alert_preferencess with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying alert_preferencess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Alert_preferencesService(db)
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
        logger.debug(f"Found {result['total']} alert_preferencess")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying alert_preferencess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Alert_preferencesResponse)
async def get_alert_preferences(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single alert_preferences by ID (user can only see their own records)"""
    logger.debug(f"Fetching alert_preferences with id: {id}, fields={fields}")
    
    service = Alert_preferencesService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Alert_preferences with id {id} not found")
            raise HTTPException(status_code=404, detail="Alert_preferences not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching alert_preferences {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Alert_preferencesResponse, status_code=201)
async def create_alert_preferences(
    data: Alert_preferencesData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert_preferences"""
    logger.debug(f"Creating new alert_preferences with data: {data}")
    
    service = Alert_preferencesService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create alert_preferences")
        
        logger.info(f"Alert_preferences created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating alert_preferences: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating alert_preferences: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Alert_preferencesResponse], status_code=201)
async def create_alert_preferencess_batch(
    request: Alert_preferencesBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple alert_preferencess in a single request"""
    logger.debug(f"Batch creating {len(request.items)} alert_preferencess")
    
    service = Alert_preferencesService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} alert_preferencess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Alert_preferencesResponse])
async def update_alert_preferencess_batch(
    request: Alert_preferencesBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple alert_preferencess in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} alert_preferencess")
    
    service = Alert_preferencesService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} alert_preferencess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Alert_preferencesResponse)
async def update_alert_preferences(
    id: int,
    data: Alert_preferencesUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing alert_preferences (requires ownership)"""
    logger.debug(f"Updating alert_preferences {id} with data: {data}")

    service = Alert_preferencesService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Alert_preferences with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Alert_preferences not found")
        
        logger.info(f"Alert_preferences {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating alert_preferences {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating alert_preferences {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_alert_preferencess_batch(
    request: Alert_preferencesBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple alert_preferencess by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} alert_preferencess")
    
    service = Alert_preferencesService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} alert_preferencess successfully")
        return {"message": f"Successfully deleted {deleted_count} alert_preferencess", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_alert_preferences(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single alert_preferences by ID (requires ownership)"""
    logger.debug(f"Deleting alert_preferences with id: {id}")
    
    service = Alert_preferencesService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Alert_preferences with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Alert_preferences not found")
        
        logger.info(f"Alert_preferences {id} deleted successfully")
        return {"message": "Alert_preferences deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert_preferences {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")