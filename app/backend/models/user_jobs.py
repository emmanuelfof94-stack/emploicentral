from core.database import Base
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class User_jobs(Base):
    """Relation utilisateur ↔ offre : favoris + suivi de candidature."""

    __tablename__ = "user_jobs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)
    saved = Column(Boolean, default=False, nullable=True)
    # '' | 'to_apply' | 'applied' | 'interview' | 'rejected'
    status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
