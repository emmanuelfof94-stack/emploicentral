from datetime import datetime

from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class Notification(Base):
    """Notification in-app + trace d'envoi (sert aussi de clé de dédup user+job)."""

    __tablename__ = "notifications"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(Integer, nullable=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)
    # Canaux effectivement tentés/envoyés, ex. "in_app,email"
    channels = Column(String, nullable=True)
    is_read = Column(Boolean, nullable=True, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
