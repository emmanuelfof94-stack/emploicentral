from core.database import Base
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class Job_offers(Base):
    __tablename__ = "job_offers"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    description = Column(String, nullable=True)
    requirements = Column(String, nullable=True)
    salary_range = Column(String, nullable=True)
    source = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    posted_date = Column(String, nullable=True)
    valid_through = Column(String, nullable=True)  # date d'expiration "YYYY-MM-DD"
    is_active = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)