import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.job_offers import Job_offersService
from dependencies.auth import get_admin_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/job_offers", tags=["job_offers"])


# ---------- Pydantic Schemas ----------
class Job_offersData(BaseModel):
    """Entity data schema (for create/update)"""
    title: str
    company: str
    location: str = None
    contract_type: str = None
    sector: str = None
    description: str = None
    requirements: str = None
    salary_range: str = None
    source: str = None
    source_url: str = None
    posted_date: str = None
    valid_through: str = None
    is_active: bool = None


class Job_offersUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    posted_date: Optional[str] = None
    valid_through: Optional[str] = None
    is_active: Optional[bool] = None


class Job_offersResponse(BaseModel):
    """Entity response schema"""
    id: int
    title: str
    company: str
    location: Optional[str] = None
    contract_type: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    posted_date: Optional[str] = None
    valid_through: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Job_offersListResponse(BaseModel):
    """List response schema"""
    items: List[Job_offersResponse]
    total: int
    skip: int
    limit: int


class Job_offersBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Job_offersData]


class Job_offersBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Job_offersUpdateData


class Job_offersBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Job_offersBatchUpdateItem]


class Job_offersBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Job_offersListResponse)
async def query_job_offerss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    """Query job_offerss with filtering, sorting, and pagination"""
    logger.debug(f"Querying job_offerss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Job_offersService(db)
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
        )
        logger.debug(f"Found {result['total']} job_offerss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying job_offerss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Job_offersListResponse)
async def query_job_offerss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query job_offerss with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying job_offerss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Job_offersService(db)
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
        logger.debug(f"Found {result['total']} job_offerss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying job_offerss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Job_offersResponse)
async def get_job_offers(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    """Get a single job_offers by ID"""
    logger.debug(f"Fetching job_offers with id: {id}, fields={fields}")
    
    service = Job_offersService(db)
    try:
        result = await service.get_by_id(id)
        if not result:
            logger.warning(f"Job_offers with id {id} not found")
            raise HTTPException(status_code=404, detail="Job_offers not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job_offers {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Job_offersResponse, status_code=201)
async def create_job_offers(
    data: Job_offersData,
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new job_offers (admin uniquement)"""
    logger.debug(f"Creating new job_offers with data: {data}")
    
    service = Job_offersService(db)
    try:
        result = await service.create(data.model_dump())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create job_offers")
        
        logger.info(f"Job_offers created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating job_offers: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating job_offers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Job_offersResponse], status_code=201)
async def create_job_offerss_batch(
    request: Job_offersBatchCreateRequest,
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple job_offerss in a single request (admin uniquement)"""
    logger.debug(f"Batch creating {len(request.items)} job_offerss")
    
    service = Job_offersService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump())
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} job_offerss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Job_offersResponse])
async def update_job_offerss_batch(
    request: Job_offersBatchUpdateRequest,
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple job_offerss in a single request (admin uniquement)"""
    logger.debug(f"Batch updating {len(request.items)} job_offerss")
    
    service = Job_offersService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict)
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} job_offerss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Job_offersResponse)
async def update_job_offers(
    id: int,
    data: Job_offersUpdateData,
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing job_offers (admin uniquement)"""
    logger.debug(f"Updating job_offers {id} with data: {data}")

    service = Job_offersService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict)
        if not result:
            logger.warning(f"Job_offers with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Job_offers not found")
        
        logger.info(f"Job_offers {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating job_offers {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating job_offers {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_job_offerss_batch(
    request: Job_offersBatchDeleteRequest,
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple job_offerss by their IDs (admin uniquement)"""
    logger.debug(f"Batch deleting {len(request.ids)} job_offerss")
    
    service = Job_offersService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id)
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} job_offerss successfully")
        return {"message": f"Successfully deleted {deleted_count} job_offerss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_job_offers(
    id: int,
    current_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single job_offers by ID (admin uniquement)"""
    logger.debug(f"Deleting job_offers with id: {id}")
    
    service = Job_offersService(db)
    try:
        success = await service.delete(id)
        if not success:
            logger.warning(f"Job_offers with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Job_offers not found")
        
        logger.info(f"Job_offers {id} deleted successfully")
        return {"message": "Job_offers deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job_offers {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")