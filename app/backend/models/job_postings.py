from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from core.database import Base


class Job_postings(Base):
    """Métadonnées d'une offre publiée par un recruteur, en marge de `job_offers`.

    Le contenu de l'offre reste dans `job_offers` (pour réutiliser tout l'existant :
    feed candidat, scoring, génération de CV, sauvegarde/candidature). Cette table
    de côté évite d'altérer `job_offers` : elle porte le propriétaire et l'état de
    modération. La modération réutilise `job_offers.is_active` : une offre recruteur
    est créée `is_active=False` (invisible au feed) et passe à True à l'approbation.
    """

    __tablename__ = "job_postings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    job_id = Column(Integer, nullable=False, index=True)      # -> job_offers.id
    posted_by = Column(String, nullable=False, index=True)    # -> users.id (recruteur)
    company_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending / approved / rejected
    reject_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
