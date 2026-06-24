import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.job_offers import Job_offers

logger = logging.getLogger(__name__)


# ------------------ Service Layer ------------------
class Job_offersService:
    """Service layer for Job_offers operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any]) -> Optional[Job_offers]:
        """Create a new job_offers"""
        try:
            obj = Job_offers(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created job_offers with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating job_offers: {str(e)}")
            raise

    async def get_by_id(self, obj_id: int) -> Optional[Job_offers]:
        """Get job_offers by ID"""
        try:
            query = select(Job_offers).where(Job_offers.id == obj_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching job_offers {obj_id}: {str(e)}")
            raise

    async def get_list(
        self, 
        skip: int = 0, 
        limit: int = 20, 
        query_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of job_offerss"""
        try:
            query = select(Job_offers)
            count_query = select(func.count(Job_offers.id))
            
            if query_dict:
                for field, value in query_dict.items():
                    if hasattr(Job_offers, field):
                        query = query.where(getattr(Job_offers, field) == value)
                        count_query = count_query.where(getattr(Job_offers, field) == value)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            if sort:
                if sort.startswith('-'):
                    field_name = sort[1:]
                    if hasattr(Job_offers, field_name):
                        query = query.order_by(getattr(Job_offers, field_name).desc())
                else:
                    if hasattr(Job_offers, sort):
                        query = query.order_by(getattr(Job_offers, sort))
            else:
                query = query.order_by(Job_offers.id.desc())

            result = await self.db.execute(query.offset(skip).limit(limit))
            items = result.scalars().all()

            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching job_offers list: {str(e)}")
            raise

    async def update(self, obj_id: int, update_data: Dict[str, Any]) -> Optional[Job_offers]:
        """Update job_offers"""
        try:
            obj = await self.get_by_id(obj_id)
            if not obj:
                logger.warning(f"Job_offers {obj_id} not found for update")
                return None
            for key, value in update_data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)

            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Updated job_offers {obj_id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating job_offers {obj_id}: {str(e)}")
            raise

    async def delete(self, obj_id: int) -> bool:
        """Delete job_offers"""
        try:
            obj = await self.get_by_id(obj_id)
            if not obj:
                logger.warning(f"Job_offers {obj_id} not found for deletion")
                return False
            await self.db.delete(obj)
            await self.db.commit()
            logger.info(f"Deleted job_offers {obj_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting job_offers {obj_id}: {str(e)}")
            raise

    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[Job_offers]:
        """Get job_offers by any field"""
        try:
            if not hasattr(Job_offers, field_name):
                raise ValueError(f"Field {field_name} does not exist on Job_offers")
            result = await self.db.execute(
                select(Job_offers).where(getattr(Job_offers, field_name) == field_value)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching job_offers by {field_name}: {str(e)}")
            raise

    async def list_by_field(
        self, field_name: str, field_value: Any, skip: int = 0, limit: int = 20
    ) -> List[Job_offers]:
        """Get list of job_offerss filtered by field"""
        try:
            if not hasattr(Job_offers, field_name):
                raise ValueError(f"Field {field_name} does not exist on Job_offers")
            result = await self.db.execute(
                select(Job_offers)
                .where(getattr(Job_offers, field_name) == field_value)
                .offset(skip)
                .limit(limit)
                .order_by(Job_offers.id.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching job_offerss by {field_name}: {str(e)}")
            raise