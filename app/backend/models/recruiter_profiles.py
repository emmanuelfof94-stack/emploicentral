from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from core.database import Base


class Recruiter_profiles(Base):
    """Profil d'un compte recruteur (entreprise). Le rôle est porté par `users.role`
    ('recruiter') ; cette table ne stocke que les infos entreprise, sans modifier la
    table `users` existante.
    """

    __tablename__ = "recruiter_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
