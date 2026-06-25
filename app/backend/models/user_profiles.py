from core.database import Base
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text


class User_profiles(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    skills = Column(String, nullable=True)
    experience_years = Column(Integer, nullable=True)
    education = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    location = Column(String, nullable=True)
    cv_object_key = Column(String, nullable=True)
    cv_analyzed = Column(Boolean, default=False, nullable=True)
    profile_summary = Column(String, nullable=True)
    # Texte brut du CV uploadé, persisté en base (le fichier sur disque est éphémère
    # sur l'hébergement gratuit). Sert à la génération de CV pour garder le contenu réel.
    cv_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)