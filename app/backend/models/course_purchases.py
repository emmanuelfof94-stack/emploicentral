from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from core.database import Base


class Course_purchases(Base):
    """Achat (manuel) d'un cours payant par un candidat.

    Flux : le candidat déclare avoir payé (status='pending') → l'admin vérifie le
    versement mobile money et valide (status='paid') → l'accès au cours protégé
    est débloqué pour ce candidat. Une ligne par (user, cours).
    """

    __tablename__ = "course_purchases"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    course_slug = Column(String, nullable=False, index=True)   # ex. "pmp"
    status = Column(String, nullable=False, default="pending")  # pending / paid / rejected
    payment_ref = Column(String, nullable=True)                 # n° mobile money / réf du candidat
    amount = Column(String, nullable=True)                      # ex. "20 000 FCFA" (au moment de l'achat)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
