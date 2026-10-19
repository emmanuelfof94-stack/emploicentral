from core.database import Base
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint


class Job_views(Base):
    """Vue d'une offre recruteur ouverte DANS l'appli (fiche détail d'un candidat connecté).

    Une ligne par (offre, candidat, jour) : rouvrir la fiche le même jour ne gonfle pas
    le compteur. Les visites des pages publiques `/offres/{id}` sont, elles, comptées
    depuis `page_views` (analytics intégré) — pas de double enregistrement.
    """

    __tablename__ = "job_views"
    __table_args__ = (
        UniqueConstraint("job_id", "viewer_id", "day", name="uq_job_views_job_viewer_day"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    job_id = Column(Integer, nullable=False, index=True)
    viewer_id = Column(String, nullable=False)
    day = Column(String, nullable=False)  # "YYYY-MM-DD"
    created_at = Column(DateTime(timezone=True), default=datetime.now, index=True)
