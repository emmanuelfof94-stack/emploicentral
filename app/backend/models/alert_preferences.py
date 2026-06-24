from core.database import Base
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class Alert_preferences(Base):
    __tablename__ = "alert_preferences"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    notify_email = Column(Boolean, nullable=True)
    notify_whatsapp = Column(Boolean, nullable=True)
    notify_push = Column(Boolean, nullable=True)
    min_score = Column(Integer, nullable=True)
    sectors = Column(String, nullable=True)
    locations = Column(String, nullable=True)
    contract_types = Column(String, nullable=True)
    # Used by the alerts UI (live matching + in-app notifications)
    min_salary = Column(Integer, nullable=True)
    keywords = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)