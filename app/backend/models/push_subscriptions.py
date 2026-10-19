from core.database import Base
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String


class Push_subscriptions(Base):
    """Abonnement Web Push d'un navigateur (un utilisateur peut en avoir plusieurs :
    téléphone, ordinateur…). `endpoint` est unique : réabonner le même navigateur
    met à jour la ligne au lieu d'en créer une nouvelle."""

    __tablename__ = "push_subscriptions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False, unique=True, index=True)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
