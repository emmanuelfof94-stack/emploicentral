import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert_preferences import Alert_preferences

logger = logging.getLogger(__name__)


# ------------------ Service Layer ------------------
class Alert_preferencesService:
    """Service layer for Alert_preferences operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Alert_preferences]:
        """Create a new alert_preferences"""
        try:
            if user_id:
                data['user_id'] = user_id
            obj = Alert_preferences(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created alert_preferences with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating alert_preferences: {str(e)}")
            raise

    async def check_ownership(self, obj_id: int, user_id: str) -> bool:
        """Check if user owns this record"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            return obj is not None
        except Exception as e:
            logger.error(f"Error checking ownership for alert_preferences {obj_id}: {str(e)}")
            return False

    async def get_by_id(self, obj_id: int, user_id: Optional[str] = None) -> Optional[Alert_preferences]:
        """Get alert_preferences by ID (user can only see their own records)"""
        try:
            query = select(Alert_preferences).where(Alert_preferences.id == obj_id)
            if user_id:
                query = query.where(Alert_preferences.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching alert_preferences {obj_id}: {str(e)}")
            raise

    async def get_list(
        self, 
        skip: int = 0, 
        limit: int = 20, 
        user_id: Optional[str] = None,
        query_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of alert_preferencess (user can only see their own records)"""
        try:
            query = select(Alert_preferences)
            count_query = select(func.count(Alert_preferences.id))
            
            if user_id:
                query = query.where(Alert_preferences.user_id == user_id)
                count_query = count_query.where(Alert_preferences.user_id == user_id)
            
            if query_dict:
                for field, value in query_dict.items():
                    if hasattr(Alert_preferences, field):
                        query = query.where(getattr(Alert_preferences, field) == value)
                        count_query = count_query.where(getattr(Alert_preferences, field) == value)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            if sort:
                if sort.startswith('-'):
                    field_name = sort[1:]
                    if hasattr(Alert_preferences, field_name):
                        query = query.order_by(getattr(Alert_preferences, field_name).desc())
                else:
                    if hasattr(Alert_preferences, sort):
                        query = query.order_by(getattr(Alert_preferences, sort))
            else:
                query = query.order_by(Alert_preferences.id.desc())

            result = await self.db.execute(query.offset(skip).limit(limit))
            items = result.scalars().all()

            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching alert_preferences list: {str(e)}")
            raise

    async def update(self, obj_id: int, update_data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Alert_preferences]:
        """Update alert_preferences (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Alert_preferences {obj_id} not found for update")
                return None
            for key, value in update_data.items():
                if hasattr(obj, key) and key != 'user_id':
                    setattr(obj, key, value)

            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Updated alert_preferences {obj_id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating alert_preferences {obj_id}: {str(e)}")
            raise

    async def delete(self, obj_id: int, user_id: Optional[str] = None) -> bool:
        """Delete alert_preferences (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Alert_preferences {obj_id} not found for deletion")
                return False
            await self.db.delete(obj)
            await self.db.commit()
            logger.info(f"Deleted alert_preferences {obj_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting alert_preferences {obj_id}: {str(e)}")
            raise

    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[Alert_preferences]:
        """Get alert_preferences by any field"""
        try:
            if not hasattr(Alert_preferences, field_name):
                raise ValueError(f"Field {field_name} does not exist on Alert_preferences")
            result = await self.db.execute(
                select(Alert_preferences).where(getattr(Alert_preferences, field_name) == field_value)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching alert_preferences by {field_name}: {str(e)}")
            raise

    async def list_by_field(
        self, field_name: str, field_value: Any, skip: int = 0, limit: int = 20
    ) -> List[Alert_preferences]:
        """Get list of alert_preferencess filtered by field"""
        try:
            if not hasattr(Alert_preferences, field_name):
                raise ValueError(f"Field {field_name} does not exist on Alert_preferences")
            result = await self.db.execute(
                select(Alert_preferences)
                .where(getattr(Alert_preferences, field_name) == field_value)
                .offset(skip)
                .limit(limit)
                .order_by(Alert_preferences.id.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching alert_preferencess by {field_name}: {str(e)}")
            raise