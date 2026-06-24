import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.user_jobs import User_jobsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/user_jobs", tags=["user_jobs"])


class User_jobsData(BaseModel):
    """Entity data schema (create/update)."""
    job_id: int = None
    saved: bool = None
    status: str = None


class User_jobsUpdateData(BaseModel):
    """Update entity data (partial)."""
    job_id: Optional[int] = None
    saved: Optional[bool] = None
    status: Optional[str] = None


class User_jobsResponse(BaseModel):
    id: int
    user_id: str
    job_id: Optional[int] = None
    saved: Optional[bool] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class User_jobsListResponse(BaseModel):
    items: List[User_jobsResponse]
    total: int
    skip: int
    limit: int


@router.get("", response_model=User_jobsListResponse)
async def query_user_jobs(
    query: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = User_jobsService(db)
    query_dict = None
    if query:
        try:
            query_dict = json.loads(query)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid query JSON format")
    result = await service.get_list(
        skip=skip, limit=limit, user_id=str(current_user.id), query_dict=query_dict
    )
    return result


@router.post("", response_model=User_jobsResponse, status_code=201)
async def create_user_jobs(
    data: User_jobsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = User_jobsService(db)
    result = await service.create(data.model_dump(exclude_none=True), user_id=str(current_user.id))
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create record")
    return result


@router.put("/{id}", response_model=User_jobsResponse)
async def update_user_jobs(
    id: int,
    data: User_jobsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = User_jobsService(db)
    result = await service.update(
        id, data.model_dump(exclude_none=True), user_id=str(current_user.id)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Record not found")
    return result


@router.delete("/{id}")
async def delete_user_jobs(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = User_jobsService(db)
    ok = await service.delete(id, user_id=str(current_user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"success": True}
