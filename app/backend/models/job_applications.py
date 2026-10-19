from core.database import Base
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text


class Job_applications(Base):
    """Candidature envoyée PAR EmploiCentral au nom du candidat (CV + lettre en PJ).

    Distinct de `user_jobs.status` (suivi déclaratif, y compris pour les offres
    externes) : cette table garde la trace de ce qui est réellement parti, à qui,
    et avec quelle lettre — preuve pour le candidat et garde-fou anti-doublon.
    """

    __tablename__ = "job_applications"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)
    # 'recruiter' (offre publiée sur EmploiCentral) | 'email' (adresse trouvée dans l'annonce)
    channel = Column(String, nullable=False)
    recipient = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    letter = Column(Text, nullable=True)
    cv_template = Column(String, nullable=True)
    status = Column(String, nullable=False, default="sent")  # sent | failed
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
