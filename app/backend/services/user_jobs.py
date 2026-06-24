import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_jobs import User_jobs

logger = logging.getLogger(__name__)


class User_jobsService:
    """Service layer for User_jobs (saved offers + application tracking)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[User_jobs]:
        try:
            if user_id:
                data["user_id"] = user_id
            obj = User_jobs(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating user_jobs: {e}")
            raise

    async def get_by_id(self, obj_id: int, user_id: Optional[str] = None) -> Optional[User_jobs]:
        query = select(User_jobs).where(User_jobs.id == obj_id)
        if user_id:
            query = query.where(User_jobs.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 200,
        user_id: Optional[str] = None,
        query_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        query = select(User_jobs)
        count_query = select(func.count(User_jobs.id))
        if user_id:
            query = query.where(User_jobs.user_id == user_id)
            count_query = count_query.where(User_jobs.user_id == user_id)
        if query_dict:
            for field, value in query_dict.items():
                if hasattr(User_jobs, field):
                    query = query.where(getattr(User_jobs, field) == value)
                    count_query = count_query.where(getattr(User_jobs, field) == value)

        total = (await self.db.execute(count_query)).scalar()
        query = query.order_by(User_jobs.updated_at.desc())
        result = await self.db.execute(query.offset(skip).limit(limit))
        return {"items": result.scalars().all(), "total": total, "skip": skip, "limit": limit}

    async def update(
        self, obj_id: int, update_data: Dict[str, Any], user_id: Optional[str] = None
    ) -> Optional[User_jobs]:
        obj = await self.get_by_id(obj_id, user_id=user_id)
        if not obj:
            return None
        for key, value in update_data.items():
            if hasattr(obj, key) and key not in ("user_id", "id"):
                setattr(obj, key, value)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj_id: int, user_id: Optional[str] = None) -> bool:
        obj = await self.get_by_id(obj_id, user_id=user_id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
