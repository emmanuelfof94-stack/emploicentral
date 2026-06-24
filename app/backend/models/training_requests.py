from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from core.database import Base


class Training_requests(Base):
    """Demande de formation d'un candidat sur une thématique précise.

    Le parcours (`program`) est généré au moment de la demande : via l'IA
    (`APP_AI_*`) si configurée, sinon par un moteur de templating local.
    """

    __tablename__ = "training_requests"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    theme = Column(String, nullable=False)
    level = Column(String, nullable=True)          # débutant / intermédiaire / avancé
    objective = Column(Text, nullable=True)        # précisions libres du candidat
    program = Column(Text, nullable=True)          # parcours généré (Markdown)
    ai_generated = Column(Boolean, default=False, nullable=True)
    status = Column(String, nullable=True, default="generated")  # generated / in_progress / done
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
