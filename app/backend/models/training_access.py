from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from core.database import Base


class Training_access_events(Base):
    """Journal des accès formation consommés par un candidat (quota gratuit).

    Chaque ligne = 1 accès consommé. Deux actions consomment un accès :
    - `kind='generate'` : génération d'un parcours IA (`ref` = id du parcours).
    - `kind='catalog'`  : déblocage d'une formation gratuite du catalogue
      (`ref` = id de la formation). Idempotent : on ne recompte pas un
      déblocage déjà effectué pour la même formation.

    Le quota gratuit (5 à vie) se calcule = COUNT(events) vs limite ; l'accès
    illimité s'obtient via un achat validé (voir services.training_quota).
    """

    __tablename__ = "training_access_events"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)              # "generate" | "catalog"
    ref = Column(String, nullable=True, index=True)    # id du parcours / de la formation
    created_at = Column(DateTime(timezone=True), default=datetime.now)
